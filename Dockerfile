# ePARS backend — FastAPI layer (modules/) + src/epars_agent + src/epars_policies
#
# Build:  docker build -t epars-backend .
# Run:    docker run -p 8000:8000 --env-file .env -v "$(pwd)/src/epars_agent/agent/sa_key.json:/app/src/epars_agent/agent/sa_key.json:ro" epars-backend
#
# Secrets are NOT baked into the image:
#   - .env (DATABASE_URL, GROQ_API_KEY, FRONTEND_ORIGIN) -> pass via --env-file or your
#     platform's env var settings (Render, etc.)
#   - sa_key.json (Google Calendar service account) -> mount at runtime if calendar
#     features are needed; the app runs fine without it for the /performance and
#     /agent routes that don't touch calendar tools.

FROM python:3.11-slim

WORKDIR /app

# psycopg2 and some ML wheels need a C toolchain on slim images
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install deps first (better layer caching — only re-runs when requirements change)
COPY requirements.txt requirements.txt
COPY src/epars_agent/requirements.txt src/epars_agent/requirements.txt
COPY src/epars_policies/requirements.txt src/epars_policies/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY modules/ modules/

EXPOSE 8000

# $PORT is set by platforms like Render; falls back to 8000 locally
CMD ["sh", "-c", "uvicorn modules.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
