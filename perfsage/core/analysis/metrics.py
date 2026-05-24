"""Core time-series and summary metrics computed via DuckDB over samples parquet."""

from __future__ import annotations

from pathlib import Path

import duckdb
import polars as pl


def _bucket_expr(bucket_seconds: int) -> str:
    # Use // (integer division) to avoid BIGINT/INTEGER→DOUBLE promotion in DuckDB.
    return f"(timestamp_ms // 1000 // {bucket_seconds}) * {bucket_seconds}"


def _ts_bucket_col(bucket_seconds: int) -> str:
    return f"to_timestamp({_bucket_expr(bucket_seconds)}) AS timestamp_bucket"


def compute_throughput_series(
    samples_path: Path,
    bucket_seconds: int = 5,
) -> pl.DataFrame:
    """Group by time bucket, compute RPS per bucket.

    Returns rows with: timestamp_bucket (datetime), rps (float), label (str).
    Includes an 'ALL' aggregate row per bucket plus per-label rows.
    """
    con = duckdb.connect()
    con.execute(f"CREATE VIEW samples AS SELECT * FROM read_parquet('{samples_path}')")

    sql = f"""
        SELECT {_ts_bucket_col(bucket_seconds)},
               COUNT(*) * 1.0 / {bucket_seconds} AS rps,
               'ALL' AS label
        FROM samples
        GROUP BY {_bucket_expr(bucket_seconds)}
        UNION ALL
        SELECT {_ts_bucket_col(bucket_seconds)},
               COUNT(*) * 1.0 / {bucket_seconds} AS rps,
               label
        FROM samples
        GROUP BY {_bucket_expr(bucket_seconds)}, label
        ORDER BY timestamp_bucket, label
    """
    return con.execute(sql).pl()


def compute_error_series(
    samples_path: Path,
    bucket_seconds: int = 5,
) -> pl.DataFrame:
    """Return timestamp_bucket, error_count, total_count, error_rate, response_code."""
    con = duckdb.connect()
    con.execute(f"CREATE VIEW samples AS SELECT * FROM read_parquet('{samples_path}')")

    sql = f"""
        SELECT {_ts_bucket_col(bucket_seconds)},
               SUM(CASE WHEN NOT success THEN 1 ELSE 0 END)::BIGINT AS error_count,
               COUNT(*)::BIGINT AS total_count,
               SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS error_rate,
               MODE(CASE WHEN NOT success THEN response_code ELSE NULL END) AS response_code
        FROM samples
        GROUP BY {_bucket_expr(bucket_seconds)}
        ORDER BY timestamp_bucket
    """
    return con.execute(sql).pl()


def compute_rt_series(
    samples_path: Path,
    bucket_seconds: int = 5,
) -> pl.DataFrame:
    """Return per-bucket: timestamp_bucket, p50, p90, p95, p99, mean, min, max, label."""
    con = duckdb.connect()
    con.execute(f"CREATE VIEW samples AS SELECT * FROM read_parquet('{samples_path}')")

    sql = f"""
        SELECT {_ts_bucket_col(bucket_seconds)},
               PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY elapsed) AS p50,
               PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY elapsed) AS p90,
               PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY elapsed) AS p95,
               PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY elapsed) AS p99,
               AVG(elapsed) AS mean,
               MIN(elapsed)::BIGINT AS min,
               MAX(elapsed)::BIGINT AS max,
               label
        FROM samples
        GROUP BY {_bucket_expr(bucket_seconds)}, label
        ORDER BY timestamp_bucket, label
    """
    return con.execute(sql).pl()


def compute_thread_series(
    samples_path: Path,
    bucket_seconds: int = 5,
) -> pl.DataFrame:
    """Return timestamp_bucket, grp_threads max per bucket, all_threads max per bucket."""
    con = duckdb.connect()
    con.execute(f"CREATE VIEW samples AS SELECT * FROM read_parquet('{samples_path}')")

    sql = f"""
        SELECT {_ts_bucket_col(bucket_seconds)},
               MAX(grp_threads)::BIGINT AS grp_threads,
               MAX(all_threads)::BIGINT AS all_threads
        FROM samples
        GROUP BY {_bucket_expr(bucket_seconds)}
        ORDER BY timestamp_bucket
    """
    return con.execute(sql).pl()


def compute_bytes_series(
    samples_path: Path,
    bucket_seconds: int = 5,
) -> pl.DataFrame:
    """Return timestamp_bucket, total_bytes, total_sent_bytes, bytes_per_sec."""
    con = duckdb.connect()
    con.execute(f"CREATE VIEW samples AS SELECT * FROM read_parquet('{samples_path}')")

    sql = f"""
        SELECT {_ts_bucket_col(bucket_seconds)},
               SUM(bytes)::BIGINT AS total_bytes,
               SUM(sent_bytes)::BIGINT AS total_sent_bytes,
               SUM(bytes) * 1.0 / {bucket_seconds} AS bytes_per_sec
        FROM samples
        GROUP BY {_bucket_expr(bucket_seconds)}
        ORDER BY timestamp_bucket
    """
    return con.execute(sql).pl()


def compute_label_summary(samples_path: Path) -> pl.DataFrame:
    """Per-label summary: count, error_count, error_rate, mean_elapsed, p50…p99, mean_bytes…."""
    con = duckdb.connect()
    con.execute(f"CREATE VIEW samples AS SELECT * FROM read_parquet('{samples_path}')")

    sql = """
        SELECT label,
               COUNT(*)::BIGINT AS count,
               SUM(CASE WHEN NOT success THEN 1 ELSE 0 END)::BIGINT AS error_count,
               SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS error_rate,
               AVG(elapsed) AS mean_elapsed,
               PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY elapsed) AS p50,
               PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY elapsed) AS p90,
               PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY elapsed) AS p95,
               PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY elapsed) AS p99,
               MIN(elapsed)::BIGINT AS min_elapsed,
               MAX(elapsed)::BIGINT AS max_elapsed,
               AVG(bytes) AS mean_bytes,
               AVG(latency) AS mean_latency,
               AVG(connect) AS mean_connect
        FROM samples
        GROUP BY label
        ORDER BY label
    """
    return con.execute(sql).pl()


def compute_correlation_matrix(samples_path: Path) -> pl.DataFrame:
    """Pearson correlation between elapsed, bytes, latency, connect, grp_threads, all_threads.

    Returns a tidy DataFrame: col_a, col_b, correlation (for heatmap use).
    """
    cols = ["elapsed", "bytes", "latency", "connect", "grp_threads", "all_threads"]
    con = duckdb.connect()
    con.execute(f"CREATE VIEW samples AS SELECT * FROM read_parquet('{samples_path}')")

    rows: list[dict[str, object]] = []
    for i, col_a in enumerate(cols):
        for col_b in cols[i:]:
            result = con.execute(
                f"SELECT CORR(CAST({col_a} AS DOUBLE), CAST({col_b} AS DOUBLE)) FROM samples"
            ).fetchone()
            corr = float(result[0]) if result and result[0] is not None else 0.0
            rows.append({"col_a": col_a, "col_b": col_b, "correlation": corr})
            if col_a != col_b:
                rows.append({"col_a": col_b, "col_b": col_a, "correlation": corr})

    return pl.DataFrame(rows)
