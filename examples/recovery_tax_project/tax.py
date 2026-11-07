"""Small tax calculator with a deliberately incorrect total calculation."""


def total_with_tax(amount: float, tax_rate: float) -> float:
    """Return the amount including a fractional tax rate."""
    return amount + tax_rate
