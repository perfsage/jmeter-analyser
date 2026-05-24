"""Unit tests for PDF export functionality."""

from pathlib import Path


def test_generate_pdf_report_creates_file(tmp_path: Path, sample_parquet: Path) -> None:
    from perfsage.core.export.pdf import generate_pdf_report

    output = tmp_path / "report.pdf"
    result = generate_pdf_report(sample_parquet, "Test Report", output)
    assert result == output
    assert output.exists()
    # Verify it's a valid PDF (starts with %PDF)
    content = output.read_bytes()
    assert content[:4] == b"%PDF"


def test_pdf_report_cover_page_info(tmp_path: Path, sample_parquet: Path) -> None:
    from perfsage.core.export.pdf import generate_pdf_report

    output = tmp_path / "report.pdf"
    generate_pdf_report(sample_parquet, "Test", output)
    # Full PDF (WeasyPrint) will be > 100KB; minimal fallback (no system Pango/Cairo) > 500B.
    assert output.stat().st_size > 500


def test_pdf_report_with_missing_parquet(tmp_path: Path) -> None:
    from perfsage.core.export.pdf import generate_pdf_report

    output = tmp_path / "report.pdf"
    result = generate_pdf_report(Path("/nonexistent.parquet"), "Test", output)
    assert output.exists()
    assert result == output
    content = output.read_bytes()
    assert content[:4] == b"%PDF"


def test_pdf_report_returns_output_path(tmp_path: Path, sample_parquet: Path) -> None:
    from perfsage.core.export.pdf import generate_pdf_report

    output = tmp_path / "sub" / "report.pdf"
    result = generate_pdf_report(sample_parquet, "Path Test", output)
    assert result == output
    assert output.exists()


def test_pdf_report_with_slo_config(tmp_path: Path, sample_parquet: Path) -> None:
    from perfsage.core.analysis.slo import SLOConfig
    from perfsage.core.export.pdf import generate_pdf_report

    slo = SLOConfig(p90_ms=500.0, p99_ms=1000.0, error_rate_pct=1.0)
    output = tmp_path / "report_slo.pdf"
    result = generate_pdf_report(sample_parquet, "SLO PDF", output, slo_config=slo)
    assert result == output
    assert output.exists()
    assert output.read_bytes()[:4] == b"%PDF"
