"""Smoke tests — ensure the app imports cleanly and /healthz works."""

from fastapi.testclient import TestClient


def test_app_imports() -> None:
    """Importing the app must not raise any exception."""
    from perfsage.main import app

    assert app is not None


def test_healthz(client: TestClient) -> None:
    """GET /healthz must return 200 and {status: ok}."""
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
