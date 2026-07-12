"""File-system helpers for managing uploaded and generated files."""

from __future__ import annotations

from pathlib import Path


class FileStore:
    """Centralised file path management for all data files on disk."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir

    def upload_path(self, job_id: str) -> Path:
        """Return path for an uploaded JTL file: data/uploads/{job_id}.jtl"""
        return self.data_dir / "uploads" / f"{job_id}.jtl"

    def samples_parquet(self, report_id: str) -> Path:
        """Return path for the canonical samples parquet: data/parquet/{report_id}/samples.parquet"""
        return self.data_dir / "parquet" / report_id / "samples.parquet"

    def quarantine_parquet(self, report_id: str) -> Path:
        """Return path for quarantined rows: data/parquet/{report_id}/quarantine.parquet"""
        return self.data_dir / "parquet" / report_id / "quarantine.parquet"

    def agg_parquet(self, report_id: str, agg_name: str) -> Path:
        """Return path for an aggregate file: data/parquet/{report_id}/agg_{agg_name}.parquet"""
        return self.data_dir / "parquet" / report_id / f"agg_{agg_name}.parquet"

    def render_cache_path(self, report_id: str, cache_name: str) -> Path:
        """Return path for a cached render payload: data/parquet/{report_id}/figs_{cache_name}.json"""
        return self.data_dir / "parquet" / report_id / f"figs_{cache_name}.json"

    def export_path(self, report_id: str, fmt: str) -> Path:
        """Return path for an export file: data/exports/{report_id}.{fmt}"""
        return self.data_dir / "exports" / f"{report_id}.{fmt}"

    def ensure_dirs(self) -> None:
        """Create all required top-level subdirectories under data_dir."""
        for sub in ("uploads", "parquet", "exports"):
            (self.data_dir / sub).mkdir(parents=True, exist_ok=True)
