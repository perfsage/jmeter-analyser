"""Settings API endpoints."""

import json

from fastapi import APIRouter, Depends, Form
from fastapi.responses import HTMLResponse

from perfsage.config import Settings, get_settings
from perfsage.core.ai._crypto import encrypt_key
from perfsage.core.analysis.slo import SLOConfig
from perfsage.core.storage.db import get_engine, get_session
from perfsage.core.storage.repos import AppSettingsRepo

router = APIRouter(prefix="/settings", tags=["settings"])


@router.post("/ai-key", response_class=HTMLResponse)
async def save_ai_key(
    provider: str = Form(...),
    api_key: str = Form(default=""),
    settings: Settings = Depends(get_settings),
) -> str:
    """Save encrypted AI API key. Returns HTML fragment."""
    if provider not in ("openai", "anthropic", "gemini"):
        return '<div style="color:#E53E3E">Invalid provider.</div>'
    if not api_key.strip():
        return '<div style="color:#E53E3E">API key cannot be empty.</div>'

    encrypted = encrypt_key(api_key.strip(), settings.perfsage_secret)
    engine = get_engine(settings.database_url)
    with get_session(engine) as session:
        AppSettingsRepo(session).set(f"{provider}_key", encrypted)

    return f'<div style="color:#38A169;font-weight:500">✓ {provider.capitalize()} key saved successfully.</div>'


@router.post("/slo", response_class=HTMLResponse)
async def save_slo_defaults(
    p90_ms: float = Form(1000.0),
    p99_ms: float = Form(3000.0),
    error_rate_pct: float = Form(1.0),
    apdex_t: float = Form(0.5),
    settings: Settings = Depends(get_settings),
) -> str:
    """Save SLO default thresholds. Returns HTML fragment."""
    config = SLOConfig(p90_ms=p90_ms, p99_ms=p99_ms, error_rate_pct=error_rate_pct, apdex_t=apdex_t)
    engine = get_engine(settings.database_url)
    with get_session(engine) as session:
        AppSettingsRepo(session).set("slo_defaults", json.dumps(config.__dict__))
    return '<div style="color:#38A169;font-weight:500">✓ SLO defaults saved.</div>'
