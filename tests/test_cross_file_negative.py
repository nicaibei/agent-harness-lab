"""Offline tests for modified-but-failed cross-file cases."""

from evals.cross_file_negative import build_report


def test_negative_cases_are_not_counted_as_successes() -> None:
    report = build_report()

    assert report["all_classified_correctly"] is True
    assert len(report["results"]) == 2
    assert all(result["tests_passed"] is False for result in report["results"])
    assert all(len(result["changed_files"]) == 2 for result in report["results"])
