#!/usr/bin/env bash
set -Eeuo pipefail

# PostgreSQL database snapshot is read-only.
# It collects:
# - database size and Postgres version
# - expected table presence
# - table estimates and dead tuple ratios from pg_stat_user_tables
# - table and index sizes
# - connection counts from pg_stat_activity
# - waiting lock counts from pg_locks
# - long transaction counts over 300s
#
# Execute:
# CONFIRM_POSTGRES_DATABASE_SNAPSHOT=run bash scripts/postgres_database_snapshot.sh
