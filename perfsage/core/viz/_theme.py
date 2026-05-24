"""PerfSage brand theme helpers for Plotly figures."""

from __future__ import annotations

import plotly.graph_objects as go

NAVY = "#0B1F3A"
CREAM = "#F6F1E7"
AMBER = "#D4A857"
WHITE = "#FFFFFF"
ERROR_RED = "#E53E3E"
SUCCESS_GREEN = "#38A169"
WARN_YELLOW = "#ECC94B"


def apply_theme(fig: go.Figure, title: str = "") -> go.Figure:
    """Apply PerfSage brand theme to a Plotly figure."""
    fig.update_layout(
        plot_bgcolor=WHITE,
        paper_bgcolor=CREAM,
        font=dict(family="Inter, sans-serif", color=NAVY),
        title=dict(text=title, font=dict(color=NAVY, size=16)),
        xaxis=dict(gridcolor="#E2E8F0", linecolor=NAVY, tickcolor=NAVY),
        yaxis=dict(gridcolor="#E2E8F0", linecolor=NAVY, tickcolor=NAVY),
        legend=dict(bgcolor=CREAM, bordercolor=NAVY, borderwidth=1),
        margin=dict(l=60, r=20, t=50, b=50),
    )
    return fig
