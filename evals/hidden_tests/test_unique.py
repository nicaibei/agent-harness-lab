"""Hidden evaluator for stable deduplication."""

from unique import unique_in_order


def test_unique_in_order_preserves_first_occurrence_order() -> None:
    assert unique_in_order([3, 1, 3, 2, 1]) == [3, 1, 2]


def test_unique_in_order_handles_empty_input() -> None:
    assert unique_in_order([]) == []
