#!/usr/bin/env bash
set -Eeuo pipefail

# PostgreSQL operational cron sequence gate.
# Default mode is dry-run. Execute the cron-equivalent sequence with:
# CONFIRM_POSTGRES_CRON_SEQUENCE=run bash scripts/postgres_operational_cron_sequence.sh
#
# Sequence:
# 1. Run operational readiness with fresh backup and restore rehearsal.
# 2. Run backup retention prune with RETENTION_DAYS=14 and MIN_KEEP=3.
# 3. Run read-only database snapshot.
# 4. Run cron evidence gate with CRON_EVIDENCE_STRICT_WAIT=true and CRON_EVIDENCE_NOT_BEFORE
#    set to the sequence start time, so only fresh artifacts from this sequence pass.
#    Sequence artifacts use POSTGRES_OPS_TRIGGER=manual_sequence and the evidence gate
#    requires CRON_EVIDENCE_REQUIRED_TRIGGER=manual_sequence.
#
# Optional local alert env:
# - If ALERT_ENV_FILE exists during run mode, it is sourced before subcommands.
# - The env file path is recorded, but its contents are never copied into artifacts.
