"""Time-series charts: response time, throughput, errors, threads, bytes over time."""

from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go
import polars as pl

from perfsage.core.analysis.metrics import (
    compute_bytes_series,
    compute_throughput_series,
)
from perfsage.core.viz._theme import (
    AMBER,
    ERROR_RED,
    NAVY,
    WARN_YELLOW,
    apply_theme,
)
from perfsage.core.viz._utils import time_bucket as _time_bucket


def fig_rt_over_time(samples_path: Path, bucket_seconds: int = 5) -> go.Figure:
    """Fig 1: Response time over time with p50/p90/p95/p99 lines and anomaly markers."""
    df = pl.read_parquet(samples_path)
    if df.is_empty():
        return apply_theme(go.Figure(), "Response Time Over Time")

    agg = (
        _time_bucket(df, bucket_seconds)
        .group_by("time_bucket")
        .agg(
            [
                pl.col("elapsed").quantile(0.50, interpolation="linear").alias("p50"),
                pl.col("elapsed").quantile(0.90, interpolation="linear").alias("p90"),
                pl.col("elapsed").quantile(0.95, interpolation="linear").alias("p95"),
                pl.col("elapsed").quantile(0.99, interpolation="linear").alias("p99"),
            ]
        )
        .sort("time_bucket")
    )

    _p95_mean = agg["p95"].mean()
    _p95_std = agg["p95"].std()
    p95_mean: float = float(_p95_mean) if _p95_mean is not None else 0.0  # type: ignore[arg-type]
    p95_std: float = float(_p95_std) if _p95_std is not None else 0.0  # type: ignore[arg-type]
    if p95_std > 0:
        z = ((agg["p95"] - p95_mean) / p95_std).abs()
        anomaly_mask = (z > 3.0).to_list()
    else:
        anomaly_mask = [False] * len(agg)

    times = agg["time_bucket"].to_list()
    p50 = agg["p50"].to_list()
    p90 = agg["p90"].to_list()
    p95 = agg["p95"].to_list()
    p99 = agg["p99"].to_list()

    fig = go.Figure()

    # Upper bound for shaded region (p99) — shown first so fill='tonexty' works
    fig.add_trace(
        go.Scatter(
            x=times,
            y=p99,
            mode="lines",
            line=dict(color=AMBER, width=1.5, dash="dot"),
            name="p99",
        )
    )
    # Lower bound with fill to create shaded band between p50 and p99
    fig.add_trace(
        go.Scatter(
            x=times,
            y=p50,
            mode="lines",
            fill="tonexty",
            fillcolor="rgba(11,31,58,0.08)",
            line=dict(color=NAVY, width=2),
            name="p50",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=times,
            y=p90,
            mode="lines",
            line=dict(color=AMBER, width=2),
            name="p90",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=times,
            y=p95,
            mode="lines",
            line=dict(color=WARN_YELLOW, width=1.5),
            name="p95",
        )
    )

    # Anomaly markers
    a_times = [t for t, a in zip(times, anomaly_mask, strict=True) if a]
    a_vals = [v for v, a in zip(p95, anomaly_mask, strict=True) if a]
    if a_times:
        fig.add_trace(
            go.Scatter(
                x=a_times,
                y=a_vals,
                mode="markers",
                marker=dict(color=ERROR_RED, size=10, symbol="x"),
                name="Anomaly",
            )
        )

    apply_theme(fig, "Response Time Over Time")
    fig.update_layout(xaxis_title="Time", yaxis_title="Response Time (ms)")
    return fig


def fig_throughput_over_time(samples_path: Path, bucket_seconds: int = 5) -> go.Figure:
    """Fig 2: RPS over time as a navy filled area chart."""
    df = compute_throughput_series(samples_path, bucket_seconds)
    if df.is_empty():
        return apply_theme(go.Figure(), "Throughput Over Time")

    all_df = df.filter(pl.col("label") == "ALL").sort("timestamp_bucket")
    if all_df.is_empty():
        return apply_theme(go.Figure(), "Throughput Over Time")

    times = all_df["timestamp_bucket"].to_list()
    rps = all_df["rps"].to_list()

    fig = go.Figure(
        go.Scatter(
            x=times,
            y=rps,
            mode="lines",
            fill="tozeroy",
            fillcolor="rgba(11,31,58,0.15)",
            line=dict(color=NAVY, width=2),
            name="RPS",
        )
    )
    apply_theme(fig, "Throughput Over Time")
    fig.update_layout(xaxis_title="Time", yaxis_title="Requests / sec")
    return fig


