"""Load and validate the formal train/holdout task manifest."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


MANIFEST_PATH = Path(__file__).with_name("formal_tasks.json")
ALLOWED_SPLITS = frozenset({"train", "holdout"})
ALLOWED_STRATA = frozenset(
    {"baseline", "recovery", "cross_file", "repository_integration", "environment", "runtime", "security"}
)
ALLOWED_STATUSES = frozenset({"real_validated", "real_validated_once", "validated_offline"})
MIN_TASK_COUNT = 30


@dataclass(frozen=True)
class FormalTaskSpec:
    """Validated metadata for one formal evaluation task."""

    task_id: str
    split: str
    strata: str
    category: str
    difficulty: str
    project: str
    evaluator: str
    offline_target: str | None
    expected_files: tuple[str, ...]
    status: str
    issue: str


def _required_string(item: Mapping[str, object], key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        msg = f"Formal task field {key!r} must be a non-empty string"
        raise ValueError(msg)
    return value


def _relative_path(root: Path, value: str, label: str) -> None:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        msg = f"Formal task field {label!r} must be repository-relative"
        raise ValueError(msg)
    if not (root / path).exists():
        msg = f"Formal task field {label!r} does not exist: {value}"
        raise ValueError(msg)


def _validate_expected_files(root: Path, project: str, item: Mapping[str, object], task_id: str) -> tuple[str, ...]:
    expected = item.get("expected_files")
    if not isinstance(expected, list) or not all(isinstance(value, str) for value in expected):
        raise ValueError(f"Formal task {task_id} expected_files must be a list of strings")
    project_root = root / project
    for filename in expected:
        path = Path(filename)
        if path.is_absolute() or ".." in path.parts or not (project_root / path).is_file():
            raise ValueError(f"Formal task {task_id} has an invalid expected file: {filename}")
    return tuple(expected)


def load_manifest(
    path: Path = MANIFEST_PATH,
    *,
    repository_root: Path | None = None,
) -> tuple[FormalTaskSpec, ...]:
    """Load and validate the versioned formal task manifest."""
    root = repository_root or path.parents[1]
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Formal task manifest must contain a list")
    if len(raw) < MIN_TASK_COUNT:
        raise ValueError(f"Formal task manifest must contain at least {MIN_TASK_COUNT} tasks")

    tasks: list[FormalTaskSpec] = []
    seen_ids: set[str] = set()
    projects_by_split: dict[str, set[str]] = {split: set() for split in ALLOWED_SPLITS}
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("Each formal task must be an object")
        task_id = _required_string(item, "id")
        if task_id in seen_ids:
            raise ValueError(f"Duplicate formal task id: {task_id}")
        seen_ids.add(task_id)
        split = _required_string(item, "split")
        if split not in ALLOWED_SPLITS:
            raise ValueError(f"Unknown formal task split: {split}")
        strata = _required_string(item, "strata")
        if strata not in ALLOWED_STRATA:
            raise ValueError(f"Unknown formal task strata: {strata}")
        project = _required_string(item, "project")
        evaluator = _required_string(item, "evaluator")
        offline_target = item.get("offline_target")
        if offline_target is not None and not isinstance(offline_target, str):
            raise ValueError(f"Formal task {task_id} offline_target must be a string")
        _relative_path(root, project, "project")
        _relative_path(root, evaluator, "evaluator")
        if offline_target is not None:
            target_path = offline_target.split("::", maxsplit=1)[0]
            _relative_path(root, target_path, "offline_target")
        expected_files = _validate_expected_files(root, project, item, task_id)
        status = _required_string(item, "status")
        if status not in ALLOWED_STATUSES:
            raise ValueError(f"Unknown formal task status: {status}")
        projects_by_split[split].add(project)
        tasks.append(
            FormalTaskSpec(
                task_id=task_id,
                split=split,
                strata=strata,
                category=_required_string(item, "category"),
                difficulty=_required_string(item, "difficulty"),
                project=project,
                evaluator=evaluator,
                offline_target=offline_target,
                expected_files=expected_files,
                status=status,
                issue=_required_string(item, "issue"),
            )
        )
    overlap = projects_by_split["train"] & projects_by_split["holdout"]
    if overlap:
        raise ValueError(f"Projects cannot appear in both train and holdout: {sorted(overlap)}")
    return tuple(tasks)
