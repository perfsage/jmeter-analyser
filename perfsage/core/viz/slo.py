"""SLO/Apdex visualization: gauges, per-label Apdex bar chart, error sunburst."""

from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go
import polars as pl
from plotly.subplots import make_subplots

from perfsage.core.analysis.percentiles import compute_overall_percentiles
from perfsage.core.analysis.slo import SLOConfig, compute_apdex
from perfsage.core.viz._theme import (
    CREAM,
    ERROR_RED,
    NAVY,
    SUCCESS_GREEN,
    WARN_YELLOW,
    apply_theme,
)


def _apdex_color(score: float) -> str:
    if score >= 0.85:
        return SUCCESS_GREEN
    if score >= 0.70:
        return WARN_YELLOW
    return ERROR_RED


def fig_slo_gauges(
    samples_path: Path,
    slo_config: SLOConfig | None = None,
) -> go.Figure:
    """Fig 16: KPI indicator gauges — APDEX, error rate, p99 latency."""
    if slo_config is None:
        slo_config = SLOConfig()

    df = pl.read_parquet(samples_path)
    if df.is_empty():
        return apply_theme(go.Figure(), "KPI Gauges")

    # Overall APDEX (weighted average across labels)
    apdex_df = compute_apdex(samples_path, t_seconds=slo_config.apdex_t)
    total_n = int(apdex_df["total"].sum())
    if total_n > 0:
        apdex_score = float(
            (apdex_df["apdex_score"] * apdex_df["total"]).sum() / total_n
        )
    else:
        apdex_score = 0.0

    # Error rate
    n = len(df)
    error_count = int((~df["success"]).sum())
    error_rate_pct = error_count / n * 100 if n > 0 else 0.0

    # P99 latency
    pcts = compute_overall_percentiles(samples_path)
    p99_ms = pcts.get("p99", 0.0)

    fig = make_subplots(
        rows=1,
        cols=3,
        specs=[[{"type": "indicator"}] * 3],
    )

    # APDEX gauge
    fig.add_trace(
        go.Indicator(
            mode="gauge+number",
            value=round(apdex_score, 3),
            title={"text": "APDEX Score"},
            gauge={
                "axis": {"range": [0, 1]},
                "bar": {"color": _apdex_color(apdex_score)},
                "steps": [
                    {"range": [0, 0.70], "color": "rgba(229,62,62,0.15)"},
                    {"range": [0.70, 0.85], "color": "rgba(236,201,75,0.15)"},
                    {"range": [0.85, 1.0], "color": "rgba(56,161,105,0.15)"},
                ],
                "threshold": {
                    "line": {"color": NAVY, "width": 3},
                    "thickness": 0.75,
                    "value": 0.85,
                },
            },
        ),
        row=1,
        col=1,
    )

    # Error rate gauge
    err_color = SUCCESS_GREEN if error_rate_pct <= slo_config.error_rate_pct else ERROR_RED
    fig.add_trace(
        go.Indicator(
            mode="gauge+number+delta",
            value=round(error_rate_pct, 2),
            title={"text": "Error Rate (%)"},
            delta={"reference": slo_config.error_rate_pct, "increasing": {"color": ERROR_RED}},
            gauge={
                "axis": {"range": [0, min(100.0, error_rate_pct * 3 + 5)]},
                "bar": {"color": err_color},
                "threshold": {
                    "line": {"color": ERROR_RED, "width": 3},
                    "thickness": 0.75,
                    "value": slo_config.error_rate_pct,
                },
            },
        ),
        row=1,
        col=2,
    )

    # P99 latency gauge
    p99_color = SUCCESS_GREEN if p99_ms <= slo_config.p99_ms else ERROR_RED
    fig.add_trace(
        go.Indicator(
            mode="gauge+number+delta",
            value=round(p99_ms, 0),
            title={"text": "p99 Latency (ms)"},
            delta={"reference": slo_config.p99_ms, "increasing": {"color": ERROR_RED}},
            gauge={
                "axis": {"range": [0, max(p99_ms * 1.5, slo_config.p99_ms * 1.5)]},
                "bar": {"color": p99_color},
                "threshold": {
                    "line": {"color": ERROR_RED, "width": 3},
                    "thickness": 0.75,
                    "value": slo_config.p99_ms,
                },
            },
        ),
        row=1,
        col=3,
    )

    fig.update_layout(
        paper_bgcolor=CREAM,
        font=dict(family="Inter, sans-serif", color=NAVY),
        title=dict(text="SLO KPI Dashboard", font=dict(color=NAVY, size=16)),
        margin=dict(l=40, r=40, t=80, b=40),
    )
    return fig


