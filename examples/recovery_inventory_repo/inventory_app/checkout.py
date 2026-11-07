"""Checkout service with a deliberately incorrect tax calculation."""

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
    """Calculate the final checkout total."""
    settings = load_settings(config_path)
    return subtotal(lines, stock) + float(settings["tax_rate"])
