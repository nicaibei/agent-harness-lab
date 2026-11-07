"""Configuration loading with a deliberately incorrect tax interpretation."""

from __future__ import annotations

import json
from pathlib import Path


def load_settings(path: str | Path) -> dict[str, float | str]:
    """Load checkout settings from a JSON file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {"tax_rate": float(data["tax_rate"]) * 100, "currency": data["currency"]}
