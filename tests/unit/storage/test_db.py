"""Unit tests for SQLModel ORM models and session helpers."""

from __future__ import annotations

import pytest
from sqlalchemy.engine import Engine

from perfsage.core.storage.db import (
    InsightSeverity,
    JobStatus,
    ReportStatus,
    get_engine,
    get_session,
)
from perfsage.core.storage.repos import AppSettingsRepo, InsightRepo, JobRepo, ReportRepo


@pytest.fixture()
def engine(tmp_path: object) -> Engine:  # type: ignore[type-arg]
    assert hasattr(tmp_path, "__truediv__")
    from pathlib import Path

    p = Path(str(tmp_path))
    eng: Engine = get_engine(f"sqlite:///{p / 'test.db'}")
    yield eng  # type: ignore[misc]
    eng.dispose()


def test_create_report(engine: Engine) -> None:
    with get_session(engine) as session:
        repo = ReportRepo(session)
        report = repo.create("My Report", "results.csv", 1024)

    assert report.id is not None
    assert len(report.id) == 36  # UUID format
    assert report.name == "My Report"
    assert report.source_filename == "results.csv"
    assert report.size_bytes == 1024
    assert report.status == ReportStatus.PENDING
    assert report.has_ai_insights is False


def test_get_report_roundtrip(engine: Engine) -> None:
    with get_session(engine) as session:
        repo = ReportRepo(session)
        created = repo.create("Roundtrip", "file.jtl", 512)
        report_id = created.id

    with get_session(engine) as session:
        fetched = ReportRepo(session).get(report_id)

    assert fetched is not None
    assert fetched.id == report_id
    assert fetched.name == "Roundtrip"


def test_report_not_found(engine: Engine) -> None:
    with get_session(engine) as session:
        result = ReportRepo(session).get("nonexistent-id")
    assert result is None


def test_list_reports(engine: Engine) -> None:
    with get_session(engine) as session:
        repo = ReportRepo(session)
        repo.create("R1", "f1.csv", 100)
        repo.create("R2", "f2.csv", 200)

    with get_session(engine) as session:
        reports = ReportRepo(session).list_all()

    assert len(reports) == 2
    names = {r.name for r in reports}
    assert names == {"R1", "R2"}


def test_update_report_status(engine: Engine) -> None:
    with get_session(engine) as session:
        report = ReportRepo(session).create("S", "s.csv", 0)
        report_id = report.id

    with get_session(engine) as session:
        ReportRepo(session).update_status(report_id, ReportStatus.PROCESSING)

    with get_session(engine) as session:
        updated = ReportRepo(session).get(report_id)

    assert updated is not None
    assert updated.status == ReportStatus.PROCESSING


def test_update_report_stats(engine: Engine) -> None:
    with get_session(engine) as session:
        report = ReportRepo(session).create("Stats", "s.csv", 0)
        report_id = report.id

    with get_session(engine) as session:
        ReportRepo(session).update_stats(report_id, parsed_row_count=500, duration_seconds=3.14)

    with get_session(engine) as session:
        updated = ReportRepo(session).get(report_id)

    assert updated is not None
    assert updated.parsed_row_count == 500
    assert abs(updated.duration_seconds - 3.14) < 1e-6


def test_create_job(engine: Engine) -> None:
    with get_session(engine) as session:
        report = ReportRepo(session).create("J", "j.csv", 0)
        job = JobRepo(session).create(report.id)

    assert job.id is not None
    assert job.report_id == report.id
    assert job.status == JobStatus.QUEUED
    assert job.progress_pct == 0.0
    assert job.phase == ""


def test_update_job_progress(engine: Engine) -> None:
    with get_session(engine) as session:
        report = ReportRepo(session).create("R", "f.csv", 0)
        job = JobRepo(session).create(report.id)
        job_id = job.id

    with get_session(engine) as session:
        JobRepo(session).update_progress(job_id, 50.0, "parse", "halfway")

    with get_session(engine) as session:
        updated = JobRepo(session).get(job_id)

    assert updated is not None
    assert updated.progress_pct == 50.0
    assert updated.phase == "parse"
    assert updated.message == "halfway"
    assert updated.status == JobStatus.RUNNING
    assert updated.started_at is not None


