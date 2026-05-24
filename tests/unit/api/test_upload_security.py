"""Security hardening tests for file upload endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
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


def test_upload_rejects_binary_file(client: TestClient) -> None:
    """Binary content (null bytes) should be rejected with 415."""
    binary_content = bytes(range(256)) * 100
    r = client.post(
        "/api/uploads/upload",
        files={"file": ("test.bin", binary_content, "application/octet-stream")},
    )
    assert r.status_code == 415


def test_upload_accepts_valid_csv(client: TestClient) -> None:
    """Valid CSV content should be accepted (202 or progress HTML)."""
    from tests.fixtures.generate_jtl import make_csv_jtl

    content = make_csv_jtl(n_rows=5)
    r = client.post(
        "/api/uploads/upload",
        files={"file": ("test.csv", content.encode(), "text/csv")},
    )
    assert r.status_code in (200, 202)


def test_upload_accepts_valid_xml(client: TestClient) -> None:
    """Valid XML/JTL content should be accepted (202 or progress HTML)."""
    from tests.fixtures.generate_jtl import make_xml_jtl

    content = make_xml_jtl(n_rows=5)
    r = client.post(
        "/api/uploads/upload",
        files={"file": ("test.jtl", content.encode(), "application/xml")},
    )
    assert r.status_code in (200, 202)


def test_paste_rejects_too_short_content(client: TestClient) -> None:
    """Paste with < 50 chars should be rejected with 400."""
    r = client.post("/api/uploads/paste", data={"content": "short", "name": "test"})
    assert r.status_code == 400


def test_paste_accepts_valid_content(client: TestClient) -> None:
    """Paste with valid CSV content (>= 50 chars) should be accepted."""
    from tests.fixtures.generate_jtl import make_csv_jtl

    content = make_csv_jtl(n_rows=3)
    r = client.post("/api/uploads/paste", data={"content": content, "name": "test"})
    assert r.status_code in (200, 202)
