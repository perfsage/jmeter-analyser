"""Tests for perfsage.core.viz.timeseries (Figs 1–5)."""

from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go

from perfsage.core.viz.timeseries import (
    fig_bytes_over_time,
    fig_errors_over_time,
    fig_rt_over_time,
    fig_threads_vs_rt,
    fig_throughput_over_time,
)

CREAM = "#F6F1E7"


# ---------------------------------------------------------------------------
# Fig 1: fig_rt_over_time
# ---------------------------------------------------------------------------


def test_fig_rt_over_time_returns_figure(sample_parquet: Path) -> None:
    fig = fig_rt_over_time(sample_parquet)
    assert isinstance(fig, go.Figure)


def test_fig_rt_over_time_has_at_least_four_traces(sample_parquet: Path) -> None:
    fig = fig_rt_over_time(sample_parquet)
    # p50, p90, p95, p99 traces (p99 first as upper-bound for fill)
    assert len(fig.data) >= 4


def test_fig_rt_over_time_has_navy_theme(sample_parquet: Path) -> None:
    fig = fig_rt_over_time(sample_parquet)
    assert fig.layout.paper_bgcolor == CREAM


def test_fig_rt_over_time_is_json_serializable(sample_parquet: Path) -> None:
    fig = fig_rt_over_time(sample_parquet)
    json_str = fig.to_json()
    assert isinstance(json_str, str)
    assert len(json_str) > 0


def test_fig_rt_over_time_slow_data(sample_parquet_slow: Path) -> None:
    fig = fig_rt_over_time(sample_parquet_slow)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 4


def test_fig_rt_over_time_spike_shows_anomaly(sample_parquet_with_spike: Path) -> None:
    fig = fig_rt_over_time(sample_parquet_with_spike)
    assert isinstance(fig, go.Figure)
    trace_names = [t.name for t in fig.data]
    assert any(name is not None for name in trace_names)


# ---------------------------------------------------------------------------
# Fig 2: fig_throughput_over_time
# ---------------------------------------------------------------------------


def test_fig_throughput_over_time_returns_figure(sample_parquet: Path) -> None:
    fig = fig_throughput_over_time(sample_parquet)
    assert isinstance(fig, go.Figure)


def test_fig_throughput_over_time_has_data(sample_parquet: Path) -> None:
    fig = fig_throughput_over_time(sample_parquet)
    assert len(fig.data) >= 1


def test_fig_throughput_over_time_has_theme(sample_parquet: Path) -> None:
    fig = fig_throughput_over_time(sample_parquet)
    assert fig.layout.paper_bgcolor == CREAM


def test_fig_throughput_over_time_json_serializable(sample_parquet: Path) -> None:
    fig = fig_throughput_over_time(sample_parquet)
    assert isinstance(fig.to_json(), str)


def test_fig_throughput_over_time_with_errors(sample_parquet_with_errors: Path) -> None:
    fig = fig_throughput_over_time(sample_parquet_with_errors)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1


# ---------------------------------------------------------------------------
# Fig 3: fig_errors_over_time
# ---------------------------------------------------------------------------


def test_fig_errors_over_time_returns_figure(sample_parquet: Path) -> None:
    fig = fig_errors_over_time(sample_parquet)
    assert isinstance(fig, go.Figure)


def test_fig_errors_over_time_has_theme(sample_parquet: Path) -> None:
    fig = fig_errors_over_time(sample_parquet)
    assert fig.layout.paper_bgcolor == CREAM


def test_fig_errors_over_time_with_errors_has_bar(sample_parquet_with_errors: Path) -> None:
    fig = fig_errors_over_time(sample_parquet_with_errors)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1


def test_fig_errors_over_time_has_error_rate_line(sample_parquet_with_errors: Path) -> None:
    fig = fig_errors_over_time(sample_parquet_with_errors)
    # Error rate line is added on secondary y-axis as a Scatter trace
    scatter_traces = [t for t in fig.data if isinstance(t, go.Scatter)]
    assert len(scatter_traces) >= 1


def test_fig_errors_over_time_json_serializable(sample_parquet: Path) -> None:
    assert isinstance(fig_errors_over_time(sample_parquet).to_json(), str)


# ---------------------------------------------------------------------------
# Fig 4: fig_threads_vs_rt
# ---------------------------------------------------------------------------


def test_fig_threads_vs_rt_returns_figure(sample_parquet: Path) -> None:
    fig = fig_threads_vs_rt(sample_parquet)
    assert isinstance(fig, go.Figure)


def test_fig_threads_vs_rt_has_two_traces(sample_parquet: Path) -> None:
    fig = fig_threads_vs_rt(sample_parquet)
    assert len(fig.data) >= 2


def test_fig_threads_vs_rt_has_theme(sample_parquet: Path) -> None:
    fig = fig_threads_vs_rt(sample_parquet)
    assert fig.layout.paper_bgcolor == CREAM


def test_fig_threads_vs_rt_has_secondary_yaxis(sample_parquet: Path) -> None:
    fig = fig_threads_vs_rt(sample_parquet)
    # One trace should reference yaxis2
    yaxes = [getattr(t, "yaxis", None) for t in fig.data]
    assert "y2" in yaxes


def test_fig_threads_vs_rt_json_serializable(sample_parquet: Path) -> None:
    assert isinstance(fig_threads_vs_rt(sample_parquet).to_json(), str)


# ---------------------------------------------------------------------------
# Fig 5: fig_bytes_over_time
# ---------------------------------------------------------------------------


def test_fig_bytes_over_time_returns_figure(sample_parquet: Path) -> None:
    fig = fig_bytes_over_time(sample_parquet)
    assert isinstance(fig, go.Figure)


def test_fig_bytes_over_time_has_two_traces(sample_parquet: Path) -> None:
    fig = fig_bytes_over_time(sample_parquet)
    assert len(fig.data) >= 2


def test_fig_bytes_over_time_has_theme(sample_parquet: Path) -> None:
    fig = fig_bytes_over_time(sample_parquet)
    assert fig.layout.paper_bgcolor == CREAM


def test_fig_bytes_over_time_json_serializable(sample_parquet: Path) -> None:
    assert isinstance(fig_bytes_over_time(sample_parquet).to_json(), str)


def test_fig_bytes_over_time_slow(sample_parquet_slow: Path) -> None:
    fig = fig_bytes_over_time(sample_parquet_slow)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 2
