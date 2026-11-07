"""Layered hidden evaluator for the inventory repository fixture."""

from pathlib import Path

from inventory_app.catalog import subtotal
from inventory_app.checkout import checkout_total
from inventory_app.settings import load_settings


CONFIG_PATH = Path.cwd() / "config" / "checkout.json"
LINES = [{"sku": "A", "quantity": 3, "unit_price": 10.0}]
STOCK = {"A": 2}


def test_settings_layer_reads_fractional_tax_rate() -> None:
    assert load_settings(CONFIG_PATH) == {"tax_rate": 0.2, "currency": "USD"}


def test_catalog_layer_respects_available_stock() -> None:
    assert subtotal(LINES, STOCK) == 20.0


def test_service_layer_combines_catalog_and_settings() -> None:
    assert checkout_total(LINES, STOCK, CONFIG_PATH) == 24.0
