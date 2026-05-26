"""Repository layer — thin wrappers over SQLModel sessions."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, col, select

from perfsage.core.storage.db import (
    AppSettings,
    Insight,
    InsightSeverity,
    Job,
    JobStatus,
    Report,
    ReportStatus,
)


class ReportRepo:
    def __init__(self, session: Session) -> None:
        self._s = session

    def create(self, name: str, source_filename: str, size_bytes: int) -> Report:
        report = Report(name=name, source_filename=source_filename, size_bytes=size_bytes)
        self._s.add(report)
        self._s.commit()
        self._s.refresh(report)
        return report

    def get(self, report_id: str) -> Report | None:
        return self._s.get(Report, report_id)

    def list_all(self, limit: int = 100) -> list[Report]:
        return self.list_page(offset=0, limit=limit)

    def list_page(self, offset: int = 0, limit: int = 25) -> list[Report]:
        stmt = select(Report).order_by(col(Report.created_at).desc()).offset(offset).limit(limit)
        return list(self._s.exec(stmt).all())

    def count(self) -> int:
        result = self._s.exec(select(func.count()).select_from(Report)).one()
        return int(result)

    def count_by_status(self) -> dict[ReportStatus, int]:
        rows = self._s.exec(
            select(Report.status, func.count()).group_by(Report.status)  # type: ignore[arg-type]
        ).all()
        return {ReportStatus(status): int(cnt) for status, cnt in rows}

    def update_status(self, report_id: str, status: ReportStatus) -> None:
        report = self._s.get(Report, report_id)
        if report is None:
            raise ValueError(f"Report not found: {report_id!r}")
        report.status = status
        self._s.add(report)
        self._s.commit()

    def update_stats(self, report_id: str, **kwargs: Any) -> None:
        report = self._s.get(Report, report_id)
        if report is None:
            raise ValueError(f"Report not found: {report_id!r}")
        for key, value in kwargs.items():
            setattr(report, key, value)
        self._s.add(report)
        self._s.commit()


class JobRepo:
    def __init__(self, session: Session) -> None:
        self._s = session

    def create(self, report_id: str) -> Job:
        job = Job(report_id=report_id)
        self._s.add(job)
        self._s.commit()
        self._s.refresh(job)
        return job

    def get(self, job_id: str) -> Job | None:
        return self._s.get(Job, job_id)

    def update_progress(self, job_id: str, pct: float, phase: str, message: str = "") -> None:
        job = self._s.get(Job, job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id!r}")
        job.progress_pct = pct
        job.phase = phase
        job.message = message
        if job.status == JobStatus.QUEUED:
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now(UTC)
        self._s.add(job)
        self._s.commit()

    def mark_done(self, job_id: str) -> None:
        job = self._s.get(Job, job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id!r}")
        job.status = JobStatus.DONE
        job.progress_pct = 100.0
        job.phase = "done"
        job.ended_at = datetime.now(UTC)
        self._s.add(job)
        self._s.commit()

    def mark_failed(self, job_id: str, error: str) -> None:
        job = self._s.get(Job, job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id!r}")
        job.status = JobStatus.FAILED
        job.error_text = error
        job.ended_at = datetime.now(UTC)
        self._s.add(job)
        self._s.commit()

    def get_active_jobs(self) -> list[Job]:
        return list(self._s.exec(select(Job).where(Job.status == JobStatus.RUNNING)).all())


class InsightRepo:
    def __init__(self, session: Session) -> None:
        self._s = session

    def create(
        self,
        report_id: str,
        kind: str,
        severity: InsightSeverity,
        message: str,
        data: dict[str, object] | None = None,
    ) -> Insight:
        insight = Insight(
            report_id=report_id,
            kind=kind,
            severity=severity,
            message=message,
            data_json=json.dumps(data) if data is not None else None,
        )
        self._s.add(insight)
        self._s.commit()
        self._s.refresh(insight)
        return insight

    def list_for_report(self, report_id: str) -> list[Insight]:
        return list(self._s.exec(select(Insight).where(Insight.report_id == report_id)).all())


class AppSettingsRepo:
    def __init__(self, session: Session) -> None:
        self._s = session

    def set(self, key: str, encrypted_value: str) -> None:
        existing = self._s.get(AppSettings, key)
        if existing is not None:
            existing.value_encrypted = encrypted_value
            self._s.add(existing)
        else:
            self._s.add(AppSettings(key=key, value_encrypted=encrypted_value))
        self._s.commit()

    def get(self, key: str) -> str | None:
        row = self._s.get(AppSettings, key)
        return row.value_encrypted if row is not None else None
