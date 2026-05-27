"""Tests for perfsage.core.viz.expert."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import plotly.graph_objects as go
import polars as pl
import pytest

from perfsage.core.analysis.slo import SLOConfig
from perfsage.core.viz.expert import (
    fig_connect_breakdown,
    fig_outlier_scatter,
    fig_percentile_fan,
    fig_sli_burn_rate_timeline,
    fig_steady_state_compare,
    fig_threads_error_heatmap,
    fig_throughput_efficiency,
    fig_transaction_mix,
)

CREAM = "#F6F1E7"
WHITE = "#FFFFFF"

_EXPERT_BUILDERS: list[tuple[str, Callable[[Path], go.Figure]]] = [
    ("fig_sli_burn_rate_timeline", lambda p: fig_sli_burn_rate_timeline(p, SLOConfig())),
    ("fig_percentile_fan", fig_percentile_fan),
    ("fig_transaction_mix", fig_transaction_mix),
    ("fig_outlier_scatter", fig_outlier_scatter),
    ("fig_connect_breakdown", fig_connect_breakdown),
    ("fig_throughput_efficiency", fig_throughput_efficiency),
    ("fig_steady_state_compare", fig_steady_state_compare),
    ("fig_threads_error_heatmap", fig_threads_error_heatmap),
]


@pytest.mark.parametrize("name,builder", _EXPERT_BUILDERS)
def test_expert_figure_returns_go_figure(
    sample_parquet: Path, name: str, builder: Callable[[Path], go.Figure]
) -> None:
    assert isinstance(builder(sample_parquet), go.Figure)


@pytest.mark.parametrize("name,builder", _EXPERT_BUILDERS)
def test_expert_figure_applies_theme_colors(
    sample_parquet: Path, name: str, builder: Callable[[Path], go.Figure]
) -> None:
    fig = builder(sample_parquet)
    assert fig.layout.paper_bgcolor == CREAM
    assert fig.layout.plot_bgcolor == WHITE


@pytest.mark.parametrize("name,builder", _EXPERT_BUILDERS)
def test_expert_figure_json_serializable(
    sample_parquet: Path, name: str, builder: Callable[[Path], go.Figure]
) -> None:
    fig = builder(sample_parquet)
    assert json.loads(fig.to_json()) is not None


def test_empty_parquet_returns_figure(tmp_path: Path) -> None:
    p = tmp_path / "empty.parquet"
    pl.DataFrame(
        {
            "timestamp_ms": pl.Series([], dtype=pl.Int64),
            "elapsed": pl.Series([], dtype=pl.Int64),
            "label": pl.Series([], dtype=pl.Utf8),
            "response_code": pl.Series([], dtype=pl.Utf8),
            "success": pl.Series([], dtype=pl.Boolean),
            "bytes": pl.Series([], dtype=pl.Int64),
            "sent_bytes": pl.Series([], dtype=pl.Int64),
            "grp_threads": pl.Series([], dtype=pl.Int64),
            "all_threads": pl.Series([], dtype=pl.Int64),
            "latency": pl.Series([], dtype=pl.Int64),
            "idle_time": pl.Series([], dtype=pl.Int64),
            "connect": pl.Series([], dtype=pl.Int64),
        }
    ).write_parquet(p)
    fig = fig_sli_burn_rate_timeline(p, slo_config=SLOConfig())
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 0


def test_threads_heatmap_trace_type(sample_parquet: Path) -> None:
    fig = fig_threads_error_heatmap(sample_parquet)
    assert len(fig.data) >= 1
    assert type(fig.data[0]).__name__ == "Heatmap"


def test_outlier_scatter_two_traces_when_mixed_tail(sample_parquet_with_tail_latency: Path) -> None:
    fig = fig_outlier_scatter(sample_parquet_with_tail_latency, sample_limit=5000)
    assert len(fig.data) >= 1
