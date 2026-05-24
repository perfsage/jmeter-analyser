"""Time-series charts: response time over time, throughput over time, concurrent users."""

import plotly.graph_objects as go
import polars as pl


def response_time_over_time(df: pl.DataFrame) -> go.Figure:
    """Render response time (mean, p95, p99) over the test timeline."""
    raise NotImplementedError


def throughput_over_time(df: pl.DataFrame) -> go.Figure:
    """Render requests-per-second throughput over the test timeline."""
    raise NotImplementedError
