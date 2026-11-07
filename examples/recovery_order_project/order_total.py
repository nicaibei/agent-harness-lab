"""Order total calculator with deliberately incorrect arithmetic."""


def total_with_tax(order: dict[str, float], tax_rate: float) -> float:
    """Return an order subtotal plus a fractional tax rate."""
    subtotal = order["quantity"] + order["unit_price"]
    return subtotal + tax_rate
