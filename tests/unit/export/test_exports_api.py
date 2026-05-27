"""Unit tests for export regeneration logic."""

import time
from pathlib import Path

from perfsage.api.exports import _should_regenerate


def test_should_regenerate_when_missing(tmp_path: Path) -> None:
    export_path = tmp_path / "report.html"
    samples_path = tmp_path / "samples.parquet"
    samples_path.write_bytes(b"data")
    assert _should_regenerate(export_path, samples_path, force=False) is True


def test_should_regenerate_when_force(tmp_path: Path) -> None:
    export_path = tmp_path / "report.html"
    export_path.write_text("cached")
    samples_path = tmp_path / "samples.parquet"
    samples_path.write_bytes(b"data")
    assert _should_regenerate(export_path, samples_path, force=True) is True


def test_should_regenerate_when_stale(tmp_path: Path) -> None:
    export_path = tmp_path / "report.html"
    export_path.write_text("cached")
    samples_path = tmp_path / "samples.parquet"
    samples_path.write_bytes(b"newer")
    old_mtime = time.time() - 60
    export_path.touch()
    import os

    os.utime(export_path, (old_mtime, old_mtime))
    assert _should_regenerate(export_path, samples_path, force=False) is True


def test_should_not_regenerate_when_fresh(tmp_path: Path) -> None:
    export_path = tmp_path / "report.html"
    samples_path = tmp_path / "samples.parquet"
    samples_path.write_bytes(b"data")
    export_path.write_text("cached")
    assert _should_regenerate(export_path, samples_path, force=False) is False
