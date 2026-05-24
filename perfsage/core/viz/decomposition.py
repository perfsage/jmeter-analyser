"""Time-series decomposition: trend, seasonality, residual components."""

import plotly.graph_objects as go
import polars as pl


def decompose(df: pl.DataFrame) -> go.Figure:
    """Decompose the response-time series into trend + seasonal + residual."""
    raise NotImplementedError
