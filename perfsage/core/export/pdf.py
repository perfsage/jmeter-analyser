"""Generate PDF report using WeasyPrint + kaleido for static chart images."""

from __future__ import annotations

import base64
import logging
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from perfsage.core.analysis.slo import SLOConfig

logger = logging.getLogger(__name__)

_FIGURES: list[tuple[str, str]] = [
    ("fig-rt-time", "Response Time Over Time"),
    ("fig-throughput-time", "Throughput Over Time"),
    ("fig-errors-time", "Errors Over Time"),
    ("fig-threads-rt", "Active Threads vs Response Time"),
    ("fig-bytes-time", "Bytes Over Time"),
    ("fig-latency-components", "Latency Components"),
    ("fig-label-multiples", "Per-Label Small Multiples"),
    ("fig-boxplots", "Boxplots per Label"),
    ("fig-rt-heatmap", "Response Time Heatmap"),
    ("fig-histogram", "Latency Histogram"),
    ("fig-cdf", "Latency CDF"),
    ("fig-rt-throughput", "RT vs Throughput"),
    ("fig-rt-concurrency", "RT vs Concurrency"),
    ("fig-rt-status", "RT by Status"),
    ("fig-correlation", "Correlation Matrix"),
    ("fig-slo-gauges", "SLO KPI Gauges"),
    ("fig-apdex", "Apdex by Label"),
    ("fig-error-sunburst", "Error Sunburst"),
    ("fig-slowest", "Slowest Transactions"),
    ("fig-variability", "Variability Chart"),
]

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
footer { text-align: center; font-size: 8pt; color: #64748B; margin-top: 1cm; border-top: 1px solid #E2E8F0; padding-top: 6px; }
"""


def _build_figures(samples_path: Path, slo_config: SLOConfig | None) -> list[object]:
    """Build all 20 figures (go.Figure objects); return None entries for failures."""
    import plotly.graph_objects as go

    from perfsage.core.viz.decomposition import (
        fig_latency_components,
        fig_per_label_small_multiples,
    )
    from perfsage.core.viz.distribution import (
        fig_boxplots_per_label,
        fig_latency_cdf,
        fig_latency_histogram,
        fig_rt_heatmap,
    )
    from perfsage.core.viz.scatter import (
        fig_correlation_matrix,
        fig_rt_vs_concurrency,
        fig_rt_vs_throughput,
        fig_rt_vs_time_by_status,
    )
    from perfsage.core.viz.slo import fig_apdex_by_label, fig_error_sunburst, fig_slo_gauges
    from perfsage.core.viz.tables import fig_slowest_transactions, fig_variability_chart
    from perfsage.core.viz.timeseries import (
        fig_bytes_over_time,
        fig_errors_over_time,
        fig_rt_over_time,
        fig_threads_vs_rt,
        fig_throughput_over_time,
    )

    builders = [
        lambda: fig_rt_over_time(samples_path),
        lambda: fig_throughput_over_time(samples_path),
        lambda: fig_errors_over_time(samples_path),
        lambda: fig_threads_vs_rt(samples_path),
        lambda: fig_bytes_over_time(samples_path),
        lambda: fig_latency_components(samples_path),
        lambda: fig_per_label_small_multiples(samples_path),
        lambda: fig_boxplots_per_label(samples_path),
        lambda: fig_rt_heatmap(samples_path),
        lambda: fig_latency_histogram(samples_path),
        lambda: fig_latency_cdf(samples_path),
        lambda: fig_rt_vs_throughput(samples_path),
        lambda: fig_rt_vs_concurrency(samples_path),
        lambda: fig_rt_vs_time_by_status(samples_path),
        lambda: fig_correlation_matrix(samples_path),
        lambda: fig_slo_gauges(samples_path, slo_config),
        lambda: fig_apdex_by_label(samples_path),
        lambda: fig_error_sunburst(samples_path),
        lambda: fig_slowest_transactions(samples_path),
        lambda: fig_variability_chart(samples_path),
    ]

    results: list[go.Figure | None] = []
    for i, builder in enumerate(builders):
        try:
            results.append(builder())  # type: ignore[no-untyped-call]
        except Exception as exc:
            logger.warning("PDF: failed to build figure %s: %s", _FIGURES[i][0], exc)
            results.append(None)
    return results


def _fig_to_base64_png(fig: object, tmp_dir: Path, fig_id: str) -> str | None:
    """Convert a Plotly figure to a base64-encoded PNG data URI."""
    try:
        import plotly.graph_objects as go

        if not isinstance(fig, go.Figure):
            return None

        png_path = tmp_dir / f"{fig_id}.png"
        fig.write_image(str(png_path), format="png", width=900, height=400, scale=1.5)
        png_bytes = png_path.read_bytes()
        b64 = base64.b64encode(png_bytes).decode("ascii")
        return f"data:image/png;base64,{b64}"
    except Exception as exc:
        logger.warning("PDF: kaleido failed for %s: %s", fig_id, exc)
        return None


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
    chart_imgs: list[tuple[str, str, str | None]],
    slo_config: SLOConfig | None,
) -> str:
    data_available = samples_path.exists()
    summary_table = _render_summary_table(samples_path) if data_available else ""
    kpi_cards = _render_kpi_cards(samples_path) if data_available else ""
    recs_html = _render_recommendations(samples_path, slo_config) if data_available else ""

    # Two charts per page
    chart_pages = ""
    for i in range(0, len(chart_imgs), 2):
        pair_html = ""
        for _fig_id, fig_title, img_uri in chart_imgs[i : i + 2]:
            if img_uri:
                pair_html += (
                    f'<div class="chart-pair">'
                    f'<div class="chart-title">{fig_title}</div>'
                    f'<img class="chart" src="{img_uri}" alt="{fig_title}">'
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
  <!-- Cover page -->
  <div class="cover">
    <h1>{report_name}</h1>
    <p>Performance Analysis Report</p>
    <p>Generated by PerfSage &mdash; {timestamp}</p>
  </div>
  <div class="page-break"></div>

  <!-- Summary & recommendations page -->
  {not_available}

  <div class="section-title">Key Performance Indicators</div>
  {kpi_cards}

  <div class="section-title">Summary by Label</div>
  {summary_table}

  <div class="section-title">Recommendations</div>
  {recs_html}

  <div class="page-break"></div>

  <!-- Charts -->
  <div class="section-title">Performance Charts</div>
  {chart_pages}

  <footer>Powered by PerfSage &mdash; {timestamp}</footer>
</body>
</html>"""


def _minimal_pdf(output_path: Path, report_name: str, error_msg: str) -> Path:
    """Write a minimal PDF using only stdlib (reportlab not needed — just raw PDF bytes)."""
    lines = [
        f"PerfSage Report: {report_name}",
        "",
        "PDF generation failed.",
        f"Error: {error_msg}",
        "",
        "Please use the HTML export instead.",
    ]
    # Minimal valid PDF with one text page
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
        b"0000000400 00000 n \n"  # approximate; readers are tolerant
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
    """Generate a PDF report.

    Renders charts as static PNG using Plotly kaleido (fig.write_image),
    saves PNGs to a temp dir, embeds as base64 data URIs, converts to PDF
    with WeasyPrint.  Falls back to a minimal PDF if WeasyPrint is unavailable.
    Returns output_path.
    """
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    tmp_dir = Path(tempfile.mkdtemp(prefix="perfsage_pdf_"))

    try:
        data_available = samples_path.exists()
        figures = _build_figures(samples_path, slo_config) if data_available else [None] * 20

        chart_imgs: list[tuple[str, str, str | None]] = []
        for i, (fig_id, fig_title) in enumerate(_FIGURES):
            fig = figures[i] if i < len(figures) else None
            img_uri = _fig_to_base64_png(fig, tmp_dir, fig_id) if fig is not None else None
            chart_imgs.append((fig_id, fig_title, img_uri))

        html_content = _build_html(samples_path, report_name, timestamp, chart_imgs, slo_config)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            import weasyprint

            weasyprint.HTML(string=html_content).write_pdf(str(output_path))
        except Exception as wp_exc:
            logger.warning(
                "WeasyPrint failed (%s); falling back to minimal PDF. "
                "Install system Pango/Cairo libraries to enable full PDF generation.",
                wp_exc,
            )
            return _minimal_pdf(output_path, report_name, str(wp_exc))

        return output_path

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
