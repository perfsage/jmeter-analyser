# PerfSage JMeter Analyser — Architectural Design Spec

**Document:** `docs/superpowers/specs/2026-05-24-perfsage-jmeter-analyser-design.md`  
**Date:** 2026-05-24  
**Status:** Draft  
**Author:** PerfSage Engineering

---

## 1. Goals

PerfSage JMeter Analyser is a self-hosted, browser-based performance analysis platform for JMeter result files.

### 1.1 Primary Goals

1. **Zero-friction analysis** — upload a JMeter CSV/JTL file and get an interactive dashboard within seconds.
2. **Deep insights** — 20 interactive Plotly visualisations covering all critical performance dimensions.
3. **SLO-aware** — user-defined SLO thresholds evaluated automatically; pass/fail RAG status on every dashboard.
4. **AI-powered** — multi-provider LLM integration for root-cause analysis and remediation recommendations.
5. **Exportable** — one-click self-contained HTML report and print-quality PDF.
6. **Dockerised** — single `docker compose up` to run everywhere.

### 1.2 Non-Goals (M0 scope)

- Multi-tenancy / authentication (out of scope until M7)
- Real-time JMeter streaming (post-M5)
- Cloud storage / S3 (post-M6)

---

## 2. Unique Selling Points

| Feature | PerfSage | BlazeMeter | JMeter Dashboard |
|---|---|---|---|
| Self-hosted | ✅ | ❌ | ✅ |
| AI recommendations | ✅ | partial | ❌ |
| 20 interactive charts | ✅ | limited | ❌ |
| Baseline comparison | ✅ | ✅ | ❌ |
| SLO engine | ✅ | ✅ | ❌ |
| PDF export | ✅ | ✅ | ❌ |
| Open stack | ✅ | ❌ | ✅ |

---

## 3. Architecture

### 3.1 High-Level Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        Browser                              │
│  HTMX fragments  +  Plotly.js (CDN)  +  SSE progress bar   │
└─────────────┬──────────────────────────────────────┬────────┘
              │ HTTP/SSE                              │ JSON charts
              ▼                                       │
