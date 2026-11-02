"""Compatibility helpers for language/font formatting.

This module intentionally has no optional third-party dependencies. It provides
safe text normalization and identity fallbacks for deployments that reference
TechVJ.util.lang_font while running without the original font package.
"""
from __future__ import annotations
import unicodedata


def clean_text(value):
    """Return a safe, whitespace-normalized string without stripping native scripts."""
    if value is None:
        return ""
    return " ".join(unicodedata.normalize("NFC", str(value)).split())


def normalize_text(value):
    return clean_text(value)


def convert_font(value, *args, **kwargs):
    """Identity fallback: preserve original/native characters."""
    return clean_text(value)


def to_font(value, *args, **kwargs):
    return convert_font(value, *args, **kwargs)


def apply_font(value, *args, **kwargs):
    return convert_font(value, *args, **kwargs)


def stylize(value, *args, **kwargs):
    return convert_font(value, *args, **kwargs)


def __getattr__(name):
    # Compatibility for legacy named font converters: preserve text rather than
    # failing startup when a converter is unavailable in this distribution.
    if name.startswith(("font_", "to_", "convert_", "apply_", "style_", "bold", "italic")):
        return convert_font
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
