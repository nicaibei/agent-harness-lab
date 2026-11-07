"""Offline checks for the repository-shaped inventory fixture."""

from pathlib import Path

from evals.real_recovery import INVENTORY_HIDDEN_TESTS, INVENTORY_PROJECT, _run_hidden_tests


def test_inventory_fixture_fails_then_passes_after_layered_repairs(tmp_path: Path) -> None:
    workspace = tmp_path / "inventory-repo"
    source_files = (
        "inventory_app/settings.py",
        "inventory_app/catalog.py",
        "inventory_app/checkout.py",
        "inventory_app/__init__.py",
        "config/checkout.json",
        "pyproject.toml",
    )
    for filename in source_files:
        target = workspace / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((INVENTORY_PROJECT / filename).read_bytes())

    assert _run_hidden_tests(workspace, INVENTORY_HIDDEN_TESTS)["success"] is False

    (workspace / "inventory_app/settings.py").write_text(
        '"""Configuration loading."""\n\nimport json\nfrom pathlib import Path\n\n\ndef load_settings(path: str | Path) -> dict[str, float | str]:\n'
        '    data = json.loads(Path(path).read_text(encoding="utf-8"))\n'
        '    return {"tax_rate": float(data["tax_rate"]), "currency": data["currency"]}\n',
        encoding="utf-8",
    )
    (workspace / "inventory_app/catalog.py").write_text(
        '"""Catalog calculations."""\n\n\ndef subtotal(lines, stock):\n'
        '    return sum(min(int(line["quantity"]), stock.get(str(line["sku"]), 0)) * float(line["unit_price"]) for line in lines)\n',
        encoding="utf-8",
    )
    (workspace / "inventory_app/checkout.py").write_text(
        '"""Checkout service."""\n\n\nfrom inventory_app.catalog import subtotal\n'
        'from inventory_app.settings import load_settings\n\n\ndef checkout_total(lines, stock, config_path):\n'
        '    settings = load_settings(config_path)\n'
        '    return subtotal(lines, stock) * (1 + float(settings["tax_rate"]))\n',
        encoding="utf-8",
    )

    result = _run_hidden_tests(workspace, INVENTORY_HIDDEN_TESTS)
    assert result["success"] is True
