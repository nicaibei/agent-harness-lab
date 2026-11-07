"""Duration parser with a deliberately incomplete unit conversion."""


def parse_duration(value: str) -> int:
    """Convert a duration such as ``1h 30m`` into seconds."""
    first = value.split()[0]
    return int(first[:-1]) * 60
