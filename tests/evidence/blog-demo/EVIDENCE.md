# Blog Demo — Evidence Index

**Date:** 2026-05-29  
**Product:** PerfSage Reveal (`aashu3201/reveal:latest`)  
**Report:** [Public APIs Load Test](http://localhost:8000/reports/841e564d-d0f3-4b67-8991-9bec274f90c3)

## Docker one-liner used

```bash
docker run -d \
  --name perfsage-reveal \
  -p 8000:8000 \
  -v perfsage-reveal-data:/app/data \
  -e PERFSAGE_SECRET="blog-demo-perfsage-reveal-secret-key-32chars" \
  aashu3201/reveal:latest
```

## JMeter load test

| Item | Value |
|------|-------|
| Plan | `jmeter/public-apis-demo.jmx` |
| Output | `jmeter/results.jtl` (3,587 samples, 484 KB) |
| Duration | ~3 min (180s scheduler) |
| Threads | 15 (15s ramp) |
| Endpoints | JSONPlaceholder posts, httpbin /status/200, GitHub /zen |
| Error rate | ~31.5% (GitHub rate-limiting under load) |

## Analysis results (PerfSage Reveal)

| KPI | Value |
|-----|-------|
| Samples | 3,587 |
| P50 | 147 ms |
| P90 | 330 ms |
| P99 | 1,124 ms |
| Error rate | 31.7% |
| SLO status | **FAIL** |

### Notable recommendations surfaced
- **[CRITICAL]** Tail latency on JSONPlaceholder: p99/p50 ratio 19.9× (threshold 10×)
- **[CRITICAL]** Error spike: 34.4% in a time bucket
- **[CRITICAL]** GitHub Zen SLO fail — 97% errors (rate limit)
- **[WARNING]** High variability on JSONPlaceholder & httpbin

## PDF export verification

| Check | Result |
|-------|--------|
| File | `screenshots/demo-report.pdf` (1.7 MB) |
| Charts embedded | ✅ Yes |
| "Chart not available" | ❌ Not present |

## LinkedIn launch post

| Item | Value |
|------|-------|
| Page | [PerfSage](https://www.linkedin.com/company/perfsage/) |
| Post URL | https://www.linkedin.com/feed/update/urn:li:share:7466238876068507648/ |
| Short link | https://lnkd.in/d4acUXjZ |
| Screenshot | `screenshots/07-linkedin-post-published.png` |

## Screenshots

| # | File | Description |
|---|------|-------------|
| 01 | `screenshots/01-dashboard-fresh.png` | Empty dashboard before upload |
| 02 | `screenshots/02-report-kpi-summary.png` | KPI cards + expert recommendations |
| 03 | `screenshots/03-scatter-chart.png` | Response time scatter by transaction |
| 04 | `screenshots/04-slo-gauges.png` | SLO KPI gauges (Apdex, error, p99) |
| 05 | `screenshots/05-error-sunburst.png` | Error sunburst breakdown |
| 06 | `screenshots/06-reports-list.png` | Reports list with analysed run |

## Artifacts

- `jmeter/public-apis-demo.jmx` — reusable test plan
- `jmeter/results.jtl` — raw JMeter output
- `jmeter/jmeter.log` — JMeter run log
- `jmeter-run.log` — console summary
- `report-id.txt` — UUID for uploaded report
- `docker-status.txt` / `docker-run-evidence.txt` — container proof
