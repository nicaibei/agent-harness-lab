"""Hidden evaluator for a cross-file temperature conversion."""

from temperature_parser import parse_reading
from temperature_report import to_celsius


def test_parse_reading_normalizes_the_unit_without_changing_value() -> None:
    assert parse_reading("32 F") == {"value": 32.0, "unit": "F"}


def test_to_celsius_converts_fahrenheit_and_keeps_celsius() -> None:
    assert to_celsius(parse_reading("86 F")) == 30.0
    assert to_celsius(parse_reading("20 C")) == 20.0
