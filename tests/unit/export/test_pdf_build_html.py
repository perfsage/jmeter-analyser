"""Unit tests for PDF HTML builder."""

from pathlib import Path

from perfsage.core.export.pdf import _build_html_for_tests


def test_build_html_embeds_file_uri(tmp_path: Path) -> None:
    png = tmp_path / "fig-rt-time.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n")
    chart_imgs = [
        ("fig-rt-time", "Response Time", png),
        ("fig-throughput", "Throughput", None),
    ]
    html = _build_html_for_tests(
        Path("/nonexistent.parquet"),
        "Test Report",
        "2026-01-01 00:00 UTC",
        chart_imgs,
        None,
        1,
    )
    assert png.resolve().as_uri() in html
    assert "pdf-footer" in html
    assert "Chart not available." in html
