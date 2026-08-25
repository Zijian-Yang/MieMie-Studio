FROM node:20-bookworm-slim@sha256:2cf067cfed83d5ea958367df9f966191a942351a2df77d6f0193e162b5febfc0 AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend ./
RUN npm run build


FROM python:3.12-slim-bookworm@sha256:b64e9d3a71eddaa1b3f80c04abf292b3139e3b7c4dd272d19c31dc1f91194d1b AS runtime

ARG POSTGRESQL_CLIENT_MAJOR=16

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/opt/venv/bin:${PATH}" \
    HOME="/tmp"

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg postgresql-client-${POSTGRESQL_CLIENT_MAJOR} \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 miemie \
    && useradd --uid 10001 --gid 10001 --no-create-home --home-dir /tmp --shell /usr/sbin/nologin miemie

WORKDIR /app

COPY requirements.txt requirements.lock.txt ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -r requirements.lock.txt

COPY backend ./backend
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

RUN install -d -o 10001 -g 10001 \
      /app/backend/data \
      /app/backend/logs \
      /var/lib/miemie/backups \
    && chown -R 10001:10001 /app/backend /app/frontend /opt/venv

USER 10001:10001

EXPOSE 8000

CMD ["sh", "-c", "export MIEMIE_SERVE_FRONTEND=true; export MIEMIE_FRONTEND_PORT=${MIEMIE_FRONTEND_PORT:-3000}; export MIEMIE_RUNTIME_GIT_COMMIT=${MIEMIE_RUNTIME_GIT_COMMIT:-unknown}; export MIEMIE_RUNTIME_RUN_MODE=prod; export MIEMIE_RUNTIME_STARTED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ); exec /opt/venv/bin/gunicorn app.main:app -w ${MIEMIE_WORKERS:-2} -k uvicorn.workers.UvicornWorker --chdir /app/backend --bind 0.0.0.0:8000 --timeout 300 --graceful-timeout 30 --access-logfile - --error-logfile -"]
