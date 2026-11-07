"""Hidden evaluator for a cross-file order calculation."""

from order_parser import parse_order
from order_total import total_with_tax


def test_parse_order_preserves_quantity_and_price() -> None:
    assert parse_order("3 x 10.00") == {"quantity": 3, "unit_price": 10.0}


def test_total_with_tax_uses_parsed_order() -> None:
    order = parse_order("3 x 10.00")
    assert total_with_tax(order, 0.2) == 36.0
