"""HTMX-driven server-rendered views using Jinja2 templates."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from perfsage.config import Settings, get_settings
from perfsage.core.analysis.slo import SLOConfig
from perfsage.core.storage.db import ReportStatus, get_engine, get_session
from perfsage.core.storage.repos import AppSettingsRepo, InsightRepo, ReportRepo

logger = logging.getLogger(__name__)

router = APIRouter(tags=["web"])
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _engine(settings: Settings) -> Any:
    return get_engine(settings.database_url)


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request, settings: Settings = Depends(get_settings)
) -> HTMLResponse:
    engine = _engine(settings)
    with get_session(engine) as session:
        repo = ReportRepo(session)
        all_reports = repo.list_all(limit=10000)
        recent = all_reports[:5]
        total = len(all_reports)
        ready = sum(1 for r in all_reports if r.status == ReportStatus.READY)
        processing = sum(1 for r in all_reports if r.status == ReportStatus.PROCESSING)
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "recent_reports": recent,
            "total_reports": total,
            "ready_reports": ready,
            "processing_reports": processing,
        },
    )


@router.get("/reports", response_class=HTMLResponse)
async def reports_list(
    request: Request, settings: Settings = Depends(get_settings)
) -> HTMLResponse:
    engine = _engine(settings)
    with get_session(engine) as session:
        reports = ReportRepo(session).list_all(limit=200)
    return templates.TemplateResponse(request, "reports_list.html", {"reports": reports})


@router.get("/reports/{report_id}", response_class=HTMLResponse)
async def report_detail(
    report_id: str,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> HTMLResponse:
    from perfsage.core.storage.files import FileStore

    engine = _engine(settings)
    file_store = FileStore(settings.data_dir)

    with get_session(engine) as session:
        report = ReportRepo(session).get(report_id)
        if report is None:
            return HTMLResponse("Report not found", status_code=404)
        insights = InsightRepo(session).list_for_report(report_id)
        app_settings = AppSettingsRepo(session)
        ai_key_configured = (
            app_settings.get("openai_key") is not None
            or app_settings.get("anthropic_key") is not None
            or app_settings.get("gemini_key") is not None
        )

    samples_path = file_store.samples_parquet(report_id)
    figures_json: dict[str, Any] = {}
    recommendations: list[Any] = []
    summary_stats: list[dict[str, str]] = []
    slo_config = SLOConfig()

    if samples_path.exists() and report.status == ReportStatus.READY:
        figures_json = _build_figures(samples_path, slo_config)
        try:
            from perfsage.core.analysis.recommendations import run_all_recommendations

            recommendations = run_all_recommendations(samples_path, slo_config)
        except Exception:
            logger.warning("Recommendations failed for report %s", report_id, exc_info=True)
        summary_stats = _build_summary_stats(report, samples_path)

    ai_insights: str | None = None
    ai_insight_obj = next((i for i in insights if i.kind == "ai_narrative"), None)
    if ai_insight_obj is not None:
        ai_insights = ai_insight_obj.message

    return templates.TemplateResponse(
        request,
        "report_detail.html",
        {
            "report": report,
            "figures_json": json.dumps(figures_json),
            "recommendations": recommendations,
            "summary_stats": summary_stats,
            "ai_insights": ai_insights,
            "ai_key_configured": ai_key_configured,
        },
    )


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request, settings: Settings = Depends(get_settings)
) -> HTMLResponse:
    engine = _engine(settings)
    configured_providers: list[str] = []
    with get_session(engine) as session:
        repo = AppSettingsRepo(session)
        if repo.get("openai_key"):
            configured_providers.append("OpenAI")
        if repo.get("anthropic_key"):
            configured_providers.append("Anthropic")
        if repo.get("gemini_key"):
            configured_providers.append("Gemini")
    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "configured_providers": configured_providers,
            "slo": SLOConfig(),
        },
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_fig(fn: Any, *args: Any, **kwargs: Any) -> Any:
    """Call a viz builder; return Plotly JSON dict or None on any error."""
    try:
        return json.loads(fn(*args, **kwargs).to_json())
    except Exception:
        logger.debug("Figure builder %s failed", getattr(fn, "__name__", fn), exc_info=True)
        return None


def _build_figures(samples_path: Path, slo_config: SLOConfig) -> dict[str, Any]:
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
    from perfsage.core.viz.slo import (
        fig_apdex_by_label,
        fig_error_sunburst,
        fig_slo_gauges,
    )
    from perfsage.core.viz.tables import fig_slowest_transactions, fig_variability_chart
    from perfsage.core.viz.timeseries import (
        fig_bytes_over_time,
        fig_errors_over_time,
        fig_rt_over_time,
        fig_threads_vs_rt,
        fig_throughput_over_time,
    )

    return {
        "fig-rt-time": _safe_fig(fig_rt_over_time, samples_path),
        "fig-throughput": _safe_fig(fig_throughput_over_time, samples_path),
        "fig-errors": _safe_fig(fig_errors_over_time, samples_path),
        "fig-threads": _safe_fig(fig_threads_vs_rt, samples_path),
        "fig-bytes": _safe_fig(fig_bytes_over_time, samples_path),
        "fig-histogram": _safe_fig(fig_latency_histogram, samples_path),
        "fig-cdf": _safe_fig(fig_latency_cdf, samples_path),
        "fig-boxplots": _safe_fig(fig_boxplots_per_label, samples_path),
        "fig-heatmap": _safe_fig(fig_rt_heatmap, samples_path),
        "fig-rt-throughput": _safe_fig(fig_rt_vs_throughput, samples_path),
        "fig-rt-concurrency": _safe_fig(fig_rt_vs_concurrency, samples_path),
        "fig-rt-status": _safe_fig(fig_rt_vs_time_by_status, samples_path),
        "fig-correlation": _safe_fig(fig_correlation_matrix, samples_path),
        "fig-components": _safe_fig(fig_latency_components, samples_path),
        "fig-multiples": _safe_fig(fig_per_label_small_multiples, samples_path),
        "fig-slo-gauges": _safe_fig(fig_slo_gauges, samples_path, slo_config),
        "fig-apdex": _safe_fig(fig_apdex_by_label, samples_path),
        "fig-slowest": _safe_fig(fig_slowest_transactions, samples_path),
        "fig-sunburst": _safe_fig(fig_error_sunburst, samples_path),
        "fig-variability": _safe_fig(fig_variability_chart, samples_path),
    }


def _build_summary_stats(report: Any, samples_path: Path) -> list[dict[str, str]]:
    try:
        from perfsage.core.analysis.metrics import compute_label_summary
        from perfsage.core.analysis.percentiles import compute_overall_percentiles

        pcts = compute_overall_percentiles(samples_path)
        lsummary = compute_label_summary(samples_path)
        error_rate = 0.0
        if "error_rate" in lsummary.columns:
            raw_mean = lsummary["error_rate"].mean()
            if raw_mean is not None:
                error_rate = float(str(raw_mean)) * 100
        return [
            {"label": "P50 (ms)", "value": f"{pcts.get('p50', 0):.0f}"},
            {"label": "P90 (ms)", "value": f"{pcts.get('p90', 0):.0f}"},
            {"label": "P99 (ms)", "value": f"{pcts.get('p99', 0):.0f}"},
            {"label": "Error Rate", "value": f"{error_rate:.1f}%"},
            {"label": "Total Samples", "value": f"{report.parsed_row_count:,}"},
        ]
    except Exception:
        logger.warning("Summary stats failed", exc_info=True)
        return []
