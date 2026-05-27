"""Expert-level charts: SLI vs SLO over time, percentile fan, mix, outliers, breakdown, efficiency, steady, heatmap."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import polars as pl

from perfsage.core.analysis.segmentation import detect_warmup_window
from perfsage.core.analysis.slo import SLOConfig
from perfsage.core.viz._theme import (
    AMBER,
    ERROR_RED,
    LABEL_COLORS,
    LABEL_PALETTE,
    NAVY,
    SUCCESS_GREEN,
    WARN_YELLOW,
    apply_theme,
)
from perfsage.core.viz._utils import time_bucket as _time_bucket


def _rgba(hex_color: str, alpha: float) -> str:
    """Convert #RRGGBB to rgba() for Plotly fills."""
    h = hex_color.removeprefix("#")
    if len(h) != 6:
        return f"rgba(128,128,128,{alpha})"
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def fig_sli_burn_rate_timeline(
    samples_path: Path,
    slo_config: SLOConfig | None = None,
    bucket_seconds: int = 10,
) -> go.Figure:
    """Error rate % and p99 latency vs fixed SLO thresholds over time."""
    title = "SLI Burn Rate Timeline"
    cfg = slo_config or SLOConfig()
    df = pl.read_parquet(samples_path)
    if df.is_empty():
        return apply_theme(go.Figure(), title)

    bucketed = _time_bucket(df, bucket_seconds)
    agg = (
        bucketed.group_by("time_bucket")
        .agg(
            [
                pl.len().alias("total"),
                (~pl.col("success")).sum().alias("errors"),
                pl.col("elapsed").quantile(0.99, interpolation="linear").alias("p99"),
            ]
        )
        .sort("time_bucket")
        .with_columns(
            pl.when(pl.col("total") == 0)
            .then(pl.lit(0.0))
            .otherwise(pl.col("errors").cast(pl.Float64) / pl.col("total") * 100)
            .alias("error_rate_pct")
        )
    )

    times = agg["time_bucket"].to_list()
    err_pct = agg["error_rate_pct"].to_list()
    p99 = agg["p99"].to_list()

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=times,
            y=err_pct,
            mode="lines",
            line=dict(color=ERROR_RED, width=2),
            name="Error rate %",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=times,
            y=p99,
            mode="lines",
            line=dict(color=NAVY, width=2),
            name="p99 latency (ms)",
            yaxis="y2",
        )
    )

    fig.add_hline(
        y=cfg.error_rate_pct, yref="y", line=dict(color=WARN_YELLOW, width=2, dash="dash")
    )
    fig.add_hline(y=cfg.p99_ms, yref="y2", line=dict(color=AMBER, width=2, dash="dash"))

    apply_theme(fig, title)
    fig.update_layout(
        xaxis_title="Time",
        yaxis_title="Error Rate (%)",
        yaxis2=dict(
            title="p99 Latency (ms)",
            overlaying="y",
            side="right",
            gridcolor="#E2E8F0",
            linecolor=NAVY,
            tickcolor=NAVY,
        ),
    )
    return fig


def fig_percentile_fan(samples_path: Path, bucket_seconds: int = 5) -> go.Figure:
    """p50–p99 percentile ribbon fan over time (nested fills)."""
    title = "Percentile Fan Over Time"
    df = pl.read_parquet(samples_path)
    if df.is_empty():
        return apply_theme(go.Figure(), title)

    qs = [
        (0.50, "p50"),
        (0.60, "p60"),
        (0.70, "p70"),
        (0.80, "p80"),
        (0.90, "p90"),
        (0.95, "p95"),
        (0.99, "p99"),
    ]
    agg_exprs = [
        pl.col("elapsed").quantile(q, interpolation="linear").alias(name) for q, name in qs
    ]
    agg = (
        _time_bucket(df, bucket_seconds).group_by("time_bucket").agg(agg_exprs).sort("time_bucket")
    )
    times = agg["time_bucket"].to_list()

    fig = go.Figure()
    names_rev = [n for _, n in reversed(qs)]
    palette = LABEL_PALETTE
    top_name = names_rev[0]
    fig.add_trace(
        go.Scatter(
            x=times,
            y=agg[top_name].to_list(),
            mode="lines",
            line=dict(color=NAVY, width=1.2),
            name="p99",
            showlegend=True,
        )
    )
    n_pairs = len(names_rev) - 1
    for idx, (_high, low) in enumerate(zip(names_rev[:-1], names_rev[1:], strict=True)):
        c = palette[idx % len(palette)]
        last = idx == n_pairs - 1
        fig.add_trace(
            go.Scatter(
                x=times,
                y=agg[low].to_list(),
                mode="lines",
                fill="tonexty",
                fillcolor=_rgba(c, 0.22 if not last else 0.35),
                line=dict(
                    color=SUCCESS_GREEN if last else c,
                    width=2.8 if last else 1,
                ),
                name="p50 (median)" if last else "",
                showlegend=last,
            )
        )
    apply_theme(fig, title)
    fig.update_layout(xaxis_title="Time", yaxis_title="Latency (ms)")
    return fig


