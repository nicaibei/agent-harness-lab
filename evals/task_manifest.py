"""Load and validate the expanded Recovery task manifest."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


MANIFEST_PATH = Path(__file__).with_name("expanded_tasks.json")
ALLOWED_CATEGORIES = frozenset(
    {
        "structured_text",
        "sequence_logic",
        "error_handling",
        "unit_parsing",
        "cross_file_contract",
        "repository_integration",
    }
)


@dataclass(frozen=True)
class TaskSpec:
    """Validated metadata for one expanded evaluation task."""

    task_id: str
    case: str
    category: str
    difficulty: str
    project: str
    hidden_tests: str
    expected_files: tuple[str, ...]
    repeat_target: int
    status: str
    issue: str


def _required_string(item: Mapping[str, object], key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        msg = f"Task field {key!r} must be a non-empty string"
        raise ValueError(msg)
    return value


def _relative_path(root: Path, value: str, label: str) -> None:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        msg = f"Task field {label!r} must be a repository-relative path"
        raise ValueError(msg)
    if not (root / path).exists():
        msg = f"Task field {label!r} does not exist: {value}"
        raise ValueError(msg)


def load_manifest(path: Path = MANIFEST_PATH, *, repository_root: Path | None = None) -> tuple[TaskSpec, ...]:
    """Load, validate, and return the expanded task manifest."""
    root = repository_root or path.parents[1]
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Expanded task manifest must contain a list")
    tasks: list[TaskSpec] = []
    seen_ids: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("Each expanded task must be an object")
        task_id = _required_string(item, "id")
        if task_id in seen_ids:
            raise ValueError(f"Duplicate expanded task id: {task_id}")
        seen_ids.add(task_id)
        category = _required_string(item, "category")
        if category not in ALLOWED_CATEGORIES:
            msg = f"Unknown task category: {category}"
            raise ValueError(msg)
        project = _required_string(item, "project")
        hidden_tests = _required_string(item, "hidden_tests")
        _relative_path(root, project, "project")
        _relative_path(root, hidden_tests, "hidden_tests")
        expected = item.get("expected_files")
        if not isinstance(expected, list) or not expected or not all(isinstance(value, str) for value in expected):
            raise ValueError(f"Task {task_id} must declare expected_files")
        for filename in expected:
            if Path(filename).is_absolute() or ".." in Path(filename).parts:
                raise ValueError(f"Task {task_id} has an unsafe expected file")
            if not (root / project / filename).is_file():
                raise ValueError(f"Task {task_id} expected file does not exist: {filename}")
        repeat_target = item.get("repeat_target")
        if not isinstance(repeat_target, int) or repeat_target < 1:
            raise ValueError(f"Task {task_id} repeat_target must be at least 1")
        tasks.append(
            TaskSpec(
                task_id=task_id,
                case=_required_string(item, "case"),
                category=category,
                difficulty=_required_string(item, "difficulty"),
                project=project,
                hidden_tests=hidden_tests,
                expected_files=tuple(expected),
                repeat_target=repeat_target,
                status=_required_string(item, "status"),
                issue=_required_string(item, "issue"),
            )
        )
    return tuple(tasks)
