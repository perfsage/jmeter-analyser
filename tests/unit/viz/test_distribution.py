"""Tests for perfsage.core.viz.distribution (Figs 6-9)."""

from __future__ import annotations

import json
from pathlib import Path

import plotly.graph_objects as go
import pytest

from perfsage.core.viz.distribution import (
    fig_boxplots_per_label,
    fig_latency_cdf,
    fig_latency_histogram,
    fig_rt_heatmap,
)

CREAM = "#F6F1E7"
WHITE = "#FFFFFF"


# ---------------------------------------------------------------------------
# Fig 6 — Latency Histogram
# ---------------------------------------------------------------------------


def test_fig_latency_histogram_returns_figure(sample_parquet: Path) -> None:
    assert isinstance(fig_latency_histogram(sample_parquet), go.Figure)


def test_fig_latency_histogram_paper_bgcolor_is_cream(sample_parquet: Path) -> None:
    assert fig_latency_histogram(sample_parquet).layout.paper_bgcolor == CREAM


def test_fig_latency_histogram_plot_bgcolor_is_white(sample_parquet: Path) -> None:
    assert fig_latency_histogram(sample_parquet).layout.plot_bgcolor == WHITE


def test_fig_latency_histogram_has_data(sample_parquet: Path) -> None:
    fig = fig_latency_histogram(sample_parquet)
    assert len(fig.data) >= 1


def test_fig_latency_histogram_is_json_serializable(sample_parquet: Path) -> None:
    json_str = fig_latency_histogram(sample_parquet).to_json()
    assert json.loads(json_str) is not None


def test_fig_latency_histogram_with_label_filter(sample_parquet: Path) -> None:
    fig = fig_latency_histogram(sample_parquet, label="Transaction 1")
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1


def test_fig_latency_histogram_unknown_label(sample_parquet: Path) -> None:
    # Should return empty figure gracefully
    fig = fig_latency_histogram(sample_parquet, label="__nonexistent__")
    assert isinstance(fig, go.Figure)


def test_fig_latency_histogram_first_trace_is_bar(sample_parquet: Path) -> None:
    # Pre-binned server-side (see fig_latency_histogram docstring) — go.Bar
    # renders the same visual shape as go.Histogram without shipping raw arrays.
    fig = fig_latency_histogram(sample_parquet)
    assert type(fig.data[0]).__name__ == "Bar"


def test_fig_latency_histogram_with_errors(sample_parquet_with_errors: Path) -> None:
    assert isinstance(fig_latency_histogram(sample_parquet_with_errors), go.Figure)


def test_fig_latency_histogram_with_slow_data(sample_parquet_slow: Path) -> None:
    assert isinstance(fig_latency_histogram(sample_parquet_slow), go.Figure)


def test_fig_latency_histogram_payload_is_binned_not_raw(sample_parquet_fast):
    fig = fig_latency_histogram(sample_parquet_fast)
    assert len(fig.data) >= 1
    trace = fig.data[0]
    # Binned output has at most ~50 points regardless of input row count;
    # a raw-array histogram trace would carry one x-value per input row (200).
    assert len(trace.x) <= 60


# ---------------------------------------------------------------------------
# Fig 7 — Latency CDF
# ---------------------------------------------------------------------------


def test_fig_latency_cdf_returns_figure(sample_parquet: Path) -> None:
    assert isinstance(fig_latency_cdf(sample_parquet), go.Figure)


def test_fig_latency_cdf_paper_bgcolor_is_cream(sample_parquet: Path) -> None:
    assert fig_latency_cdf(sample_parquet).layout.paper_bgcolor == CREAM


def test_fig_latency_cdf_plot_bgcolor_is_white(sample_parquet: Path) -> None:
    assert fig_latency_cdf(sample_parquet).layout.plot_bgcolor == WHITE


def test_fig_latency_cdf_has_data(sample_parquet: Path) -> None:
    fig = fig_latency_cdf(sample_parquet)
    assert len(fig.data) >= 1


def test_fig_latency_cdf_is_json_serializable(sample_parquet: Path) -> None:
    json_str = fig_latency_cdf(sample_parquet).to_json()
    assert json.loads(json_str) is not None


def test_fig_latency_cdf_with_errors(sample_parquet_with_errors: Path) -> None:
    assert isinstance(fig_latency_cdf(sample_parquet_with_errors), go.Figure)


def test_fig_latency_cdf_with_slow_data(sample_parquet_slow: Path) -> None:
    assert isinstance(fig_latency_cdf(sample_parquet_slow), go.Figure)


def test_fig_latency_cdf_trace_is_scatter(sample_parquet: Path) -> None:
    fig = fig_latency_cdf(sample_parquet)
    assert type(fig.data[0]).__name__ == "Scatter"


def test_fig_latency_cdf_y_max_near_100(sample_parquet: Path) -> None:
    fig = fig_latency_cdf(sample_parquet)
    y_vals = list(fig.data[0].y)
    assert max(y_vals) == pytest.approx(100.0, abs=0.01)


def test_fig_latency_cdf_monotone(sample_parquet: Path) -> None:
    fig = fig_latency_cdf(sample_parquet)
    y_vals = list(fig.data[0].y)
    for i in range(1, len(y_vals)):
        assert y_vals[i] >= y_vals[i - 1]


