"""Tests for perfsage.core.viz.tables (Figs 18, 20)."""

from __future__ import annotations

import json
from pathlib import Path

import plotly.graph_objects as go

from perfsage.core.viz.tables import (
    fig_slowest_transactions,
    fig_variability_chart,
)

CREAM = "#F6F1E7"
WHITE = "#FFFFFF"


# ---------------------------------------------------------------------------
# Fig 18 — Slowest Transactions
# ---------------------------------------------------------------------------


def test_fig_slowest_transactions_returns_figure(sample_parquet: Path) -> None:
    assert isinstance(fig_slowest_transactions(sample_parquet), go.Figure)


def test_fig_slowest_transactions_paper_bgcolor_is_cream(sample_parquet: Path) -> None:
    assert fig_slowest_transactions(sample_parquet).layout.paper_bgcolor == CREAM


def test_fig_slowest_transactions_is_json_serializable(sample_parquet: Path) -> None:
    json_str = fig_slowest_transactions(sample_parquet).to_json()
    assert json.loads(json_str) is not None


def test_fig_slowest_transactions_first_trace_is_table(sample_parquet: Path) -> None:
    fig = fig_slowest_transactions(sample_parquet)
    assert len(fig.data) >= 1
    assert type(fig.data[0]).__name__ == "Table"


def test_fig_slowest_transactions_with_errors(sample_parquet_with_errors: Path) -> None:
    assert isinstance(fig_slowest_transactions(sample_parquet_with_errors), go.Figure)


def test_fig_slowest_transactions_with_slow_data(sample_parquet_slow: Path) -> None:
    assert isinstance(fig_slowest_transactions(sample_parquet_slow), go.Figure)


def test_fig_slowest_transactions_custom_top_n(sample_parquet: Path) -> None:
    fig = fig_slowest_transactions(sample_parquet, top_n=5)
    assert isinstance(fig, go.Figure)
    table = fig.data[0]
    # 5 rows in each column
    assert len(list(table.cells.values[0])) == 5


def test_fig_slowest_transactions_default_top_20(sample_parquet: Path) -> None:
    fig = fig_slowest_transactions(sample_parquet, top_n=20)
    table = fig.data[0]
    # sample_parquet has 100 rows; all columns should have min(20, 100) rows
    assert len(list(table.cells.values[0])) == 20


def test_fig_slowest_transactions_has_5_columns(sample_parquet: Path) -> None:
    fig = fig_slowest_transactions(sample_parquet)
    table = fig.data[0]
    assert len(list(table.header.values)) == 5


def test_fig_slowest_transactions_header_column_names(sample_parquet: Path) -> None:
    fig = fig_slowest_transactions(sample_parquet)
    table = fig.data[0]
    headers = list(table.header.values)
    assert "Label" in headers
    assert "Elapsed (ms)" in headers


def test_fig_slowest_transactions_sorted_by_elapsed_desc(sample_parquet: Path) -> None:
    fig = fig_slowest_transactions(sample_parquet, top_n=10)
    table = fig.data[0]
    elapsed_vals = [int(v) for v in table.cells.values[2]]
    assert elapsed_vals == sorted(elapsed_vals, reverse=True)


def test_fig_slowest_transactions_url_truncated(sample_parquet: Path) -> None:
    fig = fig_slowest_transactions(sample_parquet)
    table = fig.data[0]
    urls = list(table.cells.values[4])
    for url in urls:
        assert len(str(url)) <= 62  # 60 chars + "…"


# ---------------------------------------------------------------------------
# Fig 20 — Variability Chart
# ---------------------------------------------------------------------------


def test_fig_variability_chart_returns_figure(sample_parquet: Path) -> None:
    assert isinstance(fig_variability_chart(sample_parquet), go.Figure)


def test_fig_variability_chart_paper_bgcolor_is_cream(sample_parquet: Path) -> None:
    assert fig_variability_chart(sample_parquet).layout.paper_bgcolor == CREAM


def test_fig_variability_chart_plot_bgcolor_is_white(sample_parquet: Path) -> None:
    assert fig_variability_chart(sample_parquet).layout.plot_bgcolor == WHITE


def test_fig_variability_chart_has_data(sample_parquet: Path) -> None:
    fig = fig_variability_chart(sample_parquet)
    assert len(fig.data) >= 1


def test_fig_variability_chart_is_json_serializable(sample_parquet: Path) -> None:
    json_str = fig_variability_chart(sample_parquet).to_json()
    assert json.loads(json_str) is not None


def test_fig_variability_chart_first_trace_is_bar(sample_parquet: Path) -> None:
    fig = fig_variability_chart(sample_parquet)
    assert type(fig.data[0]).__name__ == "Bar"


def test_fig_variability_chart_with_errors(sample_parquet_with_errors: Path) -> None:
    assert isinstance(fig_variability_chart(sample_parquet_with_errors), go.Figure)


def test_fig_variability_chart_with_slow_data(sample_parquet_slow: Path) -> None:
    assert isinstance(fig_variability_chart(sample_parquet_slow), go.Figure)


def test_fig_variability_chart_cv_values_non_negative(sample_parquet: Path) -> None:
    fig = fig_variability_chart(sample_parquet)
    bar = fig.data[0]
    for val in bar.y:
        assert float(val) >= 0.0


def test_fig_variability_chart_sorted_descending(sample_parquet: Path) -> None:
    fig = fig_variability_chart(sample_parquet)
    bar = fig.data[0]
    cv_vals = [float(v) for v in bar.y]
    assert cv_vals == sorted(cv_vals, reverse=True)


def test_fig_variability_chart_label_per_bar(sample_parquet: Path) -> None:
    import polars as pl

    raw = pl.read_parquet(sample_parquet)
    n_labels = raw["label"].n_unique()
    fig = fig_variability_chart(sample_parquet)
    bar = fig.data[0]
    assert len(bar.x) == n_labels
