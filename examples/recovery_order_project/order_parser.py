"""Order parser with a deliberately broken field mapping."""


def parse_order(value: str) -> dict[str, float]:
    """Parse an order written as ``quantity x unit_price``."""
    quantity_text, price_text = [part.strip() for part in value.split("x")]
    return {"quantity": float(price_text), "unit_price": int(quantity_text)}
