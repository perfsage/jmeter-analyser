"""Unit tests for HTML export functionality."""

from pathlib import Path

import pytest


def test_html_report_with_missing_parquet(tmp_path: Path) -> None:
    from perfsage.core.export.html import generate_html_report

    output = tmp_path / "report.html"
    result = generate_html_report(Path("/nonexistent.parquet"), "Test", output)
    assert output.exists()
    assert result == output
    content = output.read_text()
    assert "export-footer" in content


def test_html_export_footer_helper() -> None:
    from perfsage.core.export.html import _render_export_footer

    html = _render_export_footer("2026-01-01 00:00 UTC")
    assert "export-footer" in html
    assert "PerfSage" in html
    assert '<footer' not in html


@pytest.mark.slow
def test_generate_html_report_full(tmp_path: Path, sample_parquet: Path) -> None:
    """Single integration test covering HTML export structure (29 charts + inline Plotly)."""
    from perfsage.core.analysis.slo import SLOConfig
    from perfsage.core.export.html import generate_html_report
    from perfsage.core.viz.registry import EXPORT_FIGURES

    slo = SLOConfig(p90_ms=500.0, p99_ms=1000.0, error_rate_pct=1.0)
    output = tmp_path / "report.html"
    result = generate_html_report(sample_parquet, "Test Report", output, slo_config=slo)
    assert result == output
    assert output.exists()

    content = output.read_text()
    assert content.startswith("<!DOCTYPE html>")
    assert "PerfSage" in content
    assert "Test Report" in content
    assert "Plotly.newPlot" in content
    assert "cdn.plot.ly" not in content
    assert "export-footer" in content
    assert '<footer' not in content
    assert "Label" in content and "Count" in content
    assert "Recommendations" in content or "No issues" in content
    assert "Generated" in content and "UTC" in content
    for fig_id, _ in EXPORT_FIGURES:
        assert fig_id in content, f"Missing chart div '{fig_id}'"
