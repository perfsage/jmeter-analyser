"""Compute aggregate metrics (throughput, error rate, mean/p50/p95/p99)."""

import polars as pl


def compute_summary(df: pl.DataFrame) -> dict[str, float]:
    """Return a dict of top-level aggregate metrics for the entire test run."""
    raise NotImplementedError


def compute_per_label(df: pl.DataFrame) -> pl.DataFrame:
    """Return per-label aggregate metrics as a DataFrame."""
    raise NotImplementedError
