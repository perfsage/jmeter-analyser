"""Response-time distribution charts: histogram, CDF, box plots, heatmap."""

from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go
import polars as pl

from perfsage.core.viz._theme import AMBER, ERROR_RED, NAVY, WARN_YELLOW, apply_theme

# Log-scale RT bucket edges (ms) and their display labels
_RT_BIN_EDGES = [0, 100, 250, 500, 1000, 2000, 5000]
_RT_BIN_LABELS = ["0-100", "100-250", "250-500", "500-1k", "1k-2k", "2k-5k", "5k+"]


def _assign_rt_bucket(elapsed: pl.Expr) -> pl.Expr:
    """Map elapsed (ms) to a log-scale bucket label."""
    return (
        pl.when(elapsed < 100)
        .then(pl.lit("0-100"))
        .when(elapsed < 250)
        .then(pl.lit("100-250"))
        .when(elapsed < 500)
        .then(pl.lit("250-500"))
        .when(elapsed < 1000)
        .then(pl.lit("500-1k"))
        .when(elapsed < 2000)
        .then(pl.lit("1k-2k"))
        .when(elapsed < 5000)
        .then(pl.lit("2k-5k"))
        .otherwise(pl.lit("5k+"))
    )


def fig_latency_histogram(samples_path: Path, label: str | None = None) -> go.Figure:
    """Fig 6: Histogram of elapsed times with p50/p90/p99 vertical lines."""
    df = pl.read_parquet(samples_path)
    if df.is_empty():
        return apply_theme(go.Figure(), "Latency Histogram")

    if label is not None:
        df = df.filter(pl.col("label") == label)
    if df.is_empty():
        return apply_theme(go.Figure(), f"Latency Histogram — {label} (no data)")

    elapsed = df["elapsed"].to_list()
    p50 = float(df["elapsed"].quantile(0.50, interpolation="linear") or 0.0)
    p90 = float(df["elapsed"].quantile(0.90, interpolation="linear") or 0.0)
    p99 = float(df["elapsed"].quantile(0.99, interpolation="linear") or 0.0)

    title = f"Latency Histogram{f' — {label}' if label else ''}"
    fig = go.Figure(
        go.Histogram(
            x=elapsed,
            nbinsx=50,
            marker_color=NAVY,
            opacity=0.8,
            name="Requests",
        )
    )

    for val, name, color in [
        (p50, "p50", NAVY),
        (p90, "p90", AMBER),
        (p99, "p99", ERROR_RED),
    ]:
        fig.add_vline(
            x=val,
            line_dash="dash",
            line_color=color,
            annotation_text=f"{name}: {val:.0f}ms",
            annotation_position="top right",
        )

    apply_theme(fig, title)
    fig.update_layout(xaxis_title="Response Time (ms)", yaxis_title="Count")
    return fig


def fig_latency_cdf(samples_path: Path) -> go.Figure:
    """Fig 7: Cumulative distribution function with p90/p95/p99 reference lines."""
    df = pl.read_parquet(samples_path)
    if df.is_empty():
        return apply_theme(go.Figure(), "Latency CDF")

    sorted_elapsed = df["elapsed"].sort().to_list()
    n = len(sorted_elapsed)
    cdf_pct = [(i + 1) / n * 100 for i in range(n)]

    p90 = float(df["elapsed"].quantile(0.90, interpolation="linear") or 0.0)
    p95 = float(df["elapsed"].quantile(0.95, interpolation="linear") or 0.0)
    p99 = float(df["elapsed"].quantile(0.99, interpolation="linear") or 0.0)

    fig = go.Figure(
        go.Scatter(
            x=sorted_elapsed,
            y=cdf_pct,
            mode="lines",
            line=dict(color=NAVY, width=2),
            name="CDF",
        )
    )

    for val, pct, name, color in [
        (p90, 90, "p90", AMBER),
        (p95, 95, "p95", WARN_YELLOW),
        (p99, 99, "p99", ERROR_RED),
    ]:
        fig.add_hline(
            y=pct,
            line_dash="dash",
            line_color=color,
            annotation_text=f"{name}: {val:.0f}ms",
            annotation_position="bottom right",
        )

    apply_theme(fig, "Latency CDF")
    fig.update_layout(xaxis_title="Response Time (ms)", yaxis_title="% of Requests ≤ x")
    return fig


def fig_boxplots_per_label(samples_path: Path) -> go.Figure:
    """Fig 8: Box plots per transaction label, sorted by median descending."""
    df = pl.read_parquet(samples_path)
    if df.is_empty():
        return apply_theme(go.Figure(), "Response Time Distribution by Label")

    medians = (
        df.group_by("label")
        .agg(pl.col("elapsed").median().alias("median"))
        .sort("median", descending=True)
    )
    labels_sorted = medians["label"].to_list()

    fig = go.Figure()
    for lbl in labels_sorted:
        subset = df.filter(pl.col("label") == lbl)["elapsed"].to_list()
        fig.add_trace(
            go.Box(
                y=subset,
                name=str(lbl),
                marker_color=NAVY,
                line_color=NAVY,
                boxmean=True,
            )
        )

    apply_theme(fig, "Response Time Distribution by Label")
    fig.update_layout(yaxis_title="Response Time (ms)", showlegend=False)
    return fig


def fig_rt_heatmap(samples_path: Path, bucket_seconds: int = 30) -> go.Figure:
    """Fig 9: 2-D heatmap — X: time bucket, Y: log-scale RT bucket, Color: request density."""
    df = pl.read_parquet(samples_path)
    if df.is_empty():
        return apply_theme(go.Figure(), "Response Time Heatmap")

    bucket_ms = bucket_seconds * 1000
    df2 = df.with_columns(
        [
            (pl.col("timestamp_ms") // bucket_ms * bucket_ms)
            .cast(pl.Datetime("ms"))
            .alias("time_bucket"),
            _assign_rt_bucket(pl.col("elapsed")).alias("rt_bucket"),
        ]
    )

    counts = (
        df2.group_by(["time_bucket", "rt_bucket"])
        .agg(pl.len().alias("count"))
        .sort(["time_bucket", "rt_bucket"])
    )

    # Build matrix
    times_sorted = counts["time_bucket"].unique().sort().to_list()
    # Preserve log-scale order for y-axis
    rt_labels_present = [lb for lb in _RT_BIN_LABELS if lb in counts["rt_bucket"].to_list()]
    if not rt_labels_present:
        rt_labels_present = _RT_BIN_LABELS

    z: list[list[int]] = []
    for rt_lbl in rt_labels_present:
        row: list[int] = []
        for t in times_sorted:
            sub = counts.filter(
                (pl.col("time_bucket") == t) & (pl.col("rt_bucket") == rt_lbl)
            )
            row.append(int(sub["count"].sum()))
        z.append(row)

    x_strs = [str(t) for t in times_sorted]
    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=x_strs,
            y=rt_labels_present,
            colorscale="YlOrRd",
            colorbar=dict(title="Requests"),
        )
    )

    apply_theme(fig, "Response Time Density Heatmap")
    fig.update_layout(xaxis_title="Time", yaxis_title="Response Time Bucket")
    return fig
