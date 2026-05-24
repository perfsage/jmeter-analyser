"""Integration tests for export API endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def test_html_export_report_not_found(client: TestClient) -> None:
    r = client.get("/api/exports/nonexistent-id/html")
    assert r.status_code == 404


def test_pdf_export_report_not_found(client: TestClient) -> None:
    r = client.get("/api/exports/nonexistent-id/pdf")
    assert r.status_code == 404


def test_html_export_report_not_ready(client: TestClient, tmp_path: Path) -> None:
    """Report exists but is still in PENDING state → 409."""
    from perfsage.config import get_settings
    from perfsage.core.storage.db import get_engine, get_session
    from perfsage.core.storage.repos import ReportRepo

    settings = client.app.dependency_overrides[get_settings]()  # type: ignore[attr-defined]
    engine = get_engine(settings.database_url)

    with get_session(engine) as session:
        report = ReportRepo(session).create("pending-report", "test.jtl", 1024)
        report_id = report.id

    r = client.get(f"/api/exports/{report_id}/html")
    assert r.status_code == 409


def test_pdf_export_report_not_ready(client: TestClient, tmp_path: Path) -> None:
    """Report exists but is still in PENDING state → 409."""
    from perfsage.config import get_settings
    from perfsage.core.storage.db import get_engine, get_session
    from perfsage.core.storage.repos import ReportRepo

    settings = client.app.dependency_overrides[get_settings]()  # type: ignore[attr-defined]
    engine = get_engine(settings.database_url)

    with get_session(engine) as session:
        report = ReportRepo(session).create("pending-pdf-report", "test.jtl", 1024)
        report_id = report.id

    r = client.get(f"/api/exports/{report_id}/pdf")
    assert r.status_code == 409


def test_html_export_ready_report(client: TestClient, sample_parquet: Path) -> None:
    """READY report with parquet data returns HTML file."""
    from perfsage.config import get_settings
    from perfsage.core.storage.db import ReportStatus, get_engine, get_session
    from perfsage.core.storage.repos import ReportRepo

    settings = client.app.dependency_overrides[get_settings]()  # type: ignore[attr-defined]
    engine = get_engine(settings.database_url)

    with get_session(engine) as session:
        report = ReportRepo(session).create("ready-html-report", "test.jtl", 1024)
        ReportRepo(session).update_status(report.id, ReportStatus.READY)
        report_id = report.id

    # Place the parquet at the expected location
    parquet_dir = settings.data_dir / "parquet" / report_id
    parquet_dir.mkdir(parents=True, exist_ok=True)
    import shutil

    shutil.copy(sample_parquet, parquet_dir / "samples.parquet")

    r = client.get(f"/api/exports/{report_id}/html")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert b"PerfSage" in r.content


def test_pdf_export_ready_report(client: TestClient, sample_parquet: Path) -> None:
    """READY report with parquet data returns a valid PDF."""
    from perfsage.config import get_settings
    from perfsage.core.storage.db import ReportStatus, get_engine, get_session
    from perfsage.core.storage.repos import ReportRepo

    settings = client.app.dependency_overrides[get_settings]()  # type: ignore[attr-defined]
    engine = get_engine(settings.database_url)

    with get_session(engine) as session:
        report = ReportRepo(session).create("ready-pdf-report", "test.jtl", 1024)
        ReportRepo(session).update_status(report.id, ReportStatus.READY)
        report_id = report.id

    parquet_dir = settings.data_dir / "parquet" / report_id
    parquet_dir.mkdir(parents=True, exist_ok=True)
    import shutil

    shutil.copy(sample_parquet, parquet_dir / "samples.parquet")

    r = client.get(f"/api/exports/{report_id}/pdf")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content[:4] == b"%PDF"


def test_html_export_cached(client: TestClient, sample_parquet: Path) -> None:
    """Calling the HTML endpoint twice returns cached file (no regeneration)."""
    from perfsage.config import get_settings
    from perfsage.core.storage.db import ReportStatus, get_engine, get_session
    from perfsage.core.storage.repos import ReportRepo

    settings = client.app.dependency_overrides[get_settings]()  # type: ignore[attr-defined]
    engine = get_engine(settings.database_url)

    with get_session(engine) as session:
        report = ReportRepo(session).create("cached-html-report", "test.jtl", 1024)
        ReportRepo(session).update_status(report.id, ReportStatus.READY)
        report_id = report.id

    parquet_dir = settings.data_dir / "parquet" / report_id
    parquet_dir.mkdir(parents=True, exist_ok=True)
    import shutil

    shutil.copy(sample_parquet, parquet_dir / "samples.parquet")

    r1 = client.get(f"/api/exports/{report_id}/html")
    assert r1.status_code == 200

    # Pre-cache the file's mtime
    export_path = settings.data_dir / "exports" / f"{report_id}.html"
    mtime1 = export_path.stat().st_mtime

    r2 = client.get(f"/api/exports/{report_id}/html")
    assert r2.status_code == 200
    assert export_path.stat().st_mtime == mtime1  # not regenerated
