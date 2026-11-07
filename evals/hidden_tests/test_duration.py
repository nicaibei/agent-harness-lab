"""Hidden evaluator for duration parsing."""

from duration import parse_duration


def test_parse_duration_supports_hours_and_minutes() -> None:
    assert parse_duration("1h 30m") == 5400


def test_parse_duration_supports_minutes_only() -> None:
    assert parse_duration("45m") == 2700
