"""Single source of truth for package version (reads repo-root VERSION file)."""

from __future__ import annotations

from pathlib import Path


def read_version() -> str:
    for candidate in (
        Path(__file__).resolve().parents[1] / "VERSION",
        Path("/app/VERSION"),
    ):
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8").strip()
    return "0.1.0"


__version__ = read_version()
