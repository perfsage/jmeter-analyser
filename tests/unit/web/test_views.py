"""Unit tests for web view handlers."""

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


def test_dashboard_returns_200(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "PerfSage" in r.text


def test_dashboard_shows_stats(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "Total Reports" in r.text
    assert "Ready" in r.text
    assert "Processing" in r.text


def test_dashboard_has_upload_form(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "upload" in r.text.lower()
    assert "drop" in r.text.lower()


def test_reports_list_returns_200(client: TestClient) -> None:
    r = client.get("/reports")
    assert r.status_code == 200
    assert "Reports" in r.text


def test_reports_list_empty_state(client: TestClient) -> None:
    r = client.get("/reports")
    assert r.status_code == 200
    assert "No reports yet" in r.text


def test_settings_returns_200(client: TestClient) -> None:
    r = client.get("/settings")
    assert r.status_code == 200
    assert "Settings" in r.text


def test_settings_has_ai_section(client: TestClient) -> None:
    r = client.get("/settings")
    assert r.status_code == 200
    assert "AI API Keys" in r.text or "AI" in r.text


def test_settings_has_slo_section(client: TestClient) -> None:
    r = client.get("/settings")
    assert r.status_code == 200
    assert "SLO" in r.text


def test_report_detail_not_found(client: TestClient) -> None:
    r = client.get("/reports/nonexistent-id")
    assert r.status_code == 404


def test_healthz_still_works(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
