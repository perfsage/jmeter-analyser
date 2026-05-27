"""Unit tests for perfsage.core.parsing.xml_loader."""

from __future__ import annotations

import tracemalloc
from pathlib import Path

import polars as pl

from perfsage.core.parsing.xml_loader import load_xml_to_parquet
from tests.fixtures.generate_jtl import make_xml_jtl


def _write(tmp_path: Path, content: str, name: str = "test.jtl") -> Path:
    p = tmp_path / name
    p.write_text(content)
    return p


def test_loads_xml_jtl(tmp_path: Path) -> None:
    src = _write(tmp_path, make_xml_jtl(n_rows=10))
    dest = tmp_path / "out.parquet"
    quar = tmp_path / "quar.parquet"
    parsed, errors = load_xml_to_parquet(src, dest, quar)
    assert parsed == 10
    assert errors == 0
    df = pl.read_parquet(dest)
    assert set(df.columns).issuperset({"timestamp_ms", "elapsed", "label", "success"})


def test_loads_xml_with_errors(tmp_path: Path) -> None:
    src = _write(tmp_path, make_xml_jtl(n_rows=10, include_errors=True))
    dest = tmp_path / "out.parquet"
    quar = tmp_path / "quar.parquet"
    parsed, errors = load_xml_to_parquet(src, dest, quar)
    assert parsed + errors == 10


def test_xml_handles_http_sample_and_sample(tmp_path: Path) -> None:
    """Generator interleaves httpSample and sample tags — both must be parsed."""
    src = _write(tmp_path, make_xml_jtl(n_rows=6))
    dest = tmp_path / "out.parquet"
    quar = tmp_path / "quar.parquet"
    parsed, _ = load_xml_to_parquet(src, dest, quar)
    assert parsed == 6


def test_xml_columns_typed(tmp_path: Path) -> None:
    src = _write(tmp_path, make_xml_jtl(n_rows=5))
    dest = tmp_path / "out.parquet"
    quar = tmp_path / "quar.parquet"
    load_xml_to_parquet(src, dest, quar)
    df = pl.read_parquet(dest)
    assert df["timestamp_ms"].dtype == pl.Int64
    assert df["elapsed"].dtype == pl.Int64


def test_xml_writes_quarantine_parquet(tmp_path: Path) -> None:
    src = _write(tmp_path, make_xml_jtl(n_rows=5))
    dest = tmp_path / "out.parquet"
    quar = tmp_path / "quar.parquet"
    load_xml_to_parquet(src, dest, quar)
    assert quar.exists()
    qdf = pl.read_parquet(quar)
    assert "reason" in qdf.columns


def test_xml_memory_bounded(tmp_path: Path) -> None:
    """100k-row XML must parse with peak memory < 200 MB."""
    src = _write(tmp_path, make_xml_jtl(n_rows=100_000))
    dest = tmp_path / "out.parquet"
    quar = tmp_path / "quar.parquet"

    tracemalloc.start()
    parsed, errors = load_xml_to_parquet(src, dest, quar)
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert parsed == 100_000
    assert errors == 0
    peak_mb = peak_bytes / 1024 / 1024
    assert peak_mb < 200, f"Peak memory {peak_mb:.1f} MB exceeded 200 MB limit"


def test_xml_idle_time_mapped(tmp_path: Path) -> None:
    """XML 'it' attribute must be stored as idle_time with correct int value."""
    xml_content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<testResults version="1.2">\n'
        '  <httpSample ts="1700000000000" t="200" lb="Home" rc="200" rm="OK"'
        ' tn="t1" s="true" by="1024" sby="256" ng="1" na="1"'
        ' lt="80" ct="10" it="123"/>\n'
        '  <sample ts="1700000001000" t="150" lb="API" rc="200" rm="OK"'
        ' tn="t1" s="true" by="512" sby="128" ng="1" na="1"'
        ' lt="60" ct="5" it="456"/>\n'
        "</testResults>\n"
    )
    src = _write(tmp_path, xml_content)
    dest = tmp_path / "out.parquet"
    quar = tmp_path / "quar.parquet"
    parsed, errors = load_xml_to_parquet(src, dest, quar)
    assert parsed == 2
    assert errors == 0
    df = pl.read_parquet(dest)
    assert "idle_time" in df.columns
    assert df["idle_time"].to_list() == [123, 456]
