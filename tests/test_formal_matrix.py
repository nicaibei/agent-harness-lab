"""Offline tests for the unified evaluation matrix."""

from pathlib import Path

from evals.formal_matrix import build_report, render_markdown


def test_formal_matrix_keeps_experiment_denominators_separate() -> None:
    report = build_report(Path("evals/reports"))
    groups = report["groups"]

    assert groups["baseline"]["attempts"] == 14
    assert groups["real_recovery"]["recovered_after_failure"] == 5
    assert groups["cross_file_ablation"]["both_files_passed"] == 2
    assert groups["cross_file_negative"]["modified_but_failed"] == 2
    assert "不计算一个混合成功率" in render_markdown(report)
