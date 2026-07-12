# PerfSage Reveal V2 Phase 0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the report page's performance/feedback problem (slow + silent on large files) and four QA-verified defects (one security issue), without adding any new user-facing features.

**Architecture:** Collapse redundant parquet reads via a small per-path cache, remove O(n) payload from the two worst chart builders by pre-aggregating server-side, cache the rendered report payload to disk (reports are immutable once `READY`), lazily HTMX-fetch the two heaviest chart sections, and layer a reusable HTMX-driven motion/loading system (skeletons, top progress bar, button spinners, staged fade-in) on top using the existing `htmx-request` class mechanism.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, HTMX 1.9, Polars, DuckDB, Plotly, pytest.

**Spec:** `docs/superpowers/specs/2026-07-12-perfsage-v2-design.md` (Section 4 = Phase 0 detail)

---

## Task 1: Fix SLO settings never applied to reports

**Files:**
- Modify: `perfsage/core/analysis/slo.py`
- Modify: `perfsage/web/views.py:114,170`
- Modify: `perfsage/api/ai.py:66-89`
- Test: `tests/unit/analysis/test_slo.py`

`POST /api/settings/slo` persists a config via `AppSettingsRepo.set("slo_defaults", json.dumps(config.__dict__))` (`perfsage/api/settings.py:46-49`), but every consumer builds a fresh default `SLOConfig()` instead of reading it back.

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/analysis/test_slo.py`:

```python
def test_load_slo_config_returns_default_when_unset(test_settings):
    from perfsage.core.storage.db import get_engine, get_session
    from perfsage.core.analysis.slo import SLOConfig, load_slo_config

    engine = get_engine(test_settings.database_url)
    with get_session(engine) as session:
        config = load_slo_config(session)
    assert config == SLOConfig()


def test_load_slo_config_round_trips_saved_settings(test_settings):
    from perfsage.core.storage.db import get_engine, get_session
    from perfsage.core.storage.repos import AppSettingsRepo
    from perfsage.core.analysis.slo import SLOConfig, load_slo_config
    import json

    engine = get_engine(test_settings.database_url)
    saved = SLOConfig(p90_ms=250.0, p99_ms=800.0, error_rate_pct=0.5, apdex_t=0.25)
    with get_session(engine) as session:
        AppSettingsRepo(session).set("slo_defaults", json.dumps(saved.__dict__))
        config = load_slo_config(session)
    assert config == saved


def test_load_slo_config_falls_back_on_malformed_json(test_settings):
    from perfsage.core.storage.db import get_engine, get_session
    from perfsage.core.storage.repos import AppSettingsRepo
    from perfsage.core.analysis.slo import SLOConfig, load_slo_config

    engine = get_engine(test_settings.database_url)
    with get_session(engine) as session:
        AppSettingsRepo(session).set("slo_defaults", "{not valid json")
        config = load_slo_config(session)
    assert config == SLOConfig()
```

This test module doesn't currently import `test_settings` — it's the existing fixture from `tests/conftest.py`, available to any test via the `test_settings: Settings` parameter (no import needed, pytest fixture injection).

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/analysis/test_slo.py -k load_slo_config -v`
Expected: FAIL with `ImportError: cannot import name 'load_slo_config'`

- [ ] **Step 3: Implement `load_slo_config`**

In `perfsage/core/analysis/slo.py`, add near the top (after imports) and make `SLOConfig` comparable:

```python
import json
import logging

logger = logging.getLogger(__name__)
```

Change the `SLOConfig` dataclass decorator to also generate equality (it already does by default since `@dataclass` without `eq=False` generates `__eq__` — no change needed there; just confirm no `eq=False` is present).

Add this function after the `SLOConfig`/`SLOResult` dataclasses:

```python
def load_slo_config(session: "Session") -> SLOConfig:  # noqa: F821 - Session imported below
    """Load the persisted SLO defaults saved via POST /api/settings/slo.

    Falls back to SLOConfig() defaults if nothing has been saved yet, or if
    the stored value is malformed.
    """
    from perfsage.core.storage.repos import AppSettingsRepo

    raw = AppSettingsRepo(session).get("slo_defaults")
    if not raw:
        return SLOConfig()
    try:
        data = json.loads(raw)
        return SLOConfig(**data)
    except (ValueError, TypeError) as exc:
        logger.warning("Malformed slo_defaults setting (%s); using SLOConfig defaults", exc)
        return SLOConfig()
```

Replace the `"Session"` forward-ref with a real import — add to the top-level imports of `slo.py`:

```python
from sqlmodel import Session
```

