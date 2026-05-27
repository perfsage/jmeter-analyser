"""Tests for central figure registry."""

from pathlib import Path


def test_build_figure_objects_returns_all_export_ids(sample_parquet: Path) -> None:
    from perfsage.core.viz.registry import EXPORT_FIGURES, build_figure_objects

    objs = build_figure_objects(sample_parquet, None)
    export_ids = {fid for fid, _ in EXPORT_FIGURES}
    assert set(objs.keys()) == export_ids
    assert sum(1 for v in objs.values() if v is not None) >= len(EXPORT_FIGURES) // 2


def test_build_figures_json_serializes(sample_parquet: Path) -> None:
    from perfsage.core.analysis.slo import SLOConfig
    from perfsage.core.viz.registry import build_figures_json

    slo = SLOConfig(p90_ms=500.0, p99_ms=1000.0, error_rate_pct=1.0)
    figs = build_figures_json(sample_parquet, slo)
    assert "fig-rt-scatter" in figs
    assert figs["fig-rt-scatter"] is not None
    assert "data" in figs["fig-rt-scatter"]