def test_mark_job_done(engine: Engine) -> None:
    with get_session(engine) as session:
        report = ReportRepo(session).create("R", "f.csv", 0)
        job = JobRepo(session).create(report.id)
        job_id = job.id

    with get_session(engine) as session:
        JobRepo(session).mark_done(job_id)

    with get_session(engine) as session:
        done = JobRepo(session).get(job_id)

    assert done is not None
    assert done.status == JobStatus.DONE
    assert done.progress_pct == 100.0
    assert done.ended_at is not None


def test_mark_job_failed(engine: Engine) -> None:
    with get_session(engine) as session:
        report = ReportRepo(session).create("R", "f.csv", 0)
        job = JobRepo(session).create(report.id)
        job_id = job.id

    with get_session(engine) as session:
        JobRepo(session).mark_failed(job_id, "something went wrong")

    with get_session(engine) as session:
        failed = JobRepo(session).get(job_id)

    assert failed is not None
    assert failed.status == JobStatus.FAILED
    assert failed.error_text == "something went wrong"
    assert failed.ended_at is not None


def test_get_active_jobs(engine: Engine) -> None:
    with get_session(engine) as session:
        report = ReportRepo(session).create("R", "f.csv", 0)
        j1 = JobRepo(session).create(report.id)
        JobRepo(session).create(report.id)  # j2 stays QUEUED

    # j1: mark RUNNING, j2: stays QUEUED
    with get_session(engine) as session:
        JobRepo(session).update_progress(j1.id, 10.0, "parse")

    with get_session(engine) as session:
        active = JobRepo(session).get_active_jobs()

    assert len(active) == 1
    assert active[0].id == j1.id


def test_insight_creation(engine: Engine) -> None:
    with get_session(engine) as session:
        report = ReportRepo(session).create("R2", "f2.csv", 0)
        insight = InsightRepo(session).create(
            report.id, "recommendation", InsightSeverity.WARNING, "High error rate"
        )

    assert insight.id is not None
    assert insight.report_id == report.id
    assert insight.kind == "recommendation"
    assert insight.severity == InsightSeverity.WARNING
    assert insight.message == "High error rate"
    assert insight.data_json is None


def test_insight_with_data(engine: Engine) -> None:
    with get_session(engine) as session:
        report = ReportRepo(session).create("R3", "f3.csv", 0)
        insight = InsightRepo(session).create(
            report.id,
            "anomaly",
            InsightSeverity.CRITICAL,
            "Spike at 14:00",
            data={"label": "GET /api", "p99": 5000},
        )

    assert insight.data_json is not None
    import json

    data = json.loads(insight.data_json)
    assert data["p99"] == 5000


def test_list_insights_for_report(engine: Engine) -> None:
    with get_session(engine) as session:
        r1 = ReportRepo(session).create("R1", "f1.csv", 0)
        r2 = ReportRepo(session).create("R2", "f2.csv", 0)
        InsightRepo(session).create(r1.id, "rec", InsightSeverity.INFO, "m1")
        InsightRepo(session).create(r1.id, "rec", InsightSeverity.INFO, "m2")
        InsightRepo(session).create(r2.id, "rec", InsightSeverity.INFO, "m3")

    with get_session(engine) as session:
        insights = InsightRepo(session).list_for_report(r1.id)

    assert len(insights) == 2
    assert all(i.report_id == r1.id for i in insights)


def test_app_settings_repo(engine: Engine) -> None:
    with get_session(engine) as session:
        repo = AppSettingsRepo(session)
        repo.set("openai_key", "encrypted_abc")

    with get_session(engine) as session:
        val = AppSettingsRepo(session).get("openai_key")

    assert val == "encrypted_abc"


def test_app_settings_upsert(engine: Engine) -> None:
    with get_session(engine) as session:
        repo = AppSettingsRepo(session)
        repo.set("key1", "v1")
        repo.set("key1", "v2")

    with get_session(engine) as session:
        val = AppSettingsRepo(session).get("key1")

    assert val == "v2"


def test_app_settings_missing(engine: Engine) -> None:
    with get_session(engine) as session:
        val = AppSettingsRepo(session).get("no_such_key")
    assert val is None
