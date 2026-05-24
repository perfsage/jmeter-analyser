"""Scatter plots: response time vs. concurrent users, latency vs. throughput."""

import plotly.graph_objects as go
import polars as pl


def response_vs_concurrency(df: pl.DataFrame) -> go.Figure:
    """Scatter plot of response time against active thread count."""
    raise NotImplementedError
