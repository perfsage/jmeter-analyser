"""Generate PDF report using WeasyPrint + kaleido for static chart images."""

from __future__ import annotations

import logging
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from perfsage.core.analysis.slo import SLOConfig
from perfsage.core.viz.registry import EXPORT_FIGURES, build_figure_objects

logger = logging.getLogger(__name__)

_PDF_CSS = """
@page { size: A4; margin: 1.5cm 2cm; }
@page :first { margin: 0; }
body { font-family: Arial, sans-serif; color: #0B1F3A; margin: 0; padding: 0; font-size: 10pt; }
.cover {
  height: 29.7cm;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 4cm;
  background: #0B1F3A;
  color: #F6F1E7;
}
.cover h1 { font-size: 2rem; margin-bottom: 1rem; color: #D4A857; }
.cover p { font-size: 1rem; margin: 0.25rem 0; opacity: 0.9; }
.page-break { page-break-after: always; }
.section-title { font-size: 14pt; font-weight: bold; color: #0B1F3A; margin: 1rem 0 0.5rem; border-bottom: 2px solid #D4A857; padding-bottom: 4px; }
img.chart { width: 100%; border: 1px solid #E2E8F0; margin-bottom: 0.75cm; display: block; }
.chart-title { font-size: 10pt; font-weight: bold; color: #0B1F3A; margin-bottom: 4px; }
.chart-pair { page-break-inside: avoid; margin-bottom: 0.5cm; }
table.summary-table { width: 100%; border-collapse: collapse; font-size: 8pt; margin-bottom: 1cm; }
table.summary-table th { background: #0B1F3A; color: #F6F1E7; padding: 4px 6px; text-align: left; }
table.summary-table td { padding: 4px 6px; border-bottom: 1px solid #E2E8F0; }
.rec { padding: 6px 10px; margin-bottom: 6px; border-radius: 3px; font-size: 9pt; }
.rec-critical { background: #FED7D7; color: #742A2A; border-left: 3px solid #E53E3E; }
.rec-warning { background: #FEF3C7; color: #92400E; border-left: 3px solid #ECC94B; }
.rec-info { background: #EBF8FF; color: #2A4365; border-left: 3px solid #3182CE; }
.kpi-grid { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 1cm; }
.kpi-card { border: 1px solid #E2E8F0; border-radius: 4px; padding: 8px 16px; min-width: 80px; text-align: center; }
.kpi-value { font-size: 1.25rem; font-weight: bold; color: #0B1F3A; }
.kpi-label { font-size: 8pt; color: #64748B; }
.pdf-footer { text-align: center; font-size: 8pt; color: #64748B; margin-top: 1cm; border-top: 1px solid #E2E8F0; padding-top: 6px; }
"""


def _ensure_kaleido_browser() -> None:
    """Configure kaleido/choreographer to use system Chromium (Docker + local)."""
    import os
    import shutil

    candidates = [
        os.environ.get("BROWSER_PATH"),
        os.environ.get("CHROME_PATH"),
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
    ]
    browser = next((p for p in candidates if p and Path(p).is_file()), None)
    if browser is None:
        browser = (
            shutil.which("chromium")
            or shutil.which("chromium-browser")
            or shutil.which("google-chrome")
        )
    if browser:
        os.environ["BROWSER_PATH"] = browser
        os.environ["CHROME_PATH"] = browser


def _fig_to_png_path(fig: object, tmp_dir: Path, fig_id: str) -> Path | None:
    """Render a Plotly figure to PNG on disk for WeasyPrint embedding."""
    try:
        import kaleido
        import plotly.graph_objects as go

        from perfsage.core.export._kaleido_session import (
            kaleido_process_lock,
            managed_kaleido_server,
        )

        if not isinstance(fig, go.Figure):
            return None

        _ensure_kaleido_browser()

        png_path = tmp_dir / f"{fig_id}.png"
        opts = {"format": "png", "width": 900, "height": 400, "scale": 1.5}
        with kaleido_process_lock(), managed_kaleido_server():
            kaleido.write_fig_sync(fig, path=str(png_path), opts=opts)
        png_bytes = png_path.read_bytes()
        if not png_bytes.startswith(b"\x89PNG"):
            logger.warning("PDF: invalid PNG header for %s", fig_id)
            return None
        return png_path
    except Exception as exc:
        logger.warning("PDF: kaleido failed for %s: %s", fig_id, exc)
        return None


