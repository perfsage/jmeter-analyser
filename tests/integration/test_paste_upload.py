"""Integration tests for /api/uploads/paste endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from perfsage.config import Settings, get_settings
from perfsage.core.storage.db import get_engine
from perfsage.main import create_app


@pytest.fixture()
def _settings(tmp_path):  # type: ignore[type-arg]
    return Settings(
        debug=True,
        database_url=f"sqlite:///{tmp_path}/test.db",
        data_dir=tmp_path,
        redis_url="redis://localhost:6379",
        perfsage_secret="test-secret-32-chars-long-enough!",
        max_upload_bytes=10 * 1024 * 1024,
    )


@pytest.fixture()
def client(_settings: Settings):  # type: ignore[type-arg]
    mock_redis = AsyncMock()
    mock_redis.enqueue_job = AsyncMock(return_value=MagicMock(job_id="mock-arq-job"))

    engine = get_engine(_settings.database_url)

    app = create_app()
    app.dependency_overrides[get_settings] = lambda: _settings
    app.state.engine = engine
    app.state.redis = mock_redis

    return TestClient(app)  # no `with` → lifespan does NOT run


def test_paste_csv_content(client: TestClient) -> None:
    from tests.fixtures.generate_jtl import make_csv_jtl

    content = make_csv_jtl(n_rows=50)
    r = client.post("/api/uploads/paste", data={"content": content, "name": "test paste"})
    assert r.status_code == 200
    # Should return HTML progress partial
    assert "progress" in r.text.lower() or "job" in r.text.lower()


def test_paste_creates_report_and_job(client: TestClient, _settings: Settings) -> None:
    from perfsage.core.storage.db import get_session
    from perfsage.core.storage.repos import ReportRepo
    from tests.fixtures.generate_jtl import make_csv_jtl

    content = make_csv_jtl(n_rows=10)
    r = client.post("/api/uploads/paste", data={"content": content, "name": "paste-test-report"})
    assert r.status_code == 200

    engine = get_engine(_settings.database_url)
    with get_session(engine) as session:
        reports = ReportRepo(session).list_all()
    assert any(rep.name == "paste-test-report" for rep in reports)


def test_paste_default_name(client: TestClient) -> None:
    """Paste without a name gets a default name."""
    from tests.fixtures.generate_jtl import make_csv_jtl

    content = make_csv_jtl(n_rows=5)
    r = client.post("/api/uploads/paste", data={"content": content})
    assert r.status_code == 200


def test_paste_writes_file(client: TestClient, _settings: Settings) -> None:
    from perfsage.core.storage.db import get_session
    from perfsage.core.storage.files import FileStore
    from tests.fixtures.generate_jtl import make_csv_jtl

    content = make_csv_jtl(n_rows=5)
    r = client.post("/api/uploads/paste", data={"content": content, "name": "file-check"})
    assert r.status_code == 200

    engine = get_engine(_settings.database_url)
    fs = FileStore(_settings.data_dir)
    with get_session(engine) as session:
        jobs = list(session.exec(__import__("sqlmodel").select(__import__("perfsage.core.storage.db", fromlist=["Job"]).Job)).all())

    assert len(jobs) >= 1
    upload_path = fs.upload_path(jobs[-1].id)
    assert upload_path.exists()


def test_upload_htmx_returns_html(client: TestClient) -> None:
    """Upload with HX-Request header returns HTML progress fragment."""
    csv = "timeStamp,elapsed,label,responseCode,responseMessage,threadName,success,bytes,sentBytes,grpThreads,allThreads,URL,latency,IdleTime,Connect\n1716556800000,100,GET /api,200,OK,Thread-1,true,1024,256,1,1,http://example.com/api,95,0,5\n"
    r = client.post(
        "/api/uploads/upload",
        files={"file": ("results.jtl", csv.encode(), "text/plain")},
        headers={"HX-Request": "true"},
    )
    assert r.status_code == 200
    assert "progress" in r.text.lower() or "EventSource" in r.text


def test_upload_non_htmx_returns_json(client: TestClient) -> None:
    """Upload without HX-Request header still returns JSON with 202."""
    csv = "timeStamp,elapsed,label,responseCode,responseMessage,threadName,success,bytes,sentBytes,grpThreads,allThreads,URL,latency,IdleTime,Connect\n1716556800000,100,GET /api,200,OK,Thread-1,true,1024,256,1,1,http://example.com/api,95,0,5\n"
    r = client.post(
        "/api/uploads/upload",
        files={"file": ("results.jtl", csv.encode(), "text/plain")},
    )
    assert r.status_code == 202
    data = r.json()
    assert "report_id" in data
    assert "job_id" in data
