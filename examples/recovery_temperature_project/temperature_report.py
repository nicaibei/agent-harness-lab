"""Temperature conversion with deliberately incorrect Fahrenheit handling."""


def to_celsius(reading: dict[str, float | str]) -> float:
    """Convert a parsed reading to Celsius."""
    if reading["unit"] == "F":
        return float(reading["value"])
    return float(reading["value"])
