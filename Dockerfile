# ── Backend: FastAPI + Prophet ──────────────────────────────────────
FROM python:3.12-slim

# Prophet/cmdstanpy pull prebuilt wheels, but build-essential keeps any
# source-built transitive deps (e.g. holidays helpers) reliable.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install deps first for better layer caching.
COPY requirements.txt requirements-ml.txt ./
RUN pip install --no-cache-dir -r requirements-ml.txt

# App code (data/ and the DB live in a mounted volume, not the image).
COPY app ./app
COPY scripts ./scripts
COPY docker/entrypoint.sh ./docker/entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# Invoked via `sh` so Windows CRLF line endings can't break the shebang.
ENTRYPOINT ["sh", "/app/docker/entrypoint.sh"]
