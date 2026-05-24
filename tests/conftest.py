"""Shared pytest fixtures for all test suites."""

import pytest
from fastapi.testclient import TestClient

from perfsage.config import Settings, get_settings
from perfsage.main import create_app


@pytest.fixture()
def test_settings(tmp_path: object) -> Settings:
    """Return a Settings instance suitable for testing (in-memory SQLite, tmp data dir)."""
    import tempfile
    from pathlib import Path

    data_dir = Path(tempfile.mkdtemp())
    return Settings(
        debug=True,
        database_url="sqlite:///:memory:",
        data_dir=data_dir,
        redis_url="redis://localhost:6379",
        perfsage_secret="test-secret",
    )


@pytest.fixture()
def app(test_settings: Settings) -> object:
    """Return a FastAPI application configured with test settings."""
    get_settings.cache_clear()  # type: ignore[attr-defined]
    application = create_app()
    return application


@pytest.fixture()
def client(app: object) -> TestClient:
    """Return a synchronous TestClient for the FastAPI app."""
    from fastapi import FastAPI

    assert isinstance(app, FastAPI)
    return TestClient(app)
