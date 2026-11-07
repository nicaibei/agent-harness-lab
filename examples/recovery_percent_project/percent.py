"""Percentage parser with a deliberately incorrect percent conversion."""


def parse_percent(value: str) -> float:
    """Parse a decimal or percent string into a fractional value."""
    return float(value.rstrip("%"))
