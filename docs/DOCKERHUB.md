# PerfSage Reveal

**Turn raw JMeter results into actionable performance intelligence — in one container.**

[![GitHub](https://img.shields.io/badge/GitHub-perfsage%2Freveal-0B1F3A?style=flat&logo=github)](https://github.com/perfsage/reveal)

---

## 🎯 What it does

**PerfSage Reveal** ingests JTL / CSV / XML load-test output and delivers:

- **29 interactive charts** — latency scatter, percentile bands, throughput, heatmaps, CDF, APDEX, SLO gauges
- **Expert recommendations** — tail-latency ratio, saturation knee, error spikes, SLO violations
- **AI narrative** — optional GPT / Claude / Gemini insights on any report
- **Export** — self-contained HTML or print-quality PDF with embedded chart images

> **Mission:** Generate real value in performance analysis — faster triage, clearer stories, shareable reports.

---

## ⚡ Quick start

```bash
docker run -d \
  --name perfsage-reveal \
  -p 8000:8000 \
  -v perfsage-reveal-data:/app/data \
  -e PERFSAGE_SECRET="your-32-char-random-secret-here" \
  aashu3201/reveal:latest
```

Open **http://localhost:8000** → upload a `.jtl` / `.csv` / `.xml` file → explore charts → export HTML or PDF.

---

## 🐳 Tags

| Tag | Description |
|-----|-------------|
| `latest` | Latest build from `main` |
| `0.1.1` | Semver release (see [CHANGELOG](https://github.com/perfsage/reveal/blob/main/CHANGELOG.md)) |
| `sha-<commit>` | Immutable build for a specific commit |

---

## 🔧 Configuration

| Variable | Default | Required |
|----------|---------|----------|
| `PERFSAGE_SECRET` | — | **Yes** — encrypts AI API keys (32+ chars) |
| `REDIS_URL` | `redis://127.0.0.1:6379` | No — bundled in image |
| `DATABASE_URL` | `sqlite:///./data/perfsage.db` | No |
| `DATA_DIR` | `data` | No — mount a volume here |
| `MAX_UPLOAD_BYTES` | `2147483648` (2 GB) | No |
| `DEBUG` | `false` | No |

---

## 📦 What's inside

One image runs everything via **supervisord**:

```
Browser (HTMX + Plotly)
    ↔ FastAPI (uvicorn)
    → Redis (job queue + SSE progress)
    → arq worker (ingest + analysis)
    → SQLite + Parquet (persistent storage)
    → LLM providers (optional AI insights)
```

**Supported JMeter:** 2.x through 5.6 — CSV and XML JTL formats.

---

## 📚 Documentation

- **Full README:** [github.com/perfsage/reveal](https://github.com/perfsage/reveal)
- **Issues & releases:** [GitHub Releases](https://github.com/perfsage/reveal/releases)
- **License:** MIT

---

## 🛠 Docker Compose (recommended)

```bash
git clone https://github.com/perfsage/reveal.git
cd reveal
cp .env.example .env   # set PERFSAGE_SECRET
docker compose up -d
```

---

Built with ❤️ by [PerfSage](https://github.com/perfsage) — *generating value in performance analysis.*
