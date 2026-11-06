"""Offline tests for run aggregation and failure classification."""

from __future__ import annotations

import json
from pathlib import Path

from evals.report import build_report, classify_run, write_report


def _write_run(root: Path, run_id: str, **fields: object) -> None:
    run_dir = root / run_id
    run_dir.mkdir()
    base = {
        "run_id": run_id,
        "task_id": "task-a",
        "finished_at": f"2026-11-06T00:00:{run_id[-2:]}+00:00",
        "completed": True,
        "tests_passed": True,
        "diff": "diff",
        "test_runs": [],
        "events": [],
    }
    base.update(fields)
    (run_dir / "run.json").write_text(json.dumps(base), encoding="utf-8")


def test_classify_run_separates_model_and_test_failures() -> None:
    assert classify_run({"run_id": "a", "task_id": "t", "completed": True, "tests_passed": True}) == "success"
    assert classify_run({"run_id": "b", "task_id": "t", "completed": True, "tests_passed": False}) == "test_failure"
    assert classify_run(
        {
            "run_id": "c",
            "task_id": "t",
            "completed": False,
            "tests_passed": False,
            "execution_error": "OpenAIConnectionError: Connection error",
        }
    ) == "model_error"


def test_build_report_keeps_all_attempts_and_selects_latest_valid(tmp_path: Path) -> None:
    _write_run(tmp_path, "run-01", finished_at="2026-11-06T00:00:01+00:00")
    _write_run(
        tmp_path,
        "run-02",
        finished_at="2026-11-06T00:00:02+00:00",
        completed=False,
        tests_passed=False,
        execution_error="OpenAIConnectionError: Connection error",
    )
    _write_run(
        tmp_path,
        "run-03",
        task_id="task-b",
        finished_at="2026-11-06T00:00:03+00:00",
        tests_passed=False,
    )

    report = build_report(tmp_path)

    assert report["attempt_count"] == 3
    assert report["category_counts"] == {"model_error": 1, "success": 1, "test_failure": 1}
    assert report["success_count"] == 1
    assert report["attempt_success_rate"] == 1 / 3
    assert report["valid_attempt_count"] == 2
    assert report["valid_success_count"] == 1
    assert report["task_summaries"]["task-a"]["attempt_count"] == 2
    assert report["task_summaries"]["task-a"]["latest_valid_attempt"]["category"] == "success"
    assert report["task_summaries"]["task-b"]["latest_valid_attempt"]["category"] == "test_failure"


def test_write_report_creates_json_and_markdown(tmp_path: Path) -> None:
    report = build_report(tmp_path / "runs")
    json_path, markdown_path = write_report(report, tmp_path / "reports")

    assert json_path.is_file()
    assert markdown_path.is_file()
    assert "Agent Harness" in markdown_path.read_text(encoding="utf-8")
