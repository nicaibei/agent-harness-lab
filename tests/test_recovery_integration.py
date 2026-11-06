"""Integration tests for Recovery Middleware in a Deep Agents graph."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
import json

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool

from harness.recovery import RecoveryMiddleware


class BoundFakeChatModel(FakeMessagesListChatModel):
    """Offline fake model that accepts the tool binding used by create_deep_agent."""

    def bind_tools(self, tools: Any, **kwargs: Any) -> BoundFakeChatModel:
        return self


def _make_flaky_tool(attempts: list[int]) -> Any:
    @tool
    def flaky_tool(value: str) -> str:
        """Fail once with a transient timeout, then return a result."""
        attempts.append(1)
        if len(attempts) == 1:
            raise TimeoutError("temporary timeout")
        return f"ok:{value}"

    return flaky_tool


def test_agent_graph_retries_transient_tool_failure() -> None:
    attempts: list[int] = []
    events: list[dict[str, Any]] = []
    flaky_tool = _make_flaky_tool(attempts)

    with TemporaryDirectory() as directory:
        agent = create_deep_agent(
            model=BoundFakeChatModel(
                responses=[
                    AIMessage(
                        content="",
                        tool_calls=[
                            {"name": "flaky_tool", "args": {"value": "x"}, "id": "flaky-call"}
                        ],
                    ),
                    AIMessage(content="finished"),
                ]
            ),
            backend=FilesystemBackend(root_dir=Path(directory), virtual_mode=True),
            tools=[flaky_tool],
            middleware=[RecoveryMiddleware(on_event=events.append)],
        )
        result = agent.invoke({"messages": [("user", "run the flaky tool")]})

    tool_results = [message for message in result["messages"] if isinstance(message, ToolMessage)]
    assert len(tool_results) == 1
    assert tool_results[0].status == "success"
    assert tool_results[0].content == "ok:x"
    assert len(attempts) == 2
    assert [event["event"] for event in events] == [
        "recovery_failure",
        "recovery_retry",
        "recovery_success",
    ]


def test_agent_graph_can_correct_tool_arguments_after_terminal_error() -> None:
    events: list[dict[str, Any]] = []

    @tool
    def validate_value(value: str) -> str:
        """Accept only the corrected value."""
        if value != "correct":
            raise ValueError("value must be 'correct'")
        return "validated"

    with TemporaryDirectory() as directory:
        agent = create_deep_agent(
            model=BoundFakeChatModel(
                responses=[
                    AIMessage(
                        content="",
                        tool_calls=[
                            {"name": "validate_value", "args": {"value": "wrong"}, "id": "bad-call"}
                        ],
                    ),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {"name": "validate_value", "args": {"value": "correct"}, "id": "fixed-call"}
                        ],
                    ),
                    AIMessage(content="finished"),
                ]
            ),
            backend=FilesystemBackend(root_dir=Path(directory), virtual_mode=True),
            tools=[validate_value],
            middleware=[RecoveryMiddleware(on_event=events.append)],
        )
        result = agent.invoke({"messages": [("user", "validate the value")]})

    tool_results = [message for message in result["messages"] if isinstance(message, ToolMessage)]
    assert len(tool_results) == 2
    assert tool_results[0].status == "error"
    assert "value must be" in str(tool_results[0].content)
    assert tool_results[1].status == "success"
    assert tool_results[1].content == "validated"
    assert [event["event"] for event in events] == [
        "recovery_failure",
        "recovery_terminal",
        "recovery_success",
    ]


def test_agent_graph_can_recover_from_failed_test_result() -> None:
    events: list[dict[str, Any]] = []

    @tool
    def injected_tests(fix: bool = False) -> str:
        """Return a failed test result until the model requests a fix."""
        if not fix:
            return json.dumps({"success": False, "exit_code": 1, "output": "1 failed: expected 2"})
        return json.dumps({"success": True, "exit_code": 0, "output": "1 passed"})

    with TemporaryDirectory() as directory:
        agent = create_deep_agent(
            model=BoundFakeChatModel(
                responses=[
                    AIMessage(
                        content="",
                        tool_calls=[
                            {"name": "injected_tests", "args": {"fix": False}, "id": "failed-tests"}
                        ],
                    ),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {"name": "injected_tests", "args": {"fix": True}, "id": "fixed-tests"}
                        ],
                    ),
                    AIMessage(content="finished"),
                ]
            ),
            backend=FilesystemBackend(root_dir=Path(directory), virtual_mode=True),
            tools=[injected_tests],
            middleware=[RecoveryMiddleware(on_event=events.append)],
        )
        result = agent.invoke({"messages": [("user", "run the tests")]})

    tool_results = [message for message in result["messages"] if isinstance(message, ToolMessage)]
    assert len(tool_results) == 2
    assert json.loads(tool_results[0].content)["success"] is False
    assert json.loads(tool_results[1].content)["success"] is True
    assert [event["event"] for event in events] == [
        "recovery_failure",
        "recovery_terminal",
        "recovery_success",
    ]
