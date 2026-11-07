"""Hidden evaluator for fractional tax calculations."""

from tax import total_with_tax


def test_total_with_tax_applies_fractional_rate() -> None:
    assert total_with_tax(100, 0.2) == 120


def test_total_with_tax_keeps_zero_rate_unchanged() -> None:
    assert total_with_tax(50, 0) == 50
