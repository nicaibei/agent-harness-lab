"""File-scope regressions for changes invisible to a UTF-8 text diff."""

from pathlib import Path

import pytest

from harness.file_scope import assess_file_scope, file_changes, snapshot_file_hashes


def test_scope_detects_empty_creation_binary_change_and_deletion(tmp_path: Path) -> None:
    (tmp_path / "allowed.py").write_text("before", encoding="utf-8")
    (tmp_path / "binary.bin").write_bytes(b"\xff\x00")
    (tmp_path / "deleted.py").write_text("", encoding="utf-8")
    before = snapshot_file_hashes(tmp_path)
    (tmp_path / "allowed.py").write_text("after", encoding="utf-8")
    (tmp_path / "binary.bin").write_bytes(b"\xff\x01")
    (tmp_path / "empty.txt").touch()
    (tmp_path / "deleted.py").unlink()
    cache = tmp_path / ".pytest_cache"
    cache.mkdir()
    (cache / "nodeids").write_text("[]", encoding="utf-8")
    scope = assess_file_scope(file_changes(before, snapshot_file_hashes(tmp_path)), ("allowed.py",))
    assert scope["changed_files"] == ["allowed.py", "binary.bin", "deleted.py", "empty.txt"]
    assert scope["unexpected_files"] == ["binary.bin", "deleted.py", "empty.txt"]
    assert scope["diff_scope_valid"] is False


def test_missing_evidence_is_unknown_and_empty_change_set_is_valid_scope(tmp_path: Path) -> None:
    assert assess_file_scope(None, ("allowed.py",))["diff_scope_valid"] is None
    assert assess_file_scope(file_changes({}, {}), ())["diff_scope_valid"] is True
    with pytest.raises(FileNotFoundError):
        snapshot_file_hashes(tmp_path / "missing")


@pytest.mark.parametrize("name", ["../allowed.py", "/allowed.py", "C:/allowed.py", "a/../allowed.py"])
def test_invalid_recorded_paths_cannot_be_approved(name: str) -> None:
    changes = {"schema_version": "file-changes.v1", "status": "complete", "changed_files": [name]}
    assert assess_file_scope(changes, (name,))["diff_scope_valid"] is None
