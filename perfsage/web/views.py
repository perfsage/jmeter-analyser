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
from perfsage.core.ai.markdown_render import render_ai_markdown
from perfsage.core.analysis.slo import SLOConfig, load_slo_config
from perfsage.core.storage.db import ReportStatus, get_engine, get_session
from perfsage.core.storage.repos import AppSettingsRepo, InsightRepo, ReportRepo
from perfsage.core.viz.registry import EXPORT_FIGURES, build_figures_json

logger = logging.getLogger(__name__)

router = APIRouter(tags=["web"])
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

LAZY_SECTION_CHARTS: dict[str, list[tuple[str, str, str]]] = {
    "distribution": [
        ("fig-histogram", "Latency Histogram", "Overall response time distribution."),
        ("fig-cdf", "Latency CDF", "Cumulative probability of response times."),
        ("fig-boxplots", "Boxplots per Label", "Per-transaction spread and outliers."),
        ("fig-heatmap", "RT Heatmap", "Time vs label intensity map."),
        ("fig-outlier-scatter", "IQR Outliers", "Samples beyond 1.5×IQR fences."),
        ("fig-variability", "Variability", "Coefficient of variation by label."),
    ],
    "saturation": [
        ("fig-rt-throughput", "RT vs Throughput", "Find the knee where latency spikes."),
        ("fig-rt-concurrency", "RT vs Concurrency", "Latency under increasing load."),
        ("fig-correlation", "Correlation Matrix", "Metric interdependencies."),
        ("fig-threads-error-heatmap", "Threads vs Errors", "Failure density under load."),
    ],
}


def _engine(settings: Settings) -> Any:
    return get_engine(settings.database_url)


def _dumps_for_script_island(payload: Any) -> str:
    """json.dumps, with every "<" escaped so the payload is safe to embed
    inside a <script type="application/json"> element.

    The HTML tokenizer ends ANY <script> element on the literal byte sequence
    "</script" regardless of its type attribute, so a JMeter label containing
    that sequence would otherwise still break out of the script island and be
    parsed as HTML/script — the type="application/json" attribute alone does
    not prevent this. "\\u003c" is a valid JSON escape for "<" that JSON.parse
    decodes transparently but the HTML tokenizer never recognizes as a tag.
    """
    return json.dumps(payload).replace("<", "\\u003c")


def reports_list_context(
    engine: Any,
    *,
    page: int = 1,
    per_page: int = 25,
) -> dict[str, Any]:
    page = max(1, page)
    per_page = min(max(1, per_page), 100)
    offset = (page - 1) * per_page
    with get_session(engine) as session:
        repo = ReportRepo(session)
        total = repo.count()
        reports = repo.list_page(offset=offset, limit=per_page)
    total_pages = max(1, (total + per_page - 1) // per_page)
    return {
        "reports": reports,
        "page": page,
        "per_page": per_page,
        "total_reports": total,
        "total_pages": total_pages,
    }


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, settings: Settings = Depends(get_settings)) -> HTMLResponse:
    engine = _engine(settings)
    with get_session(engine) as session:
        repo = ReportRepo(session)
        recent = repo.list_page(offset=0, limit=5)
        by_status = repo.count_by_status()
        total = repo.count()
        ready = by_status.get(ReportStatus.READY, 0)
        processing = by_status.get(ReportStatus.PROCESSING, 0)
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
    request: Request,
    page: int = 1,
    per_page: int = 25,
    settings: Settings = Depends(get_settings),
) -> HTMLResponse:
    engine = _engine(settings)
    ctx = reports_list_context(engine, page=page, per_page=per_page)
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(request, "partials/reports_table.html", ctx)
    return templates.TemplateResponse(request, "reports_list.html", ctx)


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
        slo_config = load_slo_config(session)

    samples_path = file_store.samples_parquet(report_id)
    figures_json: dict[str, Any] = {}
    recommendations: list[Any] = []
    summary_stats: list[dict[str, str]] = []

    if samples_path.exists() and report.status == ReportStatus.READY:
        from perfsage.core.viz.render_cache import get_or_build_json

        lazy_ids = {cid for charts in LAZY_SECTION_CHARTS.values() for cid, _, _ in charts}
        inline_ids = {fid for fid, _ in EXPORT_FIGURES} - lazy_ids
        cache_path = file_store.render_cache_path(report_id, "main")
        figures_json = get_or_build_json(
            cache_path, lambda: build_figures_json(samples_path, slo_config, only=inline_ids)
        )
        try:
            from perfsage.core.analysis.recommendations import run_all_recommendations

            recommendations = run_all_recommendations(samples_path, slo_config)
        except Exception:
            logger.warning("Recommendations failed for report %s", report_id, exc_info=True)
        summary_stats = _build_summary_stats(report, samples_path, slo_config)

    ai_insights_html: str | None = None
    ai_insights_raw: str | None = None
    ai_insight_obj = next((i for i in insights if i.kind == "ai_narrative"), None)
    if ai_insight_obj is not None:
        ai_insights_raw = ai_insight_obj.message
        ai_insights_html = render_ai_markdown(ai_insight_obj.message)

    return templates.TemplateResponse(
        request,
        "report_detail.html",
        {
            "report": report,
            "figures_json": _dumps_for_script_island(figures_json),
            "recommendations": recommendations,
            "summary_stats": summary_stats,
            "ai_insights_html": ai_insights_html,
            "ai_insights_raw": ai_insights_raw,
            "ai_key_configured": ai_key_configured,
        },
    )


