"""Temperature parser with deliberately incorrect normalization."""


def parse_reading(value: str) -> dict[str, float | str]:
    """Parse a reading written as ``number unit``."""
    number_text, unit = value.split()
    return {"value": float(number_text) + 1, "unit": unit.lower()}
