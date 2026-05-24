# ─── builder ──────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpango-1.0-0 libpangoft2-1.0-0 libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY perfsage/ perfsage/

RUN pip install --upgrade pip && \
    pip install --prefix=/install . && \
    pip install --prefix=/install uvicorn[standard]

# ─── runtime ──────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangoft2-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN useradd --uid 1000 --create-home perfsage
WORKDIR /app

COPY --from=builder /install /usr/local
COPY --chown=perfsage:perfsage perfsage/ perfsage/

USER perfsage

EXPOSE 8000

CMD ["uvicorn", "perfsage.main:app", "--host", "0.0.0.0", "--port", "8000"]
