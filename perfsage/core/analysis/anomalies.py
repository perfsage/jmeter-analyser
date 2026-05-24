"""Statistical anomaly detection for JMeter time-series data."""

from __future__ import annotations

from pathlib import Path

import duckdb
import polars as pl


def detect_rt_spikes(
    samples_path: Path,
    z_threshold: float = 3.0,
    bucket_seconds: int = 10,
) -> pl.DataFrame:
    """Z-score anomaly detection on bucketed p95 RT.

    Returns: timestamp_bucket, p95, z_score, is_anomaly.
    """
    con = duckdb.connect()
    con.execute(f"CREATE VIEW samples AS SELECT * FROM read_parquet('{samples_path}')")

    df = con.execute(
        f"""
        SELECT to_timestamp((timestamp_ms // 1000 // {bucket_seconds}) * {bucket_seconds})
                   AS timestamp_bucket,
               PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY elapsed) AS p95
        FROM samples
        GROUP BY timestamp_ms // 1000 // {bucket_seconds}
        ORDER BY timestamp_bucket
        """
    ).pl()

    if df.is_empty() or df.shape[0] < 2:
        return df.with_columns(
            [pl.lit(0.0).alias("z_score"), pl.lit(False).alias("is_anomaly")]
        )

    mean = df["p95"].mean()
    std = df["p95"].std()

    if mean is None or std is None or std == 0.0:
        return df.with_columns(
            [pl.lit(0.0).alias("z_score"), pl.lit(False).alias("is_anomaly")]
        )

    return df.with_columns(
        [((pl.col("p95") - mean) / std).alias("z_score")]
    ).with_columns(
        [(pl.col("z_score").abs() > z_threshold).alias("is_anomaly")]
    )


def detect_error_spikes(
    samples_path: Path,
    bucket_seconds: int = 10,
    min_error_rate: float = 0.05,
) -> pl.DataFrame:
    """Return time buckets where error_rate > min_error_rate and is 2× the rolling baseline."""
    con = duckdb.connect()
    con.execute(f"CREATE VIEW samples AS SELECT * FROM read_parquet('{samples_path}')")

    df = con.execute(
        f"""
        SELECT to_timestamp((timestamp_ms // 1000 // {bucket_seconds}) * {bucket_seconds})
                   AS timestamp_bucket,
               SUM(CASE WHEN NOT success THEN 1 ELSE 0 END)::BIGINT AS error_count,
               COUNT(*)::BIGINT AS total_count,
               SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS error_rate
        FROM samples
        GROUP BY timestamp_ms // 1000 // {bucket_seconds}
        ORDER BY timestamp_bucket
        """
    ).pl()

    if df.is_empty():
        return df

    overall = df["error_rate"].mean()
    baseline = max(float(overall) if overall is not None else 0.0, 0.001)  # type: ignore[arg-type]

    return df.filter(
        (pl.col("error_rate") > min_error_rate) & (pl.col("error_rate") > 2.0 * baseline)
    )


def detect_knee_point(
    samples_path: Path,
) -> dict[str, float] | None:
    """Detect the saturation knee in the RT-vs-RPS scatter.

    Finds the point where marginal p90 RT increase exceeds 2× the baseline slope.
    Returns {"knee_rps": float, "knee_p90_ms": float} or None if not detected.
    """
    con = duckdb.connect()
    con.execute(f"CREATE VIEW samples AS SELECT * FROM read_parquet('{samples_path}')")

    bucket_seconds = 10
    rows = con.execute(
        f"""
        SELECT COUNT(*) * 1.0 / {bucket_seconds} AS rps,
               PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY elapsed) AS p90_elapsed
        FROM samples
        GROUP BY timestamp_ms // 1000 // {bucket_seconds}
        ORDER BY rps
        """
    ).fetchall()

    if len(rows) < 3:
        return None

    rps_vals = [float(r[0]) for r in rows]
    p90_vals = [float(r[1]) for r in rows]

    n_baseline = max(1, len(p90_vals) // 4)
    deltas = [p90_vals[i] - p90_vals[i - 1] for i in range(1, len(p90_vals))]
    baseline_slope = sum(deltas[:n_baseline]) / n_baseline if n_baseline > 0 else 1.0
    baseline_slope = max(baseline_slope, 0.1)

    baseline_rt = sum(p90_vals[:n_baseline]) / n_baseline

    for i, delta in enumerate(deltas):
        if delta > 2.0 * baseline_slope and p90_vals[i + 1] > 2.0 * baseline_rt:
            return {"knee_rps": rps_vals[i + 1], "knee_p90_ms": p90_vals[i + 1]}

    return None
