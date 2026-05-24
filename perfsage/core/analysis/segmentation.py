"""Warmup / steady-state detection for JMeter test runs."""

from __future__ import annotations

from pathlib import Path

import duckdb
import polars as pl


def detect_warmup_window(
    samples_path: Path,
    warmup_pct_threshold: float = 0.10,
) -> tuple[int, int]:
    """Return (warmup_end_ms, test_end_ms).

    Warmup ends when RPS first exceeds 80 % of peak sustained RPS.
    Falls back to the first ``warmup_pct_threshold`` fraction of total duration.
    """
    con = duckdb.connect()
    con.execute(f"CREATE VIEW samples AS SELECT * FROM read_parquet('{samples_path}')")

    bounds = con.execute(
        "SELECT MIN(timestamp_ms), MAX(timestamp_ms) + MAX(elapsed) FROM samples"
    ).fetchone()
    if bounds is None or bounds[0] is None:
        return (0, 0)

    min_ts = int(bounds[0])
    max_ts = int(bounds[1])
    test_duration_ms = max_ts - min_ts
    test_end_ms = max_ts
    fallback_warmup_end_ms = int(min_ts + test_duration_ms * warmup_pct_threshold)

    bucket_seconds = 5
    rps_rows = con.execute(
        f"""
        SELECT (timestamp_ms // 1000 // {bucket_seconds}) * {bucket_seconds} AS ts_bucket_s,
               COUNT(*) * 1.0 / {bucket_seconds} AS rps
        FROM samples
        GROUP BY 1
        ORDER BY 1
        """
    ).fetchall()

    if not rps_rows:
        return (fallback_warmup_end_ms, test_end_ms)

    peak_rps: float = max(float(row[1]) for row in rps_rows)
    threshold_rps = peak_rps * 0.8
    max_warmup_ms = int(min_ts + test_duration_ms * 0.5)

    for row in rps_rows:
        if float(row[1]) >= threshold_rps:
            warmup_end_ms = int(int(row[0]) * 1000)
            return (min(warmup_end_ms, max_warmup_ms), test_end_ms)

    return (fallback_warmup_end_ms, test_end_ms)


def get_steady_state_samples(samples_path: Path) -> pl.DataFrame:
    """Return only samples within the steady-state window (after warmup)."""
    warmup_end_ms, test_end_ms = detect_warmup_window(samples_path)
    con = duckdb.connect()
    con.execute(f"CREATE VIEW samples AS SELECT * FROM read_parquet('{samples_path}')")
    return con.execute(
        f"SELECT * FROM samples "
        f"WHERE timestamp_ms >= {warmup_end_ms} AND timestamp_ms <= {test_end_ms}"
    ).pl()
