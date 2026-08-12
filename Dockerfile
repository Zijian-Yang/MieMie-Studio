FROM node:20-bookworm-slim AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend ./
RUN npm run build


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/opt/venv/bin:${PATH}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -r requirements.txt

COPY backend ./backend
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

EXPOSE 8000

CMD ["sh", "-c", "export MIEMIE_SERVE_FRONTEND=true; export MIEMIE_FRONTEND_PORT=${MIEMIE_FRONTEND_PORT:-3000}; export MIEMIE_RUNTIME_GIT_COMMIT=${MIEMIE_RUNTIME_GIT_COMMIT:-unknown}; export MIEMIE_RUNTIME_RUN_MODE=prod; export MIEMIE_RUNTIME_STARTED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ); exec /opt/venv/bin/gunicorn app.main:app -w ${MIEMIE_WORKERS:-2} -k uvicorn.workers.UvicornWorker --chdir /app/backend --bind 0.0.0.0:8000 --timeout 300 --graceful-timeout 30 --access-logfile - --error-logfile -"]
