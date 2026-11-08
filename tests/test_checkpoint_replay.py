"""Offline tests for checkpointing, resumption, and event replay."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from harness.checkpoint import replay_events, summarize_checkpoints


class BoundFakeChatModel(FakeMessagesListChatModel):
    """Offline model that accepts the tool binding used by create_deep_agent."""

    def bind_tools(self, tools: Any, **kwargs: Any) -> BoundFakeChatModel:
        return self


def test_replay_summarizes_events_without_running_side_effects() -> None:
    events = [
        {"event": "run_started"},
        {"event": "policy_decision", "decision": "deny"},
        {"event": "recovery_retry"},
        {"event": "test_run", "success": True},
        {"event": "run_finished", "completed": True, "tests_passed": True},
    ]

    report = replay_events(events)

    assert report["schema_version"] == "replay.v1"
    assert report["mode"] == "events-only"
    assert report["event_count"] == 5
    assert report["policy_denials"] == 1
    assert report["recovery_retries"] == 1
    assert report["test_runs"] == 1
    assert report["completed"] is True
    assert report["tests_passed"] is True


def test_agent_resumes_from_checkpoint_after_tool_interrupt() -> None:
    calls: list[str] = []

    @tool
    def record_step(value: str) -> str:
        """Record one step after approval."""
        calls.append(value)
        return f"done:{value}"

    with TemporaryDirectory() as directory:
        checkpointer = InMemorySaver()
        agent = create_deep_agent(
            model=BoundFakeChatModel(
                responses=[
                    AIMessage(
                        content="",
                        tool_calls=[
                            {"name": "record_step", "args": {"value": "one"}, "id": "step-call"}
                        ],
                    ),
                    AIMessage(content="finished"),
                ]
            ),
            backend=FilesystemBackend(root_dir=Path(directory), virtual_mode=True),
            tools=[record_step],
            interrupt_on={"record_step": True},
            checkpointer=checkpointer,
        )
        config = {"configurable": {"thread_id": "checkpoint-demo"}}

        paused = agent.invoke({"messages": [("user", "record a step")]}, config=config)
        summary_before = summarize_checkpoints(checkpointer, config)
        calls_before_resume = list(calls)

        resumed = agent.invoke(
            Command(resume={"decisions": [{"type": "approve"}]}),
            config=config,
        )
        summary_after = summarize_checkpoints(checkpointer, config)

    assert "__interrupt__" in paused
    assert calls_before_resume == []
    assert summary_before["checkpoint_count"] > 0
    assert summary_before["persistence"] == "in-memory"
    assert calls == ["one"]
    assert resumed["messages"][-1].content == "finished"
    assert summary_after["checkpoint_count"] > summary_before["checkpoint_count"]
    assert summary_after["thread_id"] == "checkpoint-demo"
