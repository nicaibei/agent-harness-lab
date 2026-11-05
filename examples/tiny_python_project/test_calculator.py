"""Tests for the tiny calculator project."""

import pytest

from calculator import add, divide, subtract


def test_add_returns_sum() -> None:
    assert add(2, 3) == 5


def test_subtract_returns_difference() -> None:
    assert subtract(5, 3) == 2


def test_divide_returns_quotient() -> None:
    assert divide(8, 2) == 4


def test_divide_rejects_zero_denominator() -> None:
    with pytest.raises(ValueError, match="zero"):
        divide(8, 0)
