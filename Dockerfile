# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# ePARS backend — FastAPI layer (modules/) on top of src/epars_agent and
# src/epars_policies (LangChain agent + pgvector/RAG policy retrieval).
#
# Multi-stage build:
#   1. "builder"  — installs the API dependencies and downloads the pinned
#                   ONNX RAG encoder.
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
ARG RAG_MODEL_REVISION=1110a243fdf4706b3f48f1d95db1a4f5529b4d41

# ---------------------------------------------------------------------------
# Stage 1: builder — compile/install dependencies into an isolated venv
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION} AS builder
ARG RAG_MODEL_REVISION

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Install deps first (better layer caching — only re-runs when requirements change)
COPY requirements-runtime.txt requirements-runtime.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements-runtime.txt

# Fetch the matching FP32 ONNX encoder at build time. The runtime can answer RAG
# queries without importing PyTorch or downloading model weights on first use.
RUN python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='sentence-transformers/all-MiniLM-L6-v2', revision='${RAG_MODEL_REVISION}', allow_patterns=['onnx/model.onnx', 'tokenizer.json'], local_dir='/opt/rag_model')"

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
    PIP_NO_CACHE_DIR=1 \
    EPARS_RAG_MODEL_DIR=/opt/rag_model \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY src/epars_agent/agent/db.py src/epars_agent/agent/tools.py \
     src/epars_agent/agent/calendar_client.py src/epars_agent/agent/epars_agent.py \
     src/epars_agent/agent/burnout_monitor.py src/epars_agent/agent/burnout_api.py \
     /app/src/epars_agent/agent/
COPY src/epars_policies/rag_query.py /app/src/epars_policies/
COPY modules/ modules/
COPY ml_models/ ml_models/
COPY --from=builder /opt/rag_model /opt/rag_model

RUN chown -R app:app /app
USER app

EXPOSE 8000

# $PORT is set by platforms like Render; falls back to 8000 locally
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f "http://localhost:${PORT:-8000}/health" || exit 1

CMD ["sh", "-c", "uvicorn modules.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
