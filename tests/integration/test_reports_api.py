"""Integration tests for reports flush and pagination."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from perfsage.config import Settings, get_settings
from perfsage.core.storage.db import get_engine
from perfsage.core.storage.repos import ReportRepo
from perfsage.main import create_app


@pytest.fixture()
def _settings(tmp_path):  # type: ignore[type-arg]
    return Settings(
        debug=True,
        database_url=f"sqlite:///{tmp_path}/test.db",
        data_dir=tmp_path,
        redis_url="redis://localhost:6379",
        perfsage_secret="test-secret-32-chars-long-enough!",
    )


@pytest.fixture()
def client(_settings: Settings):  # type: ignore[type-arg, return]
    mock_redis = AsyncMock()
    mock_redis.enqueue_job = AsyncMock(return_value=MagicMock(job_id="mock-arq-job"))
    engine = get_engine(_settings.database_url)
    with Session(engine) as session:
        for i in range(7):
            ReportRepo(session).create(
                name=f"report-{i}",
                source_filename=f"{i}.jtl",
                size_bytes=10,
            )

    app = create_app()
    app.dependency_overrides[get_settings] = lambda: _settings
    app.state.engine = engine
    app.state.redis = mock_redis
    yield TestClient(app)


def test_flush_api_deletes_old_keeps_recent(client: TestClient) -> None:
    r = client.post("/api/reports/flush?keep_recent=2")
    assert r.status_code == 200
    data = r.json()
    assert data["deleted"] == 5
    assert data["keep_recent"] == 2


def test_reports_pagination(client: TestClient) -> None:
    r = client.get("/reports?page=1&per_page=3")
    assert r.status_code == 200
    assert "Page 1 of" in r.text

    r2 = client.get("/reports?page=2&per_page=3", headers={"HX-Request": "true"})
    assert r2.status_code == 200
    assert "report-" in r2.text
