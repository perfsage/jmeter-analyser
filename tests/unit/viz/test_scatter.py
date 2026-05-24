"""Tests for perfsage.core.viz.scatter (Figs 10-13)."""

from __future__ import annotations

import json
from pathlib import Path

import plotly.graph_objects as go

from perfsage.core.viz.scatter import (
    fig_correlation_matrix,
    fig_rt_vs_concurrency,
    fig_rt_vs_throughput,
    fig_rt_vs_time_by_status,
)

CREAM = "#F6F1E7"
WHITE = "#FFFFFF"


# ---------------------------------------------------------------------------
# Fig 10 — RT vs Throughput
# ---------------------------------------------------------------------------


def test_fig_rt_vs_throughput_returns_figure(sample_parquet: Path) -> None:
    assert isinstance(fig_rt_vs_throughput(sample_parquet), go.Figure)


def test_fig_rt_vs_throughput_paper_bgcolor_is_cream(sample_parquet: Path) -> None:
    assert fig_rt_vs_throughput(sample_parquet).layout.paper_bgcolor == CREAM


def test_fig_rt_vs_throughput_plot_bgcolor_is_white(sample_parquet: Path) -> None:
    assert fig_rt_vs_throughput(sample_parquet).layout.plot_bgcolor == WHITE


def test_fig_rt_vs_throughput_has_data(sample_parquet: Path) -> None:
    fig = fig_rt_vs_throughput(sample_parquet)
    assert len(fig.data) >= 1


def test_fig_rt_vs_throughput_is_json_serializable(sample_parquet: Path) -> None:
    json_str = fig_rt_vs_throughput(sample_parquet).to_json()
    assert json.loads(json_str) is not None


def test_fig_rt_vs_throughput_with_errors(sample_parquet_with_errors: Path) -> None:
    assert isinstance(fig_rt_vs_throughput(sample_parquet_with_errors), go.Figure)


def test_fig_rt_vs_throughput_with_slow_data(sample_parquet_slow: Path) -> None:
    assert isinstance(fig_rt_vs_throughput(sample_parquet_slow), go.Figure)


def test_fig_rt_vs_throughput_first_trace_is_scatter(sample_parquet: Path) -> None:
    fig = fig_rt_vs_throughput(sample_parquet)
    assert type(fig.data[0]).__name__ == "Scatter"


def test_fig_rt_vs_throughput_scatter_mode(sample_parquet: Path) -> None:
    fig = fig_rt_vs_throughput(sample_parquet)
    assert "markers" in fig.data[0].mode


def test_fig_rt_vs_throughput_has_trendline(sample_parquet: Path) -> None:
    fig = fig_rt_vs_throughput(sample_parquet)
    # Should have at least 2 traces: scatter + trendline
    assert len(fig.data) >= 2


# ---------------------------------------------------------------------------
# Fig 11 — RT vs Concurrency
# ---------------------------------------------------------------------------


def test_fig_rt_vs_concurrency_returns_figure(sample_parquet: Path) -> None:
    assert isinstance(fig_rt_vs_concurrency(sample_parquet), go.Figure)


def test_fig_rt_vs_concurrency_paper_bgcolor_is_cream(sample_parquet: Path) -> None:
    assert fig_rt_vs_concurrency(sample_parquet).layout.paper_bgcolor == CREAM


def test_fig_rt_vs_concurrency_plot_bgcolor_is_white(sample_parquet: Path) -> None:
    assert fig_rt_vs_concurrency(sample_parquet).layout.plot_bgcolor == WHITE


def test_fig_rt_vs_concurrency_has_data(sample_parquet: Path) -> None:
    fig = fig_rt_vs_concurrency(sample_parquet)
    assert len(fig.data) >= 1


def test_fig_rt_vs_concurrency_is_json_serializable(sample_parquet: Path) -> None:
    json_str = fig_rt_vs_concurrency(sample_parquet).to_json()
    assert json.loads(json_str) is not None


def test_fig_rt_vs_concurrency_with_errors(sample_parquet_with_errors: Path) -> None:
    assert isinstance(fig_rt_vs_concurrency(sample_parquet_with_errors), go.Figure)


def test_fig_rt_vs_concurrency_with_slow_data(sample_parquet_slow: Path) -> None:
    assert isinstance(fig_rt_vs_concurrency(sample_parquet_slow), go.Figure)


def test_fig_rt_vs_concurrency_first_trace_is_scatter(sample_parquet: Path) -> None:
    fig = fig_rt_vs_concurrency(sample_parquet)
    assert type(fig.data[0]).__name__ == "Scatter"


def test_fig_rt_vs_concurrency_scatter_mode(sample_parquet: Path) -> None:
    fig = fig_rt_vs_concurrency(sample_parquet)
    assert "markers" in fig.data[0].mode


def test_fig_rt_vs_concurrency_custom_bucket(sample_parquet: Path) -> None:
    assert isinstance(fig_rt_vs_concurrency(sample_parquet, bucket_seconds=5), go.Figure)


# ---------------------------------------------------------------------------
# Fig 12 — RT vs Time by Status
# ---------------------------------------------------------------------------


def test_fig_rt_vs_time_by_status_returns_figure(sample_parquet: Path) -> None:
    assert isinstance(fig_rt_vs_time_by_status(sample_parquet), go.Figure)


