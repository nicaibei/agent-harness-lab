"""Integration tests for command risk and approval decisions."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool

from harness.policy import PolicyMiddleware


class BoundFakeChatModel(FakeMessagesListChatModel):
    """Offline fake model that accepts the tool binding used by create_deep_agent."""

    def bind_tools(self, tools: Any, **kwargs: Any) -> BoundFakeChatModel:
        return self


@tool
def run_command(command: str) -> str:
    """Fake command tool; tests verify policy before this function is reached."""
    return f"executed: {command}"


def _run_command(
    root: Path,
    command: str,
    *,
    approval_callback: Any = None,
) -> tuple[list[Any], list[dict[str, Any]]]:
    decisions: list[dict[str, Any]] = []
    agent = create_deep_agent(
        model=BoundFakeChatModel(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {"name": "run_command", "args": {"command": command}, "id": "command-call"}
                    ],
                ),
                AIMessage(content="finished"),
            ]
        ),
        backend=FilesystemBackend(root_dir=root, virtual_mode=True),
        tools=[run_command],
        middleware=[
            PolicyMiddleware(
                on_decision=decisions.append,
                approval_callback=approval_callback,
            )
        ],
    )
    result = agent.invoke({"messages": [("user", "run the command")]})
    return result["messages"], decisions


def test_dangerous_command_is_denied_before_tool_execution() -> None:
    with TemporaryDirectory() as directory:
        messages, decisions = _run_command(Path(directory), "del safe.txt")

    errors = [message for message in messages if isinstance(message, ToolMessage) and message.status == "error"]
    assert len(errors) == 1
    assert "dangerous commands" in str(errors[0].content)
    assert decisions[0]["decision"] == "deny"
    assert decisions[0]["risk"] == "dangerous"


def test_review_command_is_denied_without_approval() -> None:
    with TemporaryDirectory() as directory:
        messages, decisions = _run_command(Path(directory), "pip install requests")

    errors = [message for message in messages if isinstance(message, ToolMessage) and message.status == "error"]
    assert len(errors) == 1
    assert "requires approval" in str(errors[0].content)
    assert decisions[0]["risk"] == "review"


def test_review_command_reaches_tool_after_approval() -> None:
    approval_requests: list[dict[str, Any]] = []
    with TemporaryDirectory() as directory:
        messages, decisions = _run_command(
            Path(directory),
            "pip install requests",
            approval_callback=lambda request: approval_requests.append(request) or True,
        )

    tool_results = [message for message in messages if isinstance(message, ToolMessage)]
    assert len(tool_results) == 1
    assert tool_results[0].status != "error"
    assert approval_requests[0]["command"] == "pip install requests"
    assert decisions[0]["decision"] == "allow"
    assert decisions[0]["reason"] == "command approved"
