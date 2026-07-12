# PerfSage Reveal V2 — Roadmap & Phase 0 Design Spec

**Document:** `docs/superpowers/specs/2026-07-12-perfsage-v2-design.md`
**Date:** 2026-07-12
**Status:** Draft
**Author:** PerfSage Engineering (CTO synthesis of Product Manager, QA Engineer, Performance Engineer, and UX Engineer subagent audits)

---

## 0. Executive Summary

PerfSage Reveal v0.1 has a sound architecture (FastAPI + HTMX SSR, Polars/DuckDB analytics, 29 Plotly charts) but two things stand between it and mass adoption:

1. **It gets slow and silent on large files.** The report page synchronously builds all 29 charts before returning any HTML, re-reading the full samples parquet 49-51 times per view, with zero loading feedback. Measured on a 5M-row file: 26-47s render, 2.2-3.5GB RAM, 36.9MB payload. Projected at 10M rows (our target scale): 55-95s, 4.5-7GB RAM — real timeout/OOM risk.
2. **It has no adoption/distribution features.** Competitive research shows the market gap is not more charts (Reveal already leads there) — it's run comparison, shareable links, CI integration, multi-format ingestion, and a public demo. These are what turn a good tool into "part of every performance engineer's arsenal."

This spec covers the full V2 roadmap (for planning) and a fully detailed **Phase 0** design (for immediate implementation): fix the performance/feedback problem and a set of QA-verified defects, without which no adoption feature matters.

---

## 1. Inputs

Four subagent audits fed this design (full transcripts available in session history):

- **Product Manager** — competitive research (JMeter dashboard, BlazeMeter, Grafana+InfluxDB, Gatling, k6, Locust, OctoPerf, JtlReporter, Heimr) and a ranked V2 feature list.
- **QA Engineer** — code-level defect audit with file:line evidence; ran the existing 429-test suite (all passing).
- **Performance Engineer** — empirical benchmark on a synthetic 5M-row/674MB JTL file using the project's real code paths; profiled hotspots with cProfile.
- **UX Engineer** — full template/CSS/JS audit; wait-point inventory and a motion/loading design system spec.

---

## 2. Strategy (decided)

- **Adoption model:** open-source-first. Free, self-hosted, "docker pull and go" is the growth loop. No paid tier this cycle.
- **Scale target:** ~1GB / ~10M-sample JTL files handled smoothly.
- **Frontend direction:** keep server-rendered Jinja2 + HTMX + Plotly. No SPA rewrite. Add lazy-loaded chart fragments and a client-side motion/loading layer on top of the existing stack.

---

## 3. V2 Roadmap (all phases)

| Phase | Theme | Scope |
|---|---|---|
| **0 — this spec** | Fix the foundation | Performance (shared reads, response caching, de-embedded histogram/boxplot, lazy chart sections), loading/motion UX system, QA-critical defect fixes |
| **1** | Adoption trio | Run-vs-run comparison & baselines, shareable read-only report links, CI/CD Action + PR-comment bot, public zero-signup demo instance |
| **2** | TAM expansion | Multi-format ingestion (k6 JSON, Gatling log, Locust CSV), CLI tool, per-report SLO editor, JUnit/Prometheus export |
| **3** | Retention & depth | Trend history across runs, AI-narrated run-diffs, distributed-run JTL merge, remaining Performance Engineer budget items (precomputed rollups, downsampling) |

Phase 1-3 feature detail, rationale, and citations are captured in the Product Manager subagent's report (summarized in Appendix A). They are **not** re-litigated here — this spec's actionable detail is Phase 0 only. Each later phase gets its own brainstorming/design pass when scheduled, per the existing spec-per-phase convention (`docs/superpowers/specs/2026-05-24-perfsage-jmeter-analyser-design.md` covered v0.1 the same way).

**Top 3 revolutionary bets (from PM research), for context on where Phases 1-2 are heading:**
1. The universal load-test analyzer — multi-format ingestion turns Reveal into the analysis layer for the whole load-testing ecosystem, not just a JMeter tool.
2. The self-hosted regression gate that lives in every PR — comparison + CI bot + AI diff narrative on every pull request.
3. Zero-friction proof — public demo + CLI + shareable links, "never heard of it" to "here's a report of my own data" in under 60 seconds.

---

## 4. Phase 0 — Detailed Design

### 4.1 Goals

- Report page time-to-first-byte drops from "wait for all 29 charts" to "wait for KPIs + hero chart"; heavy sections stream in visibly.
- No operation over ~1s runs without visible feedback (skeleton, progress bar, spinner, or fade-in).
- Peak RAM for a report render drops from GB-scale to consistently <1GB at current test scale (5M rows), with a clear path to the <1.5GB/10M-row budget.
- Four QA-verified defects fixed, including one security issue (stored XSS).

### 4.2 Performance Architecture

