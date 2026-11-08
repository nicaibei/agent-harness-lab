"""Offline checks for the single-package dependency version conflict."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from langchain_core.messages import ToolMessage
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from evals.real_recovery import (
    APPROVED_CONFLICT_DEPENDENCY_WHEEL,
    PRELOADED_CONFLICT_DEPENDENCY,
    RECOVERY_CASES,
    _create_dependency_prepare_tool,
    _create_hidden_test_tool,
    _run_hidden_tests,
)
from harness.policy import PolicyMiddleware
from harness.recovery import RecoveryMiddleware, classify_failure


class BoundFakeChatModel(FakeMessagesListChatModel):
    """Offline model that accepts the tool binding used by create_deep_agent."""

    def bind_tools(self, tools: Any, **kwargs: Any) -> BoundFakeChatModel:
        return self


def _copy_fixture(source: Path, workspace: Path) -> None:
    for item in source.rglob("*"):
        if item.is_file():
            target = workspace / item.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(item.read_bytes())


def _request(name: str, args: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(tool_call={"id": "call-1", "name": name, "args": args})


def test_version_conflict_resolves_with_approved_replacement(tmp_path: Path) -> None:
    case = RECOVERY_CASES["dependency-version-conflict"]
    workspace = tmp_path / "dependency-conflict"
    _copy_fixture(case.project, workspace)
    prepared_path = tmp_path / "prepared-dependency"
    extra_pythonpath = [PRELOADED_CONFLICT_DEPENDENCY]
    prepare_tool = _create_dependency_prepare_tool(
        APPROVED_CONFLICT_DEPENDENCY_WHEEL,
        prepared_path,
        extra_pythonpath,
        replace_pythonpath=[PRELOADED_CONFLICT_DEPENDENCY],
    )
    before = {
        path.relative_to(workspace).as_posix(): path.read_bytes()
        for path in workspace.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }

    conflict = _run_hidden_tests(
        workspace,
        case.hidden_tests,
        extra_pythonpath,
    )
    prepared = json.loads(prepare_tool.invoke({}))
    passed = _run_hidden_tests(workspace, case.hidden_tests, extra_pythonpath)
    after = {
        path.relative_to(workspace).as_posix(): path.read_bytes()
        for path in workspace.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }

    assert conflict["success"] is False
    assert conflict["failure_class"] == "dependency_conflict"
    assert prepared["success"] is True
    assert passed["success"] is True
    assert before == after


def test_recovery_classifies_dependency_conflict() -> None:
    message = ToolMessage(
        content=json.dumps(
            {"success": False, "failure_class": "dependency_conflict"}
        ),
        name="run_tests",
        tool_call_id="test-call",
    )

    assert classify_failure(message) == "dependency_conflict"


def test_policy_records_conflict_before_preparation() -> None:
    decisions: list[dict[str, Any]] = []
    policy = PolicyMiddleware(
        require_baseline_test=True,
        stop_on_environment_failure=True,
        on_decision=decisions.append,
    )
    conflict = ToolMessage(
        content=json.dumps(
            {"success": False, "failure_class": "dependency_conflict"}
        ),
        name="run_tests",
        tool_call_id="test-call",
    )

    policy.wrap_tool_call(_request("run_tests", {}), lambda _request: conflict)

    assert policy.environment_failure_detected is True
    assert policy.dependency_conflict_detected is True
    assert any(
        decision["reason"] == "external dependency failure: dependency_conflict"
        for decision in decisions
    )


def test_agent_graph_resolves_version_conflict_without_production_diff(
    tmp_path: Path,
) -> None:
    case = RECOVERY_CASES["dependency-version-conflict"]
    workspace = tmp_path / "dependency-conflict"
    _copy_fixture(case.project, workspace)
    extra_pythonpath = [PRELOADED_CONFLICT_DEPENDENCY]
    run_tests = _create_hidden_test_tool(
        workspace,
        case.hidden_tests,
        extra_pythonpath=extra_pythonpath,
    )
    prepare_dependency = _create_dependency_prepare_tool(
        APPROVED_CONFLICT_DEPENDENCY_WHEEL,
        tmp_path / "prepared-dependency",
        extra_pythonpath,
        replace_pythonpath=[PRELOADED_CONFLICT_DEPENDENCY],
    )
    policy = PolicyMiddleware(
        require_baseline_test=True,
        stop_on_environment_failure=True,
    )
    agent = create_deep_agent(
        model=BoundFakeChatModel(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[{"name": "run_tests", "args": {}, "id": "initial"}],
                ),
                AIMessage(
                    content="",
                    tool_calls=[
                        {"name": "prepare_dependency", "args": {}, "id": "prepare"}
                    ],
                ),
                AIMessage(
                    content="",
                    tool_calls=[{"name": "run_tests", "args": {}, "id": "final"}],
                ),
                AIMessage(content="finished"),
            ]
        ),
        backend=FilesystemBackend(root_dir=workspace, virtual_mode=True),
        tools=[run_tests, prepare_dependency],
        middleware=[RecoveryMiddleware(), policy],
        checkpointer=InMemorySaver(),
    )

    result = agent.invoke(
        {"messages": [("user", "resolve the approved dependency conflict")]},
        config={"configurable": {"thread_id": "dependency-conflict-offline"}},
    )
    test_results = [
        json.loads(message.content)
        for message in result["messages"]
        if isinstance(message, ToolMessage) and message.name == "run_tests"
    ]

    assert [item["success"] for item in test_results] == [False, True]
    assert policy.dependency_conflict_detected is True
    assert policy.environment_preparation_completed is True