┌─────────────────────────────┐                      │
│     FastAPI (web + REST)    │◄─────────────────────┘
│  /healthz  /api/*  /web/*   │
│  lifespan: data dir setup   │
└──────┬──────────────────────┘
       │ arq.enqueue_job()
       ▼
┌──────────────────┐    pubsub    ┌──────────────────────┐
│  Redis 7-alpine  │◄────────────►│   arq Worker         │
│  (job queue)     │              │  parse → analyse →   │
└──────────────────┘              │  charts → store      │
                                  └───────────┬──────────┘
                    ┌─────────────────────────┤
                    │                         │
          ┌─────────▼──────┐       ┌──────────▼──────────┐
          │  SQLite (meta) │       │  Parquet files       │
          │  (SQLModel)    │       │  (PyArrow / Polars)  │
          └────────────────┘       └─────────────────────-┘
                                            │
                              ┌─────────────▼──────────────┐
                              │  LLM Provider              │
                              │  OpenAI / Anthropic /      │
                              │  Google Gemini             │
                              └────────────────────────────┘
```

### 3.2 Technology Choices

| Layer | Choice | Rationale |
|---|---|---|
| Web framework | FastAPI | async, OpenAPI, excellent HTMX support via Jinja2 |
| UI | HTMX + Jinja2 | server-driven, no JS build step |
| Charts | Plotly | interactive, exportable, Python-native |
| Data engine | Polars + DuckDB | columnar, zero-copy, SQL analytics |
| Serialisation | PyArrow Parquet | compact, columnar, streaming-friendly |
| Jobs | arq + Redis | lightweight, asyncio-native, redis pubsub |
| ORM | SQLModel | SQLAlchemy + Pydantic, type-safe |
| AI | openai / anthropic / google-generativeai | multi-provider, swappable |
| Export | WeasyPrint + Plotly HTML | CSS-print PDF, fully offline |

---

## 4. Data Model

### 4.1 SQLite Entities (SQLModel)

```
Report
  id: int PK
  name: str
  filename: str
  uploaded_at: datetime
  status: Enum[pending, processing, ready, failed]
  parquet_path: str | None
  row_count: int | None
  duration_seconds: float | None
  created_at: datetime

SLOConfig
  id: int PK
  report_id: int FK Report
  name: str                    # e.g. "p95 < 500ms"
  metric: str                  # "p95_ms", "error_rate_pct", "throughput_rps"
  operator: str                # "lt", "gt", "lte", "gte"
  threshold: float
  passed: bool | None

AIInsight
  id: int PK
  report_id: int FK Report
  provider: str
  model: str
  prompt_tokens: int
  completion_tokens: int
  content_md: str
  created_at: datetime
```

### 4.2 Parquet Schema (normalised JMeter sample)

| Column | Type | Notes |
|---|---|---|
| `timestamp_ms` | int64 | epoch milliseconds |
| `elapsed_ms` | int32 | response time |
| `label` | utf8 | sampler label |
| `response_code` | utf8 | HTTP status |
| `success` | bool | |
| `bytes_received` | int32 | |
| `bytes_sent` | int32 | |
| `thread_name` | utf8 | |
| `url` | utf8 | nullable |
| `latency_ms` | int32 | nullable |
| `connect_ms` | int32 | nullable |

---

## 5. Async Processing Flow

```
POST /api/uploads/
  → validate file type & size
  → save to data/uploads/{uuid}.{ext}
  → INSERT Report(status=pending)
  → arq.enqueue_job("parse_and_analyse", file_path, report_id)
  → return {report_id, job_id}

GET /api/jobs/{job_id}/stream  (SSE)
  → subscribe to Redis channel report:{report_id}:progress
  → forward progress events to browser

arq Worker: parse_and_analyse(ctx, file_path, report_id)
  1. detect_format(file_path)
  2. load_csv / load_xml → raw DataFrame
  3. clean(df) → normalised DataFrame
  4. write_parquet(df, data/parquet/{report_id}.parquet)
  5. compute_summary(df) + compute_per_label(df)
  6. evaluate_slos(df, slos)
  7. build all 20 Plotly figures → serialize to JSON
  8. store figure JSON in SQLite (or as sidecar .json files)
  9. UPDATE Report(status=ready)
  10. publish "done" to Redis pubsub
```

---

## 6. The 20 Visualisations

| # | Name | Chart Type | Module |
|---|---|---|---|
| 1 | Response Time Over Time | Line (mean/p95/p99) | `viz/timeseries.py` |
| 2 | Throughput Over Time | Line (rps) | `viz/timeseries.py` |
| 3 | Concurrent Users Over Time | Area | `viz/timeseries.py` |
| 4 | Error Rate Over Time | Line (%) | `viz/timeseries.py` |
| 5 | Response Time Histogram | Bar | `viz/distribution.py` |
| 6 | Cumulative Distribution Function | Line | `viz/distribution.py` |
| 7 | Box Plot by Label | Box | `viz/distribution.py` |
| 8 | Violin Plot by Label | Violin | `viz/distribution.py` |
| 9 | Response Time vs. Concurrency | Scatter | `viz/scatter.py` |
| 10 | Latency vs. Throughput | Scatter | `viz/scatter.py` |
| 11 | Error Rate Heatmap (label × time) | Heatmap | `viz/heatmap.py` |
| 12 | Response Time Heatmap (hour × day) | Heatmap | `viz/heatmap.py` |
| 13 | Trend Decomposition | Multi-panel line | `viz/decomposition.py` |
| 14 | SLO Gauges | Gauge | `viz/slo.py` |
| 15 | SLO Burn-Rate Bar Chart | Grouped bar | `viz/slo.py` |
| 16 | Per-Label Summary Table | Plotly Table | `viz/tables.py` |
| 17 | Percentile Ladder | Bar (p50/p90/p95/p99) | `viz/distribution.py` |
| 18 | Baseline Comparison (two runs) | Grouped bar | `viz/timeseries.py` |
| 19 | Thread Ramp-Up Profile | Area | `viz/timeseries.py` |
| 20 | Bytes Sent/Received Over Time | Stacked area | `viz/timeseries.py` |

---

## 7. AI Integration

### 7.1 Provider Abstraction

```python
class LLMProvider(Protocol):
    async def complete(self, prompt: str, *, max_tokens: int = 2048) -> str: ...
```

Adapters: `OpenAIProvider`, `AnthropicProvider`, `GeminiProvider`

### 7.2 Analysis Prompt Flow

1. Serialise `compute_summary()` + `compute_per_label()` + `evaluate_slos()` results to JSON.
2. Build `(system_prompt, user_prompt)` via `prompts.build_analysis_prompt()`.
3. Call `provider.complete(user_prompt)` with system context.
4. Stream response tokens via SSE to the browser (Markdown rendered client-side).
5. Persist full response to `AIInsight` row.

---

## 8. Branding

| Token | Value | Usage |
|---|---|---|
| `--navy` | `#0B1F3A` | Page background, header |
| `--cream` | `#F6F1E7` | Content surface, body text |
| `--amber` | `#D4A857` | Primary CTA, headings, accent borders |

Typography: `system-ui, sans-serif` (no web font dependencies for offline use).

---

## 9. Security Considerations

- `PERFSAGE_SECRET` seeds HMAC for signed upload tokens.
- File uploads validated by magic bytes, not extension.
- WeasyPrint renders HTML in a sandboxed subprocess.
- Non-root Docker user (uid 1000).
- `data/` directory mounted as a named volume, not baked into the image.

---

## 10. Project Layout

See the README for the canonical directory tree. Key conventions:

- `perfsage/api/` — FastAPI routers (REST only, no HTML rendering)
- `perfsage/web/` — Jinja2 templates + HTMX views
- `perfsage/core/` — pure domain logic, no FastAPI imports
- `perfsage/core/jobs/` — arq task definitions; `queue.py` owns `WorkerSettings`
- `tests/unit/` — fast, no I/O
- `tests/integration/` — real SQLite + Parquet, no network
- `tests/e2e/` — Playwright, requires running server

---

## 11. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Parse 100k-row CSV | < 5 seconds |
| Generate all 20 charts | < 10 seconds after parse |
| HTML export | < 3 seconds |
| PDF export | < 15 seconds |
| Memory footprint (worker) | < 512 MB per job |
| Docker image size | < 500 MB |

---

*End of Spec — v0.1.0*
