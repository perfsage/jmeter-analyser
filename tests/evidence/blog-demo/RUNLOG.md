# PerfSage Reveal — Blog Demo Evidence Log
Date: 2026-05-27

## 1. Clean local Docker state
- Stopped `docker compose` stack
- Removed old images: perfsage-jmeter-report-analyser-{app,web,worker}

## 2. One-liner Docker run
```bash
docker run -d \
  --name perfsage-reveal \
  -p 8000:8000 \
  -v perfsage-reveal-data:/app/data \
  -e PERFSAGE_SECRET="blog-demo-perfsage-reveal-secret-key-32chars" \
  aashu3201/reveal:latest
```

## 3. JMeter load test
- Plan: `tests/evidence/blog-demo/jmeter/public-apis-demo.jmx`
- Targets: JSONPlaceholder, httpbin, GitHub Zen
- 15 threads, 15s ramp, 180s duration

## 4. Analysis
- Upload JTL to http://localhost:8000
- Screenshots in `tests/evidence/blog-demo/screenshots/`
