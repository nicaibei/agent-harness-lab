"""Offline checks for controlled dependency preparation."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from evals.real_recovery import (
    APPROVED_DEPENDENCY_WHEEL,
    DEPENDENCY_INSTALL_HIDDEN_TESTS,
    DEPENDENCY_INSTALL_PROJECT,
    _create_dependency_prepare_tool,
    _create_hidden_test_tool,
    _run_hidden_tests,
)
from harness.policy import PolicyMiddleware
from harness.recovery import RecoveryMiddleware


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


def test_approved_dependency_preparation_changes_environment_not_workspace(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "dependency-install"
    _copy_fixture(DEPENDENCY_INSTALL_PROJECT, workspace)
    prepared_path = tmp_path / "prepared-dependency"
    extra_pythonpath: list[Path] = []
    prepare_tool = _create_dependency_prepare_tool(
        APPROVED_DEPENDENCY_WHEEL,
        prepared_path,
        extra_pythonpath,
    )
    before = {
        path.relative_to(workspace).as_posix(): path.read_bytes()
        for path in workspace.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }

    failed = _run_hidden_tests(workspace, DEPENDENCY_INSTALL_HIDDEN_TESTS)
    prepared = json.loads(prepare_tool.invoke({}))
    passed = _run_hidden_tests(
        workspace,
        DEPENDENCY_INSTALL_HIDDEN_TESTS,
        extra_pythonpath,
    )
    after = {
        path.relative_to(workspace).as_posix(): path.read_bytes()
        for path in workspace.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }

    assert failed["success"] is False
    assert failed["failure_class"] == "environment"
    assert prepared["success"] is True
    assert prepared["prepared"] is True
    assert passed["success"] is True
    assert before == after


def test_policy_requires_environment_failure_before_preparation() -> None:
    policy = PolicyMiddleware(
        require_baseline_test=True,
        stop_on_environment_failure=True,
    )
    preparation = ToolMessage(
        content=json.dumps({"success": True, "prepared": True}),
        name="prepare_dependency",
        tool_call_id="prepare-call",
    )

    early = policy.wrap_tool_call(
        _request("prepare_dependency", {}),
        lambda _request: preparation,
    )
    failure = policy.wrap_tool_call(
        _request("run_tests", {}),
        lambda _request: ToolMessage(
            content=json.dumps(
                {"success": False, "failure_class": "environment"}
            ),
            name="run_tests",
            tool_call_id="test-call",
        ),
    )
    allowed = policy.wrap_tool_call(
        _request("prepare_dependency", {}),
        lambda _request: preparation,
    )

    assert isinstance(early, ToolMessage) and early.status == "error"
    assert failure is not None
    assert isinstance(allowed, ToolMessage)
    assert policy.environment_preparation_completed is True


def test_agent_graph_prepares_dependency_then_passes_hidden_tests(tmp_path: Path) -> None:
    workspace = tmp_path / "dependency-install"
    _copy_fixture(DEPENDENCY_INSTALL_PROJECT, workspace)
    extra_pythonpath: list[Path] = []
    events: list[dict[str, Any]] = []
    policy = PolicyMiddleware(
        require_baseline_test=True,
        stop_on_environment_failure=True,
        on_decision=events.append,
    )
    recovery = RecoveryMiddleware(on_event=events.append)
    run_tests = _create_hidden_test_tool(
        workspace,
        DEPENDENCY_INSTALL_HIDDEN_TESTS,
        extra_pythonpath=extra_pythonpath,
    )
    prepare_dependency = _create_dependency_prepare_tool(
        APPROVED_DEPENDENCY_WHEEL,
        tmp_path / "prepared-dependency",
        extra_pythonpath,
    )
    agent = create_deep_agent(
        model=BoundFakeChatModel(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[{"name": "run_tests", "args": {}, "id": "initial-test"}],
                ),
                AIMessage(
                    content="",
                    tool_calls=[
                        {"name": "prepare_dependency", "args": {}, "id": "prepare"}
                    ],
                ),
                AIMessage(
                    content="",
                    tool_calls=[{"name": "run_tests", "args": {}, "id": "final-test"}],
                ),
                AIMessage(content="finished"),
            ]
        ),
        backend=FilesystemBackend(root_dir=workspace, virtual_mode=True),
        tools=[run_tests, prepare_dependency],
        middleware=[recovery, policy],
        checkpointer=InMemorySaver(),
    )

    result = agent.invoke(
        {"messages": [("user", "prepare the approved dependency and run tests")]},
        config={"configurable": {"thread_id": "dependency-install-offline"}},
    )
    test_results = [
        json.loads(message.content)
        for message in result["messages"]
        if isinstance(message, ToolMessage) and message.name == "run_tests"
    ]

    assert [item["success"] for item in test_results] == [False, True]
    assert policy.environment_failure_detected is True
    assert policy.environment_preparation_completed is True
