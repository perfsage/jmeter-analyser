"""Delete reports and associated on-disk artifacts."""

from __future__ import annotations

import shutil
from pathlib import Path

from sqlalchemy.engine import Engine
from sqlmodel import Session, delete, select

from perfsage.core.storage.db import Insight, Job, Report, ReportStatus
from perfsage.core.storage.files import FileStore
from perfsage.core.storage.repos import ReportRepo


def delete_report_data(file_store: FileStore, report_id: str, session: Session) -> None:
    """Remove parquet, exports, and upload files for one report."""
    parquet_dir = file_store.data_dir / "parquet" / report_id
    if parquet_dir.exists():
        shutil.rmtree(parquet_dir)

    for fmt in ("html", "pdf"):
        export = file_store.export_path(report_id, fmt)
        if export.exists():
            export.unlink()

    jobs = list(session.exec(select(Job).where(Job.report_id == report_id)).all())
    for job in jobs:
        upload = file_store.upload_path(job.id)
        if upload.exists():
            upload.unlink()


def delete_report(session: Session, report_id: str, file_store: FileStore) -> None:
    """Delete insights, jobs, report row, and files for one report."""
    delete_report_data(file_store, report_id, session)
    session.exec(delete(Insight).where(Insight.report_id == report_id))  # type: ignore[arg-type]
    session.exec(delete(Job).where(Job.report_id == report_id))  # type: ignore[arg-type]
    session.exec(delete(Report).where(Report.id == report_id))  # type: ignore[arg-type]
    session.commit()


def flush_reports(
    engine: Engine,
    data_dir: Path,
    *,
    keep_recent: int = 0,
    force: bool = False,
) -> int:
    """Delete reports except the N most recent. Returns number deleted."""
    file_store = FileStore(data_dir)
    with Session(engine) as session:
        repo = ReportRepo(session)
        if not force:
            by_status = repo.count_by_status()
            if by_status.get(ReportStatus.PROCESSING, 0) > 0:
                raise ValueError(
                    "Cannot flush while reports are processing. "
                    "Wait for jobs to finish or pass force=true."
                )

        all_reports = repo.list_page(offset=0, limit=1_000_000)
        to_delete = all_reports[keep_recent:] if keep_recent > 0 else all_reports
        deleted = 0
        for report in to_delete:
            delete_report(session, report.id, file_store)
            deleted += 1
    return deleted