And change the function signature to `def load_slo_config(session: Session) -> SLOConfig:` (drop the string-quoted forward ref and `# noqa` comment now that it's a real import).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/analysis/test_slo.py -k load_slo_config -v`
Expected: 3 passed

- [ ] **Step 5: Wire `load_slo_config` into `report_detail` and `settings_page`**

In `perfsage/web/views.py`:

Replace line 114 (`slo_config = SLOConfig()`) inside `report_detail`. The session that fetches the report is already closed by that point — move the SLO load inside the existing `with get_session(engine) as session:` block at the top of the function (lines 101-111), right after the `app_settings = AppSettingsRepo(session)` line:

```python
    with get_session(engine) as session:
        report = ReportRepo(session).get(report_id)
        if report is None:
            return HTMLResponse("Report not found", status_code=404)
        insights = InsightRepo(session).list_for_report(report_id)
        app_settings = AppSettingsRepo(session)
        ai_key_configured = (
            app_settings.get("openai_key") is not None
            or app_settings.get("anthropic_key") is not None
            or app_settings.get("gemini_key") is not None
        )
        slo_config = load_slo_config(session)

    samples_path = file_store.samples_parquet(report_id)
    figures_json: dict[str, Any] = {}
```

(Remove the old standalone `slo_config = SLOConfig()` line that followed `samples_path = ...`.)

Add the import at the top of `views.py`:

```python
from perfsage.core.analysis.slo import SLOConfig, load_slo_config
```

Replace line 170 in `settings_page` (`"slo": SLOConfig()`). That function already has a `with get_session(engine) as session:` block — add the load inside it:

```python
    engine = _engine(settings)
    configured_providers: list[str] = []
    with get_session(engine) as session:
        repo = AppSettingsRepo(session)
        if repo.get("openai_key"):
            configured_providers.append("OpenAI")
        if repo.get("anthropic_key"):
            configured_providers.append("Anthropic")
        if repo.get("gemini_key"):
            configured_providers.append("Gemini")
        slo_config = load_slo_config(session)
    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "configured_providers": configured_providers,
            "slo": slo_config,
        },
    )
```

- [ ] **Step 6: Wire `load_slo_config` into the AI prompt builder**

In `perfsage/api/ai.py`, inside `generate_ai_insights`, the existing `with get_session(engine) as session:` block (lines 48-74) already has `settings_repo = AppSettingsRepo(session)`. Add right after that line:

```python
        settings_repo = AppSettingsRepo(session)
        slo_config = load_slo_config(session)
```

Then change line 89 from:

```python
    user_prompt = build_analysis_prompt(samples_path)
```

to:

```python
    user_prompt = build_analysis_prompt(samples_path, slo_config)
```

Add the import at the top of `ai.py`:

```python
from perfsage.core.analysis.slo import load_slo_config
```

- [ ] **Step 7: Add an integration-level regression test**

Add to `tests/unit/web/test_views.py`:

```python
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
```

- [ ] **Step 8: Run the full test file and the settings tests**

Run: `pytest tests/unit/analysis/test_slo.py tests/unit/web/test_views.py tests/unit/api/ -v`
Expected: all pass

- [ ] **Step 9: Commit**

```bash
git add perfsage/core/analysis/slo.py perfsage/web/views.py perfsage/api/ai.py tests/unit/analysis/test_slo.py tests/unit/web/test_views.py
git commit -m "fix: apply saved SLO defaults to reports, settings page, and AI prompts"
```

---

## Task 2: Fix crash on empty/all-quarantined samples

**Files:**
- Modify: `perfsage/core/analysis/percentiles.py`
- Test: `tests/unit/analysis/test_percentiles.py`

`compute_overall_percentiles` raises `TypeError: float() argument must be a string or a real number, not 'NoneType'` when the samples parquet has zero rows, because DuckDB's `PERCENTILE_CONT` over an empty table returns one row of `NULL`s.

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/analysis/test_percentiles.py`:

```python
def test_compute_overall_percentiles_empty_file_returns_zeros(tmp_path):
    import polars as pl
    from perfsage.core.analysis.percentiles import compute_overall_percentiles

    empty = pl.DataFrame({"elapsed": pl.Series([], dtype=pl.Int64)})
    path = tmp_path / "empty.parquet"
    empty.write_parquet(path)

    result = compute_overall_percentiles(path)
    assert result == {"p50": 0.0, "p75": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0, "p999": 0.0}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/analysis/test_percentiles.py -k empty_file -v`
Expected: FAIL with `TypeError: float() argument must be a string or a real number, not 'NoneType'`

- [ ] **Step 3: Implement the fix**

In `perfsage/core/analysis/percentiles.py`, replace `compute_overall_percentiles`:

```python
def compute_overall_percentiles(samples_path: Path) -> dict[str, float]:
    """Return dict: p50, p75, p90, p95, p99, p999 for all labels combined.

    Returns all-zero values (never raises) if the samples file has no rows —
    DuckDB's PERCENTILE_CONT over an empty table yields NULLs, not an error.
    """
    df = compute_percentiles(samples_path, groupby_label=False)
    if df.is_empty() or df["count"][0] == 0:
        return {"p50": 0.0, "p75": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0, "p999": 0.0}
    return {
        col: float(df[col][0]) if df[col][0] is not None else 0.0
        for col in ["p50", "p75", "p90", "p95", "p99", "p999"]
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/analysis/test_percentiles.py -v`
Expected: all pass, including the new test

- [ ] **Step 5: Commit**

```bash
git add perfsage/core/analysis/percentiles.py tests/unit/analysis/test_percentiles.py
git commit -m "fix: compute_overall_percentiles no longer raises on empty samples"
```

---

## Task 3: Fail cleanly when 100% of rows are quarantined

**Files:**
- Modify: `perfsage/core/jobs/tasks.py`
- Test: `tests/unit/jobs/test_tasks.py`

Currently `ingest_report_task` never checks `parsed_rows == 0`, so a file where every row fails validation still ends up `READY` with a broken/empty dashboard (masked by Task 2's now-fixed crash, but still a silently-useless report). Reuse the existing exception-handling path (which already marks the report `FAILED` with a clear message) instead of adding a new status.

- [ ] **Step 1: Write the failing test**

Check the existing test file first to match its fixture/mocking style:

Read `tests/unit/jobs/test_tasks.py` to see how `ingest_report_task` is currently invoked/mocked in tests (arq `ctx`, Redis mock, DB setup), then add a test following the same pattern:

```python
@pytest.mark.asyncio
async def test_ingest_all_quarantined_file_marks_report_failed(
    tmp_path, test_settings, monkeypatch
):
    """A CSV where every row fails validation must not end up READY."""
    monkeypatch.setattr(
        "perfsage.core.jobs.tasks.get_settings", lambda: test_settings
    )
    from perfsage.core.storage.db import ReportStatus, get_engine, get_session
    from perfsage.core.storage.repos import JobRepo, ReportRepo
    from perfsage.core.jobs.tasks import ingest_report_task

    engine = get_engine(test_settings.database_url)
    with get_session(engine) as session:
        report = ReportRepo(session).create("bad.csv", "bad.csv", 100)
        job = JobRepo(session).create(report.id)

    upload_path = tmp_path / "bad.csv"
    # Header present, but every data row has a non-numeric elapsed value —
    # every row is quarantined, zero rows parsed successfully.
    upload_path.write_text("timeStamp,elapsed,label,success\n1700000000000,notanumber,Home,true\n")

    class _FakeRedis:
        async def publish(self, *_args, **_kwargs):
            return None

    with pytest.raises(ValueError, match="no valid samples|all rows"):
        await ingest_report_task(
            {"redis": _FakeRedis()}, job.id, report.id, str(upload_path)
        )

    with get_session(engine) as session:
        refreshed = ReportRepo(session).get(report.id)
        assert refreshed.status == ReportStatus.FAILED
```

If `ingest_report_task` in the existing tests is invoked differently (e.g. via a helper or different fixture names), adjust the test to match that existing convention exactly rather than introducing a new pattern — read the file first.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/jobs/test_tasks.py -k all_quarantined -v`
Expected: FAIL because no `ValueError` is raised (report ends up `READY` instead)

- [ ] **Step 3: Implement the fix**

In `perfsage/core/jobs/tasks.py`, inside `ingest_report_task`, right after the `parsed_rows, error_rows = ...` branch (after line 69, before the `with get_session(engine) as session:` stats-update block that follows), add:

```python
        if parsed_rows == 0:
            raise ValueError(
                f"No valid samples found in {src.name!r} — all {error_rows} row(s) failed "
                "validation (check delimiter, headers, and timestamp/elapsed format)."
            )

        with get_session(engine) as session:
            ReportRepo(session).update_stats(
```

(This just adds the guard clause before the existing `with get_session(engine) as session:` line — the rest of that block is unchanged.) The existing `except Exception as exc:` handler at the bottom of the function already marks the job failed and the report `FAILED` with `error_msg = str(exc)`, so no other change is needed.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/jobs/test_tasks.py -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add perfsage/core/jobs/tasks.py tests/unit/jobs/test_tasks.py
git commit -m "fix: mark ingest failed instead of silently READY when all rows are quarantined"
```

---

## Task 4: Fix stored XSS via JMeter labels in inline chart JSON

**Files:**
- Modify: `perfsage/web/templates/report_detail.html`
- Modify: `perfsage/web/static/js/report.js`
- Test: `tests/unit/web/test_views.py`

`report_detail.html` embeds `var figs = {{ figures_json | safe }};` inside an executable `<script>` block. `json.dumps` does not escape `</script>`, so a JMeter label like `x</script><script>alert(1)</script>` breaks out of the script context and executes. Fix by moving the JSON into a non-executable `<script type="application/json">` island, parsed via `JSON.parse` — never interpreted as JS regardless of content.

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/web/test_views.py`. This test needs a `READY` report with a malicious label in its samples parquet — follow the existing pattern used elsewhere in the test suite for creating a ready report with a custom parquet (check `tests/integration/test_reports_api.py` or `tests/unit/storage/test_report_repo.py` for the exact helper used to mark a report `READY` with a given `samples.parquet`; reuse it). If no such helper exists yet, construct it directly:

```python
def test_report_detail_escapes_malicious_label(client: TestClient, test_settings, tmp_path) -> None:
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/web/test_views.py -k escapes_malicious_label -v`
Expected: FAIL — the literal unescaped label breaks out of the script tag in the response body

- [ ] **Step 3: Implement the fix in the template**

In `perfsage/web/templates/report_detail.html`, replace the final `<script>` block (lines 223-231):

```html
<script>
var figs = {{ figures_json | safe }};
for (var divId in figs) {
  var figJson = figs[divId];
  if (figJson && document.getElementById(divId)) {
    Plotly.newPlot(divId, figJson.data, figJson.layout, {responsive: true, displayModeBar: true});
  }
}
</script>
```

with:

```html
<script type="application/json" id="figures-data">{{ figures_json | safe }}</script>
<script>
PerfSageReport.mountFigures(document.getElementById("figures-data"));
</script>
```

`<script type="application/json">` content is never parsed as JavaScript by the browser regardless of what characters it contains, so this closes the XSS hole by construction (defense-in-depth on top of any escaping) — the JSON is only ever read as text via `.textContent` and passed to `JSON.parse`, never concatenated into executable JS source.

- [ ] **Step 4: Implement the fix in report.js**

In `perfsage/web/static/js/report.js`, add a `PerfSageReport` namespace with the mount function (this also becomes the shared mounting helper used later in Task 13 for staged fade-in and Task 9 for lazy sections):

```js
(function () {
  "use strict";

  window.PerfSageReport = window.PerfSageReport || {};

  window.PerfSageReport.mountFigures = function (jsonScriptEl) {
    if (!jsonScriptEl) return;
    var figs;
    try {
      figs = JSON.parse(jsonScriptEl.textContent);
    } catch (e) {
      console.error("PerfSage: failed to parse figures JSON", e);
      return;
    }
    for (var divId in figs) {
      var figJson = figs[divId];
      var el = document.getElementById(divId);
      if (figJson && el) {
        Plotly.newPlot(el, figJson.data, figJson.layout, {
          responsive: true,
          displayModeBar: true,
        });
      }
    }
  };

  document.addEventListener("DOMContentLoaded", function () {
```

(Keep the existing `document.addEventListener("DOMContentLoaded", ...)` body that follows — chart-tabs and section-toggle wiring — unchanged; just nest it inside this same IIFE as shown, replacing the file's original opening `(function () { "use strict"; document.addEventListener(...` structure.)

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/unit/web/test_views.py -v`
Expected: all pass, including the new XSS regression test

- [ ] **Step 6: Manually verify charts still render**

Run: `pytest tests/unit/web/test_views.py tests/unit/viz/test_registry.py -v` (confirms nothing else broke) — full visual confirmation happens later in Task 9's manual browser check once the dev server is running.

- [ ] **Step 7: Commit**

```bash
git add perfsage/web/templates/report_detail.html perfsage/web/static/js/report.js tests/unit/web/test_views.py
git commit -m "fix: stop embedding raw chart JSON in an executable script tag (XSS)"
```

---

## Task 5: Collapse redundant parquet reads with a per-path cache

**Files:**
- Create: `perfsage/core/viz/_sample_cache.py`
- Modify: `perfsage/core/viz/expert.py` (8 call sites), `distribution.py` (4), `scatter.py` (4), `decomposition.py` (2), `tables.py` (2), `slo.py` (2), `timeseries.py` (3)
- Test: `tests/unit/viz/test_sample_cache.py` (new)

25 of the 29 chart builders each independently call `pl.read_parquet(samples_path)` on the exact same file during a single report render (confirmed via `grep -rn "pl.read_parquet(samples_path)" perfsage/core/viz/`). Add a small cache keyed on `(path, mtime)` so repeated calls within a render reuse one decoded DataFrame — Polars DataFrames are immutable-by-operation (`.filter()`/`.with_columns()` return new frames), so sharing one cached reference across call sites is safe.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/viz/test_sample_cache.py`:

```python
"""Tests for the per-path samples cache used by chart builders."""

from __future__ import annotations

import polars as pl
import pytest


def _write(path, elapsed):
    pl.DataFrame({"elapsed": elapsed, "label": ["A"] * len(elapsed)}).write_parquet(path)


def test_read_samples_cached_returns_equal_dataframe(tmp_path):
    from perfsage.core.viz._sample_cache import read_samples_cached

    path = tmp_path / "s.parquet"
    _write(path, [1, 2, 3])
    df = read_samples_cached(path)
    assert df["elapsed"].to_list() == [1, 2, 3]


def test_read_samples_cached_avoids_rereading_disk(tmp_path, monkeypatch):
    from perfsage.core.viz import _sample_cache

    path = tmp_path / "s.parquet"
    _write(path, [1, 2, 3])
    _sample_cache._cached_read_parquet.cache_clear()

    call_count = {"n": 0}
    real_read = pl.read_parquet

    def _counting_read(*args, **kwargs):
        call_count["n"] += 1
        return real_read(*args, **kwargs)

    monkeypatch.setattr(pl, "read_parquet", _counting_read)

    _sample_cache.read_samples_cached(path)
    _sample_cache.read_samples_cached(path)
    _sample_cache.read_samples_cached(path)

    assert call_count["n"] == 1


def test_read_samples_cached_detects_file_change(tmp_path):
    from perfsage.core.viz._sample_cache import read_samples_cached

    path = tmp_path / "s.parquet"
    _write(path, [1, 2, 3])
    first = read_samples_cached(path)
    assert first["elapsed"].to_list() == [1, 2, 3]

    _write(path, [4, 5])
    second = read_samples_cached(path)
    assert second["elapsed"].to_list() == [4, 5]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/viz/test_sample_cache.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'perfsage.core.viz._sample_cache'`

- [ ] **Step 3: Implement the cache module**

Create `perfsage/core/viz/_sample_cache.py`:

```python
"""Per-path cache for samples.parquet reads.

Chart builders across viz/*.py each independently call pl.read_parquet on
the same samples.parquet during a single report render (measured: 25 full
reads per render). Since polars DataFrames are immutable by operation
(.filter()/.with_columns() return new frames, never mutate in place), it's
safe to share one cached DataFrame across every call site.

Cache key is (path, mtime_ns) so a changed file is never served stale.
Bounded maxsize keeps memory from growing unboundedly across many reports
in a single long-running worker/web process.
"""

from __future__ import annotations

import functools
from pathlib import Path

import polars as pl

_CACHE_SIZE = 8


@functools.lru_cache(maxsize=_CACHE_SIZE)
def _cached_read_parquet(path_str: str, mtime_ns: int) -> pl.DataFrame:
    return pl.read_parquet(path_str)


def read_samples_cached(path: Path) -> pl.DataFrame:
    """Read a samples parquet, reusing a cached DataFrame for the same
    (path, mtime) within the process instead of re-reading from disk."""
    stat = path.stat()
    return _cached_read_parquet(str(path), stat.st_mtime_ns)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/viz/test_sample_cache.py -v`
Expected: 3 passed

- [ ] **Step 5: Swap call sites to use the cache**

In each of the following files, add the import:

```python
from perfsage.core.viz._sample_cache import read_samples_cached
```

...and replace every occurrence of `pl.read_parquet(samples_path)` with `read_samples_cached(samples_path)` (mechanical, one-line-per-occurrence change, no other logic changes):

- `perfsage/core/viz/expert.py` — lines 43, 115, 177, 236, 300, 345, 391, 434 (`df = pl.read_parquet(samples_path)` in each of the 8 figure functions)
- `perfsage/core/viz/distribution.py` — lines 38, 83, 127, 158
- `perfsage/core/viz/scatter.py` — lines 21, 96, 138, 187
- `perfsage/core/viz/decomposition.py` — line 21 (`df = pl.read_parquet(samples_path)`) and line 95 (`df_raw = pl.read_parquet(samples_path)`)
- `perfsage/core/viz/tables.py` — lines 17, 66
- `perfsage/core/viz/slo.py` — lines 39, 190
- `perfsage/core/viz/timeseries.py` — lines 26, 153, 229

After editing, re-run the grep to confirm no call sites remain:

```bash
grep -rn "pl.read_parquet(samples_path)" perfsage/core/viz/
```

Expected: no output (all converted).

- [ ] **Step 6: Run the full viz test suite**

Run: `pytest tests/unit/viz/ -v`
Expected: all pass (this is a drop-in replacement — same DataFrame contents, same behavior)

- [ ] **Step 7: Commit**

```bash
git add perfsage/core/viz/_sample_cache.py perfsage/core/viz/expert.py perfsage/core/viz/distribution.py perfsage/core/viz/scatter.py perfsage/core/viz/decomposition.py perfsage/core/viz/tables.py perfsage/core/viz/slo.py perfsage/core/viz/timeseries.py tests/unit/viz/test_sample_cache.py
git commit -m "perf: cache samples.parquet reads by (path, mtime) across chart builders"
```

---

## Task 6: De-embed raw arrays from the latency histogram

**Files:**
- Modify: `perfsage/core/viz/distribution.py`
- Test: `tests/unit/viz/test_distribution.py`

`fig_latency_histogram` passes up to millions of raw `elapsed` values into `go.Histogram(x=elapsed, ...)`. Plotly then deep-copies and JSON-serializes every element. Pre-bin into 50 buckets server-side with Polars and pass counts via `go.Bar`, which renders identically but with O(bins) payload instead of O(n).

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/viz/test_distribution.py`:

```python
def test_fig_latency_histogram_payload_is_binned_not_raw(sample_parquet_fast):
    from perfsage.core.viz.distribution import fig_latency_histogram

    fig = fig_latency_histogram(sample_parquet_fast)
    assert len(fig.data) >= 1
    trace = fig.data[0]
    # Binned output has at most ~50 points regardless of input row count;
    # a raw-array histogram trace would carry one x-value per input row (200).
    assert len(trace.x) <= 60
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/viz/test_distribution.py -k binned_not_raw -v`
Expected: FAIL — `go.Histogram` trace carries all 200 raw points, `len(trace.x) == 200`

- [ ] **Step 3: Implement the fix**

In `perfsage/core/viz/distribution.py`, replace `fig_latency_histogram`:

```python
def fig_latency_histogram(samples_path: Path, label: str | None = None) -> go.Figure:
    """Fig 6: Histogram of elapsed times with p50/p90/p99 vertical lines.

    Pre-bins server-side (50 buckets) instead of shipping raw per-sample
    arrays to Plotly — same visual output, O(bins) payload instead of O(n).
    """
    df = read_samples_cached(samples_path)
    if df.is_empty():
        return apply_theme(go.Figure(), "Latency Histogram")

    if label is not None:
        df = df.filter(pl.col("label") == label)
    if df.is_empty():
        return apply_theme(go.Figure(), f"Latency Histogram — {label} (no data)")

    elapsed = df["elapsed"]
    p50 = float(elapsed.quantile(0.50, interpolation="linear") or 0.0)
    p90 = float(elapsed.quantile(0.90, interpolation="linear") or 0.0)
    p99 = float(elapsed.quantile(0.99, interpolation="linear") or 0.0)

    lo, hi = float(elapsed.min()), float(elapsed.max())
    n_bins = 50
    if hi <= lo:
        bin_edges = [lo, lo + 1.0]
        n_bins = 1
    else:
        width = (hi - lo) / n_bins
        bin_edges = [lo + i * width for i in range(n_bins + 1)]

    binned = df.with_columns(
        ((pl.col("elapsed") - lo) / (bin_edges[1] - bin_edges[0]))
        .floor()
        .clip(0, n_bins - 1)
        .cast(pl.Int64)
        .alias("_bin")
    )
    counts_df = (
        binned.group_by("_bin").agg(pl.len().alias("count")).sort("_bin")
    )
    counts_by_bin = dict(zip(counts_df["_bin"].to_list(), counts_df["count"].to_list(), strict=True))
    bin_centers = [(bin_edges[i] + bin_edges[i + 1]) / 2 for i in range(n_bins)]
    bin_counts = [counts_by_bin.get(i, 0) for i in range(n_bins)]
    bar_width = bin_edges[1] - bin_edges[0] if n_bins > 1 else 1.0

    title = f"Latency Histogram{f' — {label}' if label else ''}"
    fig = go.Figure(
        go.Bar(
            x=bin_centers,
            y=bin_counts,
            width=bar_width * 0.95,
            marker_color=NAVY,
            opacity=0.8,
            name="Requests",
        )
    )

    for val, name, color in [
        (p50, "p50", NAVY),
        (p90, "p90", AMBER),
        (p99, "p99", ERROR_RED),
    ]:
        fig.add_vline(
            x=val,
            line_dash="dash",
            line_color=color,
            annotation_text=f"{name}: {val:.0f}ms",
            annotation_position="top right",
        )

    apply_theme(fig, title)
    fig.update_layout(xaxis_title="Response Time (ms)", yaxis_title="Count", bargap=0.02)
    return fig
```

Note this task depends on Task 5's `read_samples_cached` import already being present in this file — if Task 5 was completed first (it is, per this plan's order), the import line is already there.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/viz/test_distribution.py -v`
Expected: all pass. If any pre-existing histogram test asserted on `go.Histogram`-specific fields (e.g. `trace.type == "histogram"` or `nbinsx`), update those assertions to match the new `go.Bar` trace (`trace.type == "bar"`) — read the existing test file's other histogram assertions before running and adjust them in this same step so the whole file is consistent.

- [ ] **Step 5: Commit**

```bash
git add perfsage/core/viz/distribution.py tests/unit/viz/test_distribution.py
git commit -m "perf: pre-bin latency histogram server-side instead of shipping raw samples"
```

---

## Task 7: De-embed raw arrays from per-label boxplots

**Files:**
- Modify: `perfsage/core/viz/distribution.py`
- Test: `tests/unit/viz/test_distribution.py`

`fig_boxplots_per_label` passes the full raw `elapsed` list per label into `go.Box(y=subset, ...)`. Compute quartile/whisker statistics with Polars and pass them directly via `go.Box(q1=, median=, q3=, lowerfence=, upperfence=, ...)` — Plotly renders identical box shapes without re-deriving them from raw data, and without embedding the raw data at all.

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/viz/test_distribution.py`:

```python
def test_fig_boxplots_per_label_payload_has_no_raw_y_arrays(sample_parquet):
    from perfsage.core.viz.distribution import fig_boxplots_per_label

    fig = fig_boxplots_per_label(sample_parquet)
    assert len(fig.data) >= 1
    for trace in fig.data:
        # Quartile-stat boxes carry q1/median/q3 as scalars, not a raw y= array.
        assert trace.y is None or len(trace.y) == 0
        assert trace.q1 is not None
        assert trace.median is not None
        assert trace.q3 is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/viz/test_distribution.py -k no_raw_y_arrays -v`
Expected: FAIL — current implementation sets `y=subset` (raw array) and leaves `q1`/`median`/`q3` unset (Plotly derives them client-implicitly from `y`)

- [ ] **Step 3: Implement the fix**

In `perfsage/core/viz/distribution.py`, replace `fig_boxplots_per_label`:

```python
def fig_boxplots_per_label(samples_path: Path) -> go.Figure:
    """Fig 8: Box plots per transaction label, sorted by median descending.

    Computes quartile/whisker/outlier statistics server-side and passes them
    directly to go.Box — same rendered shape as a raw-array box plot, without
    shipping every raw sample to the browser.
    """
    df = read_samples_cached(samples_path)
    if df.is_empty():
        return apply_theme(go.Figure(), "Response Time Distribution by Label")

    stats = (
        df.group_by("label")
        .agg(
            [
                pl.col("elapsed").median().alias("median"),
                pl.col("elapsed").quantile(0.25, interpolation="linear").alias("q1"),
                pl.col("elapsed").quantile(0.75, interpolation="linear").alias("q3"),
                pl.col("elapsed").min().alias("min_val"),
                pl.col("elapsed").max().alias("max_val"),
                pl.col("elapsed").mean().alias("mean"),
            ]
        )
        .sort("median", descending=True)
    )

    fig = go.Figure()
    for row in stats.to_dicts():
        q1, q3 = float(row["q1"]), float(row["q3"])
        iqr = q3 - q1
        lower_fence = max(float(row["min_val"]), q1 - 1.5 * iqr)
        upper_fence = min(float(row["max_val"]), q3 + 1.5 * iqr)
        fig.add_trace(
            go.Box(
                name=str(row["label"]),
                q1=[q1],
                median=[float(row["median"])],
                q3=[q3],
                lowerfence=[lower_fence],
                upperfence=[upper_fence],
                mean=[float(row["mean"])],
                marker_color=NAVY,
                line_color=NAVY,
                boxmean=True,
            )
        )

    apply_theme(fig, "Response Time Distribution by Label")
    fig.update_layout(yaxis_title="Response Time (ms)", showlegend=False)
    return fig
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/viz/test_distribution.py -v`
Expected: all pass. As with Task 6, review and update any pre-existing boxplot assertions in this file that referenced raw `y` arrays.

- [ ] **Step 5: Commit**

```bash
git add perfsage/core/viz/distribution.py tests/unit/viz/test_distribution.py
git commit -m "perf: compute boxplot quartile stats server-side instead of shipping raw samples"
```

---

## Task 8: Add figure subset filtering and a render cache

**Files:**
- Modify: `perfsage/core/viz/registry.py`
- Create: `perfsage/core/viz/render_cache.py`
- Modify: `perfsage/core/storage/files.py`
- Test: `tests/unit/viz/test_registry.py`, `tests/unit/viz/test_render_cache.py` (new)

Two building blocks needed before Task 9 can lazily fetch individual sections and cache their output: (a) `build_figures_json` must support building only a subset of figures, (b) a small disk cache keyed by report + figure-set name, since a `READY` report's parquet never changes.

- [ ] **Step 1: Write the failing test for figure subsetting**

Add to `tests/unit/viz/test_registry.py`:

```python
def test_build_figures_json_only_builds_requested_subset(sample_parquet):
    from perfsage.core.viz.registry import build_figures_json

    result = build_figures_json(sample_parquet, None, only={"fig-slo-gauges", "fig-apdex"})
    assert set(result.keys()) == {"fig-slo-gauges", "fig-apdex"}


def test_build_figures_json_only_none_builds_everything(sample_parquet):
    from perfsage.core.viz.registry import build_figures_json, EXPORT_FIGURES

    result = build_figures_json(sample_parquet, None)
    assert set(result.keys()) == {fid for fid, _ in EXPORT_FIGURES}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/viz/test_registry.py -k only_builds -v`
Expected: FAIL with `TypeError: build_figures_json() got an unexpected keyword argument 'only'`

- [ ] **Step 3: Implement subsetting in registry.py**

In `perfsage/core/viz/registry.py`, change both `build_figure_objects` and `build_figures_json` signatures:

```python
def build_figure_objects(
    samples_path: Path,
    slo_config: SLOConfig | None,
    only: set[str] | None = None,
) -> dict[str, Any]:
    """Return mapping of dom_id -> Plotly Figure or None.

    If `only` is given, builds just those figure ids (skips the rest) — used
    for lazily-loaded chart sections that don't need the full 29-chart set.
    """
```

...(keep the existing body of imports and `builders: dict[str, Any] = {...}` unchanged)...

```python
    ids_to_build = [fid for fid, _ in EXPORT_FIGURES if only is None or fid in only]
    return {fid: _safe_fig_obj(builders[fid]) for fid in ids_to_build if fid in builders}


def build_figures_json(
    samples_path: Path,
    slo_config: SLOConfig | None,
    only: set[str] | None = None,
) -> dict[str, Any]:
    """Return mapping of dom_id -> Plotly JSON dict for web templates."""
    objs = build_figure_objects(samples_path, slo_config, only=only)
    result: dict[str, Any] = {}
    for fig_id, fig in objs.items():
        if fig is None:
            result[fig_id] = None
        else:
            try:
                result[fig_id] = json.loads(fig.to_json())
            except Exception:
                result[fig_id] = None
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/viz/test_registry.py -v`
Expected: all pass

- [ ] **Step 5: Write the failing test for the render cache**

Create `tests/unit/viz/test_render_cache.py`:

```python
"""Tests for the disk-backed render cache for expensive report payloads."""

from __future__ import annotations


def test_get_or_build_json_builds_and_caches(tmp_path):
    from perfsage.core.viz.render_cache import get_or_build_json

    cache_path = tmp_path / "sub" / "cache.json"
    calls = {"n": 0}

    def _build():
        calls["n"] += 1
        return {"a": 1}

    first = get_or_build_json(cache_path, _build)
    second = get_or_build_json(cache_path, _build)

    assert first == {"a": 1}
    assert second == {"a": 1}
    assert calls["n"] == 1  # second call served from cache_path, build() not called again
    assert cache_path.exists()


def test_get_or_build_json_rebuilds_on_corrupt_cache_file(tmp_path):
    from perfsage.core.viz.render_cache import get_or_build_json

    cache_path = tmp_path / "cache.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text("{not valid json")

    result = get_or_build_json(cache_path, lambda: {"b": 2})
    assert result == {"b": 2}
    assert cache_path.read_text() == '{"b": 2}'
```

- [ ] **Step 6: Run test to verify it fails**

Run: `pytest tests/unit/viz/test_render_cache.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'perfsage.core.viz.render_cache'`

- [ ] **Step 7: Implement the render cache module**

Create `perfsage/core/viz/render_cache.py`:

```python
"""Disk-backed cache for expensive per-report render payloads (figures JSON).

A Report is immutable once READY — its samples.parquet never changes after
ingest — so the JSON built for a given figure-set is safe to cache
indefinitely and reuse across every subsequent page view of that report.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


def get_or_build_json(cache_path: Path, build: Callable[[], Any]) -> Any:
    """Return the JSON-decoded contents of cache_path if present and valid,
    otherwise call build(), write its JSON-encoded result to cache_path, and
    return it. Never raises on cache I/O failure — falls back to build()."""
    if cache_path.exists():
        try:
            return json.loads(cache_path.read_text())
        except (OSError, ValueError):
            logger.warning("Render cache at %s is unreadable; rebuilding", cache_path)

    result = build()
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(result))
    except OSError:
        logger.warning("Could not write render cache at %s", cache_path)
    return result
```

- [ ] **Step 8: Add a FileStore path helper**

In `perfsage/core/storage/files.py`, add a new method to the `FileStore` class (after `agg_parquet`):

```python
    def render_cache_path(self, report_id: str, cache_name: str) -> Path:
        """Return path for a cached render payload: data/parquet/{report_id}/figs_{cache_name}.json"""
        return self.data_dir / "parquet" / report_id / f"figs_{cache_name}.json"
```

- [ ] **Step 9: Run test to verify it passes**

Run: `pytest tests/unit/viz/test_render_cache.py tests/unit/storage/test_files.py -v`
Expected: all pass

- [ ] **Step 10: Commit**

```bash
git add perfsage/core/viz/registry.py perfsage/core/viz/render_cache.py perfsage/core/storage/files.py tests/unit/viz/test_registry.py tests/unit/viz/test_render_cache.py
git commit -m "perf: support building figure subsets and cache rendered report payloads to disk"
```

---

## Task 9: Lazy-load the Distribution and Saturation sections

**Files:**
- Modify: `perfsage/web/views.py`
- Create: `perfsage/web/templates/partials/lazy_section_charts.html`
- Modify: `perfsage/web/templates/report_detail.html`
- Test: `tests/unit/web/test_views.py`

These are the two heaviest remaining sections after Tasks 6-7. Fetch them via HTMX once they scroll into view instead of building+embedding them in the initial response, so the first response only needs to build the lighter sections (Timeline, SLO, Errors) plus KPIs.

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/web/test_views.py`. This needs a `READY` report with a real samples parquet — follow the pattern from Task 4's test (or reuse a shared helper if one now exists from that task):

```python
def test_report_section_distribution_returns_only_its_charts(client: TestClient, test_settings) -> None:
    import polars as pl
    from perfsage.core.storage.db import ReportStatus, get_engine, get_session
    from perfsage.core.storage.repos import ReportRepo
    from perfsage.core.storage.files import FileStore

    engine = get_engine(test_settings.database_url)
    with get_session(engine) as session:
        report = ReportRepo(session).create("r.csv", "r.csv", 10)
        ReportRepo(session).update_stats(
            report.id, status=ReportStatus.READY, parsed_row_count=3, row_count=3
        )
        report_id = report.id

    file_store = FileStore(test_settings.data_dir)
    samples_path = file_store.samples_parquet(report_id)
    samples_path.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(
        {
            "timestamp_ms": [1_700_000_000_000, 1_700_000_001_000, 1_700_000_002_000],
            "elapsed": [100, 200, 300],
            "label": ["Home", "Home", "API"],
            "success": [True, True, True],
        }
    ).write_parquet(samples_path)

    r = client.get(f"/reports/{report_id}/section/distribution")
    assert r.status_code == 200
    assert "fig-histogram" in r.text
    assert "fig-rt-throughput" not in r.text  # that's the saturation section, not this one


def test_report_section_unknown_id_returns_404(client: TestClient) -> None:
    r = client.get("/reports/nonexistent/section/not-a-real-section")
    assert r.status_code == 404


def test_report_detail_no_longer_inlines_distribution_charts(client: TestClient, test_settings) -> None:
    import polars as pl
    from perfsage.core.storage.db import ReportStatus, get_engine, get_session
    from perfsage.core.storage.repos import ReportRepo
    from perfsage.core.storage.files import FileStore

    engine = get_engine(test_settings.database_url)
    with get_session(engine) as session:
        report = ReportRepo(session).create("r2.csv", "r2.csv", 10)
        ReportRepo(session).update_stats(
            report.id, status=ReportStatus.READY, parsed_row_count=2, row_count=2
        )
        report_id = report.id

    file_store = FileStore(test_settings.data_dir)
    samples_path = file_store.samples_parquet(report_id)
    samples_path.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(
        {
            "timestamp_ms": [1_700_000_000_000, 1_700_000_001_000],
            "elapsed": [100, 200],
            "label": ["Home", "Home"],
            "success": [True, True],
        }
    ).write_parquet(samples_path)

    r = client.get(f"/reports/{report_id}")
    assert r.status_code == 200
    assert 'hx-get="/reports/{}/section/distribution"'.format(report_id) in r.text
    # The initial response must not have already computed the histogram JSON inline.
    assert '"fig-histogram":' not in r.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/web/test_views.py -k "report_section or no_longer_inlines" -v`
Expected: FAIL — `/reports/{id}/section/distribution` route doesn't exist (404 for the wrong reason / no route registered)

- [ ] **Step 3: Define the lazy section chart lists and add the route**

In `perfsage/web/views.py`, add near the top (after the `templates = Jinja2Templates(...)` line):

```python
LAZY_SECTION_CHARTS: dict[str, list[tuple[str, str, str]]] = {
    "distribution": [
        ("fig-histogram", "Latency Histogram", "Overall response time distribution."),
        ("fig-cdf", "Latency CDF", "Cumulative probability of response times."),
        ("fig-boxplots", "Boxplots per Label", "Per-transaction spread and outliers."),
        ("fig-heatmap", "RT Heatmap", "Time vs label intensity map."),
        ("fig-outlier-scatter", "IQR Outliers", "Samples beyond 1.5×IQR fences."),
        ("fig-variability", "Variability", "Coefficient of variation by label."),
    ],
    "saturation": [
        ("fig-rt-throughput", "RT vs Throughput", "Find the knee where latency spikes."),
        ("fig-rt-concurrency", "RT vs Concurrency", "Latency under increasing load."),
        ("fig-correlation", "Correlation Matrix", "Metric interdependencies."),
        ("fig-threads-error-heatmap", "Threads vs Errors", "Failure density under load."),
    ],
}
```

Add the new route after `report_detail`:

```python
@router.get("/reports/{report_id}/section/{section_id}", response_class=HTMLResponse)
async def report_section(
    report_id: str,
    section_id: str,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> HTMLResponse:
    from perfsage.core.storage.files import FileStore
    from perfsage.core.viz.render_cache import get_or_build_json

    charts = LAZY_SECTION_CHARTS.get(section_id)
    if charts is None:
        return HTMLResponse("Unknown section", status_code=404)

    engine = _engine(settings)
    file_store = FileStore(settings.data_dir)

    with get_session(engine) as session:
        report = ReportRepo(session).get(report_id)
        if report is None or report.status != ReportStatus.READY:
            return HTMLResponse("Report not ready", status_code=404)
        slo_config = load_slo_config(session)

    samples_path = file_store.samples_parquet(report_id)
    if not samples_path.exists():
        return HTMLResponse("Report data not found", status_code=404)

    chart_ids = {cid for cid, _, _ in charts}
    cache_path = file_store.render_cache_path(report_id, section_id)
    figures_json = get_or_build_json(
        cache_path, lambda: build_figures_json(samples_path, slo_config, only=chart_ids)
    )

    return templates.TemplateResponse(
        request,
        "partials/lazy_section_charts.html",
        {"charts": charts, "figures_json": json.dumps(figures_json)},
    )
```

- [ ] **Step 4: Create the shared lazy-section partial template**

Create `perfsage/web/templates/partials/lazy_section_charts.html`:

```html
<div class="chart-grid-2">
  {% for chart_id, title, caption in charts %}
  <div class="card chart-card">
    <h3 class="chart-card-title">{{ title }}</h3>
    <p class="chart-caption">{{ caption }}</p>
    <div id="{{ chart_id }}"></div>
  </div>
  {% endfor %}
</div>
<script type="application/json" class="figures-data-fragment">{{ figures_json | safe }}</script>
<script>
PerfSageReport.mountFigures(document.currentScript.previousElementSibling);
</script>
```

- [ ] **Step 5: Update `report_detail` to exclude lazy-section figures and pass section metadata**

In `perfsage/web/views.py`, inside `report_detail`, change the `figures_json = build_figures_json(samples_path, slo_config)` line (around line 120) to exclude the lazy sections and use the render cache for the remaining (inline) set:

```python
    if samples_path.exists() and report.status == ReportStatus.READY:
        from perfsage.core.viz.render_cache import get_or_build_json

        lazy_ids = {cid for charts in LAZY_SECTION_CHARTS.values() for cid, _, _ in charts}
        inline_ids = {fid for fid, _ in EXPORT_FIGURES} - lazy_ids
        cache_path = file_store.render_cache_path(report_id, "main")
        figures_json = get_or_build_json(
            cache_path, lambda: build_figures_json(samples_path, slo_config, only=inline_ids)
        )
        try:
```

Add the needed import at the top of `views.py`:

```python
from perfsage.core.viz.registry import EXPORT_FIGURES, build_figures_json
```

(replacing the existing `from perfsage.core.viz.registry import build_figures_json` line with this combined import).

- [ ] **Step 6: Update the template to lazily fetch Distribution and Saturation**

In `perfsage/web/templates/report_detail.html`, replace the Distribution section body (lines 131-147):

```html
  <div class="report-section-body">
    <div class="chart-grid-2">
      {% for chart_id, title, caption in [
        ('fig-histogram', 'Latency Histogram', 'Overall response time distribution.'),
        ('fig-cdf', 'Latency CDF', 'Cumulative probability of response times.'),
        ('fig-boxplots', 'Boxplots per Label', 'Per-transaction spread and outliers.'),
        ('fig-heatmap', 'RT Heatmap', 'Time vs label intensity map.'),
        ('fig-outlier-scatter', 'IQR Outliers', 'Samples beyond 1.5×IQR fences.'),
        ('fig-variability', 'Variability', 'Coefficient of variation by label.'),
      ] %}
      <div class="card chart-card">
        <h3 class="chart-card-title">{{ title }}</h3>
        <p class="chart-caption">{{ caption }}</p>
        <div id="{{ chart_id }}"></div>
      </div>
      {% endfor %}
    </div>
  </div>
```

with:

```html
  <div class="report-section-body"
       hx-get="/reports/{{ report.id }}/section/distribution"
       hx-trigger="revealed"
       hx-swap="innerHTML">
    <div class="chart-grid-2">
      {% for chart_id, title, caption in [
        ('fig-histogram', 'Latency Histogram', 'Overall response time distribution.'),
        ('fig-cdf', 'Latency CDF', 'Cumulative probability of response times.'),
        ('fig-boxplots', 'Boxplots per Label', 'Per-transaction spread and outliers.'),
        ('fig-heatmap', 'RT Heatmap', 'Time vs label intensity map.'),
        ('fig-outlier-scatter', 'IQR Outliers', 'Samples beyond 1.5×IQR fences.'),
        ('fig-variability', 'Variability', 'Coefficient of variation by label.'),
      ] %}
      <div class="card chart-card">
        <h3 class="chart-card-title">{{ title }}</h3>
        <p class="chart-caption">{{ caption }}</p>
        <div class="skeleton chart-skeleton"></div>
      </div>
      {% endfor %}
    </div>
  </div>
```

Apply the same transformation to the Saturation section body (lines 157-171 in the original), swapping in `hx-get="/reports/{{ report.id }}/section/saturation"` and keeping its own 4 chart entries as skeleton placeholders instead of `<div id="{{ chart_id }}"></div>`.

- [ ] **Step 7: Run test to verify it passes**

Run: `pytest tests/unit/web/test_views.py -v`
Expected: all pass

- [ ] **Step 8: Run the full test suite to check for regressions**

Run: `pytest -q -m "not slow" --ignore=tests/e2e`
Expected: all pass (429+ existing tests plus all tests added in Tasks 1-9)

- [ ] **Step 9: Commit**

```bash
git add perfsage/web/views.py perfsage/web/templates/partials/lazy_section_charts.html perfsage/web/templates/report_detail.html tests/unit/web/test_views.py
git commit -m "perf: lazily HTMX-load Distribution and Saturation chart sections"
```

---

## Task 10: Motion tokens and skeleton shimmer CSS

**Files:**
- Modify: `perfsage/web/static/css/perfsage.css`

- [ ] **Step 1: Add motion tokens and reduced-motion guard**

In `perfsage/web/static/css/perfsage.css`, add to the existing `:root { ... }` block (after `--font-mono`):

```css
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);
  --dur-fast: 150ms;
  --dur-base: 220ms;
  --dur-slow: 300ms;
```

Add this block right after the `:root { ... }` block closes:

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

- [ ] **Step 2: Add skeleton shimmer styles**

Append to the end of `perfsage.css`:

```css
/* Skeleton loading placeholders */
.skeleton {
  position: relative;
  overflow: hidden;
  background: #EDF2F7;
  border-radius: 6px;
}
.skeleton::after {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, #EDF2F7 25%, #F7FAFC 37%, #EDF2F7 63%);
  background-size: 200% 100%;
  animation: skeleton-shimmer 1.4s var(--ease-in-out) infinite;
}
@keyframes skeleton-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
.kpi-value.skeleton { height: 1.75rem; width: 60%; margin: 0.25rem auto 0; }
.chart-skeleton { height: 340px; border-radius: 6px; }

/* Chart fade-in once mounted (see report.js PerfSageReport.mountFigures) */
.chart-card [id^="fig-"] {
  opacity: 0;
  transition: opacity var(--dur-slow) var(--ease-out);
  min-height: 340px;
}
.chart-card [id^="fig-"].chart-loaded {
  opacity: 1;
}
```

- [ ] **Step 3: Verify no syntax errors by loading a page**

Run: `pytest tests/unit/web/test_views.py -v` (templates + static files are served as-is; this at least confirms the app still boots and renders pages without error after the CSS edit)
Expected: all pass

- [ ] **Step 4: Commit**

```bash
git add perfsage/web/static/css/perfsage.css
git commit -m "style: add motion tokens, reduced-motion guard, and skeleton shimmer CSS"
```

---

## Task 11: Global HTMX top progress bar

**Files:**
- Modify: `perfsage/web/templates/base.html`
- Modify: `perfsage/web/static/css/perfsage.css`

- [ ] **Step 1: Add the progress bar element and CSS**

In `perfsage/web/static/css/perfsage.css`, append:

```css
/* Global HTMX top progress bar */
#htmx-top-bar {
  position: fixed;
  top: 0;
  left: 0;
  height: 3px;
  width: 0%;
  background: var(--amber);
  z-index: 10000;
  opacity: 0;
  transition: width var(--dur-slow) var(--ease-out), opacity var(--dur-fast) linear;
}
#htmx-top-bar.is-active { opacity: 1; }
```

- [ ] **Step 2: Add the element and driver script to base.html**

In `perfsage/web/templates/base.html`, add the bar element right after `<body>`:

```html
<body>
  <div id="htmx-top-bar"></div>
```

Add a script before the closing `</body>` tag (after the existing `{% block scripts %}{% endblock %}`):

```html
  <script>
    (function () {
      var bar = document.getElementById("htmx-top-bar");
      var hideTimeout;
      document.body.addEventListener("htmx:beforeRequest", function () {
        clearTimeout(hideTimeout);
        bar.classList.add("is-active");
        bar.style.width = "90%";
      });
      document.body.addEventListener("htmx:afterOnLoad", function () {
        bar.style.width = "100%";
      });
      document.body.addEventListener("htmx:afterSettle", function () {
        hideTimeout = setTimeout(function () {
          bar.classList.remove("is-active");
          bar.style.width = "0%";
        }, 200);
      });
    })();
  </script>
</body>
```

This single global listener covers every HTMX-driven interaction in the app (pagination, flush, settings forms, AI generate, and the new lazy chart sections from Task 9) with zero per-template wiring.

- [ ] **Step 3: Verify pages still render**

Run: `pytest tests/unit/web/test_views.py -v`
Expected: all pass

- [ ] **Step 4: Commit**

```bash
git add perfsage/web/templates/base.html perfsage/web/static/css/perfsage.css
git commit -m "feat: add global HTMX top progress bar for all async requests"
```

---

## Task 12: Button/form busy states

**Files:**
- Modify: `perfsage/web/static/css/perfsage.css`
- Modify: `perfsage/web/templates/index.html`, `reports_list.html`, `settings.html` (add `hx-disabled-elt`)

HTMX already adds the `htmx-request` class to the element that triggered a request — no per-element JS needed, just CSS targeting that class plus `hx-disabled-elt` to prevent double-submits on the app's existing forms.

- [ ] **Step 1: Add busy-state CSS**

Append to `perfsage/web/static/css/perfsage.css`:

```css
/* Button/form busy state (HTMX auto-adds .htmx-request to the triggering element) */
.btn-primary.htmx-request,
.btn-amber.htmx-request,
.btn-outline.htmx-request {
  opacity: 0.7;
  cursor: wait;
  pointer-events: none;
}
.btn-primary.htmx-request::after,
.btn-amber.htmx-request::after,
.btn-outline.htmx-request::after {
  content: "";
  display: inline-block;
  width: 0.8em;
  height: 0.8em;
  margin-left: 0.5em;
  border: 2px solid currentColor;
  border-right-color: transparent;
  border-radius: 50%;
  animation: btn-spin 0.6s linear infinite;
  vertical-align: -0.15em;
}
@keyframes btn-spin { to { transform: rotate(360deg); } }
```

- [ ] **Step 2: Add `hx-disabled-elt` to existing HTMX forms/buttons**

Read `perfsage/web/templates/index.html`, `perfsage/web/templates/reports_list.html`, and `perfsage/web/templates/settings.html` to find each element carrying `hx-post` or `hx-get` (upload/paste forms, flush button, AI-key and SLO settings forms), and add `hx-disabled-elt="this"` to each one, e.g. change:

```html
<button class="btn-primary" hx-post="/api/reports/flush" hx-confirm="...">Flush</button>
```

to:

```html
<button class="btn-primary" hx-post="/api/reports/flush" hx-confirm="..." hx-disabled-elt="this">Flush</button>
```

Apply the same `hx-disabled-elt="this"` addition to every `hx-post`/`hx-get` form/button found in those three templates (do not remove or change any existing attributes — only add this one).

- [ ] **Step 3: Verify existing HTMX interactions still work**

Run: `pytest tests/unit/web/test_views.py tests/integration/ -v`
Expected: all pass (attribute addition doesn't change server-side behavior or the HTML assertions those tests check)

- [ ] **Step 4: Commit**

```bash
git add perfsage/web/static/css/perfsage.css perfsage/web/templates/index.html perfsage/web/templates/reports_list.html perfsage/web/templates/settings.html
git commit -m "feat: add busy-state spinner CSS and disable-on-submit to HTMX forms"
```

---

## Task 13: Staged chart fade-in

**Files:**
- Modify: `perfsage/web/static/js/report.js`

Task 10 already added the `.chart-card [id^="fig-"]` opacity-0 CSS and `.chart-loaded` opacity-1 rule. Wire `PerfSageReport.mountFigures` (from Task 4) to add `.chart-loaded` once each `Plotly.newPlot` promise resolves, so charts fade in individually rather than all popping in at once — covers both the initial inline charts and the Task 9 lazy-loaded fragments, since both call this same function.

- [ ] **Step 1: Update `mountFigures` to fade in per chart**

In `perfsage/web/static/js/report.js`, replace the `mountFigures` body from Task 4:

```js
  window.PerfSageReport.mountFigures = function (jsonScriptEl) {
    if (!jsonScriptEl) return;
    var figs;
    try {
      figs = JSON.parse(jsonScriptEl.textContent);
    } catch (e) {
      console.error("PerfSage: failed to parse figures JSON", e);
      return;
    }
    for (var divId in figs) {
      var figJson = figs[divId];
      var el = document.getElementById(divId);
      if (!figJson || !el) continue;
      Plotly.newPlot(el, figJson.data, figJson.layout, {
        responsive: true,
        displayModeBar: true,
      }).then(function (gd) {
        gd.classList.add("chart-loaded");
      });
    }
  };
```

(The only change from Task 4's version: `Plotly.newPlot(...)` return value is a Promise that resolves with the graph div once rendering completes — `.then()` adds `chart-loaded`, which Task 10's CSS transitions from `opacity: 0` to `opacity: 1`.)

- [ ] **Step 2: Manually verify in a browser**

This step is visual/behavioral and not meaningfully unit-testable — run the dev server and confirm charts fade in rather than popping in abruptly:

```bash
uvicorn perfsage.main:app --reload &
```

Navigate to a report page in a browser, confirm charts individually fade from transparent to opaque as they mount, then stop the server:

```bash
kill %1
```

- [ ] **Step 3: Run the full test suite**

Run: `pytest -q -m "not slow" --ignore=tests/e2e`
Expected: all pass (JS-only change, no Python test surface)

- [ ] **Step 4: Commit**

```bash
git add perfsage/web/static/js/report.js
git commit -m "feat: fade in each chart individually once its Plotly render resolves"
```

---

## Task 14: Fix `aria-expanded` bug and smoother section collapse

**Files:**
- Modify: `perfsage/web/static/js/report.js`
- Modify: `perfsage/web/static/css/perfsage.css`
- Modify: `perfsage/web/templates/report_detail.html`

`aria-expanded="true"` is hardcoded in the template on every section toggle button and never updated by JS — a real accessibility bug flagged by the UX audit. Fix it, and replace the hard `display:none` collapse with a smooth transition using the motion tokens from Task 10.

- [ ] **Step 1: Fix the JS to toggle `aria-expanded`**

In `perfsage/web/static/js/report.js`, update the section-toggle handler:

```js
    document.querySelectorAll(".report-section-toggle").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var section = btn.closest(".report-section");
        if (!section) return;
        var collapsed = section.classList.toggle("collapsed");
        btn.setAttribute("aria-expanded", collapsed ? "false" : "true");
      });
    });
```

- [ ] **Step 2: Smooth the collapse transition in CSS**

In `perfsage/web/static/css/perfsage.css`, replace the existing hard-toggle rule:

```css
.report-section.collapsed .report-section-body { display: none; }
```

with a transition-based collapse:

```css
.report-section-body {
  max-height: 100000px;
  opacity: 1;
  overflow: hidden;
  transition: opacity var(--dur-base) var(--ease-out);
}
.report-section.collapsed .report-section-body {
  max-height: 0;
  opacity: 0;
  padding-top: 0;
}
```

(Remove the old standalone `.report-section-body { background: transparent; padding-top: 1rem; }` rule's `padding-top` duplication is fine — Jinja/CSS cascade will apply the new rule's `padding-top: 1rem` from the base state since it's declared before the `.collapsed` override; verify by leaving the original `.report-section-body { background: transparent; padding-top: 1rem; }` rule in place and only adding the new rules above it, rather than deleting it — the more specific `.collapsed` selector wins when active.)

- [ ] **Step 3: Verify no test regressions**

Run: `pytest tests/unit/web/test_views.py -v`
Expected: all pass (no test currently asserts on `aria-expanded` value, but confirm none do; if one does with a hardcoded `"true"` expectation on initial page load, that's still correct since sections start expanded)

- [ ] **Step 4: Commit**

```bash
git add perfsage/web/static/js/report.js perfsage/web/static/css/perfsage.css
git commit -m "fix: update aria-expanded on section toggle and animate collapse instead of display:none"
```

---

## Task 15: Regression tests protecting the performance fixes

**Files:**
- Create: `scripts/bench_report.py`
- Test: already covered by Tasks 5-8's unit tests (cache hit-count assertion, binned-payload assertions, subset-filtering assertions)

Task 5's `test_read_samples_cached_avoids_rereading_disk`, Task 6's `test_fig_latency_histogram_payload_is_binned_not_raw`, and Task 7's `test_fig_boxplots_per_label_payload_has_no_raw_y_arrays` already act as regression guards against these specific fixes silently regressing. This task adds a standalone local benchmarking script (not wired into CI in this slice — that's a Phase 0b follow-up once a dedicated large-file fixture generator exists) so performance can be spot-checked before/after future changes.

- [ ] **Step 1: Create the benchmark script**

Create `scripts/bench_report.py`:

```python
#!/usr/bin/env python
"""Local benchmark: time report-page figure building for a given samples parquet.

Usage:
    python scripts/bench_report.py path/to/samples.parquet

Not wired into CI — for local before/after comparisons when touching
perfsage/core/viz/ or perfsage/core/analysis/.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    samples_path = Path(sys.argv[1])
    if not samples_path.exists():
        print(f"File not found: {samples_path}")
        sys.exit(1)

    from perfsage.core.analysis.slo import SLOConfig
    from perfsage.core.viz.registry import EXPORT_FIGURES, build_figures_json

    slo_config = SLOConfig()

    print(f"Benchmarking {samples_path} ({samples_path.stat().st_size / 1e6:.1f} MB)")

    start = time.perf_counter()
    figures = build_figures_json(samples_path, slo_config)
    elapsed = time.perf_counter() - start

    import json

    payload_bytes = len(json.dumps(figures))
    built = sum(1 for v in figures.values() if v is not None)

    print(f"build_figures_json: {elapsed:.2f}s, {built}/{len(EXPORT_FIGURES)} figures built, "
          f"payload {payload_bytes / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it against the existing test fixture generator to sanity-check it works**

Run:

```bash
python -c "
from tests.fixtures.generate_jtl import make_csv_jtl
from perfsage.core.parsing.csv_loader import load_csv_to_parquet
from pathlib import Path
Path('/tmp/bench').mkdir(exist_ok=True)
Path('/tmp/bench/sample.csv').write_text(make_csv_jtl(n_rows=50000, include_errors=True))
load_csv_to_parquet(Path('/tmp/bench/sample.csv'), Path('/tmp/bench/samples.parquet'), Path('/tmp/bench/quarantine.parquet'), delimiter=',')
"
python scripts/bench_report.py /tmp/bench/samples.parquet
```

Expected: prints a build time and payload size with no errors, confirming the script runs end-to-end against real project code after all of Tasks 5-8's changes.

- [ ] **Step 3: Commit**

```bash
git add scripts/bench_report.py
git commit -m "chore: add local report-build benchmark script"
```

---

## Final Verification

- [ ] **Run the complete test suite**

```bash
pytest -q -m "not slow" --ignore=tests/e2e
```

Expected: all tests pass (429 pre-existing + all tests added across Tasks 1-9).

- [ ] **Run ruff and mypy** (existing project quality gates per `.cursor/rules/core.mdc` and `pyproject.toml`)

```bash
ruff check perfsage/ && ruff format --check perfsage/ && mypy perfsage/
```

Fix any lint/type issues surfaced (e.g. missing type hints on new functions like `load_slo_config`, `read_samples_cached`, `get_or_build_json`) before considering Phase 0 complete.

- [ ] **Manual browser verification** (per UX design — not unit-testable)

Start the app locally (`uvicorn perfsage.main:app --reload` + `arq perfsage.core.jobs.worker.WorkerSettings` if a worker entrypoint exists, or per `README.md`'s local dev instructions), upload a real JTL sample, and confirm:
1. Top progress bar appears during pagination/flush/settings/AI-generate.
2. Report page loads with KPIs and Timeline/SLO/Errors sections immediately; Distribution and Saturation sections show skeleton placeholders that swap to real charts with a fade-in as you scroll to them.
3. Buttons show a spinner and disable while an HTMX request is in flight.
4. Section collapse/expand animates smoothly instead of snapping.
5. `Cmd+F` / view-source confirms the figures JSON now lives in a `<script type="application/json">` block, not an executable `<script>` block.
