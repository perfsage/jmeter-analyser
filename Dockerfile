# ─── builder ──────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpango-1.0-0 libpangoft2-1.0-0 libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md VERSION ./
COPY perfsage/ perfsage/

RUN pip install --upgrade pip && \
    pip install --prefix=/install .

# ─── runtime ──────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# WeasyPrint needs pango + fontconfig for PDF rendering; kaleido bundles its own chromium.
# libgdk-pixbuf2.0-0 was replaced by libgdk-pixbuf-xlib-2.0-0 in Debian bookworm+
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf-xlib-2.0-0 \
    libffi8 \
    fontconfig \
    libglib2.0-0 \
    libnss3 \
    libgbm1 \
    libxss1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libdrm2 \
    libxkbcommon0 \
    libcups2 \
    chromium \
    redis-server \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --uid 1000 --create-home perfsage && \
    mkdir -p /app/data/redis /var/log/supervisor && \
    chown -R perfsage:perfsage /app

WORKDIR /app

COPY --from=builder /install /usr/local
COPY perfsage/ perfsage/
COPY VERSION /app/VERSION
COPY docker/supervisord.conf /etc/supervisor/conf.d/perfsage.conf

ARG PERFSAGE_VERSION=0.1.0
LABEL org.opencontainers.image.title="PerfSage JMeter Analyser" \
      org.opencontainers.image.description="AI-powered JMeter performance report analysis" \
      org.opencontainers.image.source="https://github.com/perfsage/jmeter-analyser" \
      org.opencontainers.image.version="${PERFSAGE_VERSION}" \
      org.opencontainers.image.vendor="PerfSage"

ENV REDIS_URL=redis://127.0.0.1:6379
ENV BROWSER_PATH=/usr/bin/chromium
ENV CHROME_PATH=/usr/bin/chromium

# Warm kaleido/choreographer as the runtime user so PDF chart export works on first request.
USER perfsage
RUN python -c "import plotly.graph_objects as go; go.Figure(data=[go.Scatter(x=[1], y=[1])]).write_image('/tmp/kaleido-warmup.png')"
USER root

EXPOSE 8000

VOLUME ["/app/data"]

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/perfsage.conf"]
