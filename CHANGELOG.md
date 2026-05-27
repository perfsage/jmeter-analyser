# Changelog

All notable changes to **PerfSage Reveal** are documented here.
Version numbers follow [Semantic Versioning](https://semver.org/) and align with git tags (`v0.1.0`).

## [0.1.1] — 2026-05-27

### Changed
- 🏷 **Rebrand** from *PerfSage JMeter Analyser* → **PerfSage Reveal**
- GitHub repo: `perfsage/reveal` · Docker image: `perfsage/reveal`

## [0.1.0] — 2026-05-26

### Added
- 🚀 Single-container Docker image (Redis + arq worker + uvicorn via supervisord)
- 📊 **29 expert-grade visualizations** — scatter, heatmaps, CDF, APDEX, SLO gauges, and more
- 🧠 AI narrative insights (OpenAI, Anthropic, Gemini) with encrypted key storage
- 📄 Standalone **HTML** and **PDF** export (WeasyPrint + kaleido chart rendering)
- 🔍 Expert recommendations — tail latency, saturation knee, error spikes, SLO violations
- 📁 Persistent reports with Parquet storage and paginated report list
- 🧪 E2E tests including large-dataset (4,500+ row) PDF export validation

### Fixed
- 🐛 PDF chart export in Docker — supervisord now sets `HOME`, `BROWSER_PATH`, and `CHROME_PATH` for the `perfsage` user

[0.1.1]: https://github.com/perfsage/reveal/releases/tag/v0.1.1
[0.1.0]: https://github.com/perfsage/reveal/releases/tag/v0.1.0
