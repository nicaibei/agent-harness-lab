"""Hidden evaluator for the real Recovery experiment."""

from title_utils import normalize_title


def test_normalize_title_collapses_spaces_to_hyphens() -> None:
    assert normalize_title("  Hello   World ") == "hello-world"


def test_normalize_title_normalizes_mixed_case() -> None:
    assert normalize_title("Agent  Harness") == "agent-harness"
