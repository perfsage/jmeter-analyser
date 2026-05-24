# PerfSage JMeter Analyser

> AI-powered JMeter performance report analysis with 20+ expert-grade visualizations.

## Features

- **Upload or paste** JTL/CSV/XML results from any JMeter version (2.x–5.6)
- **20 interactive visualizations** including scatter plots, latency heatmaps, CDF, APDEX, SLO gauges
- **Expert recommendations** (tail-latency ratio, saturation knee, error spikes, SLO violations)
- **AI-powered narrative** (OpenAI GPT-4, Anthropic Claude, or Google Gemini)
- **Persistent reports** — all analyses survive container restarts
- **Export** to standalone HTML or PDF

## Quick Start

### Docker (recommended)

```bash
# Clone and start
git clone https://github.com/perfsage/jmeter-analyser
cd jmeter-analyser

# Configure
cp .env.example .env
# Edit .env — set PERFSAGE_SECRET to a random 32-char string

# Start
docker compose up -d

# Open
open http://localhost:8000
```

### Local Development

```bash
# Install
python -m venv .venv && source .venv/bin/activate
pip install -e ".[test]"

# Start Redis (required for background jobs)
docker run -d -p 6379:6379 redis:7-alpine

# Set environment
export PERFSAGE_SECRET="your-32-char-secret-here"
export REDIS_URL="redis://localhost:6379"

# Start web server
uvicorn perfsage.main:app --reload

# Start worker (in a second terminal)
arq perfsage.core.jobs.queue.WorkerSettings
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `PERFSAGE_SECRET` | (required) | Secret key for encrypting AI API keys. Must be set. |
| `REDIS_URL` | `redis://redis:6379` | Redis URL for job queue |
| `DATABASE_URL` | `sqlite:///./data/perfsage.db` | SQLite database path |
| `DATA_DIR` | `data` | Directory for Parquet files and exports |
| `MAX_UPLOAD_BYTES` | `2147483648` (2GB) | Maximum upload file size |
| `DEBUG` | `false` | Enable debug logging |

## AI Provider Setup

1. Go to **Settings** in the UI (`/settings`)
2. Select your provider (OpenAI, Anthropic, or Gemini)
3. Enter your API key
4. On any report page, click **Generate AI Insights**

Keys are encrypted at rest using Fernet (AES-128-CBC) with a key derived from `PERFSAGE_SECRET`.

## Architecture

```
Browser (HTMX + Plotly)
    ↔ FastAPI (uvicorn) — web views + REST API
    → Redis (arq job queue + SSE progress)
    → arq worker (ingest + analysis)
    → SQLite (report metadata)
    → Parquet files (samples + aggregates)
    → LLM provider (AI insights)
```

## Supported JMeter Versions

- JMeter 2.x (CSV: timeStamp, elapsed, label, responseCode, responseMessage, threadName, dataType, success, bytes)
- JMeter 3.x–4.x (adds sentBytes, grpThreads, allThreads, URL, Latency, IdleTime, Connect, failureMessage)
- JMeter 5.x–5.6 (same as 3.x with normalised column names)
- XML JTL (all versions: httpSample and sample elements)

## Running Tests

```bash
pip install -e ".[test]"
pytest -q
```

## License

MIT — see [LICENSE](LICENSE) for details.
