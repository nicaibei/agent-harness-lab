"""Checkout service."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from inventory_app.catalog import subtotal
from inventory_app.settings import load_settings


def checkout_total(
    lines: Sequence[Mapping[str, object]],
    stock: Mapping[str, int],
    config_path: str | Path,
) -> float:
    """Calculate the final checkout total from the configured tax rate."""
    settings = load_settings(config_path)
    return subtotal(lines, stock) * (1 + float(settings["tax_rate"]))
