"""Latency decomposition and per-label small-multiples charts."""

from __future__ import annotations

import math
from pathlib import Path

import plotly.graph_objects as go
import polars as pl
from plotly.subplots import make_subplots

from perfsage.core.analysis.metrics import compute_rt_series
from perfsage.core.viz._sample_cache import read_samples_cached
from perfsage.core.viz._theme import AMBER, CREAM, NAVY, SUCCESS_GREEN, apply_theme
from perfsage.core.viz._utils import time_bucket as _time_bucket

_MAX_LABELS = 12


def fig_latency_components(samples_path: Path, bucket_seconds: int = 10) -> go.Figure:
    """Fig 14: Stacked area — connect, latency (TTFB), and transfer time per bucket."""
    df = read_samples_cached(samples_path)
    if df.is_empty():
        return apply_theme(go.Figure(), "Latency Components Over Time")

    # transfer_time = elapsed - latency - connect - idle_time  (clamp to 0)
    df = df.with_columns(
        pl.max_horizontal(
            pl.col("elapsed") - pl.col("latency") - pl.col("connect") - pl.col("idle_time"),
            pl.lit(0).cast(pl.Int64),
        ).alias("transfer_time")
    )

    agg = (
        _time_bucket(df, bucket_seconds)
        .group_by("time_bucket")
        .agg(
            [
                pl.col("connect").mean().alias("connect_mean"),
                pl.col("latency").mean().alias("latency_mean"),
                pl.col("transfer_time").mean().alias("transfer_mean"),
            ]
        )
        .sort("time_bucket")
    )

    times = agg["time_bucket"].to_list()

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=times,
            y=agg["connect_mean"].to_list(),
            mode="lines",
            stackgroup="one",
            fillcolor="rgba(212,168,87,0.5)",
            line=dict(color=AMBER, width=1),
            name="Connect Time",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=times,
            y=agg["latency_mean"].to_list(),
            mode="lines",
            stackgroup="one",
            fillcolor="rgba(56,161,105,0.5)",
            line=dict(color=SUCCESS_GREEN, width=1),
            name="Time to First Byte",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=times,
            y=agg["transfer_mean"].to_list(),
            mode="lines",
            stackgroup="one",
            fillcolor="rgba(11,31,58,0.4)",
            line=dict(color=NAVY, width=1),
            name="Transfer Time",
        )
    )

    apply_theme(fig, "Latency Components Over Time")
    fig.update_layout(xaxis_title="Time", yaxis_title="Response Time (ms)")
    return fig


def fig_per_label_small_multiples(samples_path: Path) -> go.Figure:
    """Fig 15: Small-multiples grid — one subplot per label, p90 RT over time."""
    rt_df = compute_rt_series(samples_path, bucket_seconds=10)
    if rt_df.is_empty():
        return apply_theme(go.Figure(), "Response Time by Label")

    # Top 12 labels by total request volume
    df_raw = read_samples_cached(samples_path)
    top_labels_df = (
        df_raw.group_by("label")
        .agg(pl.len().alias("count"))
        .sort("count", descending=True)
        .head(_MAX_LABELS)
    )
    top_labels = top_labels_df["label"].to_list()

    rt_df = rt_df.filter(pl.col("label").is_in(top_labels))
    if rt_df.is_empty():
        return apply_theme(go.Figure(), "Response Time by Label")

    n_labels = len(top_labels)
    ncols = min(3, n_labels)
    nrows = math.ceil(n_labels / ncols)

    fig = make_subplots(
        rows=nrows,
        cols=ncols,
        subplot_titles=[str(lbl) for lbl in top_labels],
        shared_xaxes=False,
        vertical_spacing=0.08,
        horizontal_spacing=0.06,
    )

    for idx, lbl in enumerate(top_labels):
        row = idx // ncols + 1
        col = idx % ncols + 1
        lbl_df = rt_df.filter(pl.col("label") == lbl).sort("timestamp_bucket")
        fig.add_trace(
            go.Scatter(
                x=lbl_df["timestamp_bucket"].to_list(),
                y=lbl_df["p90"].to_list(),
                mode="lines",
                line=dict(color=NAVY, width=1.5),
                name=str(lbl),
                showlegend=False,
            ),
            row=row,
            col=col,
        )

    fig.update_layout(
        plot_bgcolor="white",
        paper_bgcolor=CREAM,
        font=dict(family="Inter, sans-serif", color=NAVY),
        title=dict(text="p90 Response Time by Label", font=dict(color=NAVY, size=16)),
        height=300 * nrows,
        margin=dict(l=60, r=20, t=60, b=50),
    )
    return fig
