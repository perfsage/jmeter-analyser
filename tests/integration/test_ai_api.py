"""Integration tests for AI and settings API endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_generate_ai_insights_no_key(client: TestClient) -> None:
    r = client.post("/api/ai/nonexistent-report-id/generate")
    assert r.status_code in (200, 404)
    assert "not found" in r.text.lower() or "no ai provider" in r.text.lower()


def test_save_ai_key_invalid_provider(client: TestClient) -> None:
    r = client.post("/api/settings/ai-key", data={"provider": "invalid", "api_key": "test"})
    assert r.status_code == 200
    assert "Invalid provider" in r.text


def test_save_ai_key_empty_key(client: TestClient) -> None:
    r = client.post("/api/settings/ai-key", data={"provider": "openai", "api_key": ""})
    assert r.status_code == 200
    assert "empty" in r.text.lower()


def test_save_ai_key_valid(client: TestClient) -> None:
    r = client.post(
        "/api/settings/ai-key", data={"provider": "openai", "api_key": "sk-test-key-123"}
    )
    assert r.status_code == 200
    assert "saved" in r.text.lower()


def test_save_slo_defaults(client: TestClient) -> None:
    r = client.post(
        "/api/settings/slo",
        data={"p90_ms": "800", "p99_ms": "2000", "error_rate_pct": "2.0", "apdex_t": "0.5"},
    )
    assert r.status_code == 200
    assert "saved" in r.text.lower()