def fig_transaction_mix(samples_path: Path, bucket_seconds: int = 10) -> go.Figure:
    """Stacked area of transaction label share (%) over time."""
    title = "Transaction Mix Over Time"
    df = pl.read_parquet(samples_path)
    if df.is_empty():
        return apply_theme(go.Figure(), title)

    bucketed = _time_bucket(df, bucket_seconds)
    counts = bucketed.group_by(["time_bucket", "label"]).len().rename({"len": "n"})
    totals = counts.group_by("time_bucket").agg(pl.col("n").sum().alias("total"))
    shares = counts.join(totals, on="time_bucket").with_columns(
        (pl.col("n").cast(pl.Float64) / pl.col("total") * 100).alias("share_pct")
    )
    labels = shares["label"].unique().sort().to_list()
    times_master = shares["time_bucket"].unique().sort().to_list()

    fig = go.Figure()
    for idx, lbl in enumerate(labels):
        sub = shares.filter(pl.col("label") == lbl).sort("time_bucket")
        # align to full time index for continuous areas
        time_to_share = dict(
            zip(sub["time_bucket"].to_list(), sub["share_pct"].to_list(), strict=True)
        )
        y = [float(time_to_share.get(t, 0.0)) for t in times_master]
        color = LABEL_COLORS[idx % len(LABEL_COLORS)]
        fig.add_trace(
            go.Scatter(
                x=times_master,
                y=y,
                mode="lines",
                stackgroup="mix",
                line=dict(width=0.4, color=color),
                fillcolor=_rgba(color, 0.55),
                name=str(lbl),
            )
        )

    apply_theme(fig, title)
    fig.update_layout(xaxis_title="Time", yaxis_title="Share of requests (%)")
    return fig


def _stratified_sample(df: pl.DataFrame, sample_limit: int) -> pl.DataFrame:
    total_rows = len(df)
    if total_rows <= sample_limit:
        return df
    parts: list[pl.DataFrame] = []
    for lbl in df["label"].unique().sort().to_list():
        subset = df.filter(pl.col("label") == lbl)
        share = subset.height / total_rows
        target = max(1, int(round(sample_limit * share)))
        take = min(target, subset.height)
        parts.append(subset.sample(n=take, seed=42))
    out = pl.concat(parts)
    if out.height > sample_limit:
        out = out.sample(n=sample_limit, seed=43)
    return out


