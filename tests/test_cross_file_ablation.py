"""Offline tests for cross-file file-level ablations."""

from evals.cross_file_ablation import build_report


def test_cross_file_ablation_requires_both_files() -> None:
    report = build_report()

    assert report["passed_expected_matrix"] is True
    results = report["results"]
    assert len(results) == 8
    assert sum(result["success"] for result in results) == 2
