"""Checkpoint summaries and side-effect-free event replay."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver


def summarize_checkpoints(
    checkpointer: BaseCheckpointSaver,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Return JSON-safe metadata for the checkpoints of one thread."""
    checkpoints = list(checkpointer.list(config))
    latest = checkpointer.get_tuple(config)
    latest_config = latest.config if latest is not None else {}
    configurable = latest_config.get("configurable", {})
    return {
        "thread_id": config.get("configurable", {}).get("thread_id"),
        "checkpoint_count": len(checkpoints),
        "latest_checkpoint_id": configurable.get("checkpoint_id"),
        "persistence": "in-memory",
    }


def replay_events(events: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Replay an event trace into a summary without calling tools or models."""
    event_list = list(events)
    names = [str(event.get("event", "unknown")) for event in event_list]
    finished = next(
        (event for event in reversed(event_list) if event.get("event") == "run_finished"),
        {},
    )
    return {
        "mode": "events-only",
        "event_count": len(event_list),
        "event_names": names,
        "policy_denials": sum(
            event.get("decision") == "deny" for event in event_list if event.get("event") == "policy_decision"
        ),
        "recovery_retries": sum(event.get("event") == "recovery_retry" for event in event_list),
        "test_runs": sum(event.get("event") == "test_run" for event in event_list),
        "completed": finished.get("completed"),
        "tests_passed": finished.get("tests_passed"),
    }
