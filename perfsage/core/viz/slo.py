"""SLO gauge and burn-rate charts."""

import plotly.graph_objects as go

from perfsage.core.analysis.slo import SLOResult


def slo_gauge(result: SLOResult) -> go.Figure:
    """Render a gauge chart for a single SLO result."""
    raise NotImplementedError


def burn_rate_chart(results: list[SLOResult]) -> go.Figure:
    """Render a grouped bar chart comparing actual vs. target SLO values."""
    raise NotImplementedError
