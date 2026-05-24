"""Interactive summary tables rendered with Plotly."""

import plotly.graph_objects as go
import polars as pl


def summary_table(df: pl.DataFrame) -> go.Figure:
    """Render a Plotly Table from a per-label metrics DataFrame."""
    raise NotImplementedError
