# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# ePARS backend — FastAPI layer (modules/) on top of src/epars_agent and
# src/epars_policies (LangChain agent + pgvector/RAG policy retrieval).
#
# Multi-stage build:
#   1. "builder"  — installs build tooling + Python deps into a venv, so the
#                   final image never carries a C compiler or pip cache.
#   2. "runtime"  — copies just the venv + source into a slim image, runs as
#                   a non-root user, and exposes a container HEALTHCHECK.
#
# Build:  docker build -t epars-backend .
# Run:    docker run -p 8000:8000 --env-file .env epars-backend
#
# Local multi-container dev: docker compose up --build   (see docker-compose.yml)
#
#
# --- Render deployment -----------------------------------------------------
#
#   services:
#     - type: web
#       name: epars-backend
#       runtime: docker
#       dockerfilePath: ./Dockerfile
#       healthCheckPath: /health
#       envVars:
#         - key: DATABASE_URL
#           sync: false
#         - key: GROQ_API_KEY
#           sync: false
#         - key: FRONTEND_ORIGIN
#           value: https://<frontend-domain>
# -----------------------------------------------------------------------------

ARG PYTHON_VERSION=3.11-slim

# ---------------------------------------------------------------------------
# Stage 1: builder — compile/install dependencies into an isolated venv
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION} AS builder

# psycopg2 and some ML wheels (sentence-transformers deps) need a C toolchain
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Install deps first (better layer caching — only re-runs when requirements change)
COPY requirements.txt requirements.txt
COPY src/epars_agent/requirements.txt src/epars_agent/requirements.txt
COPY src/epars_policies/requirements.txt src/epars_policies/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------------------
# Stage 2: runtime — slim image with just the venv + application code
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION} AS runtime

# curl is used only by the HEALTHCHECK below
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system app && useradd --system --gid app --home-dir /app app

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY src/ src/
COPY modules/ modules/

RUN chown -R app:app /app
USER app

EXPOSE 8000

# $PORT is set by platforms like Render; falls back to 8000 locally
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f "http://localhost:${PORT:-8000}/health" || exit 1

CMD ["sh", "-c", "uvicorn modules.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
