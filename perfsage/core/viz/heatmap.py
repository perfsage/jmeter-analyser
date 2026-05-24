"""Heatmaps: error rate by label × time, response time by hour × day."""

import plotly.graph_objects as go
import polars as pl


def error_rate_heatmap(df: pl.DataFrame) -> go.Figure:
    """Heatmap of error rate segmented by label and time bucket."""
    raise NotImplementedError
