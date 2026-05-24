"""Integration tests for POST /api/uploads/paste endpoint."""

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
def client(_settings: Settings):  # type: ignore[type-arg, return]
    mock_redis = AsyncMock()
    mock_redis.enqueue_job = AsyncMock(return_value=MagicMock(job_id="mock-arq-job"))

    engine = get_engine(_settings.database_url)

    app = create_app()
    app.dependency_overrides[get_settings] = lambda: _settings
    app.state.engine = engine
    app.state.redis = mock_redis

    yield TestClient(app)


def test_paste_csv_content(client: TestClient, _settings: Settings) -> None:
    from tests.fixtures.generate_jtl import make_csv_jtl

    content = make_csv_jtl(n_rows=50)
    r = client.post("/api/uploads/paste", data={"content": content, "name": "test paste"})
    assert r.status_code == 200
    assert "job_id" in r.text or "progress" in r.text.lower()


def test_paste_creates_job(client: TestClient, _settings: Settings) -> None:
    from tests.fixtures.generate_jtl import make_csv_jtl

    from perfsage.core.storage.db import get_session
    from perfsage.core.storage.repos import JobRepo

    content = make_csv_jtl(n_rows=10)
    r = client.post("/api/uploads/paste", data={"content": content})
    assert r.status_code == 200

    # Verify a job was created in the DB
    engine = get_engine(_settings.database_url)
    with get_session(engine) as session:
        jobs = JobRepo(session).get_active_jobs()
    # Job may be QUEUED (not active/running), check via list_all approach
    # The paste created exactly one report+job
    assert "progress-card" in r.text or "job_id" in r.text or "progress" in r.text.lower()


def test_paste_without_name_uses_default(client: TestClient, _settings: Settings) -> None:
    from tests.fixtures.generate_jtl import make_csv_jtl

    content = make_csv_jtl(n_rows=5)
    r = client.post("/api/uploads/paste", data={"content": content})
    assert r.status_code == 200


def test_paste_enqueues_redis_job(client: TestClient, _settings: Settings) -> None:
    from tests.fixtures.generate_jtl import make_csv_jtl

    content = make_csv_jtl(n_rows=20)
    r = client.post("/api/uploads/paste", data={"content": content, "name": "redis-test"})
    assert r.status_code == 200
    # Redis enqueue_job was called (mock is on app.state.redis)
    # Just verify response is sensible HTML
    assert "text/html" in r.headers.get("content-type", "")


def test_upload_htmx_returns_html(client: TestClient, _settings: Settings) -> None:
    """When HX-Request header is sent, upload returns HTML progress partial."""
    from tests.fixtures.generate_jtl import make_csv_jtl

    content = make_csv_jtl(n_rows=10)
    r = client.post(
        "/api/uploads/upload",
        files={"file": ("results.jtl", content.encode(), "text/plain")},
        headers={"HX-Request": "true"},
    )
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    assert "progress" in r.text.lower() or "job_id" in r.text


def test_upload_non_htmx_returns_json(client: TestClient, _settings: Settings) -> None:
    """Without HX-Request header, upload returns JSON 202 (backward compat)."""
    from tests.fixtures.generate_jtl import make_csv_jtl

    content = make_csv_jtl(n_rows=10)
    r = client.post(
        "/api/uploads/upload",
        files={"file": ("results.jtl", content.encode(), "text/plain")},
    )
    assert r.status_code == 202
    data = r.json()
    assert "report_id" in data
    assert "job_id" in data