# ---------------------------------------------------------------------------
# Fig 8 — Box Plots per Label
# ---------------------------------------------------------------------------


def test_fig_boxplots_per_label_returns_figure(sample_parquet: Path) -> None:
    assert isinstance(fig_boxplots_per_label(sample_parquet), go.Figure)


def test_fig_boxplots_per_label_paper_bgcolor_is_cream(sample_parquet: Path) -> None:
    assert fig_boxplots_per_label(sample_parquet).layout.paper_bgcolor == CREAM


def test_fig_boxplots_per_label_plot_bgcolor_is_white(sample_parquet: Path) -> None:
    assert fig_boxplots_per_label(sample_parquet).layout.plot_bgcolor == WHITE


def test_fig_boxplots_per_label_has_data(sample_parquet: Path) -> None:
    fig = fig_boxplots_per_label(sample_parquet)
    assert len(fig.data) > 0


def test_fig_boxplots_per_label_is_json_serializable(sample_parquet: Path) -> None:
    json_str = fig_boxplots_per_label(sample_parquet).to_json()
    assert json.loads(json_str) is not None


def test_fig_boxplots_per_label_traces_are_box(sample_parquet: Path) -> None:
    fig = fig_boxplots_per_label(sample_parquet)
    for trace in fig.data:
        assert type(trace).__name__ == "Box"


def test_fig_boxplots_per_label_with_errors(sample_parquet_with_errors: Path) -> None:
    assert isinstance(fig_boxplots_per_label(sample_parquet_with_errors), go.Figure)


def test_fig_boxplots_per_label_with_slow_data(sample_parquet_slow: Path) -> None:
    assert isinstance(fig_boxplots_per_label(sample_parquet_slow), go.Figure)


def test_fig_boxplots_per_label_one_box_per_label(sample_parquet: Path) -> None:
    import polars as pl

    raw = pl.read_parquet(sample_parquet)
    n_labels = raw["label"].n_unique()
    fig = fig_boxplots_per_label(sample_parquet)
    assert len(fig.data) == n_labels


def test_fig_boxplots_per_label_sorted_by_median(sample_parquet_slow: Path) -> None:
    fig = fig_boxplots_per_label(sample_parquet_slow)
    # All boxes present (2 labels in slow fixture)
    assert len(fig.data) >= 1


def test_fig_boxplots_per_label_payload_has_no_raw_y_arrays(sample_parquet):
    fig = fig_boxplots_per_label(sample_parquet)
    assert len(fig.data) >= 1
    for trace in fig.data:
        # Quartile-stat boxes carry q1/median/q3 as scalars, not a raw y= array.
        assert trace.y is None or len(trace.y) == 0
        assert trace.q1 is not None
        assert trace.median is not None
        assert trace.q3 is not None


# ---------------------------------------------------------------------------
# Fig 9 — RT Heatmap
# ---------------------------------------------------------------------------


def test_fig_rt_heatmap_returns_figure(sample_parquet: Path) -> None:
    assert isinstance(fig_rt_heatmap(sample_parquet), go.Figure)


def test_fig_rt_heatmap_paper_bgcolor_is_cream(sample_parquet: Path) -> None:
    assert fig_rt_heatmap(sample_parquet).layout.paper_bgcolor == CREAM


def test_fig_rt_heatmap_plot_bgcolor_is_white(sample_parquet: Path) -> None:
    assert fig_rt_heatmap(sample_parquet).layout.plot_bgcolor == WHITE


def test_fig_rt_heatmap_first_trace_is_heatmap(sample_parquet: Path) -> None:
    fig = fig_rt_heatmap(sample_parquet)
    assert len(fig.data) >= 1
    assert type(fig.data[0]).__name__ == "Heatmap"


def test_fig_rt_heatmap_is_json_serializable(sample_parquet: Path) -> None:
    json_str = fig_rt_heatmap(sample_parquet).to_json()
    assert json.loads(json_str) is not None


def test_fig_rt_heatmap_with_errors(sample_parquet_with_errors: Path) -> None:
    assert isinstance(fig_rt_heatmap(sample_parquet_with_errors), go.Figure)


def test_fig_rt_heatmap_with_slow_data(sample_parquet_slow: Path) -> None:
    fig = fig_rt_heatmap(sample_parquet_slow)
    assert isinstance(fig, go.Figure)
    # Slow data (5000ms) should have non-zero values in the 5k+ bucket
    heatmap = fig.data[0]
    y_labels = list(heatmap.y)
    assert "5k+" in y_labels


def test_fig_rt_heatmap_z_is_matrix(sample_parquet: Path) -> None:
    fig = fig_rt_heatmap(sample_parquet)
    heatmap = fig.data[0]
    assert heatmap.z is not None
    assert len(heatmap.z) > 0


def test_fig_rt_heatmap_custom_bucket(sample_parquet: Path) -> None:
    assert isinstance(fig_rt_heatmap(sample_parquet, bucket_seconds=10), go.Figure)


def test_fig_rt_heatmap_x_count_matches_time_buckets(sample_parquet: Path) -> None:
    fig = fig_rt_heatmap(sample_parquet)
    heatmap = fig.data[0]
    z_cols = len(heatmap.z[0]) if heatmap.z and len(heatmap.z) > 0 else 0
    x_len = len(heatmap.x) if heatmap.x is not None else 0
    assert z_cols == x_len
