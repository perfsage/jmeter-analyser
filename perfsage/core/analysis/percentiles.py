"""Percentile calculations for response time distributions."""

import polars as pl


def percentiles(df: pl.DataFrame, quantiles: list[float] | None = None) -> dict[float, float]:
    """Compute response-time percentiles for the given quantiles (default p50/p90/p95/p99)."""
    raise NotImplementedError
