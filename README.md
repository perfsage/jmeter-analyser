<div align="center">

# ✨ PerfSage Reveal

### *Uncover what your load test really means*

**Generating value in performance analysis** — upload JMeter results, get expert charts, SLO insights, AI narratives, and shareable HTML/PDF reports.

[![Docker Hub](https://img.shields.io/docker/v/aashu3201/reveal?label=Docker%20Hub&logo=docker&color=2496ED)](https://hub.docker.com/r/aashu3201/reveal)
[![Version](https://img.shields.io/badge/version-0.1.1-D4A857)](VERSION)
[![Python](https://img.shields.io/badge/python-3.12+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-0B1F3A)](LICENSE)

[🚀 Quick Start](#-installation) · [📊 Features](#-features) · [🐳 Docker Hub](https://hub.docker.com/r/aashu3201/reveal) · [📦 Releases](https://github.com/perfsage/reveal/releases)

</div>

---

## 🎯 Why PerfSage Reveal?

Load tests produce **millions of rows** — but stakeholders need **answers**, not spreadsheets.

**Reveal** transforms raw JTL / CSV / XML into clarity:

| | |
|---|---|
| 📈 **29 expert visualizations** | Scatter, heatmaps, CDF, APDEX, SLO gauges, correlation matrices |
| 🧠 **Smart recommendations** | Tail-latency ratio, saturation knee, error spikes, SLO violations |
| 🤖 **AI narrative** | Optional GPT-4, Claude, or Gemini insights on any report |
| 📄 **One-click export** | Self-contained HTML or print-quality PDF with embedded charts |
| 💾 **Persistent reports** | Survive restarts — SQLite + Parquet, paginated dashboard |

> **Our mission:** Turn performance data into decisions — faster triage, clearer stories, zero toolchain friction.

---

## ✨ Features

- **📤 Upload or paste** — JMeter 2.x through 5.6 (CSV & XML JTL)
- **📊 Interactive charts** — Plotly-powered, tabbed report UI
- **🎯 SLO tracking** — Configurable thresholds, burn-rate timeline, compliance gauges
- **🔬 Expert analysis** — Warmup detection, steady-state compare, outlier scatter
- **🤖 Multi-provider AI** — Keys encrypted at rest (Fernet + `PERFSAGE_SECRET`)
- **📑 Export** — Standalone HTML or PDF (29 chart images via kaleido + WeasyPrint)
- **🐳 Single container** — Redis, background worker, and web server bundled

---

## 🚀 Installation

Choose the path that fits your workflow:

### Option 1 — Docker Hub pull *(fastest)*

```bash
docker pull aashu3201/reveal:latest

docker run -d \
  --name perfsage-reveal \
  -p 8000:8000 \
  -v perfsage-reveal-data:/app/data \
  -e PERFSAGE_SECRET="change-me-to-a-32-char-random-string" \
  aashu3201/reveal:latest
```

Open **http://localhost:8000** 🎉

---

### Option 2 — Docker Compose *(recommended for teams)*

```bash
git clone https://github.com/perfsage/reveal.git
cd reveal

cp .env.example .env
# ✏️ Edit .env — set PERFSAGE_SECRET to a random 32+ character string

docker compose up -d
```

Open **http://localhost:8000** · View logs with `docker compose logs -f`

---

### Option 3 — Build from source

```bash
git clone https://github.com/perfsage/reveal.git
cd reveal

docker compose build
docker compose up -d
```

Every push to `main` triggers a CI build → [Docker Hub](https://hub.docker.com/r/aashu3201/reveal).

---

### Option 4 — Local Python development

```bash
git clone https://github.com/perfsage/reveal.git
cd reveal

python -m venv .venv && source .venv/bin/activate
pip install -e ".[test]"

# Redis (required for background jobs)
docker run -d -p 6379:6379 redis:7-alpine

export PERFSAGE_SECRET="your-32-char-secret-here"
export REDIS_URL="redis://localhost:6379"

# Terminal 1 — web server
uvicorn perfsage.main:app --reload

# Terminal 2 — background worker
arq perfsage.core.jobs.queue.WorkerSettings
```

Open **http://localhost:8000**

---

## 📖 Usage

```
1. Upload  →  Drop a .jtl / .csv / .xml file (or paste content)
2. Wait    →  Background worker ingests → Parquet → analysis
3. Explore →  29 charts, KPIs, recommendations, optional AI insights
4. Export  →  Download HTML or PDF from the report page
5. Manage  →  All Reports → paginated list, flush old analyses
```

**AI setup:** Settings → pick provider → enter API key → **Generate AI Insights** on any report.

---

## ⚙️ Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `PERFSAGE_SECRET` | *(required)* | Encrypts AI API keys — **must** be set |
| `REDIS_URL` | `redis://127.0.0.1:6379` | Bundled inside Docker image |
| `DATABASE_URL` | `sqlite:///./data/perfsage.db` | Report metadata |
| `DATA_DIR` | `data` | Parquet, exports, uploads — **mount a volume here** |
| `MAX_UPLOAD_BYTES` | `2147483648` (2 GB) | Max upload size |
| `DEBUG` | `false` | Verbose logging |

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Browser  (HTMX + Plotly.js)                            │
└──────────────────────────┬──────────────────────────────┘
                           │ HTTP / SSE
┌──────────────────────────▼──────────────────────────────┐
│  FastAPI (uvicorn)  —  web views + REST API             │
├─────────────────────────────────────────────────────────┤
│  Redis  →  arq worker  →  ingest + analysis             │
│  SQLite (metadata)  +  Parquet (samples & aggregates)   │
│  LLM providers (OpenAI / Anthropic / Gemini) — optional │
└─────────────────────────────────────────────────────────┘
```

**One Docker container** runs Redis, worker, and web via supervisord.

---

## 📋 Supported JMeter formats

| Version | Format | Notes |
|---------|--------|-------|
| 2.x | CSV | Core columns: timeStamp, elapsed, label, responseCode… |
| 3.x – 4.x | CSV | + sentBytes, Latency, Connect, failureMessage |
| 5.x – 5.6 | CSV | Normalised column names (`latency` vs `Latency`) |
| All | XML JTL | `httpSample` and `sample` elements |

---

## 🏷 Versioning

Versions are tracked in-repo:

| File | Purpose |
|------|---------|
| [`VERSION`](VERSION) | Current semver — used by Docker tags & health check |
| [`CHANGELOG.md`](CHANGELOG.md) | Release notes |
| Git tags | `v0.1.0`, `v0.1.1`, … — trigger semver Docker Hub tags |

**Release flow:**

```bash
# 1. Bump VERSION + CHANGELOG.md
# 2. Commit and tag
git tag v0.1.1 && git push origin main --tags
# 3. GitHub Actions builds & pushes aashu3201/reveal:0.1.1 + :latest
```

---

## 🧪 Tests

```bash
pip install -e ".[test]"

pytest -q                          # unit + integration
pytest -m "not slow" -q            # skip kaleido PDF renders
pytest tests/e2e/ -q               # requires app at localhost:8000
```

---

## 🤝 CI / CD

| Workflow | Trigger | Action |
|----------|---------|--------|
| **CI** | Push & PR | Ruff, mypy, pytest |
| **Docker Publish** | Push to `main` or tag `v*` | Build multi-arch image → Docker Hub + sync README |

**Required GitHub secrets:** `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`

See [`docs/GITHUB_SECRETS.md`](docs/GITHUB_SECRETS.md) for setup.

---

## 📄 License

MIT — see [LICENSE](LICENSE).

---

<div align="center">

**Built by [PerfSage](https://github.com/perfsage)** · *Generating value in performance analysis* ✨

[Docker Hub](https://hub.docker.com/r/aashu3201/reveal) · [GitHub](https://github.com/perfsage/reveal) · [Report an issue](https://github.com/perfsage/reveal/issues)

</div>
