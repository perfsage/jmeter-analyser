"""Central registry for all report figures (web + exports)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from perfsage.core.analysis.slo import SLOConfig

logger = logging.getLogger(__name__)

EXPORT_FIGURES: list[tuple[str, str]] = [
    ("fig-rt-scatter", "Response Time Scatter by Transaction"),
    ("fig-rt-time", "Response Time Percentile Bands"),
    ("fig-percentile-fan", "Percentile Fan Over Time"),
    ("fig-throughput", "Throughput Over Time"),
    ("fig-errors", "Errors Over Time"),
    ("fig-threads", "Active Threads vs Response Time"),
    ("fig-bytes", "Bytes Over Time"),
    ("fig-sli-burn", "SLI Burn Rate Timeline"),
    ("fig-transaction-mix", "Transaction Mix Over Time"),
    ("fig-connect-breakdown", "Latency Component Breakdown"),
    ("fig-throughput-efficiency", "Throughput Efficiency"),
    ("fig-steady-compare", "Warmup vs Steady State"),
    ("fig-histogram", "Latency Histogram"),
    ("fig-cdf", "Latency CDF"),
    ("fig-boxplots", "Boxplots per Label"),
    ("fig-heatmap", "Response Time Heatmap"),
    ("fig-outlier-scatter", "Outlier Scatter (IQR)"),
    ("fig-rt-throughput", "RT vs Throughput"),
    ("fig-rt-concurrency", "RT vs Concurrency"),
    ("fig-rt-status", "RT by Status"),
    ("fig-threads-error-heatmap", "Threads vs Error Rate"),
    ("fig-correlation", "Correlation Matrix"),
    ("fig-components", "Latency Components"),
    ("fig-multiples", "Per-Label Small Multiples"),
    ("fig-slo-gauges", "SLO KPI Gauges"),
    ("fig-apdex", "Apdex by Label"),
    ("fig-slowest", "Slowest Transactions"),
    ("fig-sunburst", "Error Sunburst"),
    ("fig-variability", "Variability Chart"),
]


def _safe_fig_obj(fn: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return fn(*args, **kwargs)
    except Exception:
        logger.debug("Figure builder %s failed", getattr(fn, "__name__", fn), exc_info=True)
        return None


def build_figure_objects(
    samples_path: Path,
    slo_config: SLOConfig | None,
    only: set[str] | None = None,
) -> dict[str, Any]:
    """Return mapping of dom_id -> Plotly Figure or None.

    If `only` is given, builds just those figure ids (skips the rest) — used
    for lazily-loaded chart sections that don't need the full 29-chart set.
    """
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
    from perfsage.core.viz.expert import (
        fig_connect_breakdown,
        fig_outlier_scatter,
        fig_percentile_fan,
        fig_sli_burn_rate_timeline,
        fig_steady_state_compare,
        fig_threads_error_heatmap,
        fig_throughput_efficiency,
        fig_transaction_mix,
    )
    from perfsage.core.viz.scatter import (
        fig_correlation_matrix,
        fig_rt_scatter_by_label,
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

    builders: dict[str, Any] = {
        "fig-rt-scatter": lambda: fig_rt_scatter_by_label(samples_path),
        "fig-rt-time": lambda: fig_rt_over_time(samples_path),
        "fig-percentile-fan": lambda: fig_percentile_fan(samples_path),
        "fig-throughput": lambda: fig_throughput_over_time(samples_path),
        "fig-errors": lambda: fig_errors_over_time(samples_path),
        "fig-threads": lambda: fig_threads_vs_rt(samples_path),
        "fig-bytes": lambda: fig_bytes_over_time(samples_path),
        "fig-sli-burn": lambda: fig_sli_burn_rate_timeline(samples_path, slo_config),
        "fig-transaction-mix": lambda: fig_transaction_mix(samples_path),
        "fig-connect-breakdown": lambda: fig_connect_breakdown(samples_path),
        "fig-throughput-efficiency": lambda: fig_throughput_efficiency(samples_path),
        "fig-steady-compare": lambda: fig_steady_state_compare(samples_path),
        "fig-histogram": lambda: fig_latency_histogram(samples_path),
        "fig-cdf": lambda: fig_latency_cdf(samples_path),
        "fig-boxplots": lambda: fig_boxplots_per_label(samples_path),
        "fig-heatmap": lambda: fig_rt_heatmap(samples_path),
        "fig-outlier-scatter": lambda: fig_outlier_scatter(samples_path),
        "fig-rt-throughput": lambda: fig_rt_vs_throughput(samples_path),
        "fig-rt-concurrency": lambda: fig_rt_vs_concurrency(samples_path),
        "fig-rt-status": lambda: fig_rt_vs_time_by_status(samples_path),
        "fig-threads-error-heatmap": lambda: fig_threads_error_heatmap(samples_path),
        "fig-correlation": lambda: fig_correlation_matrix(samples_path),
        "fig-components": lambda: fig_latency_components(samples_path),
        "fig-multiples": lambda: fig_per_label_small_multiples(samples_path),
        "fig-slo-gauges": lambda: fig_slo_gauges(samples_path, slo_config),
        "fig-apdex": lambda: fig_apdex_by_label(samples_path),
        "fig-slowest": lambda: fig_slowest_transactions(samples_path),
        "fig-sunburst": lambda: fig_error_sunburst(samples_path),
        "fig-variability": lambda: fig_variability_chart(samples_path),
    }

    ids_to_build = [fid for fid, _ in EXPORT_FIGURES if only is None or fid in only]
    return {fid: _safe_fig_obj(builders[fid]) for fid in ids_to_build if fid in builders}


def build_figures_json(
    samples_path: Path,
    slo_config: SLOConfig | None,
    only: set[str] | None = None,
) -> dict[str, Any]:
    """Return mapping of dom_id -> Plotly JSON dict for web templates."""
    objs = build_figure_objects(samples_path, slo_config, only=only)
    result: dict[str, Any] = {}
    for fig_id, fig in objs.items():
        if fig is None:
            result[fig_id] = None
        else:
            try:
                result[fig_id] = json.loads(fig.to_json())
            except Exception:
                result[fig_id] = None
    return result
