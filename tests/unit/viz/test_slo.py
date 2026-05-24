"""Tests for perfsage.core.viz.slo (Figs 16, 17, 19)."""

from __future__ import annotations

import json
from pathlib import Path

import plotly.graph_objects as go

from perfsage.core.analysis.slo import SLOConfig
from perfsage.core.viz.slo import (
    fig_apdex_by_label,
    fig_error_sunburst,
    fig_slo_gauges,
)

CREAM = "#F6F1E7"
WHITE = "#FFFFFF"


# ---------------------------------------------------------------------------
# Fig 16 — SLO Gauges
# ---------------------------------------------------------------------------


def test_fig_slo_gauges_returns_figure(sample_parquet: Path) -> None:
    assert isinstance(fig_slo_gauges(sample_parquet), go.Figure)


def test_fig_slo_gauges_paper_bgcolor_is_cream(sample_parquet: Path) -> None:
    assert fig_slo_gauges(sample_parquet).layout.paper_bgcolor == CREAM


def test_fig_slo_gauges_has_three_indicators(sample_parquet: Path) -> None:
    fig = fig_slo_gauges(sample_parquet)
    indicator_traces = [t for t in fig.data if type(t).__name__ == "Indicator"]
    assert len(indicator_traces) == 3


def test_fig_slo_gauges_is_json_serializable(sample_parquet: Path) -> None:
    json_str = fig_slo_gauges(sample_parquet).to_json()
    assert json.loads(json_str) is not None


def test_fig_slo_gauges_with_errors(sample_parquet_with_errors: Path) -> None:
    assert isinstance(fig_slo_gauges(sample_parquet_with_errors), go.Figure)


def test_fig_slo_gauges_with_slow_data(sample_parquet_slow: Path) -> None:
    assert isinstance(fig_slo_gauges(sample_parquet_slow), go.Figure)


def test_fig_slo_gauges_with_custom_slo_config(sample_parquet: Path) -> None:
    cfg = SLOConfig(p90_ms=500.0, p99_ms=2000.0, error_rate_pct=0.5, apdex_t=1.0)
    fig = fig_slo_gauges(sample_parquet, slo_config=cfg)
    assert isinstance(fig, go.Figure)


def test_fig_slo_gauges_indicator_titles(sample_parquet: Path) -> None:
    fig = fig_slo_gauges(sample_parquet)
    titles = [t.title.text for t in fig.data if hasattr(t, "title")]
    assert any("APDEX" in (t or "") for t in titles)
    assert any("Error Rate" in (t or "") for t in titles)
    assert any("p99" in (t or "") or "Latency" in (t or "") for t in titles)


def test_fig_slo_gauges_apdex_in_0_to_1(sample_parquet: Path) -> None:
    fig = fig_slo_gauges(sample_parquet)
    apdex_trace = fig.data[0]
    assert apdex_trace.value is not None
    assert 0.0 <= float(apdex_trace.value) <= 1.0


def test_fig_slo_gauges_with_spike_data(sample_parquet_with_spike: Path) -> None:
    assert isinstance(fig_slo_gauges(sample_parquet_with_spike), go.Figure)


# ---------------------------------------------------------------------------
# Fig 17 — APDEX by Label
# ---------------------------------------------------------------------------


def test_fig_apdex_by_label_returns_figure(sample_parquet: Path) -> None:
    assert isinstance(fig_apdex_by_label(sample_parquet), go.Figure)


def test_fig_apdex_by_label_paper_bgcolor_is_cream(sample_parquet: Path) -> None:
    assert fig_apdex_by_label(sample_parquet).layout.paper_bgcolor == CREAM


def test_fig_apdex_by_label_plot_bgcolor_is_white(sample_parquet: Path) -> None:
    assert fig_apdex_by_label(sample_parquet).layout.plot_bgcolor == WHITE


def test_fig_apdex_by_label_has_data(sample_parquet: Path) -> None:
    fig = fig_apdex_by_label(sample_parquet)
    assert len(fig.data) >= 1


def test_fig_apdex_by_label_is_json_serializable(sample_parquet: Path) -> None:
    json_str = fig_apdex_by_label(sample_parquet).to_json()
    assert json.loads(json_str) is not None


def test_fig_apdex_by_label_first_trace_is_bar(sample_parquet: Path) -> None:
    fig = fig_apdex_by_label(sample_parquet)
    assert type(fig.data[0]).__name__ == "Bar"


def test_fig_apdex_by_label_horizontal_orientation(sample_parquet: Path) -> None:
    fig = fig_apdex_by_label(sample_parquet)
    assert fig.data[0].orientation == "h"


def test_fig_apdex_by_label_with_errors(sample_parquet_with_errors: Path) -> None:
    assert isinstance(fig_apdex_by_label(sample_parquet_with_errors), go.Figure)


def test_fig_apdex_by_label_with_slow_data(sample_parquet_slow: Path) -> None:
    assert isinstance(fig_apdex_by_label(sample_parquet_slow), go.Figure)


def test_fig_apdex_by_label_scores_in_range(sample_parquet: Path) -> None:
    fig = fig_apdex_by_label(sample_parquet)
    bar = fig.data[0]
    for val in bar.x:
        assert 0.0 <= float(val) <= 1.0


# ---------------------------------------------------------------------------
# Fig 19 — Error Sunburst
# ---------------------------------------------------------------------------


def test_fig_error_sunburst_returns_figure(sample_parquet: Path) -> None:
    # All success — should return an empty graceful figure
    assert isinstance(fig_error_sunburst(sample_parquet), go.Figure)


def test_fig_error_sunburst_paper_bgcolor_is_cream(sample_parquet: Path) -> None:
    assert fig_error_sunburst(sample_parquet).layout.paper_bgcolor == CREAM


def test_fig_error_sunburst_is_json_serializable(sample_parquet: Path) -> None:
    json_str = fig_error_sunburst(sample_parquet).to_json()
    assert json.loads(json_str) is not None


def test_fig_error_sunburst_no_errors_graceful(sample_parquet: Path) -> None:
    fig = fig_error_sunburst(sample_parquet)
    assert isinstance(fig, go.Figure)
    # Either empty data or a valid sunburst — both are acceptable
    if fig.data:
        assert type(fig.data[0]).__name__ == "Sunburst"


def test_fig_error_sunburst_with_errors_has_sunburst(
    sample_parquet_with_errors: Path,
) -> None:
    fig = fig_error_sunburst(sample_parquet_with_errors)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1
    assert type(fig.data[0]).__name__ == "Sunburst"


def test_fig_error_sunburst_with_errors_has_response_codes(
    sample_parquet_with_errors: Path,
) -> None:
    fig = fig_error_sunburst(sample_parquet_with_errors)
    sunburst = fig.data[0]
    # "500" should be in the ids (inner ring response code)
    assert "500" in list(sunburst.ids)


def test_fig_error_sunburst_with_error_data_has_labels(
    sample_parquet_with_errors: Path,
) -> None:
    fig = fig_error_sunburst(sample_parquet_with_errors)
    sunburst = fig.data[0]
    assert len(sunburst.labels) > 0


def test_fig_error_sunburst_with_slow_data(sample_parquet_slow: Path) -> None:
    # slow data has no errors
    fig = fig_error_sunburst(sample_parquet_slow)
    assert isinstance(fig, go.Figure)


def test_fig_error_sunburst_values_positive(sample_parquet_with_errors: Path) -> None:
    fig = fig_error_sunburst(sample_parquet_with_errors)
    sunburst = fig.data[0]
    for v in sunburst.values:
        assert int(v) >= 0