def fig_errors_over_time(samples_path: Path, bucket_seconds: int = 5) -> go.Figure:
    """Fig 3: Error count stacked by response_code + error rate % line."""
    df = pl.read_parquet(samples_path)
    if df.is_empty():
        return apply_theme(go.Figure(), "Errors Over Time")

    bucketed = _time_bucket(df, bucket_seconds)

    # Per-bucket overall counts for error_rate line
    total_agg = (
        bucketed.group_by("time_bucket")
        .agg(
            [
                pl.len().alias("total"),
                (~pl.col("success")).sum().alias("error_count"),
            ]
        )
        .sort("time_bucket")
        .with_columns(
            (pl.col("error_count").cast(pl.Float64) / pl.col("total") * 100).alias(
                "error_rate_pct"
            )
        )
    )

    # Per-bucket, per response_code error counts (errors only)
    error_df = bucketed.filter(~pl.col("success"))
    fig = go.Figure()

    if not error_df.is_empty():
        error_agg = (
            error_df.group_by(["time_bucket", "response_code"])
            .agg(pl.len().alias("count"))
            .sort(["time_bucket", "response_code"])
        )
        response_codes = error_agg["response_code"].unique().sort().to_list()
        bar_colors = [ERROR_RED, AMBER, WARN_YELLOW, NAVY]

        for idx, rc in enumerate(response_codes):
            rc_df = error_agg.filter(pl.col("response_code") == rc).sort("time_bucket")
            fig.add_trace(
                go.Bar(
                    x=rc_df["time_bucket"].to_list(),
                    y=rc_df["count"].to_list(),
                    name=f"HTTP {rc}",
                    marker_color=bar_colors[idx % len(bar_colors)],
                )
            )

    # Error rate % line on secondary y-axis
    fig.add_trace(
        go.Scatter(
            x=total_agg["time_bucket"].to_list(),
            y=total_agg["error_rate_pct"].to_list(),
            mode="lines",
            line=dict(color=ERROR_RED, width=2, dash="dash"),
            name="Error Rate %",
            yaxis="y2",
        )
    )

    apply_theme(fig, "Errors Over Time")
    fig.update_layout(
        barmode="stack",
        xaxis_title="Time",
        yaxis_title="Error Count",
        yaxis2=dict(
            title="Error Rate (%)",
            overlaying="y",
            side="right",
            gridcolor="#E2E8F0",
            linecolor=NAVY,
            tickcolor=NAVY,
        ),
    )
    return fig


def fig_threads_vs_rt(samples_path: Path, bucket_seconds: int = 5) -> go.Figure:
    """Fig 4: Active threads (primary y) vs p90 RT (secondary y) — dual axis."""
    df = pl.read_parquet(samples_path)
    if df.is_empty():
        return apply_theme(go.Figure(), "Threads vs Response Time")

    agg = (
        _time_bucket(df, bucket_seconds)
        .group_by("time_bucket")
        .agg(
            [
                pl.col("all_threads").max().alias("all_threads"),
                pl.col("elapsed").quantile(0.90, interpolation="linear").alias("p90"),
            ]
        )
        .sort("time_bucket")
    )

    times = agg["time_bucket"].to_list()

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=times,
            y=agg["all_threads"].to_list(),
            mode="lines",
            fill="tozeroy",
            fillcolor="rgba(11,31,58,0.12)",
            line=dict(color=NAVY, width=2),
            name="Active Threads",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=times,
            y=agg["p90"].to_list(),
            mode="lines",
            line=dict(color=AMBER, width=2),
            name="p90 RT (ms)",
            yaxis="y2",
        )
    )

    apply_theme(fig, "Active Threads vs Response Time")
    fig.update_layout(
        xaxis_title="Time",
        yaxis_title="Active Threads",
        yaxis2=dict(
            title="p90 Response Time (ms)",
            overlaying="y",
            side="right",
            gridcolor="#E2E8F0",
            linecolor=NAVY,
            tickcolor=NAVY,
        ),
    )
    return fig


def fig_bytes_over_time(samples_path: Path, bucket_seconds: int = 5) -> go.Figure:
    """Fig 5: Bytes received + sent over time — stacked area."""
    df_bytes = compute_bytes_series(samples_path, bucket_seconds)
    if df_bytes.is_empty():
        return apply_theme(go.Figure(), "Bytes Over Time")

    df_bytes = df_bytes.sort("timestamp_bucket")
    times = df_bytes["timestamp_bucket"].to_list()

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=times,
            y=df_bytes["total_sent_bytes"].to_list(),
            mode="lines",
            fill="tozeroy",
            fillcolor="rgba(212,168,87,0.3)",
            line=dict(color=AMBER, width=1.5),
            name="Sent Bytes",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=times,
            y=df_bytes["total_bytes"].to_list(),
            mode="lines",
            fill="tonexty",
            fillcolor="rgba(11,31,58,0.15)",
            line=dict(color=NAVY, width=2),
            name="Received Bytes",
        )
    )

    apply_theme(fig, "Bytes Over Time")
    fig.update_layout(xaxis_title="Time", yaxis_title="Bytes")
    return fig