def test_fig_rt_vs_time_by_status_paper_bgcolor_is_cream(sample_parquet: Path) -> None:
    assert fig_rt_vs_time_by_status(sample_parquet).layout.paper_bgcolor == CREAM


def test_fig_rt_vs_time_by_status_plot_bgcolor_is_white(sample_parquet: Path) -> None:
    assert fig_rt_vs_time_by_status(sample_parquet).layout.plot_bgcolor == WHITE


def test_fig_rt_vs_time_by_status_has_data(sample_parquet: Path) -> None:
    fig = fig_rt_vs_time_by_status(sample_parquet)
    assert len(fig.data) >= 1


def test_fig_rt_vs_time_by_status_is_json_serializable(sample_parquet: Path) -> None:
    json_str = fig_rt_vs_time_by_status(sample_parquet).to_json()
    assert json.loads(json_str) is not None


def test_fig_rt_vs_time_by_status_with_errors(sample_parquet_with_errors: Path) -> None:
    fig = fig_rt_vs_time_by_status(sample_parquet_with_errors)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 2  # success + error groups


def test_fig_rt_vs_time_by_status_with_slow_data(sample_parquet_slow: Path) -> None:
    assert isinstance(fig_rt_vs_time_by_status(sample_parquet_slow), go.Figure)


def test_fig_rt_vs_time_by_status_success_group_present(sample_parquet: Path) -> None:
    fig = fig_rt_vs_time_by_status(sample_parquet)
    names = {trace.name for trace in fig.data}
    assert "Success" in names


def test_fig_rt_vs_time_by_status_all_scatter_traces(sample_parquet: Path) -> None:
    fig = fig_rt_vs_time_by_status(sample_parquet)
    for trace in fig.data:
        assert type(trace).__name__ == "Scatter"


def test_fig_rt_vs_time_by_status_sampling_note(tmp_path: Path) -> None:
    """Test that very large datasets get a sampling note in the title."""
    import polars as pl

    n = 60_000
    base_ts = 1_700_000_000_000
    df = pl.DataFrame(
        {
            "timestamp_ms": [base_ts + i * 10 for i in range(n)],
            "elapsed": [200] * n,
            "label": ["L"] * n,
            "response_code": ["200"] * n,
            "success": [True] * n,
            "bytes": [1024] * n,
            "sent_bytes": [256] * n,
            "grp_threads": [10] * n,
            "all_threads": [10] * n,
            "url": ["http://example.com"] * n,
            "latency": [190] * n,
            "idle_time": [0] * n,
            "connect": [10] * n,
            "response_message": ["OK"] * n,
            "thread_name": ["T-1"] * n,
            "failure_message": [""] * n,
        }
    )
    p = tmp_path / "large.parquet"
    df.write_parquet(p)
    fig = fig_rt_vs_time_by_status(p)
    assert "sampled" in fig.layout.title.text.lower()


# ---------------------------------------------------------------------------
# Fig 13 — Correlation Matrix
# ---------------------------------------------------------------------------


def test_fig_correlation_matrix_returns_figure(sample_parquet: Path) -> None:
    assert isinstance(fig_correlation_matrix(sample_parquet), go.Figure)


def test_fig_correlation_matrix_paper_bgcolor_is_cream(sample_parquet: Path) -> None:
    assert fig_correlation_matrix(sample_parquet).layout.paper_bgcolor == CREAM


def test_fig_correlation_matrix_plot_bgcolor_is_white(sample_parquet: Path) -> None:
    assert fig_correlation_matrix(sample_parquet).layout.plot_bgcolor == WHITE


def test_fig_correlation_matrix_is_json_serializable(sample_parquet: Path) -> None:
    json_str = fig_correlation_matrix(sample_parquet).to_json()
    assert json.loads(json_str) is not None


def test_fig_correlation_matrix_first_trace_is_heatmap(sample_parquet: Path) -> None:
    fig = fig_correlation_matrix(sample_parquet)
    assert type(fig.data[0]).__name__ == "Heatmap"


def test_fig_correlation_matrix_with_errors(sample_parquet_with_errors: Path) -> None:
    assert isinstance(fig_correlation_matrix(sample_parquet_with_errors), go.Figure)


def test_fig_correlation_matrix_6x6_shape(sample_parquet: Path) -> None:
    fig = fig_correlation_matrix(sample_parquet)
    hm = fig.data[0]
    assert len(hm.x) == 6
    assert len(hm.y) == 6


def test_fig_correlation_matrix_diagonal_is_one(sample_parquet: Path) -> None:
    fig = fig_correlation_matrix(sample_parquet)
    hm = fig.data[0]
    z = hm.z
    for i in range(6):
        assert abs(z[i][i] - 1.0) < 1e-6


def test_fig_correlation_matrix_values_bounded(sample_parquet: Path) -> None:
    fig = fig_correlation_matrix(sample_parquet)
    hm = fig.data[0]
    for row in hm.z:
        for val in row:
            # Allow tiny floating-point overshoot (e.g. 1.0000000000000002)
            assert -1.01 <= val <= 1.01


def test_fig_correlation_matrix_with_slow_data(sample_parquet_slow: Path) -> None:
    assert isinstance(fig_correlation_matrix(sample_parquet_slow), go.Figure)
