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


def test_settings_page_reflects_saved_slo_defaults(client: TestClient) -> None:
    r = client.post(
        "/api/settings/slo",
        data={"p90_ms": "250", "p99_ms": "800", "error_rate_pct": "0.5", "apdex_t": "0.25"},
    )
    assert r.status_code == 200
    r2 = client.get("/settings")
    assert r2.status_code == 200
    assert "250" in r2.text
    assert "800" in r2.text


def test_report_detail_escapes_malicious_label(
    client: TestClient, test_settings, tmp_path
) -> None:
    import polars as pl
    from perfsage.core.storage.db import ReportStatus, get_engine, get_session
    from perfsage.core.storage.repos import ReportRepo
    from perfsage.core.storage.files import FileStore

    engine = get_engine(test_settings.database_url)
    with get_session(engine) as session:
        report = ReportRepo(session).create("xss.csv", "xss.csv", 10)
        ReportRepo(session).update_stats(
            report.id, status=ReportStatus.READY, parsed_row_count=1, row_count=1
        )
        report_id = report.id

    file_store = FileStore(test_settings.data_dir)
    samples_path = file_store.samples_parquet(report_id)
    samples_path.parent.mkdir(parents=True, exist_ok=True)
    malicious_label = "x</script><script>window.__pwned=1</script>"
    pl.DataFrame(
        {
            "timestamp_ms": [1_700_000_000_000],
            "elapsed": [100],
            "label": [malicious_label],
            "success": [True],
        }
    ).write_parquet(samples_path)

    r = client.get(f"/reports/{report_id}")
    assert r.status_code == 200
    assert "<script>window.__pwned" not in r.text
    assert "</script><script>" not in r.text
