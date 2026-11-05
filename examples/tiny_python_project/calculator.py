"""Tiny calculator project used by the baseline coding agent."""


def add(left: float, right: float) -> float:
    """Return the sum of two numbers."""
    return left + right


def subtract(left: float, right: float) -> float:
    """Return the difference between two numbers."""
    return left - right


def divide(left: float, right: float) -> float:
    """Return the quotient of two numbers."""
    if right == 0:
        raise ValueError("Cannot divide by zero.")
    return left / right
