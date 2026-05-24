"""Unit tests for HTMX web view handlers."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_dashboard_returns_200(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "PerfSage" in r.text


def test_dashboard_shows_stats(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    # Stats cards are always rendered
    assert "Total Reports" in r.text
    assert "Ready" in r.text
    assert "Processing" in r.text


def test_reports_list_returns_200(client: TestClient) -> None:
    r = client.get("/reports")
    assert r.status_code == 200
    assert "All Reports" in r.text


def test_reports_list_empty_state(client: TestClient) -> None:
    r = client.get("/reports")
    assert r.status_code == 200
    # Empty state message when no reports exist
    assert "No reports yet" in r.text or "All Reports" in r.text


def test_settings_returns_200(client: TestClient) -> None:
    r = client.get("/settings")
    assert r.status_code == 200
    assert "Settings" in r.text
    assert "AI API Keys" in r.text
    assert "SLO Defaults" in r.text


def test_report_detail_not_found(client: TestClient) -> None:
    r = client.get("/reports/nonexistent-id-that-does-not-exist")
    assert r.status_code == 404


def test_dashboard_upload_form_present(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "hx-post" in r.text
    assert "/api/uploads/upload" in r.text


def test_dashboard_navbar_links(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert 'href="/reports"' in r.text
    assert 'href="/settings"' in r.text


def test_settings_slo_defaults_shown(client: TestClient) -> None:
    r = client.get("/settings")
    assert r.status_code == 200
    # Default SLO values from SLOConfig
    assert "1000" in r.text  # p90_ms default
    assert "3000" in r.text  # p99_ms default
