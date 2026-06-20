#!/usr/bin/env bash
set -Eeuo pipefail

# PostgreSQL-only operational readiness gate.
# Default mode is dry-run. Execute checks with:
# CONFIRM_POSTGRES_OPERATIONAL_READINESS=run bash scripts/postgres_operational_readiness.sh
#
# To create a fresh dump and restore it into an isolated rehearsal database:
# CONFIRM_POSTGRES_OPERATIONAL_READINESS=run POSTGRES_OPS_BACKUP_RESTORE=run bash scripts/postgres_operational_readiness.sh

# Checks:
# - compose.env keeps final PostgreSQL-only policy:
#   MIEMIE_DATABASE_ENABLED=true
#   MIEMIE_DATABASE_WRITE_MODE=postgres
#   MIEMIE_DATABASE_READ_MODE=postgres
#   MIEMIE_DATABASE_JSON_FALLBACK_READ=false
#   MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=false
#   MIEMIE_DATABASE_RECONCILE_STRICT=true
# - local and public /api/health report status=ok and database.ok=true
# - Compose containers are visible and Docker stats can be collected
# - remaining JSON outside quarantine exactly matches: backend/data/config.example.json
# - a fresh PostgreSQL backup exists, or POSTGRES_OPS_BACKUP_RESTORE=run creates and restores one
