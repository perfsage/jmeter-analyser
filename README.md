# PerfSage JMeter Analyser

**PerfSage** is a Python-only, Dockerised, browser-based JMeter result analyser.

Upload JMeter CSV/XML result files, get instant interactive dashboards, SLO analysis, AI-powered recommendations, and exportable PDF reports.

## Branding

- Navy `#0B1F3A` — primary background
- Cream `#F6F1E7` — content surface
- Amber `#D4A857` — accent / CTA

## Quick Start

```bash
cp .env.example .env
docker compose up
# open http://localhost:8000
```

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[test]"
pre-commit install
pytest -q
```

## Architecture

```
Browser (HTMX + Plotly)
    <-> FastAPI (web + REST + SSE)
    --> Redis (arq queue + progress pubsub)
    --> arq worker
    --> Parquet files on disk
    --> SQLite (SQLModel)
    --> LLM provider (OpenAI / Anthropic / Gemini)
```

## Project Structure

See `docs/superpowers/specs/` for the full architectural spec and `docs/superpowers/plans/` for the implementation roadmap.

## License

Proprietary — © PerfSage 2026
