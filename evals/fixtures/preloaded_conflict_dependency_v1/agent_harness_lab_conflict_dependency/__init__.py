"""Preloaded but incompatible version of the conflict dependency."""

__version__ = "1.0.0"


def readiness_message() -> str:
    """Return the version-specific readiness signal."""
    return "dependency-v1-ready"
