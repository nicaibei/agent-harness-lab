"""Catalog calculations with a deliberately ignored stock limit."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


def subtotal(lines: Sequence[Mapping[str, object]], stock: Mapping[str, int]) -> float:
    """Calculate the requested line subtotal."""
    return sum(float(line["quantity"]) * float(line["unit_price"]) for line in lines)