def render_chart_pngs(
    figure_objs: dict[str, object | None],
    tmp_dir: Path,
) -> tuple[list[tuple[str, str, Path | None]], int]:
    """Render all export figures to PNG in one Kaleido browser session."""
    import kaleido
    import plotly.graph_objects as go

    from perfsage.core.export._kaleido_session import (
        kaleido_process_lock,
        managed_kaleido_server,
    )

    _ensure_kaleido_browser()

    chart_imgs: list[tuple[str, str, Path | None]] = []
    fig_dicts: list[dict[str, object]] = []
    pending: list[tuple[str, str, Path]] = []

    for fig_id, fig_title in EXPORT_FIGURES:
        fig = figure_objs.get(fig_id)
        if fig is None or not isinstance(fig, go.Figure):
            chart_imgs.append((fig_id, fig_title, None))
            continue

        png_path = tmp_dir / f"{fig_id}.png"
        fig_dicts.append(
            {
                "fig": fig,
                "path": str(png_path),
                "opts": {"format": "png", "width": 900, "height": 400, "scale": 1.5},
            }
        )
        pending.append((fig_id, fig_title, png_path))

    if fig_dicts:
        try:
            with kaleido_process_lock(), managed_kaleido_server():
                kaleido.write_fig_from_object_sync(fig_dicts)
        except Exception as exc:
            logger.warning("PDF: batch kaleido render failed: %s", exc)
            for fig_id, fig_title, _png_path in pending:
                chart_imgs.append((fig_id, fig_title, None))
            return chart_imgs, 0

    rendered = 0
    for fig_id, fig_title, png_path in pending:
        try:
            png_bytes = png_path.read_bytes()
            if png_bytes.startswith(b"\x89PNG"):
                chart_imgs.append((fig_id, fig_title, png_path))
                rendered += 1
            else:
                logger.warning("PDF: invalid PNG header for %s", fig_id)
                chart_imgs.append((fig_id, fig_title, None))
        except Exception as exc:
            logger.warning("PDF: could not read PNG for %s: %s", fig_id, exc)
            chart_imgs.append((fig_id, fig_title, None))

    return chart_imgs, rendered


def _render_summary_table(samples_path: Path) -> str:
    try:
        from perfsage.core.analysis.metrics import compute_label_summary

        df = compute_label_summary(samples_path)
        if df.is_empty():
            return "<p>No data available.</p>"

        rows_html = ""
        for row in df.to_dicts():
            err_pct = float(row.get("error_rate") or 0) * 100
            rows_html += (
                f"<tr>"
                f"<td>{row.get('label', '')}</td>"
                f"<td>{int(row.get('count', 0)):,}</td>"
                f"<td>{float(row.get('mean_elapsed', 0)):.0f}</td>"
                f"<td>{float(row.get('p50', 0)):.0f}</td>"
                f"<td>{float(row.get('p90', 0)):.0f}</td>"
                f"<td>{float(row.get('p95', 0)):.0f}</td>"
                f"<td>{float(row.get('p99', 0)):.0f}</td>"
                f"<td>{err_pct:.2f}%</td>"
                f"</tr>"
            )

        return f"""<table class="summary-table">
  <thead>
    <tr>
      <th>Label</th><th>Count</th><th>Mean (ms)</th>
      <th>p50</th><th>p90</th><th>p95</th><th>p99</th><th>Error Rate</th>
    </tr>
  </thead>
  <tbody>{rows_html}</tbody>
</table>"""
    except Exception as exc:
        logger.warning("PDF: summary table failed: %s", exc)
        return "<p>Summary table unavailable.</p>"


def _render_kpi_cards(samples_path: Path) -> str:
    try:
        from perfsage.core.analysis.percentiles import compute_overall_percentiles

        stats = compute_overall_percentiles(samples_path)
        cards = "".join(
            f'<div class="kpi-card">'
            f'<div class="kpi-value">{v:.0f} ms</div>'
            f'<div class="kpi-label">{k.upper()}</div>'
            f"</div>"
            for k, v in stats.items()
        )
        return f'<div class="kpi-grid">{cards}</div>'
    except Exception:
        return ""


def _render_recommendations(samples_path: Path, slo_config: SLOConfig | None) -> str:
    try:
        from perfsage.core.analysis.recommendations import run_all_recommendations
        from perfsage.core.storage.db import InsightSeverity

        recs = run_all_recommendations(samples_path, slo_config)
        if not recs:
            return "<p style='color:#38A169'>&#10003; No issues detected.</p>"

        _css_map = {
            InsightSeverity.CRITICAL: "rec rec-critical",
            InsightSeverity.WARNING: "rec rec-warning",
            InsightSeverity.INFO: "rec rec-info",
        }
        items = "".join(
            f'<div class="{_css_map.get(r.severity, "rec rec-info")}">'
            f"<strong>[{r.severity.upper()}]</strong> {r.message}"
            f"</div>"
            for r in recs
        )
        return items
    except Exception as exc:
        logger.warning("PDF: recommendations failed: %s", exc)
        return ""