def fig_apdex_by_label(samples_path: Path, t_seconds: float = 0.5) -> go.Figure:
    """Fig 17: Horizontal bar chart of APDEX score per label, color-coded by score."""
    apdex_df = compute_apdex(samples_path, t_seconds=t_seconds)
    if apdex_df.is_empty():
        return apply_theme(go.Figure(), "APDEX by Label")

    apdex_df = apdex_df.sort("apdex_score", descending=False)
    scores = apdex_df["apdex_score"].to_list()
    labels = [str(lbl) for lbl in apdex_df["label"].to_list()]
    colors = [_apdex_color(float(s)) for s in scores]

    fig = go.Figure(
        go.Bar(
            x=scores,
            y=labels,
            orientation="h",
            marker_color=colors,
            text=[f"{float(s):.3f}" for s in scores],
            textposition="outside",
            name="APDEX",
        )
    )

    # Threshold lines
    for val, color, label in [
        (0.85, SUCCESS_GREEN, "Excellent (0.85)"),
        (0.70, WARN_YELLOW, "Fair (0.70)"),
    ]:
        fig.add_vline(
            x=val,
            line_dash="dash",
            line_color=color,
            annotation_text=label,
            annotation_position="top",
        )

    apply_theme(fig, "APDEX Score by Label")
    fig.update_layout(
        xaxis=dict(range=[0, 1.1], title="APDEX Score"),
        yaxis_title="Label",
    )
    return fig


def fig_error_sunburst(samples_path: Path) -> go.Figure:
    """Fig 19: Sunburst — inner ring: response_code, outer ring: label (errors only)."""
    df = pl.read_parquet(samples_path)
    if df.is_empty():
        return apply_theme(go.Figure(), "Error Distribution")

    error_df = df.filter(~pl.col("success"))
    if error_df.is_empty():
        fig = go.Figure()
        return apply_theme(fig, "Error Distribution (No errors in dataset)")

    counts = (
        error_df.group_by(["response_code", "label"])
        .agg(pl.len().alias("count"))
    )

    rc_totals = counts.group_by("response_code").agg(pl.col("count").sum().alias("rc_total"))

    ids: list[str] = []
    labels: list[str] = []
    parents: list[str] = []
    values: list[int] = []

    # Root nodes: response codes (inner ring)
    for row in rc_totals.to_dicts():
        rc = str(row["response_code"])
        ids.append(rc)
        labels.append(rc)
        parents.append("")
        values.append(int(str(row["rc_total"])))

    # Leaf nodes: labels under each response code (outer ring)
    for row in counts.to_dicts():
        rc = str(row["response_code"])
        lbl = str(row["label"])
        ids.append(f"{rc}|{lbl}")
        labels.append(lbl)
        parents.append(rc)
        values.append(int(str(row["count"])))

    fig = go.Figure(
        go.Sunburst(
            ids=ids,
            labels=labels,
            parents=parents,
            values=values,
            branchvalues="total",
            insidetextorientation="radial",
            marker=dict(colorscale="Reds"),
        )
    )

    apply_theme(fig, "Error Distribution by Response Code and Label")
    fig.update_layout(margin=dict(l=10, r=10, t=60, b=10))
    return fig
