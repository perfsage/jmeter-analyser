"""Shared utilities for viz module."""

from __future__ import annotations

import polars as pl


def time_bucket_expr(bucket_seconds: int) -> str:
    """
    DuckDB SQL expression for integer time bucketing.
    Uses integer division to avoid BIGINT/INTEGER→DOUBLE promotion.
    """
    return f"(timestamp_ms // 1000 // {bucket_seconds}) * {bucket_seconds}"


def time_bucket(df: pl.DataFrame, bucket_seconds: int) -> pl.DataFrame:
    """Add a ``time_bucket`` column (Datetime ms) to *df* using integer division."""
    bucket_ms = bucket_seconds * 1000
    return df.with_columns(
        (pl.col("timestamp_ms") // bucket_ms * bucket_ms)
        .cast(pl.Datetime("ms"))
        .alias("time_bucket")
    )
