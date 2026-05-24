"""Unit tests for HTML export functionality."""

from pathlib import Path


def test_generate_html_report_creates_file(tmp_path: Path, sample_parquet: Path) -> None:
    from perfsage.core.export.html import generate_html_report

    output = tmp_path / "report.html"
    result = generate_html_report(sample_parquet, "Test Report", output)
    assert result == output
    assert output.exists()
    content = output.read_text()
    assert "PerfSage" in content
    assert "Test Report" in content


def test_html_report_contains_plotly_script(tmp_path: Path, sample_parquet: Path) -> None:
    from perfsage.core.export.html import generate_html_report

    output = tmp_path / "report.html"
    generate_html_report(sample_parquet, "Test", output)
    content = output.read_text()
    assert "plotly" in content.lower()


def test_html_report_contains_charts(tmp_path: Path, sample_parquet: Path) -> None:
    from perfsage.core.export.html import generate_html_report

    output = tmp_path / "report.html"
    generate_html_report(sample_parquet, "Test", output)
    content = output.read_text()
    assert "Plotly.newPlot" in content or "fig-rt-time" in content


def test_html_report_with_missing_parquet(tmp_path: Path) -> None:
    from perfsage.core.export.html import generate_html_report

    output = tmp_path / "report.html"
    result = generate_html_report(Path("/nonexistent.parquet"), "Test", output)
    assert output.exists()
    assert result == output


def test_html_report_contains_all_chart_divs(tmp_path: Path, sample_parquet: Path) -> None:
    from perfsage.core.export.html import _FIGURES, generate_html_report

    output = tmp_path / "report.html"
    generate_html_report(sample_parquet, "Charts Test", output)
    content = output.read_text()
    for fig_id, _ in _FIGURES:
        assert fig_id in content, f"Expected chart div id '{fig_id}' not found in HTML"


def test_html_report_contains_summary_table(tmp_path: Path, sample_parquet: Path) -> None:
    from perfsage.core.export.html import generate_html_report

    output = tmp_path / "report.html"
    generate_html_report(sample_parquet, "Summary Test", output)
    content = output.read_text()
    # Summary table headers
    assert "Label" in content
    assert "Count" in content


def test_html_report_contains_recommendations_section(
    tmp_path: Path, sample_parquet: Path
) -> None:
    from perfsage.core.export.html import generate_html_report

    output = tmp_path / "report.html"
    generate_html_report(sample_parquet, "Rec Test", output)
    content = output.read_text()
    # Either recommendations section heading or "no issues" message
    assert "Recommendations" in content or "No issues" in content


def test_html_report_is_valid_html(tmp_path: Path, sample_parquet: Path) -> None:
    from perfsage.core.export.html import generate_html_report

    output = tmp_path / "report.html"
    generate_html_report(sample_parquet, "HTML Valid", output)
    content = output.read_text()
    assert content.startswith("<!DOCTYPE html>")
    assert "</html>" in content


def test_html_report_returns_output_path(tmp_path: Path, sample_parquet: Path) -> None:
    from perfsage.core.export.html import generate_html_report

    output = tmp_path / "sub" / "report.html"
    result = generate_html_report(sample_parquet, "Path Test", output)
    assert result == output
    assert output.exists()


def test_html_report_with_slo_config(tmp_path: Path, sample_parquet: Path) -> None:
    from perfsage.core.analysis.slo import SLOConfig
    from perfsage.core.export.html import generate_html_report

    slo = SLOConfig(p90_ms=500.0, p99_ms=1000.0, error_rate_pct=1.0)
    output = tmp_path / "report_slo.html"
    result = generate_html_report(sample_parquet, "SLO Test", output, slo_config=slo)
    assert result == output
    assert output.exists()


def test_html_report_embeds_cdn_link(tmp_path: Path, sample_parquet: Path) -> None:
    from perfsage.core.export.html import PLOTLY_CDN, generate_html_report

    output = tmp_path / "report.html"
    generate_html_report(sample_parquet, "CDN Test", output)
    content = output.read_text()
    assert PLOTLY_CDN in content


def test_html_report_contains_timestamp(tmp_path: Path, sample_parquet: Path) -> None:
    from perfsage.core.export.html import generate_html_report

    output = tmp_path / "report.html"
    generate_html_report(sample_parquet, "Timestamp Test", output)
    content = output.read_text()
    assert "Generated" in content and "UTC" in content
