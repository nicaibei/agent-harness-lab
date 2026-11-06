"""Tests for Recovery Middleware failure classification and recovery limits."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from langchain_core.messages import ToolMessage

from harness.recovery import RecoveryMiddleware, classify_failure


def _request(name: str = "flaky_tool") -> SimpleNamespace:
    return SimpleNamespace(tool_call={"id": "call-1", "name": name, "args": {}})


def test_classifies_transient_and_terminal_failures() -> None:
    assert classify_failure(TimeoutError("timed out")) == "transient"
    assert classify_failure(
        ToolMessage(content="Policy denied tool call", status="error", tool_call_id="call-1")
    ) == "policy"
    assert classify_failure(
        ToolMessage(content="bad arguments", status="error", tool_call_id="call-1")
    ) == "tool_error"
    assert classify_failure(
        ToolMessage(
            content='{"success": false, "exit_code": 1, "output": "1 failed"}',
            status="success",
            tool_call_id="call-1",
        )
    ) == "tool_error"


def test_retries_transient_exception_once() -> None:
    attempts = 0
    events: list[dict[str, Any]] = []

    def handler(_request: Any) -> ToolMessage:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise TimeoutError("temporary timeout")
        return ToolMessage(content="ok", status="success", tool_call_id="call-1")

    result = RecoveryMiddleware(on_event=events.append).wrap_tool_call(_request(), handler)

    assert isinstance(result, ToolMessage)
    assert result.content == "ok"
    assert attempts == 2
    assert [event["event"] for event in events] == [
        "recovery_failure",
        "recovery_retry",
        "recovery_success",
    ]


def test_does_not_retry_policy_denial() -> None:
    attempts = 0

    def handler(_request: Any) -> ToolMessage:
        nonlocal attempts
        attempts += 1
        return ToolMessage(content="Policy denied tool call", status="error", tool_call_id="call-1")

    result = RecoveryMiddleware().wrap_tool_call(_request(), handler)

    assert isinstance(result, ToolMessage)
    assert result.status == "error"
    assert attempts == 1


def test_blocks_third_identical_call() -> None:
    attempts = 0

    def handler(_request: Any) -> ToolMessage:
        nonlocal attempts
        attempts += 1
        return ToolMessage(content="bad arguments", status="error", tool_call_id="call-1")

    recovery = RecoveryMiddleware(max_repeated_calls=2)
    recovery.wrap_tool_call(_request(), handler)
    recovery.wrap_tool_call(_request(), handler)
    result = recovery.wrap_tool_call(_request(), handler)

    assert isinstance(result, ToolMessage)
    assert "repeated identical" in str(result.content)
    assert attempts == 2
