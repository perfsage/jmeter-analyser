"""Unit tests for PDF export functionality."""

import os
import time
from pathlib import Path
from unittest.mock import patch

import plotly.graph_objects as go
import pytest


@pytest.mark.slow
@pytest.mark.timeout(180)
def test_generate_pdf_report_creates_file(tmp_path: Path, sample_parquet: Path) -> None:
    from perfsage.core.export.pdf import generate_pdf_report

    output = tmp_path / "report.pdf"
    result = generate_pdf_report(sample_parquet, "Test Report", output)
    assert result == output
    assert output.exists()
    assert output.read_bytes()[:4] == b"%PDF"


def test_pdf_report_with_missing_parquet(tmp_path: Path) -> None:
    from perfsage.core.export.pdf import generate_pdf_report

    output = tmp_path / "report.pdf"
    result = generate_pdf_report(Path("/nonexistent.parquet"), "Test", output)
    assert output.exists()
    assert result == output
    assert output.read_bytes()[:4] == b"%PDF"


def test_pdf_build_html_includes_chart_img(tmp_path: Path, sample_parquet: Path) -> None:
    from perfsage.core.export import pdf as pdf_mod

    png = tmp_path / "fig-rt-scatter.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 100)
    chart_imgs = [("fig-rt-scatter", "RT Scatter", png)]
    html = pdf_mod._build_html_for_tests(sample_parquet, "Test", "2026-01-01", chart_imgs, None, 1)
    assert '<img class="chart"' in html
    assert "Chart not available." not in html


def test_pdf_fig_to_png_path_handles_failure(tmp_path: Path) -> None:
    import kaleido

    from perfsage.core.export.pdf import _fig_to_png_path

    bad_fig = go.Figure()
    with patch.object(kaleido, "write_fig_sync", side_effect=RuntimeError("kaleido down")):
        assert _fig_to_png_path(bad_fig, tmp_path, "bad") is None


def test_pdf_fig_to_png_path_validates_header(tmp_path: Path) -> None:
    import kaleido

    from perfsage.core.export.pdf import _fig_to_png_path

    fig = go.Figure(data=[go.Scatter(x=[1], y=[1])])
    png = tmp_path / "ok.png"
    png.write_bytes(b"NOTPNG")

    def _write_bad_png(*_args: object, **_kwargs: object) -> None:
        png.write_bytes(b"NOTPNG")

    with patch.object(kaleido, "write_fig_sync", side_effect=_write_bad_png):
        assert _fig_to_png_path(fig, tmp_path, "ok") is None


def test_ensure_kaleido_browser_sets_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from perfsage.core.export import pdf as pdf_mod

    browser = tmp_path / "chromium"
    browser.write_text("#!/bin/sh\n", encoding="utf-8")
    browser.chmod(0o755)
    saved = {k: os.environ.get(k) for k in ("BROWSER_PATH", "CHROME_PATH")}
    monkeypatch.delenv("BROWSER_PATH", raising=False)
    monkeypatch.delenv("CHROME_PATH", raising=False)
    monkeypatch.setattr(pdf_mod.shutil, "which", lambda _name: str(browser))
    try:
        pdf_mod._ensure_kaleido_browser()
        assert Path(os.environ["BROWSER_PATH"]).is_file()
        assert os.environ["CHROME_PATH"] == os.environ["BROWSER_PATH"]
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _weasyprint_available() -> bool:
    try:
        import weasyprint

        weasyprint.HTML(string="<html><body>x</body></html>").write_pdf()
        return True
    except Exception:
        return False


@pytest.mark.slow
@pytest.mark.timeout(180)
def test_render_chart_pngs_batch(tmp_path: Path, sample_parquet: Path) -> None:
    """Kaleido batch render must reuse one browser (not ~2.5 s per chart)."""
    from perfsage.core.export.pdf import render_chart_pngs
    from perfsage.core.viz.registry import build_figure_objects

    objs = build_figure_objects(sample_parquet, None)
    png_dir = tmp_path / "pngs"
    png_dir.mkdir()

    started = time.perf_counter()
    chart_imgs, rendered = render_chart_pngs(objs, png_dir)
    elapsed = time.perf_counter() - started

    assert rendered >= 25, f"expected most charts rendered, got {rendered}/29"
    assert elapsed < 45, f"batch render took {elapsed:.1f}s — browser likely restarted per chart"
    for _fig_id, _title, png_path in chart_imgs:
        if png_path is not None:
            assert png_path.read_bytes().startswith(b"\x89PNG")


@pytest.mark.slow
@pytest.mark.timeout(180)
@pytest.mark.skipif(not _weasyprint_available(), reason="WeasyPrint system libraries not installed")
def test_generate_pdf_report_embeds_chart_images(tmp_path: Path, sample_parquet: Path) -> None:
    from perfsage.core.export.pdf import generate_pdf_report

    output = tmp_path / "report.pdf"
    generate_pdf_report(sample_parquet, "Chart Test", output)
    content = output.read_bytes()
    assert content[:4] == b"%PDF"
    assert b"Chart rendering failed" not in content
    assert b"Chart not available." not in content
    assert len(content) > 100_000, "PDF too small — chart images likely missing"
