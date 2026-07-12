"""Generate a self-contained HTML report with embedded Plotly charts."""

from __future__ import annotations

import base64
import html as html_escape
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from perfsage.core.analysis.metrics import compute_label_summary
from perfsage.core.analysis.percentiles import compute_overall_percentiles
from perfsage.core.analysis.recommendations import run_all_recommendations
from perfsage.core.analysis.slo import SLOConfig
from perfsage.core.storage.db import InsightSeverity
from perfsage.core.viz.registry import EXPORT_FIGURES, build_figure_objects

logger = logging.getLogger(__name__)

_PLOTLY_JS_PATH = Path(__file__).parent.parent.parent / "web" / "static" / "js" / "plotly.min.js"
_LOGO_PATH = Path(__file__).parent.parent.parent / "web" / "static" / "img" / "perfsage-logo.png"

_EXPORT_CSS = """
:root { --navy: #0B1F3A; --cream: #F6F1E7; --amber: #D4A857; --white: #FFFFFF; }
body { background: var(--cream); color: var(--navy); font-family: Inter, Arial, sans-serif; margin: 0; }
.navbar { background: var(--navy); padding: 1rem 2rem; color: var(--cream); }
.card { background: var(--white); border-radius: 8px; box-shadow: 0 1px 3px rgba(11,31,58,0.12); padding: 1.5rem; margin-bottom: 1.5rem; }
table.data-table { width: 100%; border-collapse: collapse; }
table.data-table th { background: var(--navy); color: var(--cream); padding: 0.75rem 1rem; text-align: left; }
table.data-table td { padding: 0.75rem 1rem; border-bottom: 1px solid #E2E8F0; }
.export-footer { background: #0B1F3A; color: #F6F1E7; text-align: center; padding: 1.5rem; margin-top: 2rem; font-size: 0.875rem; }
.export-footer a { color: #D4A857; text-decoration: none; font-weight: 600; }
.export-footer img { height: 28px; vertical-align: middle; margin-right: 0.5rem; }
"""

_SEVERITY_CSS: dict[InsightSeverity, str] = {
    InsightSeverity.CRITICAL: "background:#FED7D7;color:#742A2A;border-left:4px solid #E53E3E",
    InsightSeverity.WARNING: "background:#FEF3C7;color:#92400E;border-left:4px solid #ECC94B",
    InsightSeverity.INFO: "background:#EBF8FF;color:#2A4365;border-left:4px solid #3182CE",
}


def _dumps_for_script_island(payload: Any) -> str:
    """json.dumps, with every "<" escaped so the payload is safe to embed
    directly inside an executable <script> block.

    Browsers terminate a <script> element on the literal byte sequence
    "</script" regardless of any attributes on the tag, so a JMeter label
    like "x</script><script>...</script>" can break out of the script
    context even with type="application/json". "\\u003c" is a valid JSON
    escape for "<" that JSON.parse decodes transparently but the HTML
    tokenizer never recognizes as the start of a tag.
    """
    return json.dumps(payload).replace("<", "\\u003c")


def _logo_data_uri() -> str:
    try:
        raw = _LOGO_PATH.read_bytes()
        b64 = base64.b64encode(raw).decode("ascii")
        return f"data:image/png;base64,{b64}"
    except Exception:
        return ""


def _render_summary_table(samples_path: Path) -> str:
    try:
        df = compute_label_summary(samples_path)
        if df.is_empty():
            return "<p>No data available.</p>"

        rows_html = ""
        for row in df.to_dicts():
            err_pct = float(row.get("error_rate") or 0) * 100
            label = html_escape.escape(str(row.get("label", "")))
            rows_html += (
                f"<tr>"
                f"<td>{label}</td>"
                f"<td>{int(row.get('count', 0)):,}</td>"
                f"<td>{float(row.get('mean_elapsed', 0)):.0f}</td>"
                f"<td>{float(row.get('p50', 0)):.0f}</td>"
                f"<td>{float(row.get('p90', 0)):.0f}</td>"
                f"<td>{float(row.get('p95', 0)):.0f}</td>"
                f"<td>{float(row.get('p99', 0)):.0f}</td>"
                f"<td>{err_pct:.2f}%</td>"
                f"</tr>"
            )

        return f"""
<table class="data-table">
  <thead>
    <tr>
      <th>Label</th><th>Count</th><th>Mean (ms)</th>
      <th>p50</th><th>p90</th><th>p95</th><th>p99</th><th>Error Rate</th>
    </tr>
  </thead>
  <tbody>{rows_html}</tbody>
</table>"""
    except Exception as exc:
        logger.warning("Failed to build summary table: %s", exc)
        return "<p>Summary table unavailable.</p>"


