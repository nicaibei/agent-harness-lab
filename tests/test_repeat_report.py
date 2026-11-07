"""Offline tests for repeated Recovery reporting."""

import json
from pathlib import Path

from evals.repeat_report import build_report, render_markdown


def _write_run(root: Path, run_id: str, diff: str, first: bool, last: bool) -> None:
    run_dir = root / run_id
    run_dir.mkdir()
    report = {
        "run_id": run_id,
        "task_id": "task-repeat",
        "completed": True,
        "tests_passed": last,
        "diff": diff,
        "test_runs": [json.dumps({"success": first}), json.dumps({"success": last})],
        "events": [
            {"event": "policy_decision", "decision": "deny"},
            {"event": "recovery_failure", "tool": "ls"},
        ],
    }
    (run_dir / "run.json").write_text(json.dumps(report), encoding="utf-8")


def test_repeat_report_tracks_variance_without_merging_tasks(tmp_path: Path) -> None:
    _write_run(tmp_path, "one", "abc", False, True)
    _write_run(tmp_path, "two", "abcdef", False, True)

    report = build_report(tmp_path, "task-repeat")

    assert report["run_count"] == 2
    assert report["final_successes"] == 2
    assert report["recovered_after_failure"] == 2
    assert report["diff_chars"] == {"min": 3, "max": 6, "mean": 4.5}
    assert report["exploration_errors"] == 2
    assert "重复 Recovery" in render_markdown(report)
