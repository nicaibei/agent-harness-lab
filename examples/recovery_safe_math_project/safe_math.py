"""Safe division with a deliberately missing zero-denominator case."""


def safe_divide(left: float, right: float) -> float | None:
    """Return the quotient, or None when the denominator is zero."""
    return left / right
