"""Generate a self-contained HTML report with embedded Plotly charts."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import plotly.graph_objects as go

from perfsage.core.analysis.metrics import compute_label_summary
from perfsage.core.analysis.percentiles import compute_overall_percentiles
from perfsage.core.analysis.recommendations import run_all_recommendations
from perfsage.core.analysis.slo import SLOConfig
from perfsage.core.storage.db import InsightSeverity

logger = logging.getLogger(__name__)

PLOTLY_CDN = "https://cdn.plot.ly/plotly-2.30.0.min.js"

_CSS_PATH = Path(__file__).parent.parent.parent / "web" / "static" / "css" / "perfsage.css"

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

_SEVERITY_CSS: dict[InsightSeverity, str] = {
    InsightSeverity.CRITICAL: "background:#FED7D7;color:#742A2A;border-left:4px solid #E53E3E",
    InsightSeverity.WARNING: "background:#FEF3C7;color:#92400E;border-left:4px solid #ECC94B",
    InsightSeverity.INFO: "background:#EBF8FF;color:#2A4365;border-left:4px solid #3182CE",
}


def _build_figures(samples_path: Path, slo_config: SLOConfig | None) -> list[go.Figure | None]:
    """Build all 20 figures; return None for any that fail."""
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
            fig_id = _FIGURES[i][0]
            logger.warning("Failed to build figure %s: %s", fig_id, exc)
            results.append(None)
    return results


def _render_summary_table(samples_path: Path) -> str:
    try:
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
        return f'<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:1rem;margin-bottom:2rem">{items}</div>'
    except Exception as exc:
        logger.warning("Failed to build overall stats: %s", exc)
        return ""


def _render_recommendations(samples_path: Path, slo_config: SLOConfig | None) -> str:
    try:
        recs = run_all_recommendations(samples_path, slo_config)
        if not recs:
            return '<div class="card"><p style="color:#38A169">&#10003; No issues detected.</p></div>'

        items = ""
        for rec in recs:
            style = _SEVERITY_CSS.get(rec.severity, "")
            badge = rec.severity.upper()
            items += (
                f'<div style="{style};padding:0.75rem 1rem;border-radius:4px;margin-bottom:0.5rem">'
                f'<strong>[{badge}]</strong> {rec.message}'
                f"</div>"
            )
        return f'<div class="card"><h3 style="margin-top:0">Recommendations</h3>{items}</div>'
    except Exception as exc:
        logger.warning("Failed to build recommendations: %s", exc)
        return ""


def generate_html_report(
    samples_path: Path,
    report_name: str,
    output_path: Path,
    slo_config: SLOConfig | None = None,
) -> Path:
    """Generate a complete standalone HTML report.

    Embeds Plotly JS from CDN (link, not inline — keeps file small),
    embeds all 20 charts as JSON (Plotly.newPlot calls in <script>),
    includes brand CSS inline, recommendations, and summary stats.
    Returns output_path.
    """
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    css_content = ""
    try:
        css_content = _CSS_PATH.read_text()
    except Exception as exc:
        logger.warning("Could not load CSS: %s", exc)

    data_available = samples_path.exists()

    figures = _build_figures(samples_path, slo_config) if data_available else [None] * 20
    overall_stats = _render_overall_stats(samples_path) if data_available else ""
    summary_table = _render_summary_table(samples_path) if data_available else ""
    recommendations_html = _render_recommendations(samples_path, slo_config) if data_available else ""

    # Build chart divs
    chart_divs = ""
    for _i, (fig_id, fig_title) in enumerate(_FIGURES):
        chart_divs += (
            f'<div class="card" style="margin-bottom:1.5rem">'
            f'<h3 style="margin-top:0;font-size:1rem;color:#64748B">{fig_title}</h3>'
            f'<div id="{fig_id}" style="width:100%;height:450px"></div>'
            f"</div>"
        )

    # Build Plotly.newPlot calls
    plot_scripts = ""
    for i, (fig_id, _) in enumerate(_FIGURES):
        fig = figures[i] if i < len(figures) else None
        if fig is not None:
            try:
                fig_json = fig.to_json()
                plot_scripts += (
                    f"(function(){{\n"
                    f"  var spec = {fig_json};\n"
                    f"  Plotly.newPlot('{fig_id}', spec.data, spec.layout, {{responsive:true}});\n"
                    f"}})();\n"
                )
            except Exception as exc:
                logger.warning("Failed to serialize figure %s: %s", fig_id, exc)
                plot_scripts += f"// Figure '{fig_id}' failed to render.\n"
        else:
            plot_scripts += f"// Figure '{fig_id}' not available.\n"

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
  <title>{report_name} \u2014 PerfSage Analysis</title>
  <script src="{PLOTLY_CDN}"></script>
  <style>
{css_content}
  </style>
</head>
<body>
  <nav class="navbar">
    <div class="brand">PerfSage Analyser</div>
    <span style="color:#F6F1E7;margin-left:auto;font-size:0.875rem">Generated {timestamp}</span>
  </nav>
  <main style="max-width:1280px;margin:0 auto;padding:2rem">
    <h1 style="color:#0B1F3A;margin-bottom:0.5rem">{report_name}</h1>
    <p style="color:#64748B;margin-bottom:2rem;font-size:0.875rem">Performance Analysis Report &mdash; PerfSage</p>

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
  <footer style="text-align:center;padding:2rem;color:#64748B;font-size:0.75rem;border-top:1px solid #E2E8F0;margin-top:2rem">
    Powered by <a href="https://perfsage.com" style="color:#0B1F3A">PerfSage</a>
  </footer>
  <script>
{plot_scripts}
  </script>
</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
