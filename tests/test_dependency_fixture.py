"""Offline checks for the missing dependency environment fixture."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from langchain_core.messages import ToolMessage

from evals.real_recovery import (
    DEPENDENCY_HIDDEN_TESTS,
    DEPENDENCY_PROJECT,
    _run_hidden_tests,
)
from harness.policy import PolicyMiddleware
from harness.recovery import RecoveryMiddleware, classify_failure


def _copy_fixture(source: Path, workspace: Path) -> None:
    for item in source.rglob("*"):
        if item.is_file():
            target = workspace / item.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(item.read_bytes())


def _request(name: str, args: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(tool_call={"id": "call-1", "name": name, "args": args})


def test_missing_dependency_is_classified_without_editing_the_fixture(tmp_path: Path) -> None:
    workspace = tmp_path / "missing-dependency"
    _copy_fixture(DEPENDENCY_PROJECT, workspace)

    result = _run_hidden_tests(workspace, DEPENDENCY_HIDDEN_TESTS)

    assert result["success"] is False
    assert result["failure_class"] == "environment"
    assert "ENVIRONMENT_FAILURE:" in str(result["output"])
    assert (workspace / "service_app" / "__init__.py").read_text(encoding="utf-8").startswith(
        '"""Service package'
    )


def test_environment_failure_blocks_mutations_after_baseline_test() -> None:
    decisions: list[dict[str, Any]] = []
    policy = PolicyMiddleware(
        require_baseline_test=True,
        stop_on_environment_failure=True,
        on_decision=decisions.append,
    )
    failure = ToolMessage(
        content=json.dumps(
            {
                "success": False,
                "failure_class": "environment",
                "output": "required dependency is unavailable",
            }
        ),
        name="run_tests",
        tool_call_id="test-call",
    )

    result = policy.wrap_tool_call(
        _request("run_tests", {}),
        lambda _request: failure,
    )
    blocked = policy.wrap_tool_call(
        _request("write_file", {"file_path": "/service_app/app.py", "content": "bad"}),
        lambda request: ToolMessage(content="written", name=request.tool_call["name"]),
    )

    assert result is failure
    assert policy.environment_failure_detected is True
    assert isinstance(blocked, ToolMessage)
    assert blocked.status == "error"
    assert "environment failure" in str(blocked.content)
    assert any(decision["decision"] == "deny" for decision in decisions)


def test_recovery_classifies_structured_environment_failure() -> None:
    result = ToolMessage(
        content=json.dumps(
            {
                "success": False,
                "failure_class": "environment",
                "output": "x" * 600,
            }
        ),
        name="run_tests",
        tool_call_id="test-call",
    )

    assert classify_failure(result) == "environment"


def test_recovery_records_environment_failure_around_policy() -> None:
    recovery_events: list[dict[str, Any]] = []
    policy = PolicyMiddleware(
        require_baseline_test=True,
        stop_on_environment_failure=True,
    )
    recovery = RecoveryMiddleware(
        on_event=recovery_events.append,
    )
    failure = ToolMessage(
        content=json.dumps({"success": False, "failure_class": "environment"}),
        name="run_tests",
        tool_call_id="test-call",
    )

    result = recovery.wrap_tool_call(
        _request("run_tests", {}),
        lambda request: policy.wrap_tool_call(request, lambda _request: failure),
    )

    assert result is failure
    assert any(
        event["event"] == "recovery_failure" and event["category"] == "environment"
        for event in recovery_events
    )
