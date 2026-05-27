"""Export API endpoints for HTML and PDF download."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from perfsage.config import Settings, get_settings
from perfsage.core.export.html import generate_html_report
from perfsage.core.export.pdf import generate_pdf_report
from perfsage.core.storage.db import ReportStatus, get_engine, get_session
from perfsage.core.storage.files import FileStore
from perfsage.core.storage.repos import ReportRepo

router = APIRouter(prefix="/exports", tags=["exports"])


def _should_regenerate(export_path: Path, samples_path: Path, force: bool) -> bool:
    if force or not export_path.exists():
        return True
    if not samples_path.exists():
        return False
    return export_path.stat().st_mtime < samples_path.stat().st_mtime


@router.get("/{report_id}/html")
async def download_html_report(
    report_id: str,
    force: bool = Query(False),
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    """Generate and download HTML report."""
    engine = get_engine(settings.database_url)
    file_store = FileStore(settings.data_dir)

    with get_session(engine) as session:
        report = ReportRepo(session).get(report_id)
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        if report.status != ReportStatus.READY:
            raise HTTPException(status_code=409, detail="Report not ready yet")
        report_name = report.name

    samples_path = file_store.samples_parquet(report_id)
    output_path = file_store.export_path(report_id, "html")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if _should_regenerate(output_path, samples_path, force):
        generate_html_report(samples_path, report_name, output_path)

    safe_name = report_name.replace(" ", "_")
    return FileResponse(
        path=str(output_path),
        filename=f"{safe_name}_report.html",
        media_type="text/html",
    )


@router.get("/{report_id}/pdf")
async def download_pdf_report(
    report_id: str,
    force: bool = Query(False),
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    """Generate and download PDF report. Takes 10–30 s for large reports."""
    engine = get_engine(settings.database_url)
    file_store = FileStore(settings.data_dir)

    with get_session(engine) as session:
        report = ReportRepo(session).get(report_id)
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        if report.status != ReportStatus.READY:
            raise HTTPException(status_code=409, detail="Report not ready yet")
        report_name = report.name

    samples_path = file_store.samples_parquet(report_id)
    output_path = file_store.export_path(report_id, "pdf")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if _should_regenerate(output_path, samples_path, force):
        generate_pdf_report(samples_path, report_name, output_path)

    safe_name = report_name.replace(" ", "_")
    return FileResponse(
        path=str(output_path),
        filename=f"{safe_name}_report.pdf",
        media_type="application/pdf",
    )
