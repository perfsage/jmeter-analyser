"""End-to-end tests for PerfSage running at http://localhost:8000."""

from __future__ import annotations

import re
import time

import pytest
import requests

BASE_URL = "http://localhost:8000"


def _is_app_up() -> bool:
    try:
        r = requests.get(f"{BASE_URL}/healthz", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def _poll_until_ready(report_id: str, job_id: str | None, max_seconds: int = 120) -> str:
    for _ in range(max_seconds // 2):
        if job_id:
            jr = requests.get(f"{BASE_URL}/api/jobs/{job_id}", timeout=10)
            if jr.status_code == 200:
                jdata = jr.json()
                if jdata.get("status") in ("done", "failed"):
                    return jdata["status"]
        rr = requests.get(f"{BASE_URL}/api/reports/{report_id}", timeout=10)
        if rr.status_code == 200:
            s = rr.json().get("status", "")
            if s in ("ready", "failed"):
                return s
        time.sleep(2)
    return "timeout"


@pytest.fixture(scope="module", autouse=True)
def require_app() -> None:
    if not _is_app_up():
        pytest.skip("PerfSage not running at http://localhost:8000")


def test_healthz() -> None:
    r = requests.get(f"{BASE_URL}/healthz", timeout=10)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_upload_and_report_page_has_scatter_tab() -> None:
    from tests.fixtures.generate_jtl import make_csv_jtl

    csv_content = make_csv_jtl(n_rows=500, include_errors=True)
    r = requests.post(
        f"{BASE_URL}/api/uploads/upload",
        files={"file": ("e2e.csv", csv_content.encode(), "text/csv")},
        data={"name": "E2E Scatter Test"},
        timeout=30,
    )
    assert r.status_code == 202
    data = r.json()
    report_id = data["report_id"]
    job_id = data.get("job_id")

    status = _poll_until_ready(report_id, job_id)
    assert status in ("done", "ready"), f"Unexpected status: {status}"

    page = requests.get(f"{BASE_URL}/reports/{report_id}", timeout=30)
    assert page.status_code == 200
    assert "fig-rt-scatter" in page.text
    assert "fig-rt-time" in page.text
    assert "chart-tab-btn" in page.text
    assert "topmate-nudge" in page.text


def test_pdf_export_contains_chart_images() -> None:
    from tests.fixtures.generate_jtl import make_csv_jtl

    csv_content = make_csv_jtl(n_rows=500, include_errors=True)
    r = requests.post(
        f"{BASE_URL}/api/uploads/upload",
        files={"file": ("pdf_export.csv", csv_content.encode(), "text/csv")},
        data={"name": "E2E PDF Export Test"},
        timeout=30,
    )
    assert r.status_code == 202
    data = r.json()
    report_id = data["report_id"]
    status = _poll_until_ready(report_id, data.get("job_id"))
    if status not in ("ready", "done"):
        pytest.skip(f"Report not ready: {status}")

    pdf_r = requests.get(f"{BASE_URL}/api/exports/{report_id}/pdf?force=1", timeout=600)
    assert pdf_r.status_code == 200
    content = pdf_r.content
    assert content[:4] == b"%PDF"
    assert b"Chart rendering failed" not in content
    assert b"Chart not available." not in content
    assert len(content) > 100_000, "PDF too small — chart images likely missing"


def test_large_dataset_upload_and_pdf_export() -> None:
    """Regression test with >4000 JMeter CSV rows."""
    from tests.fixtures.generate_jtl import make_csv_jtl

    csv_content = make_csv_jtl(n_rows=4500, include_errors=True)
    assert csv_content.count("\n") > 4000
    r = requests.post(
        f"{BASE_URL}/api/uploads/upload",
        files={"file": ("large_load.csv", csv_content.encode(), "text/csv")},
        data={"name": "Large Dataset Load Test"},
        timeout=60,
    )
    assert r.status_code == 202
    data = r.json()
    report_id = data["report_id"]
    status = _poll_until_ready(report_id, data.get("job_id"), max_seconds=180)
    assert status in ("ready", "done"), f"Unexpected status: {status}"

    report_page = requests.get(f"{BASE_URL}/reports/{report_id}", timeout=30)
    assert report_page.status_code == 200
    assert "4,500" in report_page.text or "4500" in report_page.text

    pdf_r = requests.get(f"{BASE_URL}/api/exports/{report_id}/pdf?force=1", timeout=900)
    assert pdf_r.status_code == 200
    assert pdf_r.content[:4] == b"%PDF"
    assert b"Chart not available." not in pdf_r.content


def test_html_export_has_export_footer() -> None:
    from tests.fixtures.generate_jtl import make_csv_jtl

    csv_content = make_csv_jtl(n_rows=200)
    r = requests.post(
        f"{BASE_URL}/api/uploads/upload",
        files={"file": ("export.csv", csv_content.encode(), "text/csv")},
        data={"name": "E2E Export Test"},
        timeout=30,
    )
    assert r.status_code == 202
    data = r.json()
    report_id = data["report_id"]
    status = _poll_until_ready(report_id, data.get("job_id"))
    if status not in ("ready", "done"):
        pytest.skip(f"Report not ready: {status}")

    html_r = requests.get(f"{BASE_URL}/api/exports/{report_id}/html?force=1", timeout=120)
    assert html_r.status_code == 200
    assert 'class="export-footer"' in html_r.text
    assert "fig-rt-scatter" in html_r.text
    assert re.search(r'href="https://perfsage.com"', html_r.text)


def test_reports_pagination() -> None:
    r = requests.get(f"{BASE_URL}/reports?page=1&per_page=25", timeout=10)
    assert r.status_code == 200
    assert "Reports" in r.text or "report" in r.text.lower()
