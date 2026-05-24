"""File-system helpers for managing uploaded and generated files."""

from pathlib import Path

from perfsage.config import get_settings


def uploads_dir() -> Path:
    """Return the uploads directory, creating it if necessary."""
    path = get_settings().data_dir / "uploads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def exports_dir() -> Path:
    """Return the exports directory, creating it if necessary."""
    path = get_settings().data_dir / "exports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def parquet_dir() -> Path:
    """Return the Parquet storage directory, creating it if necessary."""
    path = get_settings().data_dir / "parquet"
    path.mkdir(parents=True, exist_ok=True)
    return path