@router.get("/reports/{report_id}/section/{section_id}", response_class=HTMLResponse)
async def report_section(
    report_id: str,
    section_id: str,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> HTMLResponse:
    from perfsage.core.storage.files import FileStore
    from perfsage.core.viz.render_cache import get_or_build_json

    charts = LAZY_SECTION_CHARTS.get(section_id)
    if charts is None:
        return HTMLResponse("Unknown section", status_code=404)

    engine = _engine(settings)
    file_store = FileStore(settings.data_dir)

    with get_session(engine) as session:
        report = ReportRepo(session).get(report_id)
        if report is None or report.status != ReportStatus.READY:
            return HTMLResponse("Report not ready", status_code=404)
        slo_config = load_slo_config(session)

    samples_path = file_store.samples_parquet(report_id)
    if not samples_path.exists():
        return HTMLResponse("Report data not found", status_code=404)

    chart_ids = {cid for cid, _, _ in charts}
    cache_path = file_store.render_cache_path(report_id, section_id)
    figures_json = get_or_build_json(
        cache_path, lambda: build_figures_json(samples_path, slo_config, only=chart_ids)
    )

    return templates.TemplateResponse(
        request,
        "partials/lazy_section_charts.html",
        {"charts": charts, "figures_json": _dumps_for_script_island(figures_json)},
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
        slo_config = load_slo_config(session)
    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "configured_providers": configured_providers,
            "slo": slo_config,
        },
    )


def _build_summary_stats(
    report: Any, samples_path: Path, slo_config: SLOConfig
) -> list[dict[str, str]]:
    try:
        from perfsage.core.analysis.metrics import compute_label_summary
        from perfsage.core.analysis.percentiles import compute_overall_percentiles
        from perfsage.core.analysis.slo import compute_slo_compliance

        pcts = compute_overall_percentiles(samples_path)
        lsummary = compute_label_summary(samples_path)
        error_rate = 0.0
        if "error_rate" in lsummary.columns:
            raw_mean = lsummary["error_rate"].mean()
            if raw_mean is not None:
                error_rate = float(str(raw_mean)) * 100

        slo_results = compute_slo_compliance(samples_path, slo_config)
        overall_ok = all(r.overall_compliant for r in slo_results) if slo_results else True
        slo_label = "PASS" if overall_ok else "FAIL"

        return [
            {"label": "P50 (ms)", "value": f"{pcts.get('p50', 0):.0f}"},
            {"label": "P90 (ms)", "value": f"{pcts.get('p90', 0):.0f}"},
            {"label": "P99 (ms)", "value": f"{pcts.get('p99', 0):.0f}"},
            {"label": "Error Rate", "value": f"{error_rate:.1f}%"},
            {"label": "SLO Status", "value": slo_label},
            {"label": "Samples", "value": f"{report.parsed_row_count:,}"},
        ]
    except Exception:
        logger.warning("Summary stats failed", exc_info=True)
        return []
