# PerfSage JMeter Analyser — Implementation Plan

**Document:** `docs/superpowers/plans/2026-05-24-perfsage-jmeter-analyser.md`  
**Date:** 2026-05-24  
**Status:** Active  
**Spec:** `docs/superpowers/specs/2026-05-24-perfsage-jmeter-analyser-design.md`

---

## Overview

10 milestones (M0–M9) taking the project from skeleton to production-ready.  
Each milestone is self-contained and ends with all tests green.

---

## M0 — Spec + Skeleton ✅

**Goal:** Working project scaffold, CI green, Docker builds.

### Steps

- [x] M0.1 — Write architectural spec (`docs/superpowers/specs/`)
- [x] M0.2 — Write this implementation plan (`docs/superpowers/plans/`)
- [x] M0.3 — `pyproject.toml` with all dependencies
- [x] M0.4 — Full directory scaffold + stub modules (docstring + `raise NotImplementedError`)
- [x] M0.5 — `perfsage/config.py` — `pydantic-settings` `Settings` + `get_settings()`
- [x] M0.6 — `perfsage/main.py` — FastAPI app factory, lifespan, `GET /healthz`
- [x] M0.7 — `Dockerfile` (multi-stage, non-root)
- [x] M0.8 — `docker-compose.yml` (web + worker + redis)
- [x] M0.9 — `.pre-commit-config.yaml` (ruff + mypy)
- [x] M0.10 — `.github/workflows/ci.yml` (lint + typecheck + test)
- [x] M0.11 — `tests/conftest.py` + `tests/unit/test_smoke.py`
- [x] M0.12 — `git commit -m "feat: M0 - project skeleton and spec docs"`

**Exit criteria:** `pytest -q` passes, `ruff check .` clean, `mypy perfsage` passes.

---

## M1 — JMeter File Parsing

**Goal:** Upload a JMeter CSV or JTL/XML and get a clean Parquet file on disk.

### Steps

- [ ] M1.1 — TDD: write `tests/unit/test_detect.py` (format detection)
- [ ] M1.2 — Implement `core/parsing/detect.py`
- [ ] M1.3 — TDD: write `tests/unit/test_csv_loader.py` with `tests/fixtures/jmeter-samples/small.csv`
- [ ] M1.4 — Implement `core/parsing/csv_loader.py` using Polars lazy scan
- [ ] M1.5 — TDD: write `tests/unit/test_xml_loader.py` with `tests/fixtures/jmeter-samples/small.jtl`
- [ ] M1.6 — Implement `core/parsing/xml_loader.py` using lxml iterparse
- [ ] M1.7 — TDD: `tests/unit/test_cleanup.py` (duplicate rows, null timestamps, type coercion)
- [ ] M1.8 — Implement `core/parsing/cleanup.py`
- [ ] M1.9 — Write Parquet to `data/parquet/{report_id}.parquet` via PyArrow
- [ ] M1.10 — Integration test: upload → Parquet exists + row count matches

**Exit criteria:** 100k-row CSV parsed and written to Parquet in < 5 s.

---

## M2 — Metrics & Analysis Engine

**Goal:** Compute all aggregate metrics, percentiles, SLOs, anomalies.

### Steps

- [ ] M2.1 — TDD: `tests/unit/test_metrics.py` (summary dict, per-label DataFrame)
- [ ] M2.2 — Implement `core/analysis/metrics.py` using DuckDB SQL
- [ ] M2.3 — TDD: `tests/unit/test_percentiles.py` (p50/p90/p95/p99)
- [ ] M2.4 — Implement `core/analysis/percentiles.py`
- [ ] M2.5 — TDD: `tests/unit/test_slo.py` (pass/fail cases)
- [ ] M2.6 — Implement `core/analysis/slo.py`
- [ ] M2.7 — TDD: `tests/unit/test_anomalies.py` (known spike dataset)
- [ ] M2.8 — Implement `core/analysis/anomalies.py` (IQR + z-score)
- [ ] M2.9 — TDD: `tests/unit/test_segmentation.py`
- [ ] M2.10 — Implement `core/analysis/segmentation.py`
- [ ] M2.11 — Hypothesis property tests for `percentiles()` (monotonicity)

**Exit criteria:** All analysis tests green; DuckDB query on 100k rows < 1 s.

---

## M3 — Database & Storage Layer

**Goal:** SQLModel entities, repository pattern, file helpers all wired up.

### Steps

- [ ] M3.1 — Define `Report`, `SLOConfig`, `AIInsight` SQLModel models in `core/storage/db.py`
- [ ] M3.2 — TDD: `tests/integration/test_repos.py` (CRUD on in-memory SQLite)
- [ ] M3.3 — Implement `core/storage/repos.py` `ReportRepository`
- [ ] M3.4 — Implement `core/storage/files.py` (uploads/exports/parquet dir helpers)
- [ ] M3.5 — Wire `create_db_and_tables()` into lifespan in `main.py`
- [ ] M3.6 — Alembic migration scaffold (auto-generate from SQLModel)
- [ ] M3.7 — Integration test: report created → retrieved → deleted

**Exit criteria:** All storage tests green on in-memory SQLite.

---

## M4 — Upload API & Background Job Pipeline

**Goal:** `POST /api/uploads/` enqueues job; SSE stream pushes progress to browser.

### Steps

- [ ] M4.1 — TDD: `tests/integration/test_upload_api.py` (multipart form, size limit)
- [ ] M4.2 — Implement `api/uploads.py` `POST /api/uploads/`
- [ ] M4.3 — Implement `core/jobs/tasks.py` `parse_and_analyse()` full pipeline
- [ ] M4.4 — Wire arq Redis connection in lifespan
- [ ] M4.5 — TDD: SSE endpoint test (`GET /api/jobs/{job_id}/stream`)
- [ ] M4.6 — Implement SSE progress endpoint in `api/jobs.py`
- [ ] M4.7 — Integration test: upload → job enqueued → status polling → ready

