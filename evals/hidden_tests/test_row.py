"""Hidden evaluator for CSV-like row parsing."""

from row import parse_row


def test_parse_row_maps_name_then_score() -> None:
    assert parse_row("Alice, 42") == {"name": "Alice", "score": 42}


def test_parse_row_strips_both_fields() -> None:
    assert parse_row(" Bob , 7 ") == {"name": "Bob", "score": 7}
