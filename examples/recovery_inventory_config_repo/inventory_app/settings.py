"""Configuration loading."""

from __future__ import annotations

import json
from pathlib import Path


def load_settings(path: str | Path) -> dict[str, float | str]:
    """Load checkout settings while preserving the fractional tax rate."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {"tax_rate": float(data["tax_rate"]), "currency": data["currency"]}
