"""Unit tests for export cache invalidation."""

import time
from pathlib import Path


def test_should_regenerate_when_missing(tmp_path: Path) -> None:
    from perfsage.api.exports import _should_regenerate

    export_path = tmp_path / "out.html"
    samples = tmp_path / "samples.parquet"
    samples.write_bytes(b"x")
    assert _should_regenerate(export_path, samples, force=False) is True


def test_should_regenerate_when_force(tmp_path: Path) -> None:
    from perfsage.api.exports import _should_regenerate

    export_path = tmp_path / "out.html"
    export_path.write_text("cached")
    samples = tmp_path / "samples.parquet"
    samples.write_bytes(b"x")
    assert _should_regenerate(export_path, samples, force=True) is True


def test_should_not_regenerate_when_fresh(tmp_path: Path) -> None:
    from perfsage.api.exports import _should_regenerate

    export_path = tmp_path / "out.html"
    samples = tmp_path / "samples.parquet"
    samples.write_bytes(b"data")
    export_path.write_text("cached")
    time.sleep(0.02)
    export_path.touch()
    assert _should_regenerate(export_path, samples, force=False) is False
