"""Offline tests for deterministic fault-injection evaluation cases."""

from __future__ import annotations

from pathlib import Path

from evals.fault_injection import build_fault_report, write_fault_report


def test_fault_report_distinguishes_middleware_retry_and_model_correction() -> None:
    report = build_fault_report()

    assert report["case_count"] == 3
    assert report["successful_cases"] == 3
    assert report["middleware_retry_cases"] == 1
    assert report["model_correction_cases"] == 2
    cases = {case["case_id"]: case for case in report["cases"]}
    assert cases["transient-timeout"]["action_changed"] is False
    assert cases["wrong-argument"]["action_changed"] is True
    assert cases["test-failure"]["action_changed"] is True
    assert cases["test-failure"]["tests_passed"] is True
    assert cases["test-failure"]["diff"]


def test_fault_report_writes_json_and_markdown(tmp_path: Path) -> None:
    json_path, markdown_path = write_fault_report(build_fault_report(), tmp_path)

    assert json_path.is_file()
    assert markdown_path.is_file()
    assert "Fault Injection" in markdown_path.read_text(encoding="utf-8")
