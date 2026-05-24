"""Unit tests for perfsage.core.analysis.metrics."""

from pathlib import Path

from perfsage.core.analysis.metrics import (
    compute_bytes_series,
    compute_correlation_matrix,
    compute_error_series,
    compute_label_summary,
    compute_rt_series,
    compute_thread_series,
    compute_throughput_series,
)


def test_throughput_series_has_rps(sample_parquet: Path) -> None:
    df = compute_throughput_series(sample_parquet)
    assert "rps" in df.columns
    assert df["rps"].sum() > 0


def test_throughput_series_has_all_label(sample_parquet: Path) -> None:
    df = compute_throughput_series(sample_parquet)
    assert "ALL" in df["label"].to_list()


def test_throughput_series_has_per_label(sample_parquet: Path) -> None:
    df = compute_throughput_series(sample_parquet)
    labels = df["label"].unique().to_list()
    # Should have both 'ALL' and at least one specific label.
    assert len(labels) >= 2


def test_throughput_series_has_timestamp_bucket(sample_parquet: Path) -> None:
    df = compute_throughput_series(sample_parquet)
    assert "timestamp_bucket" in df.columns


def test_error_series_columns(sample_parquet: Path) -> None:
    df = compute_error_series(sample_parquet)
    for col in ("timestamp_bucket", "error_count", "total_count", "error_rate"):
        assert col in df.columns, f"Missing column: {col}"


def test_error_series_no_errors(sample_parquet_fast: Path) -> None:
    df = compute_error_series(sample_parquet_fast)
    assert df["error_rate"].max() == 0.0


def test_error_series_with_errors(sample_parquet_with_errors: Path) -> None:
    df = compute_error_series(sample_parquet_with_errors)
    assert "error_rate" in df.columns
    assert df["error_rate"].max() > 0


def test_rt_series_columns(sample_parquet: Path) -> None:
    df = compute_rt_series(sample_parquet)
    for col in ("timestamp_bucket", "p50", "p90", "p95", "p99", "mean", "min", "max", "label"):
        assert col in df.columns, f"Missing column: {col}"


def test_rt_series_percentile_ordering(sample_parquet: Path) -> None:
    df = compute_rt_series(sample_parquet)
    row = df.to_dicts()[0]
    assert row["p50"] <= row["p90"] <= row["p95"] <= row["p99"]


def test_thread_series_columns(sample_parquet: Path) -> None:
    df = compute_thread_series(sample_parquet)
    for col in ("timestamp_bucket", "grp_threads", "all_threads"):
        assert col in df.columns


def test_bytes_series_columns(sample_parquet: Path) -> None:
    df = compute_bytes_series(sample_parquet)
    for col in ("timestamp_bucket", "total_bytes", "total_sent_bytes", "bytes_per_sec"):
        assert col in df.columns


def test_bytes_series_positive(sample_parquet: Path) -> None:
    df = compute_bytes_series(sample_parquet)
    assert df["total_bytes"].sum() > 0
    assert df["bytes_per_sec"].sum() > 0


def test_label_summary_columns(sample_parquet: Path) -> None:
    df = compute_label_summary(sample_parquet)
    for col in (
        "label",
        "count",
        "error_count",
        "error_rate",
        "mean_elapsed",
        "p50",
        "p90",
        "p95",
        "p99",
        "min_elapsed",
        "max_elapsed",
        "mean_bytes",
        "mean_latency",
        "mean_connect",
    ):
        assert col in df.columns, f"Missing column: {col}"


def test_label_summary_error_rate_zero(sample_parquet_fast: Path) -> None:
    df = compute_label_summary(sample_parquet_fast)
    assert df["error_rate"].max() == 0.0


def test_label_summary_error_rate_nonzero(sample_parquet_with_errors: Path) -> None:
    df = compute_label_summary(sample_parquet_with_errors)
    assert df["error_rate"].max() > 0


def test_correlation_matrix_columns(sample_parquet: Path) -> None:
    df = compute_correlation_matrix(sample_parquet)
    for col in ("col_a", "col_b", "correlation"):
        assert col in df.columns


def test_correlation_matrix_self_correlation(sample_parquet: Path) -> None:
    df = compute_correlation_matrix(sample_parquet)
    self_rows = df.filter(df["col_a"] == df["col_b"])
    for row in self_rows.to_dicts():
        assert abs(float(row["correlation"]) - 1.0) < 1e-6


def test_correlation_matrix_symmetric(sample_parquet: Path) -> None:
    df = compute_correlation_matrix(sample_parquet)
    for row in df.to_dicts():
        # Lookup the transpose pair.
        match = df.filter((df["col_a"] == row["col_b"]) & (df["col_b"] == row["col_a"]))
        if not match.is_empty():
            assert abs(float(match["correlation"][0]) - float(row["correlation"])) < 1e-6