def fig_outlier_scatter(samples_path: Path, sample_limit: int = 5000) -> go.Figure:
    """Scatter of latency vs time; IQR outliers highlighted per label."""
    title = "Outlier Scatter (IQR)"
    df = pl.read_parquet(samples_path)
    if df.is_empty():
        return apply_theme(go.Figure(), title)

    fences: dict[str, tuple[float, float]] = {}
    for lbl in df["label"].unique().sort().to_list():
        elapsed = df.filter(pl.col("label") == lbl)["elapsed"]
        if elapsed.is_empty():
            continue
        q1 = float(elapsed.quantile(0.25))  # type: ignore[arg-type]
        q3 = float(elapsed.quantile(0.75))  # type: ignore[arg-type]
        iqr = q3 - q1
        lo = q1 - 1.5 * iqr
        hi = q3 + 1.5 * iqr
        fences[str(lbl)] = (lo, hi)

    df = _stratified_sample(df, sample_limit)
    df = df.with_columns(pl.col("timestamp_ms").cast(pl.Datetime("ms")).alias("ts"))

    fig = go.Figure()
    for idx, lbl in enumerate(df["label"].unique().sort().to_list()):
        sub = df.filter(pl.col("label") == lbl)
        if sub.is_empty():
            continue
        lo_hi = fences.get(str(lbl), (-float("inf"), float("inf")))
        low, high = lo_hi
        sub = sub.with_columns(
            ((pl.col("elapsed") < low) | (pl.col("elapsed") > high)).alias("_out")
        )
        typical = sub.filter(~pl.col("_out"))
        outlier = sub.filter(pl.col("_out"))
        base_color = LABEL_COLORS[idx % len(LABEL_COLORS)]

        if not typical.is_empty():
            fig.add_trace(
                go.Scatter(
                    x=typical["ts"].to_list(),
                    y=typical["elapsed"].to_list(),
                    mode="markers",
                    marker=dict(color=base_color, size=5, opacity=0.35),
                    name=f"{lbl} (inlier)",
                    legendgroup=str(lbl),
                )
            )
        if not outlier.is_empty():
            fig.add_trace(
                go.Scatter(
                    x=outlier["ts"].to_list(),
                    y=outlier["elapsed"].to_list(),
                    mode="markers",
                    marker=dict(color=ERROR_RED, size=9, symbol="circle-open"),
                    name=f"{lbl} (outlier)",
                    legendgroup=str(lbl),
                )
            )

    apply_theme(fig, title)
    fig.update_layout(xaxis_title="Time", yaxis_title="Response time (ms)")
    return fig


def fig_connect_breakdown(samples_path: Path, bucket_seconds: int = 10) -> go.Figure:
    """Stacked mean connect, latency, and idle components over time."""
    title = "Latency Component Breakdown"
    df = pl.read_parquet(samples_path)
    if df.is_empty():
        return apply_theme(go.Figure(), title)

    agg = (
        _time_bucket(df, bucket_seconds)
        .group_by("time_bucket")
        .agg(
            [
                pl.col("connect").mean().alias("connect"),
                pl.col("latency").mean().alias("latency"),
                pl.col("idle_time").mean().alias("idle_time"),
            ]
        )
        .sort("time_bucket")
    )
    times = agg["time_bucket"].to_list()

    fig = go.Figure()
    order = [
        ("connect", "Connect (ms)", NAVY),
        ("latency", "Latency (ms)", AMBER),
        ("idle_time", "Idle (ms)", WARN_YELLOW),
    ]
    for col, lbl, color in order:
        fig.add_trace(
            go.Scatter(
                x=times,
                y=agg[col].to_list(),
                mode="lines",
                stackgroup="breakdown",
                line=dict(width=0.6, color=color),
                fillcolor=_rgba(color, 0.35),
                name=lbl,
            )
        )

    apply_theme(fig, title)
    fig.update_layout(xaxis_title="Time", yaxis_title="Mean ms (stacked)")
    return fig


def fig_throughput_efficiency(samples_path: Path, bucket_seconds: int = 10) -> go.Figure:
    """Total bytes transferred per cumulative ms elapsed (aggregate bytes/ms) over time."""
    title = "Throughput Efficiency"
    df = pl.read_parquet(samples_path)
    if df.is_empty():
        return apply_theme(go.Figure(), title)

    agg = (
        _time_bucket(df, bucket_seconds)
        .group_by("time_bucket")
        .agg(
            [
                pl.col("bytes").sum().alias("bytes_sum"),
                pl.col("sent_bytes").sum().alias("sent_sum"),
                pl.col("elapsed").sum().alias("elapsed_sum"),
            ]
        )
        .sort("time_bucket")
        .with_columns(
            (
                (pl.col("bytes_sum") + pl.col("sent_sum"))
                / pl.when(pl.col("elapsed_sum") == 0)
                .then(pl.lit(None))
                .otherwise(pl.col("elapsed_sum"))
            ).alias("bytes_per_ms")
        )
    )
    times = agg["time_bucket"].to_list()
    eff = agg["bytes_per_ms"].fill_null(0.0).to_list()

    fig = go.Figure(
        go.Scatter(
            x=times,
            y=eff,
            mode="lines",
            fill="tozeroy",
            fillcolor="rgba(57,161,105,0.12)",
            line=dict(color=SUCCESS_GREEN, width=2),
            name="(bytes_in + bytes_out) / Σ elapsed",
        )
    )
    apply_theme(fig, title)
    fig.update_layout(xaxis_title="Time", yaxis_title="Bytes / ms")
    return fig


