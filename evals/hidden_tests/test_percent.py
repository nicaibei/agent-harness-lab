"""Hidden evaluator for percentage parsing."""

from percent import parse_percent


def test_parse_percent_converts_percent_suffix_to_fraction() -> None:
    assert parse_percent("20%") == 0.2


def test_parse_percent_keeps_decimal_fraction() -> None:
    assert parse_percent("0.5") == 0.5
