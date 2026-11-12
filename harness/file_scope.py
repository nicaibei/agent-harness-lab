"""Compare workspace file contents independently of a text-only diff."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping
from pathlib import Path, PurePosixPath, PureWindowsPath


_CACHE_DIRECTORIES = frozenset({"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"})


def snapshot_file_hashes(root: Path) -> dict[str, str]:
    """Hash workspace files, including binary and empty files, without following links.

    Known Python/test cache directories are excluded. A missing root raises
    `FileNotFoundError` rather than silently representing an empty workspace.
    """
    if not root.is_dir():
        msg = f"Workspace is missing: {root}"
        raise FileNotFoundError(msg)
    snapshot: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if set(relative.parts[:-1]) & _CACHE_DIRECTORIES:
            continue
        if path.is_symlink():
            content = os.readlink(path).encode("utf-8")
            snapshot[relative.as_posix()] = "symlink:" + hashlib.sha256(content).hexdigest()
        elif path.is_file():
            snapshot[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return snapshot


def file_changes(before: Mapping[str, str], after: Mapping[str, str]) -> dict[str, object]:
    """Describe content changes, creations and deletions using file membership too."""
    return {
        "schema_version": "file-changes.v1",
        "status": "complete",
        "changed_files": sorted(
            name for name in before.keys() | after.keys() if before.get(name) != after.get(name)
        ),
        "before": dict(before),
        "after": dict(after),
    }


def _valid_relative_path(value: object) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return (
        not path.is_absolute()
        and not PureWindowsPath(value).drive
        and ".." not in path.parts
        and path.as_posix() == value
        and value != "."
    )


def assess_file_scope(changes: object, expected_files: tuple[str, ...]) -> dict[str, object]:
    """Reject unlisted paths; missing or invalid snapshot evidence stays unknown."""
    unknown = {
        "expected_files": list(expected_files),
        "changed_files": None,
        "unexpected_files": None,
        "diff_scope_valid": None,
        "scope_status": "missing_or_invalid_evidence",
    }
    if not isinstance(changes, Mapping):
        return unknown
    if changes.get("schema_version") != "file-changes.v1" or changes.get("status") != "complete":
        return unknown
    changed = changes.get("changed_files")
    if not isinstance(changed, list) or not all(_valid_relative_path(name) for name in changed):
        return unknown
    unexpected = sorted(set(changed) - set(expected_files))
    return {
        "expected_files": list(expected_files),
        "changed_files": sorted(set(changed)),
        "unexpected_files": unexpected,
        "diff_scope_valid": not unexpected,
        "scope_status": "checked",
    }
