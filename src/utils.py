"""Shared utility helpers for the Tesla FDE analysis project."""

from __future__ import annotations

import re
from pathlib import Path


def get_project_root() -> Path:
    """Return the repository root based on this file location."""
    return Path(__file__).resolve().parents[1]


def ensure_directory(path: Path) -> Path:
    """Create a directory if needed and return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def to_snake_case(value: str) -> str:
    """Convert a string to snake_case for standardized column names."""
    cleaned = re.sub(r"[^\w\s]", " ", value).strip().lower()
    cleaned = re.sub(r"[\s\-]+", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned)
    return cleaned.strip("_")


def normalize_identifier(value: str) -> str:
    """
    Normalize text for lightweight matching across columns/sheets.

    This removes punctuation and spaces so similarly named fields can be compared.
    """
    return re.sub(r"[^a-z0-9]", "", value.lower())
