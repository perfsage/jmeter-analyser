"""Unit tests for perfsage.core.analysis.percentiles."""

from pathlib import Path

from perfsage.core.analysis.percentiles import compute_overall_percentiles, compute_percentiles


def test_compute_percentiles_basic(sample_parquet: Path) -> None:
    df = compute_percentiles(sample_parquet)
    assert "p50" in df.columns
    assert "p99" in df.columns
    assert df["count"].sum() > 0


def test_compute_percentiles_has_expected_columns(sample_parquet: Path) -> None:
    df = compute_percentiles(sample_parquet)
    for col in ("count", "mean", "std", "min", "max", "p50", "p75", "p90", "p95", "p99", "p999"):
        assert col in df.columns, f"Missing column: {col}"


def test_percentiles_per_label(sample_parquet: Path) -> None:
    df = compute_percentiles(sample_parquet, groupby_label=True)
    assert "label" in df.columns
    assert df.shape[0] >= 2


def test_percentiles_no_groupby(sample_parquet: Path) -> None:
    df = compute_percentiles(sample_parquet, groupby_label=False)
    assert "label" not in df.columns
    assert df.shape[0] == 1


def test_percentile_ordering(sample_parquet: Path) -> None:
    df = compute_percentiles(sample_parquet, groupby_label=False)
    row = df.to_dicts()[0]
    assert row["p50"] <= row["p75"] <= row["p90"] <= row["p95"] <= row["p99"] <= row["p999"]


def test_custom_percentiles(sample_parquet: Path) -> None:
    df = compute_percentiles(sample_parquet, percentiles=[0.5, 0.99], groupby_label=False)
    assert "p50" in df.columns
    assert "p99" in df.columns
    assert "p90" not in df.columns


def test_compute_overall_percentiles(sample_parquet: Path) -> None:
    result = compute_overall_percentiles(sample_parquet)
    assert set(result.keys()) == {"p50", "p75", "p90", "p95", "p99", "p999"}
    assert result["p50"] <= result["p99"]
    assert result["p99"] <= result["p999"]


def test_percentiles_fast_data(sample_parquet_fast: Path) -> None:
    result = compute_overall_percentiles(sample_parquet_fast)
    assert result["p99"] < 50


def test_percentiles_slow_data(sample_parquet_slow: Path) -> None:
    result = compute_overall_percentiles(sample_parquet_slow)
    assert result["p50"] >= 5000


def test_compute_overall_percentiles_empty_file_returns_zeros(tmp_path):
    import polars as pl

    from perfsage.core.analysis.percentiles import compute_overall_percentiles

    empty = pl.DataFrame({"elapsed": pl.Series([], dtype=pl.Int64)})
    path = tmp_path / "empty.parquet"
    empty.write_parquet(path)

    result = compute_overall_percentiles(path)
    assert result == {"p50": 0.0, "p75": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0, "p999": 0.0}
