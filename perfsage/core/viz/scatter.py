"""Scatter and relationship charts: RT vs throughput, concurrency, status, correlation."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import polars as pl

from perfsage.core.analysis.anomalies import detect_knee_point
from perfsage.core.analysis.metrics import compute_correlation_matrix
from perfsage.core.viz._theme import AMBER, ERROR_RED, LABEL_COLORS, NAVY, apply_theme
from perfsage.core.viz._utils import time_bucket as _time_bucket

_SAMPLE_LIMIT = 50_000


def fig_rt_vs_throughput(samples_path: Path, bucket_seconds: int = 10) -> go.Figure:
    """Fig 10: p90 RT vs RPS scatter, color by test progress, knee point marked."""
    df = pl.read_parquet(samples_path)
    if df.is_empty():
        return apply_theme(go.Figure(), "RT vs Throughput")

    agg = (
        _time_bucket(df, bucket_seconds)
        .group_by("time_bucket")
        .agg(
            [
                pl.col("elapsed").quantile(0.90, interpolation="linear").alias("p90"),
                (pl.len().cast(pl.Float64) / bucket_seconds).alias("rps"),
            ]
        )
        .sort("time_bucket")
    )

    n = len(agg)
    color_vals = list(range(n))  # gradient from early (0) to late (n-1)

    fig = go.Figure(
        go.Scatter(
            x=agg["rps"].to_list(),
            y=agg["p90"].to_list(),
            mode="markers",
            marker=dict(
                color=color_vals,
                colorscale="Blues",
                showscale=True,
                colorbar=dict(title="Bucket Index (Early→Late)"),
                size=8,
            ),
            name="Buckets",
        )
    )

    # Trendline via numpy polyfit
    rps_arr = agg["rps"].to_numpy()
    p90_arr = agg["p90"].to_numpy()
    if len(rps_arr) >= 2 and rps_arr.max() != rps_arr.min():
        coeffs = np.polyfit(rps_arr, p90_arr, 1)
        x_line = np.linspace(float(rps_arr.min()), float(rps_arr.max()), 100)
        y_line = np.polyval(coeffs, x_line)
        fig.add_trace(
            go.Scatter(
                x=x_line.tolist(),
                y=y_line.tolist(),
                mode="lines",
                line=dict(color=AMBER, width=1.5, dash="dash"),
                name="Trend",
            )
        )

    # Knee point
    knee = detect_knee_point(samples_path)
    if knee is not None:
        fig.add_vline(
            x=knee["knee_rps"],
            line_dash="dot",
            line_color=ERROR_RED,
            annotation_text=f"Knee: {knee['knee_rps']:.1f} RPS",
        )
        fig.add_hline(
            y=knee["knee_p90_ms"],
            line_dash="dot",
            line_color=ERROR_RED,
            annotation_text=f"Knee p90: {knee['knee_p90_ms']:.0f}ms",
        )

    apply_theme(fig, "RT vs Throughput")
    fig.update_layout(xaxis_title="Requests/sec", yaxis_title="p90 Response Time (ms)")
    return fig


def fig_rt_vs_concurrency(samples_path: Path, bucket_seconds: int = 10) -> go.Figure:
    """Fig 11: p90 RT vs active thread count scatter, colored by test progress."""
    df = pl.read_parquet(samples_path)
    if df.is_empty():
        return apply_theme(go.Figure(), "RT vs Concurrency")

    agg = (
        _time_bucket(df, bucket_seconds)
        .group_by("time_bucket")
        .agg(
            [
                pl.col("elapsed").quantile(0.90, interpolation="linear").alias("p90"),
                pl.col("all_threads").max().alias("threads"),
            ]
        )
        .sort("time_bucket")
    )

    n = len(agg)
    color_vals = list(range(n))

    fig = go.Figure(
        go.Scatter(
            x=agg["threads"].to_list(),
            y=agg["p90"].to_list(),
            mode="markers",
            marker=dict(
                color=color_vals,
                colorscale="Oranges",
                showscale=True,
                colorbar=dict(title="Bucket Index (Early→Late)"),
                size=8,
            ),
            name="Buckets",
        )
    )

    apply_theme(fig, "RT vs Concurrency")
    fig.update_layout(xaxis_title="Active Threads", yaxis_title="p90 Response Time (ms)")
    return fig


def fig_rt_vs_time_by_status(samples_path: Path) -> go.Figure:
    """Fig 12: Raw scatter of elapsed vs timestamp, colored by response status."""
    df = pl.read_parquet(samples_path)
    if df.is_empty():
        return apply_theme(go.Figure(), "Response Time by Status")

    total_rows = len(df)
    sampled_note = ""
    if total_rows > _SAMPLE_LIMIT:
        df = df.sample(n=_SAMPLE_LIMIT, seed=42)
        sampled_note = f" (sampled {_SAMPLE_LIMIT:,} of {total_rows:,} rows)"

    # Assign color category
    df = df.with_columns(
        pl.when(pl.col("success"))
        .then(pl.lit("Success"))
        .when(pl.col("response_code").str.starts_with("4"))
        .then(pl.lit("Client Error"))
        .otherwise(pl.lit("Server Error"))
        .alias("status_group")
    )

    ts_ms = (pl.col("timestamp_ms").cast(pl.Datetime("ms"))).alias("ts")
    df = df.with_columns([ts_ms])

    color_map = {"Success": NAVY, "Client Error": AMBER, "Server Error": ERROR_RED}

    fig = go.Figure()
    for group, color in color_map.items():
        subset = df.filter(pl.col("status_group") == group)
        if subset.is_empty():
            continue
        fig.add_trace(
            go.Scatter(
                x=subset["ts"].to_list(),
                y=subset["elapsed"].to_list(),
                mode="markers",
                marker=dict(color=color, size=4, opacity=0.3),
                name=group,
            )
        )

    title = f"Response Time by Status{sampled_note}"
    apply_theme(fig, title)
    fig.update_layout(xaxis_title="Time", yaxis_title="Response Time (ms)")
    return fig


def fig_rt_scatter_by_label(samples_path: Path, sample_limit: int = 5000) -> go.Figure:
    """Scatter of elapsed vs time, one trace per label with proportional stratified sampling."""
    title = "Response Time Scatter by Transaction"
    df = pl.read_parquet(samples_path)
    if df.is_empty():
        return apply_theme(go.Figure(), title)

    total_rows = len(df)
    sampled_note = ""
    if total_rows > sample_limit:
        parts: list[pl.DataFrame] = []
        for lbl in df["label"].unique().sort().to_list():
            subset = df.filter(pl.col("label") == lbl)
            share = subset.height / total_rows
            target = max(1, int(round(sample_limit * share)))
            take = min(target, subset.height)
            parts.append(subset.sample(n=take, seed=42))
        df = pl.concat(parts)
        if df.height > sample_limit:
            df = df.sample(n=sample_limit, seed=43)
        sampled_note = f" — sampled {df.height:,} of {total_rows:,}"

    df = df.with_columns((pl.col("timestamp_ms").cast(pl.Datetime("ms"))).alias("ts"))

    fig = go.Figure()
    for idx, lbl in enumerate(df["label"].unique().sort().to_list()):
        sub = df.filter(pl.col("label") == lbl)
        color = LABEL_COLORS[idx % len(LABEL_COLORS)]
        fig.add_trace(
            go.Scatter(
                x=sub["ts"].to_list(),
                y=sub["elapsed"].to_list(),
                mode="markers",
                marker=dict(color=color, size=5, opacity=0.45),
                name=str(lbl),
            )
        )

    apply_theme(fig, f"{title}{sampled_note}")
    fig.update_layout(xaxis_title="Time", yaxis_title="Response time (ms)")
    return fig


def fig_correlation_matrix(samples_path: Path) -> go.Figure:
    """Fig 13: Pearson correlation heatmap for key metrics."""
    corr_df = compute_correlation_matrix(samples_path)
    if corr_df.is_empty():
        return apply_theme(go.Figure(), "Correlation Matrix")

    cols = ["elapsed", "bytes", "latency", "connect", "grp_threads", "all_threads"]

    # Build square matrix
    matrix = [[0.0] * len(cols) for _ in range(len(cols))]
    lookup: dict[tuple[str, str], float] = {
        (str(row["col_a"]), str(row["col_b"])): float(str(row["correlation"]))
        for row in corr_df.to_dicts()
    }
    for i, ca in enumerate(cols):
        for j, cb in enumerate(cols):
            matrix[i][j] = lookup.get((ca, cb), 0.0)

    annotations: list[dict[str, object]] = [
        {
            "x": cb,
            "y": ca,
            "text": f"{matrix[i][j]:.2f}",
            "showarrow": False,
            "font": {"color": "white" if abs(matrix[i][j]) > 0.5 else NAVY},
        }
        for i, ca in enumerate(cols)
        for j, cb in enumerate(cols)
    ]

    fig = go.Figure(
        go.Heatmap(
            z=matrix,
            x=cols,
            y=cols,
            colorscale="RdBu",
            zmid=0,
            zmin=-1,
            zmax=1,
            colorbar=dict(title="Pearson r"),
        )
    )
    fig.update_layout(annotations=annotations)

    apply_theme(fig, "Correlation Matrix")
    return fig
