"""Application logic that is correct once the required dependency is selected."""

from service_app import readiness_message


def main() -> None:
    """Start the demo service and print its readiness signal."""
    print(readiness_message())
