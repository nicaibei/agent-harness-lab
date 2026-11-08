"""Service package entry point with a deliberate import typo."""

from service_app.configs import load_settings

__all__ = ["load_settings"]
