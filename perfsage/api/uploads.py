"""REST endpoints for JMeter file uploads."""

from __future__ import annotations

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from perfsage.config import Settings, get_settings
from perfsage.core.storage.db import ReportStatus, get_session
from perfsage.core.storage.files import FileStore
from perfsage.core.storage.repos import JobRepo, ReportRepo

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("/upload", status_code=202)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    name: str | None = None,
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    """Stream-upload a JMeter JTL file, create Report + Job, enqueue ingest task.

    Returns ``{"report_id": ..., "job_id": ...}``.
    Rejects files exceeding ``settings.max_upload_bytes`` with HTTP 413.
    """
    report_name = name or file.filename or "unnamed"
    engine = request.app.state.engine

    fs = FileStore(settings.data_dir)
    fs.ensure_dirs()

    # Create DB records first so we can name the upload file after job.id.
    with get_session(engine) as session:
        report = ReportRepo(session).create(
            name=report_name,
            source_filename=file.filename or "upload.jtl",
            size_bytes=0,
        )
        job = JobRepo(session).create(report_id=report.id)

    upload_path = fs.upload_path(job.id)

    # Stream upload to disk; abort + 413 if too large.
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

    # Update size on the report now that we know the real byte count.
    with get_session(engine) as session:
        ReportRepo(session).update_stats(report.id, size_bytes=written)

    # Enqueue arq background job.
    redis = request.app.state.redis
    await redis.enqueue_job(
        "ingest_report_task",
        job_id=job.id,
        report_id=report.id,
        upload_path=str(upload_path),
    )

    return {"report_id": report.id, "job_id": job.id}
