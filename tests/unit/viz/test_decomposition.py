"""Tests for perfsage.core.viz.decomposition (Figs 14-15)."""

from __future__ import annotations

import json
from pathlib import Path

import plotly.graph_objects as go

from perfsage.core.viz.decomposition import (
    fig_latency_components,
    fig_per_label_small_multiples,
)

CREAM = "#F6F1E7"
WHITE = "#FFFFFF"


# ---------------------------------------------------------------------------
# Fig 14 — Latency Components
# ---------------------------------------------------------------------------


def test_fig_latency_components_returns_figure(sample_parquet: Path) -> None:
    assert isinstance(fig_latency_components(sample_parquet), go.Figure)


def test_fig_latency_components_paper_bgcolor_is_cream(sample_parquet: Path) -> None:
    assert fig_latency_components(sample_parquet).layout.paper_bgcolor == CREAM


def test_fig_latency_components_plot_bgcolor_is_white(sample_parquet: Path) -> None:
    assert fig_latency_components(sample_parquet).layout.plot_bgcolor == WHITE


def test_fig_latency_components_has_three_traces(sample_parquet: Path) -> None:
    fig = fig_latency_components(sample_parquet)
    assert len(fig.data) == 3


def test_fig_latency_components_is_json_serializable(sample_parquet: Path) -> None:
    json_str = fig_latency_components(sample_parquet).to_json()
    assert json.loads(json_str) is not None


def test_fig_latency_components_trace_names(sample_parquet: Path) -> None:
    fig = fig_latency_components(sample_parquet)
    names = {trace.name for trace in fig.data}
    assert "Connect Time" in names
    assert "Time to First Byte" in names
    assert "Transfer Time" in names


def test_fig_latency_components_with_errors(sample_parquet_with_errors: Path) -> None:
    assert isinstance(fig_latency_components(sample_parquet_with_errors), go.Figure)


def test_fig_latency_components_with_slow_data(sample_parquet_slow: Path) -> None:
    assert isinstance(fig_latency_components(sample_parquet_slow), go.Figure)


def test_fig_latency_components_stacked_area(sample_parquet: Path) -> None:
    fig = fig_latency_components(sample_parquet)
    # All traces should have stackgroup set
    for trace in fig.data:
        assert hasattr(trace, "stackgroup")
        assert trace.stackgroup == "one"


def test_fig_latency_components_custom_bucket(sample_parquet: Path) -> None:
    assert isinstance(fig_latency_components(sample_parquet, bucket_seconds=5), go.Figure)


# ---------------------------------------------------------------------------
# Fig 15 — Per-Label Small Multiples
# ---------------------------------------------------------------------------


def test_fig_per_label_small_multiples_returns_figure(sample_parquet: Path) -> None:
    assert isinstance(fig_per_label_small_multiples(sample_parquet), go.Figure)


def test_fig_per_label_small_multiples_paper_bgcolor_is_cream(sample_parquet: Path) -> None:
    assert fig_per_label_small_multiples(sample_parquet).layout.paper_bgcolor == CREAM


def test_fig_per_label_small_multiples_has_data(sample_parquet: Path) -> None:
    fig = fig_per_label_small_multiples(sample_parquet)
    assert len(fig.data) > 0


def test_fig_per_label_small_multiples_is_json_serializable(sample_parquet: Path) -> None:
    json_str = fig_per_label_small_multiples(sample_parquet).to_json()
    assert json.loads(json_str) is not None


def test_fig_per_label_small_multiples_with_errors(sample_parquet_with_errors: Path) -> None:
    assert isinstance(fig_per_label_small_multiples(sample_parquet_with_errors), go.Figure)


def test_fig_per_label_small_multiples_with_slow_data(sample_parquet_slow: Path) -> None:
    assert isinstance(fig_per_label_small_multiples(sample_parquet_slow), go.Figure)


def test_fig_per_label_small_multiples_trace_count_bounded(sample_parquet: Path) -> None:
    fig = fig_per_label_small_multiples(sample_parquet)
    # Should not exceed 12 subplots
    assert len(fig.data) <= 12


def test_fig_per_label_small_multiples_all_scatter_traces(sample_parquet: Path) -> None:
    fig = fig_per_label_small_multiples(sample_parquet)
    for trace in fig.data:
        assert type(trace).__name__ == "Scatter"


def test_fig_per_label_small_multiples_respects_max_labels(sample_parquet: Path) -> None:
    """Sample parquet has 5 labels; all should be present."""
    import polars as pl

    raw = pl.read_parquet(sample_parquet)
    n_labels = min(raw["label"].n_unique(), 12)
    fig = fig_per_label_small_multiples(sample_parquet)
    assert len(fig.data) == n_labels
