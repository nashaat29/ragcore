# syntax=docker/dockerfile:1.5

# --- Builder Stage ---
FROM python:3.11-slim as builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
RUN pip install --upgrade pip && pip install --user -e .

# --- Final Stage ---
FROM python:3.11-slim as final

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/root/.local/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /root/.local /root/.local

COPY ragcore/ ./ragcore/
COPY pyproject.toml README.md ./

RUN pip install --no-deps -e .

RUN addgroup --system app && adduser --system --ingroup app app

RUN mkdir -p /app/rag_data && chown -R app:app /app/rag_data/indexes /app/rag_data/cache /app/rag_data/logs

ENV RAGCORE_DATA_DIR=/app/rag_data \
    RAGCORE_SERVER_HOST=0.0.0.0 \
    RAGCORE_SERVER_PORT=29000

USER app

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:29000/health/live || exit 1

EXPOSE 29000

VOLUME ["/app/rag_data"]

CMD ["uvicorn", "ragcore.api.server:create_app", "--host", "0.0.0.0", "--port", "29000", "--factory"]
