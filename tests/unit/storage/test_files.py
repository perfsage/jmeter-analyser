"""Unit tests for FileStore path management."""

from __future__ import annotations

from pathlib import Path

from perfsage.core.storage.files import FileStore


def test_upload_path(tmp_path: Path) -> None:
    fs = FileStore(tmp_path)
    p = fs.upload_path("job-123")
    assert p == tmp_path / "uploads" / "job-123.jtl"


def test_samples_parquet(tmp_path: Path) -> None:
    fs = FileStore(tmp_path)
    p = fs.samples_parquet("report-456")
    assert p == tmp_path / "parquet" / "report-456" / "samples.parquet"


def test_quarantine_parquet(tmp_path: Path) -> None:
    fs = FileStore(tmp_path)
    p = fs.quarantine_parquet("report-456")
    assert p == tmp_path / "parquet" / "report-456" / "quarantine.parquet"


def test_agg_parquet(tmp_path: Path) -> None:
    fs = FileStore(tmp_path)
    p = fs.agg_parquet("report-789", "summary")
    assert p == tmp_path / "parquet" / "report-789" / "agg_summary.parquet"


def test_export_path(tmp_path: Path) -> None:
    fs = FileStore(tmp_path)
    p = fs.export_path("report-789", "csv")
    assert p == tmp_path / "exports" / "report-789.csv"


def test_ensure_dirs(tmp_path: Path) -> None:
    fs = FileStore(tmp_path)
    fs.ensure_dirs()
    for sub in ("uploads", "parquet", "exports"):
        assert (tmp_path / sub).is_dir()


def test_ensure_dirs_idempotent(tmp_path: Path) -> None:
    fs = FileStore(tmp_path)
    fs.ensure_dirs()
    fs.ensure_dirs()  # calling twice must not raise
    assert (tmp_path / "uploads").is_dir()