**Exit criteria:** End-to-end upload test passes with real arq worker (in-process mode).

---

## M5 — 20 Visualisations

**Goal:** All 20 Plotly charts implemented and serialisable to JSON.

### Steps

- [ ] M5.1 — TDD: fixture DataFrame → each chart function returns `go.Figure`
- [ ] M5.2 — Implement `viz/timeseries.py` (charts 1–4, 18–20)
- [ ] M5.3 — Implement `viz/distribution.py` (charts 5–8, 17)
- [ ] M5.4 — Implement `viz/scatter.py` (charts 9–10)
- [ ] M5.5 — Implement `viz/heatmap.py` (charts 11–12)
- [ ] M5.6 — Implement `viz/decomposition.py` (chart 13)
- [ ] M5.7 — Implement `viz/slo.py` (charts 14–15)
- [ ] M5.8 — Implement `viz/tables.py` (chart 16)
- [ ] M5.9 — Snapshot test: each figure's `to_json()` is stable
- [ ] M5.10 — Benchmark: all 20 charts generated < 10 s

**Exit criteria:** 20 chart tests green; JSON round-trip verified.

---

## M6 — HTMX Dashboard UI

**Goal:** Browser shows upload form, live progress bar, interactive dashboard.

### Steps

- [ ] M6.1 — Extend `base.html` with nav, upload form, HTMX wiring
- [ ] M6.2 — `web/templates/dashboard.html` — chart grid (Plotly JSON embedded)
- [ ] M6.3 — `web/templates/upload.html` — drag-and-drop, SSE progress bar
- [ ] M6.4 — `web/templates/report_list.html` — paginated report list
- [ ] M6.5 — `web/views.py` — all view routes with Jinja2 context
- [ ] M6.6 — CSS in `web/static/css/perfsage.css` (navy/cream/amber variables)
- [ ] M6.7 — E2E test (Playwright): upload → dashboard loads with charts
- [ ] M6.8 — Accessibility pass (ARIA labels, keyboard navigation)

**Exit criteria:** Playwright E2E test passes; Lighthouse score > 80.

---

## M7 — AI Integration

**Goal:** One-click AI analysis with streaming Markdown output.

### Steps

- [ ] M7.1 — TDD: mock provider → `analyse_with_ai()` returns non-empty string
- [ ] M7.2 — Implement `core/ai/providers/openai_provider.py`
- [ ] M7.3 — Implement `core/ai/providers/anthropic_provider.py`
- [ ] M7.4 — Implement `core/ai/providers/gemini_provider.py`
- [ ] M7.5 — Settings: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `AI_PROVIDER`
- [ ] M7.6 — `api/ai.py` `POST /api/ai/analyse/{report_id}` → SSE stream
- [ ] M7.7 — Dashboard "Analyse with AI" button (HTMX SSE target)
- [ ] M7.8 — Persist `AIInsight` row after completion
- [ ] M7.9 — Integration test with recorded VCR cassette

**Exit criteria:** AI analysis streams tokens to the browser; cassette-based test green.

---

## M8 — Export (HTML + PDF)

**Goal:** One-click download of self-contained HTML report and PDF.

### Steps

- [ ] M8.1 — TDD: `tests/unit/test_html_export.py` (file written, contains chart JSON)
- [ ] M8.2 — Implement `core/export/html.py` — inline Plotly JS + all chart JSON
- [ ] M8.3 — TDD: `tests/unit/test_pdf_export.py` (file written, non-zero bytes)
- [ ] M8.4 — Implement `core/export/pdf.py` using WeasyPrint
- [ ] M8.5 — `api/exports.py` `GET /api/exports/{report_id}/html` + `.../pdf`
- [ ] M8.6 — Dashboard "Download" buttons
- [ ] M8.7 — E2E test: click download → file saved to `data/exports/`

**Exit criteria:** HTML < 10 MB, PDF < 5 MB for a 10k-row test run.

---

## M9 — Hardening, Security, Polish

**Goal:** Production-ready: auth, rate limiting, monitoring, documentation.

### Steps

- [ ] M9.1 — Token-based upload authentication (HMAC-signed URL)
- [ ] M9.2 — Rate limiting on upload endpoint (slowapi)
- [ ] M9.3 — `/metrics` endpoint (Prometheus-compatible via starlette-prometheus)
- [ ] M9.4 — Structured logging (structlog)
- [ ] M9.5 — Docker healthcheck in Dockerfile
- [ ] M9.6 — `docs/` user guide (Markdown)
- [ ] M9.7 — Full hypothesis property test sweep
- [ ] M9.8 — Security scan (pip-audit, bandit)
- [ ] M9.9 — Load test the API itself (locust)
- [ ] M9.10 — Final `git tag v1.0.0`

**Exit criteria:** CI green, Docker image < 500 MB, `pip-audit` clean, load test passes.

---

## Dependency Map

```
M0 → M1 → M2 → M3 → M4
                      ↓
               M5 → M6 → M7
                    ↓
                   M8
                    ↓
                   M9
```

---

## Definition of Done (per milestone)

1. All new tests pass (`pytest -q`).
2. `ruff check .` + `ruff format --check .` clean.
3. `mypy perfsage` passes.
4. Docker image builds without errors.
5. Git commit with message `feat: M{n} - <title>`.

---

*End of Plan — v0.1.0*
