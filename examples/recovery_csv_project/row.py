"""CSV-like row parser with a deliberately incorrect field mapping."""


def parse_row(value: str) -> dict[str, int | str]:
    """Parse a comma-separated name and score."""
    score_text, name = value.split(",")
    return {"name": name, "score": int(score_text)}