def _render_overall_stats(samples_path: Path) -> str:
    try:
        stats = compute_overall_percentiles(samples_path)
        items = "".join(
            f'<div class="card" style="text-align:center;padding:1rem">'
            f'<div style="font-size:1.5rem;font-weight:700;color:#0B1F3A">{v:.0f} ms</div>'
            f'<div style="font-size:0.875rem;color:#64748B">{k.upper()}</div>'
            f"</div>"
            for k, v in stats.items()
        )
        return (
            f'<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));'
            f'gap:1rem;margin-bottom:2rem">{items}</div>'
        )
    except Exception as exc:
        logger.warning("Failed to build overall stats: %s", exc)
        return ""


def _render_recommendations(samples_path: Path, slo_config: SLOConfig | None) -> str:
    try:
        recs = run_all_recommendations(samples_path, slo_config)
        if not recs:
            return (
                '<div class="card"><p style="color:#38A169">&#10003; No issues detected.</p></div>'
            )

        items = ""
        for rec in recs:
            style = _SEVERITY_CSS.get(rec.severity, "")
            badge = rec.severity.upper()
            message = html_escape.escape(rec.message)
            items += (
                f'<div style="{style};padding:0.75rem 1rem;border-radius:4px;margin-bottom:0.5rem">'
                f"<strong>[{badge}]</strong> {message}"
                f"</div>"
            )
        return f'<div class="card"><h3 style="margin-top:0">Recommendations</h3>{items}</div>'
    except Exception as exc:
        logger.warning("Failed to build recommendations: %s", exc)
        return ""


def _render_export_footer(timestamp: str) -> str:
    logo = _logo_data_uri()
    logo_html = f'<img src="{logo}" alt="PerfSage">' if logo else ""
    return (
        f'<div class="export-footer">'
        f"Powered by {logo_html}"
        f'<a href="https://perfsage.com">PerfSage</a> &mdash; {timestamp}'
        f"</div>"
    )


def generate_html_report(
    samples_path: Path,
    report_name: str,
    output_path: Path,
    slo_config: SLOConfig | None = None,
) -> Path:
    """Generate a complete standalone HTML report with embedded Plotly."""
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    safe_report_name = html_escape.escape(report_name)

    plotly_js = ""
    try:
        plotly_js = _PLOTLY_JS_PATH.read_text()
    except Exception as exc:
        logger.warning("Could not load Plotly JS: %s", exc)

    data_available = samples_path.exists()
    figure_objs = (
        build_figure_objects(samples_path, slo_config)
        if data_available
        else {fid: None for fid, _ in EXPORT_FIGURES}
    )

    overall_stats = _render_overall_stats(samples_path) if data_available else ""
    summary_table = _render_summary_table(samples_path) if data_available else ""
    recommendations_html = (
        _render_recommendations(samples_path, slo_config) if data_available else ""
    )
    footer_html = _render_export_footer(timestamp)

    chart_divs = ""
    for fig_id, fig_title in EXPORT_FIGURES:
        chart_divs += (
            f'<div class="card" style="margin-bottom:1.5rem">'
            f'<h3 style="margin-top:0;font-size:1rem;color:#64748B">{fig_title}</h3>'
            f'<div id="{fig_id}" style="width:100%;height:450px"></div>'
            f"</div>"
        )

    plot_scripts = ""
    for fig_id, _ in EXPORT_FIGURES:
        fig = figure_objs.get(fig_id)
        if fig is not None:
            try:
                fig_spec = json.loads(fig.to_json())
                fig_json = _dumps_for_script_island(fig_spec)
                plot_scripts += (
                    f"(function(){{\n"
                    f"  var spec = {fig_json};\n"
                    f"  Plotly.newPlot('{fig_id}', spec.data, spec.layout, {{responsive:true}});\n"
                    f"}})();\n"
                )
            except Exception as exc:
                logger.warning("Failed to serialize figure %s: %s", fig_id, exc)

    not_available_banner = (
        '<div style="background:#FEF3C7;padding:1rem;border-radius:4px;margin-bottom:1rem">'
        "&#9888; Data file not available — chart shells rendered without data."
        "</div>"
        if not data_available
        else ""
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{safe_report_name} \u2014 PerfSage Analysis</title>
  <style>
{_EXPORT_CSS}
  </style>
</head>
<body>
  <nav class="navbar">
    <div>PerfSage Reveal</div>
    <span style="margin-left:auto;font-size:0.875rem">Generated {timestamp}</span>
  </nav>
  <main style="max-width:1280px;margin:0 auto;padding:2rem">
    <h1 style="color:#0B1F3A;margin-bottom:0.5rem">{safe_report_name}</h1>
    <p style="color:#64748B;margin-bottom:2rem;font-size:0.875rem">Performance Analysis Report</p>

    {not_available_banner}
    {overall_stats}

    <div class="card" style="margin-bottom:1.5rem">
      <h2 style="margin-top:0;font-size:1.125rem">Summary by Label</h2>
      {summary_table}
    </div>

    {recommendations_html}

    <h2 style="color:#0B1F3A;margin-top:2rem;margin-bottom:1rem">Charts</h2>
    {chart_divs}
  </main>
  {footer_html}
  <script>
{plotly_js}
  </script>
  <script>
{plot_scripts}
  </script>
</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
