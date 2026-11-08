"""Tests for Policy Middleware decisions."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from langchain_core.messages import ToolMessage

from harness.policy import PolicyMiddleware, classify_command


def _request(name: str, args: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(tool_call={"id": "call-1", "name": name, "args": args})


def _handler(request: Any) -> ToolMessage:
    return ToolMessage(content="executed", name=request.tool_call["name"], tool_call_id="call-1")


def test_allows_workspace_file_reads_and_records_decision() -> None:
    decisions: list[dict[str, Any]] = []
    policy = PolicyMiddleware(on_decision=decisions.append)

    result = policy.wrap_tool_call(_request("read_file", {"file_path": "/calculator.py"}), _handler)

    assert isinstance(result, ToolMessage)
    assert result.content == "executed"
    assert decisions[0]["decision"] == "allow"


def test_denies_path_traversal_before_handler() -> None:
    called = False

    def handler(_request: Any) -> ToolMessage:
        nonlocal called
        called = True
        return ToolMessage(content="executed")

    result = PolicyMiddleware().wrap_tool_call(
        _request("write_file", {"file_path": "/../outside.txt", "content": "x"}),
        handler,
    )

    assert isinstance(result, ToolMessage)
    assert result.status == "error"
    assert "outside the workspace" in str(result.content)
    assert called is False


def test_denies_sensitive_file() -> None:
    policy = PolicyMiddleware()

    secret = policy.wrap_tool_call(_request("read_file", {"file_path": "/.env"}), _handler)

    assert isinstance(secret, ToolMessage) and secret.status == "error"


def test_denies_delete() -> None:
    delete = PolicyMiddleware().wrap_tool_call(
        _request("delete", {"file_path": "/calculator.py"}),
        _handler,
    )

    assert isinstance(delete, ToolMessage) and delete.status == "error"


def test_denies_unknown_tool_and_budget_exhaustion() -> None:
    policy = PolicyMiddleware(max_tool_calls=1)

    unknown = policy.wrap_tool_call(_request("execute", {"command": "rm -rf /"}), _handler)
    over_budget = policy.wrap_tool_call(_request("read_file", {"file_path": "/calculator.py"}), _handler)

    assert isinstance(unknown, ToolMessage) and unknown.status == "error"
    assert "allowlisted" in str(unknown.content)
    assert isinstance(over_budget, ToolMessage) and over_budget.status == "error"
    assert "budget" in str(over_budget.content)


def test_classifies_commands_by_execution_risk() -> None:
    assert classify_command("python -m pytest -q") == "safe"
    assert classify_command("pip install requests") == "review"
    assert classify_command("rm -rf workspace") == "dangerous"


def test_requires_and_records_approval_for_review_commands() -> None:
    approvals: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    policy = PolicyMiddleware(
        on_decision=decisions.append,
        approval_callback=lambda request: approvals.append(request) or True,
    )

    result = policy.wrap_tool_call(
        _request("run_command", {"command": "pip install requests"}),
        _handler,
    )

    assert isinstance(result, ToolMessage)
    assert result.content == "executed"
    assert approvals[0]["risk"] == "review"
    assert decisions[-1]["reason"] == "command approved"


def test_baseline_test_gate_blocks_mutations_until_tests_run() -> None:
    policy = PolicyMiddleware(require_baseline_test=True)

    blocked = policy.wrap_tool_call(
        _request("edit_file", {"file_path": "/calculator.py", "old_string": "x", "new_string": "y"}),
        _handler,
    )
    baseline = policy.wrap_tool_call(_request("run_tests", {}), _handler)
    allowed = policy.wrap_tool_call(
        _request("edit_file", {"file_path": "/calculator.py", "old_string": "x", "new_string": "y"}),
        _handler,
    )

    assert isinstance(blocked, ToolMessage) and blocked.status == "error"
    assert "baseline test" in str(blocked.content)
    assert isinstance(baseline, ToolMessage)
    assert isinstance(allowed, ToolMessage)
    assert allowed.content == "executed"
