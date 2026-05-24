"""SQLModel ORM models and database session helpers."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from enum import StrEnum

from sqlalchemy.engine import Engine
from sqlmodel import Field, Session, SQLModel, create_engine


class ReportStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class InsightSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Report(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str
    source_filename: str
    status: ReportStatus = ReportStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    size_bytes: int = 0
    row_count: int = 0
    parsed_row_count: int = 0
    error_row_count: int = 0
    duration_seconds: float = 0.0
    jmeter_version_detected: str | None = None
    slo_config_json: str | None = None
    has_ai_insights: bool = False
    tenant_id: str | None = None


class Job(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    report_id: str = Field(foreign_key="report.id")
    status: JobStatus = JobStatus.QUEUED
    progress_pct: float = 0.0
    phase: str = ""
    message: str = ""
    started_at: datetime | None = None
    ended_at: datetime | None = None
    error_text: str | None = None


class Insight(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    report_id: str = Field(foreign_key="report.id")
    kind: str
    severity: InsightSeverity
    message: str
    data_json: str | None = None


class AppSettings(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value_encrypted: str


def get_engine(database_url: str) -> Engine:
    """Create a SQLAlchemy engine and ensure all tables exist."""
    connect_args: dict[str, object] = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    engine = create_engine(database_url, connect_args=connect_args)
    SQLModel.metadata.create_all(engine)
    return engine


@contextmanager
def get_session(engine: Engine) -> Generator[Session, None, None]:
    """Yield a database session; commit on success, rollback on exception.

    ``expire_on_commit=False`` keeps object attributes accessible after the
    session closes so callers can read returned model instances freely.
    """
    with Session(engine, expire_on_commit=False) as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise
