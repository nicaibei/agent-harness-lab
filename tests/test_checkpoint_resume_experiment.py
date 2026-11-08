"""Regression tests for the checkpoint/resume experiment runner."""

from __future__ import annotations

import json
from pathlib import Path

import evals.checkpoint_resume as checkpoint_resume


def test_checkpoint_resume_runner_records_waiting_and_resume(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(checkpoint_resume, "CHECKPOINT_RUNS_ROOT", tmp_path / "runs")

    run_dir = checkpoint_resume.run_checkpoint_resume_experiment()
    report = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))

    assert report["paused"] is True
    assert report["resumed"] is True
    assert report["side_effects_before_resume"] is False
    assert report["tests_passed"] is True
    assert report["checkpoint_after_resume"]["checkpoint_count"] > report[
        "checkpoint_before_resume"
    ]["checkpoint_count"]
    assert report["replay"]["test_runs"] == 1
    assert [event["event"] for event in report["events"]] == [
        "run_started",
        "workspace_created",
        "run_waiting",
        "run_resumed",
        "test_run",
        "run_finished",
    ]


def test_checkpoint_resume_survives_a_process_restart(tmp_path: Path) -> None:
    run_dir = checkpoint_resume.run_checkpoint_process_restart_experiment(
        tmp_path / "process-restart"
    )
    report = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))

    assert report["paused"] is True
    assert report["resumed"] is True
    assert report["side_effects_before_resume"] is False
    assert report["tests_passed"] is True
    assert report["checkpoint_after_resume"]["checkpoint_count"] > report[
        "checkpoint_before_resume"
    ]["checkpoint_count"]
    assert (run_dir / "checkpoint-store.json").is_file()
    assert report["replay"]["event_names"] == [
        "run_started",
        "workspace_created",
        "run_waiting",
        "process_restarted",
        "run_resumed",
        "test_run",
        "run_finished",
    ]

