"""Application startup logic."""

from service_app import load_settings


def main() -> None:
    """Start the demo service and print its readiness signal."""
    print(f"service-ready:{load_settings()['name']}")
