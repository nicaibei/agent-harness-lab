"""Hidden evaluator for safe division."""

from safe_math import safe_divide


def test_safe_divide_returns_a_quotient() -> None:
    assert safe_divide(8, 2) == 4


def test_safe_divide_returns_none_for_zero_denominator() -> None:
    assert safe_divide(1, 0) is None