**Problem, precisely:** every chart builder and analysis function independently opens its own `pl.read_parquet()` or DuckDB `read_parquet(...)` call against the same file. There is no shared DataFrame, no shared DuckDB connection, no lazy scan anywhere in `perfsage/core/{viz,analysis}`.

**Changes:**

1. **Shared read per render.** Introduce a `ReportContext` (or extend the existing figure-building entry point) that reads `samples.parquet` into a single Polars DataFrame (or opens one DuckDB connection registering the parquet as a view) once per render, and thread it through every figure builder and analysis function as a parameter instead of each doing its own I/O. This touches every function signature in `perfsage/core/viz/*.py` and `perfsage/core/analysis/*.py` that currently calls `pl.read_parquet`/`read_parquet(...)` directly — a mechanical but wide change. Measured impact: 49-51 reads → 1; expected RAM drop from 2.2-3.5GB to <500MB just from this.
2. **De-embed raw arrays from histogram/boxplot.** `fig-histogram` and `fig-boxplots` currently pass 5M raw floats into `go.Histogram`/`go.Box`, which Plotly deep-copies and JSON-serializes in full. Change both to pre-aggregate server-side using existing Polars/DuckDB primitives: histogram → compute ~50 bin counts and pass `go.Bar`/pre-binned `go.Histogram` with `x`/`y` bin edges+counts; boxplot → compute `q1/median/q3` + whisker bounds per label via `.quantile()` and pass directly via `go.Box(q1=…, median=…, q3=…, lowerfence=…, upperfence=…)` (no `y=` raw array). Same visual output, O(bins) instead of O(n) payload. Measured impact: -53% build time, -94% of the 36.9MB payload, at 5M rows.
3. **Rendered-output cache.** A `Report` is immutable once `READY` (its parquet never changes after ingest). Cache the fully-built `figures_json` + recommendations + KPI summary to a file next to `samples.parquet` (e.g. `report_cache.json`) after first render; subsequent views read the cache directly, skipping the entire build pipeline. Invalidate only if the report is re-processed (should not happen post-READY) — a simple existence check is sufficient, no TTL needed. Measured impact: repeat views 26-47s → <0.5s.
4. **Lazy-loaded heavy sections.** Convert the **Distribution** and **Saturation** chart sections (the ones containing histogram, boxplots, scatter, heatmap — the heaviest remaining builders after #2) to HTMX-fetched fragments: `GET /reports/{id}/section/{section_id}` returning just that section's chart HTML+JSON, wired with `hx-trigger="revealed"` so they load as the user scrolls into view. The initial `GET /reports/{id}` response includes KPIs, the hero chart, and lighter sections (Timeline, SLO, Errors) inline, plus skeleton placeholders for the two lazy sections. This is the change that actually removes the multi-second-to-minute blank wait on first view.

**Explicitly deferred to Phase 0b / Phase 3** (Performance Engineer's items #5-#8 — precomputed rollups at ingest, stratified/LTTB downsampling for scatter/timeline, payload slimming, parallel builders): these target the full <2s-TTFB-at-10M-rows budget but require new ingest-time artifacts and correctness work (guaranteeing outliers survive downsampling) that don't fit a single implementation slice. Items #1-#4 above already remove the two dominant measured costs and the primary "frozen UI" complaint; #5-#8 are the next iteration once #1-#4 are proven in production.

**Performance budget for this phase** (revised down from the full V2 budget to reflect deferred items): at 5M rows, cold first-view <10s with visible progressive loading, cached/repeat view <1s, peak RSS <1GB. Full <2s-TTFB-at-10M-rows target remains a Phase 0b goal.

### 4.3 UX / Motion System

Consistent with the UX Engineer's audit — reusing the existing HTMX `htmx-request` class mechanism means most of this requires zero per-element wiring:

1. **Motion tokens** added to `perfsage.css`: `--ease-out`, `--dur-fast/base/slow` (150/220/300ms), shimmer gradient variable, and a `prefers-reduced-motion` guard disabling all animation durations for users who request it.
2. **Skeleton shimmer** for KPI cards and chart placeholders — server-rendered `.skeleton` blocks shown before real content mounts (or before a lazy section's HTMX fragment arrives), removed via a fade transition on load.
3. **Global top progress bar** — one fixed-position element driven by a single `htmx:beforeRequest`/`htmx:afterSettle` listener in `base.html`. Covers pagination, flush, settings, upload, and the new lazy-section fetches with no per-template changes.
4. **Button/form busy states** — one CSS rule targeting the `.htmx-request` class HTMX already adds to any triggering element: dims the button, disables pointer events, appends a spinner glyph. Paired with `hx-disabled-elt="this"` on forms to prevent double-submit.
5. **Staged chart fade-in** — each chart div starts at `opacity:0`, flips to `.chart-loaded` (opacity 1) once its `Plotly.newPlot(...)` promise resolves, whether it arrived inline or via a lazy HTMX fragment.
6. **Export progress** — deferred to Phase 1 alongside export/CI work (UX flagged it P1, not P0); PDF export keeps its current behavior for now but gets a button spinner via #4 for free.

Quick, pre-existing-pattern wins folded into this pass at no extra design cost: fix hardcoded `aria-expanded="true"` never updating on section toggle (accessibility bug, one-line JS fix); extend the existing `.section-chevron` transition pattern to the section body itself for smoother collapse.

### 4.4 QA Defect Fixes (this phase)

| # | Defect | Fix |
|---|---|---|
| 1 | SLO settings saved via `POST /api/settings/slo` but never read back — every consumer (`views.py`, `ai.py`, settings page itself) constructs a hardcoded default `SLOConfig()` | Add a single `load_slo_config()` helper reading from `AppSettingsRepo`, falling back to defaults if unset; use it everywhere `SLOConfig()` is currently constructed directly |
| 2 | `compute_overall_percentiles` raises `TypeError` on an empty/all-quarantined samples parquet (DuckDB returns one NULL row for aggregate-without-GROUP-BY on empty input); masked by a blanket `except Exception` producing a silent blank summary | Guard for zero/all-null input explicitly; return a well-defined "no data" result instead of raising |
| 3 | A file where 100% of rows are quarantined is still marked `READY` with no indication to the user | `ingest_report_task` checks `parsed_rows == 0` (or below a sane threshold) after cleanup and marks the report with a distinct degraded state / visible warning banner instead of a silently-broken `READY` dashboard |
| 4 | **Stored XSS**: JMeter transaction labels flow unescaped into inline `<script>var figs = {{ figures_json | safe }};</script>` — `json.dumps` does not escape `</script>`, so a label like `x</script><script>...` breaks out of the script context | Move figure JSON to a `<script type="application/json">` island (never interpreted as executable) read via `JSON.parse` in JS, or at minimum apply `</script>`→`<\/script>` escaping before embedding. Prefer the JSON-island approach — safer by construction, and matches how the existing AI-narrative sanitization is handled correctly elsewhere |

**Explicitly deferred to Phase 1** (lower severity / larger scope): stuck-job reaper independent of the FastAPI lifespan hook (worker-only crash recovery), unbounded in-memory quarantine buffer, `normalize_timestamp` UTC assumption for string timestamps. These are real resiliency gaps but none block the Phase 0 goal and each deserves its own scoped fix rather than being squeezed in.

### 4.5 Testing Plan

- Add regression tests for each Phase 0 QA fix, drawn directly from the QA Engineer's "top 10 missing tests" list (items 1-4 map directly to defects above; item 4's XSS regression test is mandatory given it's a real vulnerability).
- Add a perf regression script (`scripts/bench_report.py`, per the Performance Engineer's harness recommendation) using a 1M-row fixture, asserting render time/RSS/payload stay within a checked-in baseline — run as a fast CI gate.
- Existing 429-test suite must stay green throughout (`pytest -q -m "not slow" --ignore=tests/e2e`).
- Manual verification of the lazy-loading + motion system in a browser (skeleton→content transitions, top bar, button spinners) since these are primarily visual/behavioral.

### 4.6 Non-Goals (Phase 0)

- No new user-facing features (comparison, sharing, CI, multi-format) — that's Phase 1-2.
- No precomputed ingest-time rollups or downsampling — Phase 0b.
- No export-progress modal, dark mode, or broader accessibility pass beyond the specific fixes in 4.3 — Phase 1+ per UX's P1/P2 backlog.
- No changes to the ingest pipeline itself (already well-architected per Performance Engineer's findings — not a bottleneck).

---

## 5. Appendix A — Phase 1-3 Feature Reference (from PM research)

Captured here for continuity; each will get its own design pass when scheduled.

**Phase 1 (Must-have adoption features):** run-vs-run comparison & baseline diffs; shareable read-only report links (expiring token URL, no auth); CI/CD Action + PR-comment bot posting KPI deltas and exiting non-zero on SLO breach; public zero-signup demo instance.

**Phase 2 (Should-have, TAM expansion):** multi-format ingestion (k6 JSON, Gatling log, Locust CSV) normalized into the existing Polars schema so all 29 charts + AI narrative work unmodified; CLI tool (`perfsage upload results.jtl --wait --fail-on-slo-breach`); per-report SLO editor in the upload flow; JUnit/Prometheus/OpenMetrics export; distributed-run JTL merge with correct time alignment.

**Phase 3 (Should/Could-have, retention & depth):** trend history across many runs (built on Phase 1's comparison data model); AI-narrated diff explanations ("P95 on /checkout regressed 23% — likely cause: DB pool saturation"); remaining Performance Engineer budget items (precomputed rollups at ingest, LTTB/stratified downsampling, payload slimming, parallel builders) to hit the full 10M-row/<2s-TTFB budget.

**Explicitly Won't (this planning horizon):** multi-tenant auth, plugin/rule marketplace — both cut against the "free, frictionless, single-container" open-source-first strategy.
