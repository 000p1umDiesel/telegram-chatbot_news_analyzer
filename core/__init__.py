"""Core package exposing application settings and shared components."""

from .config import get_settings, settings  # noqa: F401

__all__ = [
    "get_settings",
    "settings",
]
