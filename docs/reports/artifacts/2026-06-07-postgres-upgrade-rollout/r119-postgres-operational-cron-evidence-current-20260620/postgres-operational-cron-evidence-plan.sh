#!/usr/bin/env bash
set -Eeuo pipefail

# Check the latest scheduled PostgreSQL operational cron evidence.
# Default mode only writes this plan. Execute the current check with:
# CONFIRM_POSTGRES_CRON_EVIDENCE=check bash scripts/postgres_operational_cron_evidence.sh
#
# Evidence roots:
# - operational readiness artifacts: validation-artifacts/postgres-ops-*
# - backup retention artifacts: validation-artifacts/postgres-backup-retention-*
#
# A state of "waiting" means no scheduled cron artifact is available yet.
# Set CRON_EVIDENCE_STRICT_WAIT=true when a CI/deploy gate should fail on waiting.
