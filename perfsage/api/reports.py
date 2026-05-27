"""REST endpoints for managing analysis reports."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from perfsage.config import Settings, get_settings
from perfsage.core.storage.db import get_engine
from perfsage.core.storage.report_cleanup import flush_reports

router = APIRouter(prefix="/reports", tags=["reports"])
_templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "web" / "templates"))


class FlushResult(BaseModel):
    deleted: int
    keep_recent: int


@router.post("/flush", response_model=None)
async def flush_old_reports(
    request: Request,
    keep_recent: int = Query(0, ge=0, description="Keep N most recent reports; 0 deletes all"),
    force: bool = Query(False, description="Allow flush while reports are processing"),
    settings: Settings = Depends(get_settings),
) -> FlushResult | HTMLResponse | JSONResponse:
    """Delete old reports and their parquet/export/upload files."""
    engine = get_engine(settings.database_url)
    try:
        deleted = flush_reports(
            engine,
            settings.data_dir,
            keep_recent=keep_recent,
            force=force,
        )
    except ValueError as exc:
        if request.headers.get("HX-Request"):
            return HTMLResponse(
                f'<div class="alert alert-error" style="margin-bottom:1rem">{exc}</div>',
                status_code=409,
            )
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if request.headers.get("HX-Request"):
        from perfsage.web.views import reports_list_context

        ctx = reports_list_context(engine, page=1, per_page=25)
        ctx["flush_message"] = f"Removed {deleted} report(s)."
        return _templates.TemplateResponse(
            request,
            "partials/reports_table.html",
            ctx,
        )

    return JSONResponse(content=FlushResult(deleted=deleted, keep_recent=keep_recent).model_dump())
