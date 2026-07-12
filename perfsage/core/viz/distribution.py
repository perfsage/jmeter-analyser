"""Response-time distribution charts: histogram, CDF, box plots, heatmap."""

from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go
import polars as pl

from perfsage.core.viz._sample_cache import read_samples_cached
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
    """Fig 6: Histogram of elapsed times with p50/p90/p99 vertical lines.

    Pre-bins server-side (50 buckets) instead of shipping raw per-sample
    arrays to Plotly — same visual output, O(bins) payload instead of O(n).
    """
    df = read_samples_cached(samples_path)
    if df.is_empty():
        return apply_theme(go.Figure(), "Latency Histogram")

    if label is not None:
        df = df.filter(pl.col("label") == label)
    if df.is_empty():
        return apply_theme(go.Figure(), f"Latency Histogram — {label} (no data)")

    elapsed = df["elapsed"]
    p50 = float(elapsed.quantile(0.50, interpolation="linear") or 0.0)
    p90 = float(elapsed.quantile(0.90, interpolation="linear") or 0.0)
    p99 = float(elapsed.quantile(0.99, interpolation="linear") or 0.0)

    lo, hi = float(elapsed.min()), float(elapsed.max())
    n_bins = 50
    if hi <= lo:
        bin_edges = [lo, lo + 1.0]
        n_bins = 1
    else:
        width = (hi - lo) / n_bins
        bin_edges = [lo + i * width for i in range(n_bins + 1)]

    binned = df.with_columns(
        ((pl.col("elapsed") - lo) / (bin_edges[1] - bin_edges[0]))
        .floor()
        .clip(0, n_bins - 1)
        .cast(pl.Int64)
        .alias("_bin")
    )
    counts_df = binned.group_by("_bin").agg(pl.len().alias("count")).sort("_bin")
    counts_by_bin = dict(zip(counts_df["_bin"].to_list(), counts_df["count"].to_list(), strict=True))
    bin_centers = [(bin_edges[i] + bin_edges[i + 1]) / 2 for i in range(n_bins)]
    bin_counts = [counts_by_bin.get(i, 0) for i in range(n_bins)]
    bar_width = bin_edges[1] - bin_edges[0] if n_bins > 1 else 1.0

    title = f"Latency Histogram{f' — {label}' if label else ''}"
    fig = go.Figure(
        go.Bar(
            x=bin_centers,
            y=bin_counts,
            width=bar_width * 0.95,
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
    fig.update_layout(xaxis_title="Response Time (ms)", yaxis_title="Count", bargap=0.02)
    return fig


def fig_latency_cdf(samples_path: Path) -> go.Figure:
    """Fig 7: Cumulative distribution function with p90/p95/p99 reference lines."""
    df = read_samples_cached(samples_path)
    if df.is_empty():
        return apply_theme(go.Figure(), "Latency CDF")

    sorted_elapsed = df["elapsed"].sort().to_list()
    step = max(1, len(sorted_elapsed) // 2000)
    sorted_elapsed = sorted_elapsed[::step]
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
    """Fig 8: Box plots per transaction label, sorted by median descending.

    Computes quartile/whisker/outlier statistics server-side and passes them
    directly to go.Box — same rendered shape as a raw-array box plot, without
    shipping every raw sample to the browser.
    """
    df = read_samples_cached(samples_path)
    if df.is_empty():
        return apply_theme(go.Figure(), "Response Time Distribution by Label")

    stats = (
        df.group_by("label")
        .agg(
            [
                pl.col("elapsed").median().alias("median"),
                pl.col("elapsed").quantile(0.25, interpolation="linear").alias("q1"),
                pl.col("elapsed").quantile(0.75, interpolation="linear").alias("q3"),
                pl.col("elapsed").min().alias("min_val"),
                pl.col("elapsed").max().alias("max_val"),
                pl.col("elapsed").mean().alias("mean"),
            ]
        )
        .sort("median", descending=True)
    )

    fig = go.Figure()
    for row in stats.to_dicts():
        q1, q3 = float(row["q1"]), float(row["q3"])
        iqr = q3 - q1
        lower_fence = max(float(row["min_val"]), q1 - 1.5 * iqr)
        upper_fence = min(float(row["max_val"]), q3 + 1.5 * iqr)
        fig.add_trace(
            go.Box(
                name=str(row["label"]),
                q1=[q1],
                median=[float(row["median"])],
                q3=[q3],
                lowerfence=[lower_fence],
                upperfence=[upper_fence],
                mean=[float(row["mean"])],
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
    df = read_samples_cached(samples_path)
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
            sub = counts.filter((pl.col("time_bucket") == t) & (pl.col("rt_bucket") == rt_lbl))
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
