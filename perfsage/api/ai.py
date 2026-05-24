"""AI insights API endpoints."""

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from perfsage.config import Settings, get_settings
from perfsage.core.ai._crypto import decrypt_key
from perfsage.core.ai.client import get_client
from perfsage.core.ai.prompts import SYSTEM_PROMPT, build_analysis_prompt
from perfsage.core.storage.db import InsightSeverity, get_engine, get_session
from perfsage.core.storage.files import FileStore
from perfsage.core.storage.repos import AppSettingsRepo, InsightRepo, ReportRepo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/{report_id}/generate", response_class=HTMLResponse)
async def generate_ai_insights(
    report_id: str,
    settings: Settings = Depends(get_settings),
) -> str:
    """Generate AI insights for a report.

    Returns HTML fragment (for HTMX swap).
    Caches result in Insight table (kind='ai_narrative').
    """
    engine = get_engine(settings.database_url)
    file_store = FileStore(settings.data_dir)

    with get_session(engine) as session:
        report = ReportRepo(session).get(report_id)
        if not report:
            return '<div style="color:#E53E3E">Report not found.</div>'

        existing = next(
            (i for i in InsightRepo(session).list_for_report(report_id) if i.kind == "ai_narrative"),
            None,
        )
        if existing:
            return (
                f'<div style="white-space:pre-wrap;font-size:0.9375rem;line-height:1.6">'
                f"{existing.message}</div>"
            )

        settings_repo = AppSettingsRepo(session)
        provider: str | None = None
        api_key: str | None = None
        for p in ("openai", "anthropic", "gemini"):
            encrypted = settings_repo.get(f"{p}_key")
            if encrypted:
                provider = p
                api_key = decrypt_key(encrypted, settings.perfsage_secret)
                break

    if not provider or not api_key:
        return (
            '<div style="color:#E53E3E">No AI provider configured. '
            'Go to <a href="/settings">Settings</a> to add an API key.</div>'
        )

    samples_path = file_store.samples_parquet(report_id)
    if not samples_path.exists():
        return (
            '<div style="color:#E53E3E">Report data not found. '
            "Re-upload the file to regenerate.</div>"
        )

    user_prompt = build_analysis_prompt(samples_path)
    if not user_prompt.strip():
        return (
            '<div style="color:#E53E3E">Could not extract metrics from report data. '
            "Ensure the report has been fully analysed.</div>"
        )

    try:
        client = get_client(provider, api_key)
        narrative = await client.complete(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=2048,
            timeout_seconds=90.0,
        )
    except TimeoutError:
        return (
            '<div style="color:#E53E3E">AI analysis timed out (90s). '
            "Try again or use a different provider.</div>"
        )
    except Exception:
        logger.exception("AI analysis failed for report %s", report_id)
        return (
            '<div style="color:#E53E3E">AI analysis failed. Check your API key and provider '
            'configuration in <a href="/settings">Settings</a>.</div>'
        )

    with get_session(engine) as session:
        InsightRepo(session).create(
            report_id=report_id,
            kind="ai_narrative",
            severity=InsightSeverity.INFO,
            message=narrative,
        )
        ReportRepo(session).update_stats(report_id, has_ai_insights=True)

    return (
        f'<div style="white-space:pre-wrap;font-size:0.9375rem;line-height:1.6">'
        f"{narrative}</div>"
    )
