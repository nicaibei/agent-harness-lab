"""Checkpoint summaries and side-effect-free event replay."""

from __future__ import annotations

import base64
import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver

from harness.schema import REPLAY_SCHEMA_VERSION


class FileCheckpointSaver(InMemorySaver):
    """Persist LangGraph checkpoints to a local JSON file for experiments."""

    persistence = "file-json"

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path
        self._load()

    @staticmethod
    def _encode(value: tuple[str, bytes]) -> list[str]:
        return [value[0], base64.b64encode(value[1]).decode("ascii")]

    @staticmethod
    def _decode(value: list[str]) -> tuple[str, bytes]:
        return value[0], base64.b64decode(value[1])

    def _load(self) -> None:
        if not self.path.is_file():
            return
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        for item in payload.get("storage", []):
            thread_id = item["thread_id"]
            namespace = item["namespace"]
            checkpoint_id = item["checkpoint_id"]
            self.storage[thread_id][namespace][checkpoint_id] = (
                self._decode(item["checkpoint"]),
                self._decode(item["metadata"]),
                item["parent_checkpoint_id"],
            )
        for item in payload.get("writes", []):
            key = (item["thread_id"], item["namespace"], item["checkpoint_id"])
            inner = (item["task_id"], item["write_index"])
            self.writes[key][inner] = (
                item["task_id"],
                item["channel"],
                self._decode(item["value"]),
                item["task_path"],
            )
        for item in payload.get("blobs", []):
            key = (
                item["thread_id"],
                item["namespace"],
                item["channel"],
                item["version"],
            )
            self.blobs[key] = self._decode(item["value"])

    def _persist(self) -> None:
        storage = []
        for thread_id, namespaces in self.storage.items():
            for namespace, checkpoints in namespaces.items():
                for checkpoint_id, (checkpoint, metadata, parent) in checkpoints.items():
                    storage.append(
                        {
                            "thread_id": thread_id,
                            "namespace": namespace,
                            "checkpoint_id": checkpoint_id,
                            "checkpoint": self._encode(checkpoint),
                            "metadata": self._encode(metadata),
                            "parent_checkpoint_id": parent,
                        }
                    )
        writes = []
        for (thread_id, namespace, checkpoint_id), values in self.writes.items():
            for (task_id, write_index), (_, channel, value, task_path) in values.items():
                writes.append(
                    {
                        "thread_id": thread_id,
                        "namespace": namespace,
                        "checkpoint_id": checkpoint_id,
                        "task_id": task_id,
                        "write_index": write_index,
                        "channel": channel,
                        "value": self._encode(value),
                        "task_path": task_path,
                    }
                )
        blobs = [
            {
                "thread_id": thread_id,
                "namespace": namespace,
                "channel": channel,
                "version": version,
                "value": self._encode(value),
            }
            for (thread_id, namespace, channel, version), value in self.blobs.items()
        ]
        payload = {"storage": storage, "writes": writes, "blobs": blobs}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def put(self, config: Any, checkpoint: Any, metadata: Any, new_versions: Any) -> Any:
        """Save a checkpoint and persist the updated store."""
        result = super().put(config, checkpoint, metadata, new_versions)
        self._persist()
        return result

    def put_writes(
        self,
        config: Any,
        writes: Any,
        task_id: str,
        task_path: str = "",
    ) -> None:
        """Save pending writes and persist the updated store."""
        super().put_writes(config, writes, task_id, task_path)
        self._persist()

    def delete_thread(self, thread_id: str) -> None:
        """Delete a thread from memory and disk."""
        super().delete_thread(thread_id)
        self._persist()


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
        "persistence": getattr(checkpointer, "persistence", "in-memory"),
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
        "schema_version": REPLAY_SCHEMA_VERSION,
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
