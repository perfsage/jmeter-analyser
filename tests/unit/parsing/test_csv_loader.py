"""Unit tests for perfsage.core.parsing.csv_loader."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from perfsage.core.parsing.csv_loader import load_csv_to_parquet, map_columns
from tests.fixtures.generate_jtl import make_csv_jtl


def _write(tmp_path: Path, content: str, name: str = "test.csv") -> Path:
    p = tmp_path / name
    p.write_text(content)
    return p


# ─── map_columns ─────────────────────────────────────────────────────────────


def test_map_columns_renames_jmeter_variants() -> None:
    df = pl.DataFrame({"timeStamp": ["1700000000000"], "elapsed": ["100"]})
    result = map_columns(df)
    assert "timestamp_ms" in result.columns
    assert "elapsed" in result.columns
    assert "timeStamp" not in result.columns


def test_map_columns_drops_unknown_columns() -> None:
    df = pl.DataFrame(
        {"timeStamp": ["1700000000000"], "dataType": ["text"], "unknown_col": ["x"]}
    )
    result = map_columns(df)
    assert "unknown_col" not in result.columns
    assert "dataType" not in result.columns  # dataType has no canonical mapping


def test_map_columns_deduplicates_canonicals() -> None:
    """Two source columns that both map to the same canonical — keep first."""
    df = pl.DataFrame({"Latency": ["80"], "latency": ["90"]})
    result = map_columns(df)
    assert result.columns.count("latency") == 1


# ─── load_csv_to_parquet ─────────────────────────────────────────────────────


def test_loads_jmeter_2x_csv(tmp_path: Path) -> None:
    src = _write(tmp_path, make_csv_jtl(n_rows=10, version="2.x"))
    dest = tmp_path / "out.parquet"
    quar = tmp_path / "quar.parquet"
    parsed, errors = load_csv_to_parquet(src, dest, quar)
    assert parsed == 10
    assert errors == 0
    df = pl.read_parquet(dest)
    assert set(df.columns).issuperset({"timestamp_ms", "elapsed", "label", "success"})


def test_loads_jmeter_3x_csv(tmp_path: Path) -> None:
    src = _write(tmp_path, make_csv_jtl(n_rows=10, version="3.x"))
    dest = tmp_path / "out.parquet"
    quar = tmp_path / "quar.parquet"
    parsed, errors = load_csv_to_parquet(src, dest, quar)
    assert parsed == 10
    assert errors == 0
    df = pl.read_parquet(dest)
    assert "sent_bytes" in df.columns
    assert "latency" in df.columns


def test_loads_jmeter_56_csv(tmp_path: Path) -> None:
    src = _write(tmp_path, make_csv_jtl(n_rows=20, version="5.6"))
    dest = tmp_path / "out.parquet"
    quar = tmp_path / "quar.parquet"
    parsed, errors = load_csv_to_parquet(src, dest, quar)
    assert parsed == 20
    assert errors == 0


def test_handles_missing_optional_columns(tmp_path: Path) -> None:
    """JMeter 2.x doesn't have sent_bytes — should still parse cleanly."""
    src = _write(tmp_path, make_csv_jtl(n_rows=5, version="2.x"))
    dest = tmp_path / "out.parquet"
    quar = tmp_path / "quar.parquet"
    parsed, errors = load_csv_to_parquet(src, dest, quar)
    df = pl.read_parquet(dest)
    assert parsed == 5
    assert errors == 0
    assert "sent_bytes" not in df.columns  # legitimately absent for 2.x


def test_quarantines_negative_elapsed(tmp_path: Path) -> None:
    content = (
        "timeStamp,elapsed,label,responseCode,responseMessage,threadName,dataType,success,bytes\n"
        "1700000000000,100,Home,200,OK,t1,text,true,1024\n"
        "1700000001000,-5,Broken,200,OK,t1,text,true,1024\n"
    )
    src = _write(tmp_path, content)
    dest = tmp_path / "out.parquet"
    quar = tmp_path / "quar.parquet"
    parsed, errors = load_csv_to_parquet(src, dest, quar)
    assert parsed == 1
    assert errors == 1
    qdf = pl.read_parquet(quar)
    assert len(qdf) == 1
    assert "elapsed" in qdf["reason"][0]


def test_handles_tab_delimiter(tmp_path: Path) -> None:
    src = _write(tmp_path, make_csv_jtl(n_rows=10, delimiter="\t"))
    dest = tmp_path / "out.parquet"
    quar = tmp_path / "quar.parquet"
    parsed, errors = load_csv_to_parquet(src, dest, quar, delimiter="\t")
    assert parsed == 10
    assert errors == 0


def test_writes_empty_quarantine_parquet(tmp_path: Path) -> None:
    """Even with zero bad rows the quarantine Parquet file must be created."""
    src = _write(tmp_path, make_csv_jtl(n_rows=5))
    dest = tmp_path / "out.parquet"
    quar = tmp_path / "quar.parquet"
    load_csv_to_parquet(src, dest, quar)
    assert quar.exists()
    qdf = pl.read_parquet(quar)
    assert list(qdf.columns) == ["row_index", "reason", "raw_json"]


def test_loads_csv_with_errors(tmp_path: Path) -> None:
    src = _write(tmp_path, make_csv_jtl(n_rows=10, include_errors=True))
    dest = tmp_path / "out.parquet"
    quar = tmp_path / "quar.parquet"
    parsed, errors = load_csv_to_parquet(src, dest, quar)
    assert parsed + errors == 10
    # All rows have valid elapsed — none quarantined; success=false is fine.
    assert parsed == 10


def test_csv_memory_bounded_100k(tmp_path: Path) -> None:
    """100k-row CSV must load completely without accumulating all chunks."""
    src = _write(tmp_path, make_csv_jtl(n_rows=100_000, version="5.6"))
    dest = tmp_path / "out.parquet"
    quar = tmp_path / "quar.parquet"
    parsed, errors = load_csv_to_parquet(src, dest, quar)
    assert parsed == 100_000
    assert errors == 0
    df = pl.read_parquet(dest)
    assert len(df) == 100_000
    assert set(df.columns).issuperset({"timestamp_ms", "elapsed", "label", "success"})
