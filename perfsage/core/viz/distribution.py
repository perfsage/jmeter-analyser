"""Response time distribution charts: histogram, CDF, violin, box plot."""

import plotly.graph_objects as go
import polars as pl


def histogram(df: pl.DataFrame, label: str | None = None) -> go.Figure:
    """Render a response-time histogram, optionally filtered by label."""
    raise NotImplementedError


def cdf(df: pl.DataFrame) -> go.Figure:
    """Render a cumulative distribution function of response times."""
    raise NotImplementedError
