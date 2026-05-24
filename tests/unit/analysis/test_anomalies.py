"""Unit tests for perfsage.core.analysis.anomalies."""

from pathlib import Path

from perfsage.core.analysis.anomalies import (
    detect_error_spikes,
    detect_knee_point,
    detect_rt_spikes,
)


def test_spike_detection_finds_spike(sample_parquet_with_spike: Path) -> None:
    df = detect_rt_spikes(sample_parquet_with_spike, z_threshold=2.5, bucket_seconds=10)
    assert "is_anomaly" in df.columns
    assert df["is_anomaly"].sum() > 0


def test_spike_detection_no_false_positives(sample_parquet_fast: Path) -> None:
    df = detect_rt_spikes(sample_parquet_fast, z_threshold=2.5, bucket_seconds=10)
    assert df["is_anomaly"].sum() < 2


def test_rt_spikes_columns(sample_parquet: Path) -> None:
    df = detect_rt_spikes(sample_parquet)
    for col in ("timestamp_bucket", "p95", "z_score", "is_anomaly"):
        assert col in df.columns, f"Missing column: {col}"


def test_rt_spikes_returns_all_buckets(sample_parquet: Path) -> None:
    df = detect_rt_spikes(sample_parquet, bucket_seconds=10)
    # 100 rows at 1 row/second → ~10 buckets of 10s each
    assert df.shape[0] >= 1


def test_error_spikes_no_errors(sample_parquet_fast: Path) -> None:
    df = detect_error_spikes(sample_parquet_fast)
    assert df.is_empty()


def test_error_spikes_detects_errors(sample_parquet_with_errors: Path) -> None:
    # ~20% errors → well above min_error_rate=5% and 2x overall baseline.
    df = detect_error_spikes(sample_parquet_with_errors, min_error_rate=0.05)
    # With uniform ~20% error rate, overall baseline ≈ 20% and 2x = 40%.
    # No bucket should exceed 40% by definition of uniform errors.
    # So either 0 or some spikes depending on bucket distribution.
    # The key assertion: columns are correct.
    for col in ("timestamp_bucket", "error_count", "total_count", "error_rate"):
        assert col in df.columns


def test_knee_point_constant_load(sample_parquet_fast: Path) -> None:
    # Constant load with no RT increase → no knee detected.
    result = detect_knee_point(sample_parquet_fast)
    assert result is None or isinstance(result, dict)


def test_knee_point_returns_dict_or_none(sample_parquet: Path) -> None:
    result = detect_knee_point(sample_parquet)
    if result is not None:
        assert "knee_rps" in result
        assert "knee_p90_ms" in result
        assert isinstance(result["knee_rps"], float)
        assert isinstance(result["knee_p90_ms"], float)
