"""Catalog calculations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


def subtotal(lines: Sequence[Mapping[str, object]], stock: Mapping[str, int]) -> float:
    """Calculate the subtotal using no more than available stock."""
    return sum(
        min(int(line["quantity"]), stock.get(str(line["sku"]), 0))
        * float(line["unit_price"])
        for line in lines
    )
