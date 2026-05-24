"""REST endpoints for JMeter file uploads."""

from __future__ import annotations

from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from perfsage.config import Settings, get_settings
from perfsage.core.storage.db import ReportStatus, get_session
from perfsage.core.storage.files import FileStore
from perfsage.core.storage.repos import JobRepo, ReportRepo

router = APIRouter(prefix="/uploads", tags=["uploads"])

_templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "web" / "templates"))


def _is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


async def _render_progress(request: Request, job_id: str, report_id: str) -> HTMLResponse:
    return _templates.TemplateResponse(
        request,
        "progress.html",
        {"job_id": job_id, "report_id": report_id},
    )


@router.post("/upload", status_code=202, response_model=None)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    name: str | None = Form(None),
    settings: Settings = Depends(get_settings),
) -> dict[str, str] | HTMLResponse:
    """Stream-upload a JMeter JTL file, create Report + Job, enqueue ingest task.

    Returns ``{"report_id": ..., "job_id": ...}`` for plain requests,
    or a progress partial HTML fragment for HTMX requests.
    Rejects files exceeding ``settings.max_upload_bytes`` with HTTP 413.
    """
    report_name = name or file.filename or "unnamed"
    engine = request.app.state.engine

    fs = FileStore(settings.data_dir)
    fs.ensure_dirs()

    with get_session(engine) as session:
        report = ReportRepo(session).create(
            name=report_name,
            source_filename=file.filename or "upload.jtl",
            size_bytes=0,
        )
        job = JobRepo(session).create(report_id=report.id)

    upload_path = fs.upload_path(job.id)

    written = 0
    try:
        async with aiofiles.open(upload_path, "wb") as out:
            while True:
                chunk = await file.read(65_536)
                if not chunk:
                    break
                written += len(chunk)
                if written > settings.max_upload_bytes:
                    upload_path.unlink(missing_ok=True)
                    with get_session(engine) as session:
                        ReportRepo(session).update_status(report.id, ReportStatus.FAILED)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds maximum allowed size of {settings.max_upload_bytes} bytes",
                    )
                await out.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        upload_path.unlink(missing_ok=True)
        with get_session(engine) as session:
            ReportRepo(session).update_status(report.id, ReportStatus.FAILED)
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}") from exc

    with get_session(engine) as session:
        ReportRepo(session).update_stats(report.id, size_bytes=written)

    redis = request.app.state.redis
    await redis.enqueue_job(
        "ingest_report_task",
        job_id=job.id,
        report_id=report.id,
        upload_path=str(upload_path),
    )

    if _is_htmx(request):
        return await _render_progress(request, job.id, report.id)
    return {"report_id": report.id, "job_id": job.id}


@router.post("/paste", response_class=HTMLResponse)
async def paste_content(
    request: Request,
    content: str = Form(...),
    name: str | None = Form(None),
    settings: Settings = Depends(get_settings),
) -> HTMLResponse:
    """Accept pasted JTL/CSV text content, write to a temp file and enqueue analysis.

    Always returns the progress partial HTML fragment (designed for HTMX forms).
    """
    report_name = name or "Pasted content"
    engine = request.app.state.engine

    fs = FileStore(settings.data_dir)
    fs.ensure_dirs()

    with get_session(engine) as session:
        report = ReportRepo(session).create(
            name=report_name,
            source_filename="paste.jtl",
            size_bytes=len(content.encode()),
        )
        job = JobRepo(session).create(report_id=report.id)

    upload_path = fs.upload_path(job.id)
    try:
        async with aiofiles.open(upload_path, "w", encoding="utf-8") as out:
            await out.write(content)
    except Exception as exc:
        upload_path.unlink(missing_ok=True)
        with get_session(engine) as session:
            ReportRepo(session).update_status(report.id, ReportStatus.FAILED)
        raise HTTPException(status_code=500, detail=f"Failed to write pasted content: {exc}") from exc

    redis = request.app.state.redis
    await redis.enqueue_job(
        "ingest_report_task",
        job_id=job.id,
        report_id=report.id,
        upload_path=str(upload_path),
    )

    return await _render_progress(request, job.id, report.id)