def fig_steady_state_compare(samples_path: Path) -> go.Figure:
    """Grouped bars: warmup vs steady p90/p99 latencies."""
    title = "Warmup vs Steady State"
    df = pl.read_parquet(samples_path)
    if df.is_empty():
        return apply_theme(go.Figure(), title)

    warmup_end_ms, test_end_ms = detect_warmup_window(samples_path)
    warmup_df = df.filter(pl.col("timestamp_ms") < warmup_end_ms)
    steady_df = df.filter(
        (pl.col("timestamp_ms") >= warmup_end_ms) & (pl.col("timestamp_ms") <= test_end_ms)
    )

    def pct(frame: pl.DataFrame, q: float) -> float:
        if frame.is_empty():
            return 0.0
        val = frame["elapsed"].quantile(q, interpolation="linear")
        return float(val) if val is not None else 0.0  # type: ignore[arg-type]

    w90, w99 = pct(warmup_df, 0.90), pct(warmup_df, 0.99)
    s90, s99 = pct(steady_df, 0.90), pct(steady_df, 0.99)

    fig = go.Figure(
        [
            go.Bar(
                name="p90",
                x=["Warmup", "Steady"],
                y=[w90, s90],
                marker_color=NAVY,
            ),
            go.Bar(
                name="p99",
                x=["Warmup", "Steady"],
                y=[w99, s99],
                marker_color=AMBER,
            ),
        ]
    )
    apply_theme(fig, title)
    fig.update_layout(barmode="group", xaxis_title="Phase", yaxis_title="Latency (ms)")
    return fig


def fig_threads_error_heatmap(samples_path: Path) -> go.Figure:
    """2D heatmap: time-bucket mean thread count vs error-rate magnitude (sample counts per cell)."""
    title = "Threads vs Error Rate"
    df = pl.read_parquet(samples_path)
    if df.is_empty():
        return apply_theme(go.Figure(), title)

    bucket_seconds = 10
    agg = (
        _time_bucket(df, bucket_seconds)
        .group_by("time_bucket")
        .agg(
            [
                pl.col("all_threads").mean().alias("mean_threads"),
                pl.len().alias("total"),
                (~pl.col("success")).sum().alias("errors"),
            ]
        )
        .with_columns(
            pl.when(pl.col("total") == 0)
            .then(pl.lit(0.0))
            .otherwise(pl.col("errors").cast(pl.Float64) / pl.col("total") * 100)
            .alias("error_rate_pct")
        )
        .sort("time_bucket")
    )

    if agg.is_empty():
        return apply_theme(go.Figure(), title)

    mt = agg["mean_threads"].to_numpy()
    er = agg["error_rate_pct"].fill_null(0.0).to_numpy()
    mt_bins = min(8, max(3, len(np.unique(mt))))
    er_edges = np.array([-0.01, 0.01, 1.0, 5.0, 25.0, 100.0])
    mt_edges = np.linspace(float(np.nanmin(mt)), float(np.nanmax(mt)), mt_bins + 1)

    h, xe, ye = np.histogram2d(mt, er, bins=[mt_edges, er_edges])
    xe_labels = [f"{xe[i]:.0f}-{xe[i + 1]:.0f}" for i in range(len(xe) - 1)]
    yer = ["≈0%", "0–1%", "1–5%", "5–25%", ">25%"]

    fig = go.Figure(
        go.Heatmap(
            z=h.tolist(),
            x=yer,
            y=xe_labels,
            colorscale="Blues",
            colorbar=dict(title="Buckets"),
        )
    )
    apply_theme(fig, title)
    fig.update_layout(
        xaxis_title="Error rate (per time bucket)",
        yaxis_title="Mean active threads",
    )
    return fig
