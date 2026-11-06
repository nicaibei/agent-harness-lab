"""Small project with a deliberately incomplete title normalizer."""


def normalize_title(value: str) -> str:
    """Normalize a title's outer whitespace and letter case."""
    return value.strip().lower()
