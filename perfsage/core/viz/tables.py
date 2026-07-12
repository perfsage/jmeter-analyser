"""Plotly table-based figures: slowest transactions and variability chart."""

from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go
import polars as pl

from perfsage.core.viz._sample_cache import read_samples_cached
from perfsage.core.viz._theme import AMBER, CREAM, ERROR_RED, NAVY, WHITE, apply_theme

_URL_MAX_LEN = 60


def fig_slowest_transactions(samples_path: Path, top_n: int = 20) -> go.Figure:
    """Fig 18: Plotly Table — top N slowest individual transactions."""
    df = read_samples_cached(samples_path)
    if df.is_empty():
        return apply_theme(go.Figure(), "Slowest Transactions")

    top = df.sort("elapsed", descending=True).head(top_n)

    # Format timestamp
    ts_col = top["timestamp_ms"].cast(pl.Datetime("ms")).dt.strftime("%Y-%m-%d %H:%M:%S").to_list()

    url_col = [
        (str(u)[:_URL_MAX_LEN] + "…" if len(str(u)) > _URL_MAX_LEN else str(u))
        for u in top["url"].to_list()
    ]

    # Alternating row colors
    n_rows = len(top)
    row_colors = [CREAM if i % 2 == 0 else WHITE for i in range(n_rows)]

    fig = go.Figure(
        go.Table(
            header=dict(
                values=["Timestamp", "Label", "Elapsed (ms)", "Response Code", "URL"],
                fill_color=NAVY,
                font=dict(color=WHITE, family="Inter, sans-serif", size=13),
                align="left",
                height=36,
            ),
            cells=dict(
                values=[
                    ts_col,
                    top["label"].to_list(),
                    top["elapsed"].to_list(),
                    top["response_code"].to_list(),
                    url_col,
                ],
                fill_color=[row_colors] * 5,
                font=dict(color=NAVY, family="Inter, sans-serif", size=12),
                align="left",
                height=30,
            ),
        )
    )

    apply_theme(fig, f"Top {top_n} Slowest Transactions")
    return fig


def fig_variability_chart(samples_path: Path) -> go.Figure:
    """Fig 20: Coefficient of variation (std/mean) bar chart per label, sorted by CV."""
    df = read_samples_cached(samples_path)
    if df.is_empty():
        return apply_theme(go.Figure(), "Response Time Variability")

    cv_df = (
        df.group_by("label")
        .agg(
            [
                pl.col("elapsed").mean().alias("mean"),
                pl.col("elapsed").std().alias("std"),
            ]
        )
        .with_columns(
            pl.when(pl.col("mean") > 0)
            .then(pl.col("std") / pl.col("mean"))
            .otherwise(pl.lit(0.0))
            .alias("cv")
        )
        .sort("cv", descending=True)
    )

    labels = [str(lbl) for lbl in cv_df["label"].to_list()]
    cvs = cv_df["cv"].to_list()

    colors = [ERROR_RED if float(c) > 2.0 else (AMBER if float(c) > 1.0 else NAVY) for c in cvs]

    fig = go.Figure(
        go.Bar(
            x=labels,
            y=[float(c) for c in cvs],
            marker_color=colors,
            text=[f"{float(c):.2f}" for c in cvs],
            textposition="outside",
            name="CV",
        )
    )

    # Reference lines
    for threshold, color, label in [
        (1.0, AMBER, "CV=1.0 (High)"),
        (2.0, ERROR_RED, "CV=2.0 (Very High)"),
    ]:
        fig.add_hline(
            y=threshold,
            line_dash="dash",
            line_color=color,
            annotation_text=label,
            annotation_position="right",
        )

    apply_theme(fig, "Response Time Variability (Coefficient of Variation)")
    fig.update_layout(xaxis_title="Label", yaxis_title="CV (std / mean)")
    return fig