def _build_html(
    samples_path: Path,
    report_name: str,
    timestamp: str,
    chart_imgs: list[tuple[str, str, Path | None]],
    slo_config: SLOConfig | None,
    rendered_count: int,
) -> str:
    data_available = samples_path.exists()
    summary_table = _render_summary_table(samples_path) if data_available else ""
    kpi_cards = _render_kpi_cards(samples_path) if data_available else ""
    recs_html = _render_recommendations(samples_path, slo_config) if data_available else ""

    chart_pages = ""
    for i in range(0, len(chart_imgs), 2):
        pair_html = ""
        for _fig_id, fig_title, png_path in chart_imgs[i : i + 2]:
            if png_path is not None:
                file_uri = png_path.resolve().as_uri()
                pair_html += (
                    f'<div class="chart-pair">'
                    f'<div class="chart-title">{fig_title}</div>'
                    f'<img class="chart" src="{file_uri}" alt="{fig_title}">'
                    f"</div>"
                )
            else:
                pair_html += (
                    f'<div class="chart-pair">'
                    f'<div class="chart-title">{fig_title}</div>'
                    f'<p style="color:#64748B;font-style:italic">Chart not available.</p>'
                    f"</div>"
                )
        chart_pages += pair_html
        if i + 2 < len(chart_imgs):
            chart_pages += '<div class="page-break"></div>'

    not_available = (
        '<p style="color:#92400E;background:#FEF3C7;padding:8px;border-radius:3px">'
        "&#9888; Data file not available &mdash; charts rendered without data."
        "</p>"
        if not data_available
        else ""
    )

    render_warning = ""
    if data_available and rendered_count == 0:
        render_warning = (
            '<p style="color:#92400E;background:#FEF3C7;padding:8px;border-radius:3px">'
            "&#9888; Chart rendering failed (check kaleido/Chrome). See logs."
            "</p>"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{report_name}</title>
  <style>
{_PDF_CSS}
  </style>
</head>
<body>
  <div class="cover">
    <h1>{report_name}</h1>
    <p>Performance Analysis Report</p>
    <p>Generated by PerfSage &mdash; {timestamp}</p>
  </div>
  <div class="page-break"></div>

  {not_available}
  {render_warning}

  <div class="section-title">Key Performance Indicators</div>
  {kpi_cards}

  <div class="section-title">Summary by Label</div>
  {summary_table}

  <div class="section-title">Recommendations</div>
  {recs_html}

  <div class="page-break"></div>

  <div class="section-title">Performance Charts</div>
  {chart_pages}

  <div class="pdf-footer">Powered by PerfSage &mdash; {timestamp}</div>
</body>
</html>"""


def _minimal_pdf(output_path: Path, report_name: str, error_msg: str) -> Path:
    lines = [
        f"PerfSage Report: {report_name}",
        "",
        "PDF generation failed.",
        f"Error: {error_msg}",
        "",
        "Please use the HTML export instead.",
    ]
    stream = (
        b"BT /F1 12 Tf 50 750 Td\n"
        + b"\n".join(
            f"({line.encode('latin-1', errors='replace').decode('latin-1')}) Tj T*".encode()
            for line in lines
        )
        + b"\nET"
    )
    stream_len = len(stream)

    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842]\n"
        b"   /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        + f"4 0 obj\n<< /Length {stream_len} >>\nstream\n".encode()
        + stream
        + b"\nendstream\nendobj\n"
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
        b"xref\n0 6\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"0000000266 00000 n \n"
        b"0000000400 00000 n \n"
        b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n450\n%%EOF\n"
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(pdf)
    return output_path


def generate_pdf_report(
    samples_path: Path,
    report_name: str,
    output_path: Path,
    slo_config: SLOConfig | None = None,
) -> Path:
    """Generate a PDF report with static chart PNGs via kaleido + WeasyPrint."""
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    tmp_dir = Path(tempfile.mkdtemp(prefix="perfsage_pdf_"))

    try:
        data_available = samples_path.exists()
        figure_objs = (
            build_figure_objects(samples_path, slo_config)
            if data_available
            else {fid: None for fid, _ in EXPORT_FIGURES}
        )

        chart_imgs, rendered = render_chart_pngs(figure_objs, tmp_dir)

        if data_available and rendered == 0:
            logger.error(
                "PDF: all %d chart renders failed — check kaleido/Chrome deps",
                len(EXPORT_FIGURES),
            )

        html_content = _build_html(
            samples_path, report_name, timestamp, chart_imgs, slo_config, rendered
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            import weasyprint

            weasyprint.HTML(string=html_content, base_url=str(tmp_dir)).write_pdf(str(output_path))
        except Exception as wp_exc:
            logger.warning("WeasyPrint failed (%s); falling back to minimal PDF.", wp_exc)
            return _minimal_pdf(output_path, report_name, str(wp_exc))

        return output_path

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# Exposed for unit tests
_build_html_for_tests = _build_html
