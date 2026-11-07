"""Offline tests for the real recovery matrix report."""

from __future__ import annotations

import json
from pathlib import Path

from evals.recovery_report import build_report, write_report


def _write_run(root: Path, name: str, first: bool, last: bool) -> None:
    run_dir = root / name
    run_dir.mkdir()
    report = {
        "run_id": name,
        "task_id": name,
        "model": "deepseek-flash",
        "baseline_gate": True,
        "completed": True,
        "tests_passed": last,
        "test_runs": [
            json.dumps({"success": first}),
            json.dumps({"success": last}),
        ],
        "diff": "changed",
        "events": [
            {"event": "policy_decision", "decision": "deny"},
            (
                {"event": "recovery_failure", "tool": "run_tests"}
                if not first
                else {"event": "recovery_success"}
            ),
        ],
    }
    (run_dir / "run.json").write_text(json.dumps(report), encoding="utf-8")


def test_recovery_report_distinguishes_recovered_and_failed_runs(tmp_path: Path) -> None:
    _write_run(tmp_path, "recovered", False, True)
    _write_run(tmp_path, "still-failed", False, False)

    report = build_report(tmp_path)

    assert report["run_count"] == 2
    assert report["successful_runs"] == 1
    assert report["recovered_after_failure"] == 1
    assert report["runs"][0]["policy_denials"] == 1
    assert report["runs"][0]["baseline_gate"] is True
    assert report["runs"][0]["test_failure_results"] == 1
    assert report["runs"][0]["test_recovery_failures"] == 1


def test_recovery_report_writes_artifacts(tmp_path: Path) -> None:
    json_path, markdown_path = write_report(build_report(tmp_path / "runs"), tmp_path / "reports")

    assert json_path.is_file()
    assert markdown_path.is_file()
    assert "Real Recovery" in markdown_path.read_text(encoding="utf-8")
