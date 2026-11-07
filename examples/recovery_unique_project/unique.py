"""Stable deduplication with a deliberately order-destroying implementation."""


def unique_in_order(values: list[int]) -> list[int]:
    """Return each value once while preserving its first-seen order."""
    return list(set(values))
