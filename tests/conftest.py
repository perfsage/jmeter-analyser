"""Shared pytest fixtures for all test suites."""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from perfsage.config import Settings, get_settings
from perfsage.main import create_app


@pytest.fixture()
def test_settings(tmp_path: Path) -> Settings:
    """Return a Settings instance suitable for testing (in-memory SQLite, tmp data dir)."""
    return Settings(
        debug=True,
        database_url=f"sqlite:///{tmp_path}/test.db",
        data_dir=tmp_path,
        redis_url="redis://localhost:6379",
        perfsage_secret="test-secret-32-chars-long-enough!",
        max_upload_bytes=10 * 1024 * 1024,
    )


@pytest.fixture()
def app(test_settings: Settings) -> FastAPI:
    """Return a FastAPI application configured with test settings."""
    get_settings.cache_clear()  # type: ignore[attr-defined]
    application = create_app()
    application.dependency_overrides[get_settings] = lambda: test_settings
    return application


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    """Return a synchronous TestClient for the FastAPI app."""
    return TestClient(app)
