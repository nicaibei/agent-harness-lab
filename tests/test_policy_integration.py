"""Integration tests for Policy Middleware in a Deep Agents graph."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, ToolMessage

from harness.policy import PolicyMiddleware


class BoundFakeChatModel(FakeMessagesListChatModel):
    """Offline fake model that accepts the tool binding used by create_deep_agent."""

    def bind_tools(self, tools: Any, **kwargs: Any) -> BoundFakeChatModel:
        return self


def _tool_call(name: str, args: dict[str, Any], call_id: str) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


def _run_agent(root: Path, responses: list[AIMessage], *, max_tool_calls: int = 30) -> tuple[list[Any], list[dict[str, Any]]]:
    decisions: list[dict[str, Any]] = []
    agent = create_deep_agent(
        model=BoundFakeChatModel(responses=responses),
        backend=FilesystemBackend(root_dir=root, virtual_mode=True),
        middleware=[PolicyMiddleware(max_tool_calls=max_tool_calls, on_decision=decisions.append)],
    )
    result = agent.invoke({"messages": [("user", "perform the requested tool call")]})
    return result["messages"], decisions


@pytest.mark.parametrize(
    ("tool_name", "file_path", "reason_fragment"),
    [
        ("read_file", "/../outside.txt", "outside the workspace"),
        ("read_file", "/.env", "sensitive files"),
        ("delete", "/safe.txt", "delete is disabled"),
    ],
)
def test_dangerous_file_calls_are_denied_inside_agent_graph(
    tool_name: str,
    file_path: str,
    reason_fragment: str,
) -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        safe_file = root / "safe.txt"
        safe_file.write_text("safe", encoding="utf-8")
        messages, decisions = _run_agent(
            root,
            [
                _tool_call(tool_name, {"file_path": file_path}, "dangerous-call"),
                AIMessage(content="stopped after policy error"),
            ],
        )

        denied = [message for message in messages if isinstance(message, ToolMessage) and message.status == "error"]
        assert len(denied) == 1
        assert reason_fragment in str(denied[0].content)
        assert decisions == [
            {
                "decision": "deny",
                "tool": tool_name,
                "reason": str(denied[0].content).removeprefix("Policy denied tool call: ").removesuffix("."),
                "call_index": 1,
            }
        ]
        assert safe_file.read_text(encoding="utf-8") == "safe"


def test_tool_budget_denial_happens_after_allowed_call() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "safe.txt").write_text("safe", encoding="utf-8")
        messages, decisions = _run_agent(
            root,
            [
                _tool_call("read_file", {"file_path": "/safe.txt"}, "first-call"),
                _tool_call("read_file", {"file_path": "/safe.txt"}, "second-call"),
                AIMessage(content="stopped after budget error"),
            ],
            max_tool_calls=1,
        )

        errors = [message for message in messages if isinstance(message, ToolMessage) and message.status == "error"]
        assert len(errors) == 1
        assert "budget exhausted" in str(errors[0].content)
        assert [decision["decision"] for decision in decisions] == ["allow", "deny"]
        assert decisions[-1]["call_index"] == 2
