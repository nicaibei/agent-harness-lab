"""Tests for deterministic baseline behavior that does not require an API key."""

from pathlib import Path

import pytest

from agent_app.baseline import (
    DEFAULT_PROJECT,
    _build_diff,
    _save_run_artifacts,
    _snapshot_files,
    run_task,
)


def test_snapshot_and_diff_report_changed_created_and_deleted_files(tmp_path: Path) -> None:
    (tmp_path / "changed.py").write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "deleted.py").write_text("remove me\n", encoding="utf-8")
    before = _snapshot_files(tmp_path)

    (tmp_path / "changed.py").write_text("value = 2\n", encoding="utf-8")
    (tmp_path / "created.py").write_text("new file\n", encoding="utf-8")
    (tmp_path / "deleted.py").unlink()
    after = _snapshot_files(tmp_path)

    diff = _build_diff(before, after)

    assert "--- a/changed.py" in diff
    assert "+value = 2" in diff
    assert "--- /dev/null" in diff
    assert "+++ b/created.py" in diff
    assert "--- a/deleted.py" in diff
    assert "+++ /dev/null" in diff


def test_snapshot_ignores_test_runner_caches(tmp_path: Path) -> None:
    cache_file = tmp_path / ".pytest_cache" / "v" / "cache" / "nodeids"
    cache_file.parent.mkdir(parents=True)
    cache_file.write_text("[]", encoding="utf-8")
    source_file = tmp_path / "calculator.py"
    source_file.write_text("value = 1\n", encoding="utf-8")

    snapshot = _snapshot_files(tmp_path)

    assert snapshot == {"calculator.py": "value = 1\n"}


def test_missing_deepseek_key_error_only_names_environment_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("agent_app.baseline.load_dotenv", lambda *_args, **_kwargs: None)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY") as error:
        run_task("test issue", DEFAULT_PROJECT)

    assert "sk-" not in str(error.value)


def test_missing_deepseek_model_error_names_environment_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("agent_app.baseline.load_dotenv", lambda *_args, **_kwargs: None)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)

    with pytest.raises(RuntimeError, match="DEEPSEEK_MODEL") as error:
        run_task("test issue", DEFAULT_PROJECT)

    assert "deepseek-reasoner" not in str(error.value)


def test_save_run_artifacts_recreates_a_missing_run_directory(tmp_path: Path) -> None:
    run_dir = tmp_path / "deleted" / "run"

    _save_run_artifacts(run_dir, {"completed": False}, "")

    assert (run_dir / "diff.patch").read_text(encoding="utf-8") == ""
    assert '"completed": false' in (run_dir / "run.json").read_text(encoding="utf-8")


def test_save_run_artifacts_preserves_run_events(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    report = {
        "completed": True,
        "events": [
            {"event": "run_started", "timestamp": "2026-11-05T00:00:00+00:00"},
            {"event": "run_finished", "timestamp": "2026-11-05T00:00:01+00:00"},
        ],
    }

    _save_run_artifacts(run_dir, report, "diff")

    saved = (run_dir / "run.json").read_text(encoding="utf-8")
    assert '"event": "run_started"' in saved
    assert '"event": "run_finished"' in saved


def test_save_run_artifacts_writes_checkpoint_and_replay_reports(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"

    _save_run_artifacts(
        run_dir,
        {"completed": True},
        "diff",
        checkpoint={"checkpoint_count": 3},
        replay={"mode": "events-only"},
    )

    assert '"checkpoint_count": 3' in (run_dir / "checkpoint.json").read_text(encoding="utf-8")
    assert '"mode": "events-only"' in (run_dir / "replay.json").read_text(encoding="utf-8")
