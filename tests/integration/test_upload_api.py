"""Integration tests for the /api/uploads/upload endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from perfsage.config import Settings, get_settings
from perfsage.core.storage.db import get_engine
from perfsage.core.storage.files import FileStore
from perfsage.main import create_app

_SAMPLE_CSV = """\
timeStamp,elapsed,label,responseCode,responseMessage,threadName,success,bytes,sentBytes,grpThreads,allThreads,URL,Latency,IdleTime,Connect
1716556800000,100,GET /api,200,OK,Thread-1,true,1024,256,1,1,http://example.com/api,95,0,5
1716556800100,200,POST /data,200,OK,Thread-1,true,2048,512,1,1,http://example.com/data,190,0,10
"""


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
def client(_settings: Settings, tmp_path):  # type: ignore[type-arg, return]
    mock_redis = AsyncMock()
    mock_redis.enqueue_job = AsyncMock(return_value=MagicMock(job_id="mock-arq-job"))

    engine = get_engine(_settings.database_url)

    app = create_app()
    app.dependency_overrides[get_settings] = lambda: _settings
    # Manually inject state so upload handler can access engine + redis
    # without triggering the real lifespan (which would connect to Redis)
    app.state.engine = engine
    app.state.redis = mock_redis

    yield TestClient(app)  # no `with` → lifespan does NOT run


def test_upload_small_csv(client: TestClient, _settings: Settings, tmp_path) -> None:  # type: ignore[type-arg]
    response = client.post(
        "/api/uploads/upload",
        files={"file": ("results.jtl", _SAMPLE_CSV.encode(), "text/plain")},
    )

    assert response.status_code == 202, response.text
    data = response.json()
    assert "report_id" in data
    assert "job_id" in data

    # File must be written to data/uploads/{job_id}.jtl
    fs = FileStore(_settings.data_dir)
    assert fs.upload_path(data["job_id"]).exists()


def test_upload_with_name(client: TestClient, _settings: Settings, tmp_path) -> None:  # type: ignore[type-arg]
    response = client.post(
        "/api/uploads/upload",
        files={"file": ("results.jtl", _SAMPLE_CSV.encode(), "text/plain")},
        data={"name": "My Perf Test"},
    )

    assert response.status_code == 202
    data = response.json()
    assert "report_id" in data


def test_upload_too_large(client: TestClient, _settings: Settings) -> None:
    big_file = b"x" * (_settings.max_upload_bytes + 1)
    response = client.post(
        "/api/uploads/upload",
        files={"file": ("huge.jtl", big_file, "text/plain")},
    )
    assert response.status_code == 413


def test_job_status_endpoint(client: TestClient, _settings: Settings, tmp_path) -> None:  # type: ignore[type-arg]
    # Upload first to create a job
    upload_resp = client.post(
        "/api/uploads/upload",
        files={"file": ("r.jtl", _SAMPLE_CSV.encode(), "text/plain")},
    )
    assert upload_resp.status_code == 202
    job_id = upload_resp.json()["job_id"]

    # Now query job status
    status_resp = client.get(f"/api/jobs/{job_id}")
    assert status_resp.status_code == 200
    job_data = status_resp.json()
    assert job_data["id"] == job_id
    assert job_data["status"] in ("queued", "running", "done", "failed", "cancelled")


def test_job_not_found(client: TestClient) -> None:
    resp = client.get("/api/jobs/no-such-job-id")
    assert resp.status_code == 404


def test_sse_endpoint_returns_event_stream(client: TestClient, _settings: Settings, tmp_path) -> None:  # type: ignore[type-arg]
    # Upload first to create a job.
    upload_resp = client.post(
        "/api/uploads/upload",
        files={"file": ("r.jtl", _SAMPLE_CSV.encode(), "text/plain")},
    )
    assert upload_resp.status_code == 202
    job_id = upload_resp.json()["job_id"]

    # Pre-mark the job as done so the SSE generator emits one event and terminates.
    # Without this, the DB-polling fallback loops indefinitely in tests.
    from perfsage.core.storage.db import get_session
    from perfsage.core.storage.repos import JobRepo

    engine = get_engine(_settings.database_url)
    with get_session(engine) as session:
        JobRepo(session).mark_done(job_id)

    # SSE endpoint must return text/event-stream; stream closes after "done" phase.
    with client.stream("GET", f"/api/jobs/{job_id}/events") as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        events = [line for line in resp.iter_lines() if line.startswith("data:")]
    assert len(events) >= 1
