"""Versioned run-artifact schema helpers."""

from __future__ import annotations

from collections.abc import Mapping


RUN_SCHEMA_VERSION = "run.v1"
EVENT_SCHEMA_VERSION = "event.v1"
REPLAY_SCHEMA_VERSION = "replay.v1"


def normalize_replay_report(replay: Mapping[str, object]) -> dict[str, object]:
    """Add the stable version field to a replay summary."""
    normalized = dict(replay)
    normalized.setdefault("schema_version", REPLAY_SCHEMA_VERSION)
    return normalized


def normalize_run_report(
    report: Mapping[str, object],
    diff: str,
    replay: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Add the stable envelope fields before writing a run artifact."""
    normalized = dict(report)
    normalized.setdefault("schema_version", RUN_SCHEMA_VERSION)
    normalized.setdefault("diff", diff)
    normalized.setdefault("execution_error", None)
    normalized.setdefault("test_runs", [])
    normalized.setdefault("events", [])
    if replay is not None:
        normalized["replay"] = normalize_replay_report(replay)
    return normalized
