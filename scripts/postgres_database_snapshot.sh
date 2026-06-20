#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_ID="${RUN_ID:-postgres-database-snapshot-$(date +%Y%m%d%H%M%S)}"
ARTIFACT_DIR="${ARTIFACT_DIR:-$ROOT_DIR/docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r120-postgres-database-snapshot}"
CONFIRM_POSTGRES_DATABASE_SNAPSHOT="${CONFIRM_POSTGRES_DATABASE_SNAPSHOT:-dry-run}"
POSTGRES_OPS_TRIGGER="${POSTGRES_OPS_TRIGGER:-manual}"
PROJECT_NAME="${PROJECT_NAME:-miemie-pre}"
ENV_FILE="${ENV_FILE:-compose.env}"
COMPOSE_FILE_1="${COMPOSE_FILE_1:-docker-compose.yml}"
COMPOSE_FILE_2="${COMPOSE_FILE_2:-docker-compose.pre.override.yml}"
LONG_TRANSACTION_SECONDS="${LONG_TRANSACTION_SECONDS:-300}"
DEAD_TUPLE_WARN_RATIO="${DEAD_TUPLE_WARN_RATIO:-0.2}"
DEAD_TUPLE_WARN_MIN="${DEAD_TUPLE_WARN_MIN:-1000}"
CONNECTION_WARN_RATIO="${CONNECTION_WARN_RATIO:-0.7}"

mkdir -p "$ARTIFACT_DIR"

STATUS_FILE="$ARTIFACT_DIR/status.json"
PLAN_FILE="$ARTIFACT_DIR/postgres-database-snapshot-plan.sh"
COMMAND_LOG="$ARTIFACT_DIR/commands.log"
: > "$COMMAND_LOG"

if [[ -x "backend/.venv/bin/python" ]]; then
  PYTHON_BIN="backend/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "python3 missing" >&2
  exit 2
fi

compose_cmd=(docker compose -p "$PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE_1")
if [[ -f "$COMPOSE_FILE_2" ]]; then
  compose_cmd+=(-f "$COMPOSE_FILE_2")
fi

json_status() {
  local state="$1"
  local stage="$2"
  local reason="${3:-}"
  "$PYTHON_BIN" - "$STATUS_FILE" "$RUN_ID" "$state" "$stage" "$reason" "$ARTIFACT_DIR" <<'PY'
import json
import os
import sys
import time
from pathlib import Path

status_file = Path(sys.argv[1])
payload = {
    "run_id": sys.argv[2],
    "state": sys.argv[3],
    "stage": sys.argv[4],
    "reason": sys.argv[5],
    "trigger": os.environ.get("POSTGRES_OPS_TRIGGER", "manual"),
    "artifact_dir": sys.argv[6],
    "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}
status_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
}

write_plan() {
  cat > "$PLAN_FILE" <<PLAN
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
# - long transaction counts over ${LONG_TRANSACTION_SECONDS}s
#
# Execute:
# CONFIRM_POSTGRES_DATABASE_SNAPSHOT=run bash scripts/postgres_database_snapshot.sh
PLAN
}

run_sql() {
  local name="$1"
  local sql="$2"
  local output="$ARTIFACT_DIR/${name}.csv"
  {
    printf '\n## [%s] query:%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$name"
    printf '%s\n' "$sql"
  } >> "$COMMAND_LOG"
  printf '%s\n' "$sql" | "${compose_cmd[@]}" exec -T postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -X -q --csv -v ON_ERROR_STOP=1' > "$output"
}

collect_snapshot() {
  run_sql "database_overview" "
select
  now() at time zone 'utc' as snapshot_utc,
  current_database() as database_name,
  current_setting('server_version') as server_version,
  pg_database_size(current_database()) as database_size_bytes,
  pg_size_pretty(pg_database_size(current_database())) as database_size_pretty,
  current_setting('max_connections')::int as max_connections;
"

  run_sql "expected_tables" "
with expected(name) as (
  values
    ('video_studio_tasks'),
    ('studio_tasks'),
    ('projects'),
    ('media_assets'),
    ('text_items'),
    ('project_entities'),
    ('benchmark_records'),
    ('users'),
    ('user_configs'),
    ('sessions'),
    ('audio_studio_tasks'),
    ('voice_profiles')
)
select
  name,
  to_regclass('public.' || name) is not null as present
from expected
order by name;
"

  run_sql "alembic_version" "
select
  case when to_regclass('public.alembic_version') is null then '' else (select version_num from alembic_version limit 1) end as version_num;
"

  run_sql "table_stats" "
select
  schemaname,
  relname,
  n_live_tup,
  n_dead_tup,
  case when n_live_tup > 0 then round(n_dead_tup::numeric / n_live_tup::numeric, 6) else 0 end as dead_tuple_ratio,
  coalesce(last_vacuum::text, '') as last_vacuum,
  coalesce(last_autovacuum::text, '') as last_autovacuum,
  coalesce(last_analyze::text, '') as last_analyze,
  coalesce(last_autoanalyze::text, '') as last_autoanalyze
from pg_stat_user_tables
order by relname;
"

  run_sql "relation_sizes" "
select
  relname,
  pg_total_relation_size(relid) as total_bytes,
  pg_relation_size(relid) as table_bytes,
  pg_indexes_size(relid) as index_bytes,
  pg_size_pretty(pg_total_relation_size(relid)) as total_pretty
from pg_catalog.pg_statio_user_tables
order by pg_total_relation_size(relid) desc, relname;
"

  run_sql "index_usage" "
select
  schemaname,
  relname,
  indexrelname,
  idx_scan,
  idx_tup_read,
  idx_tup_fetch
from pg_stat_user_indexes
order by relname, indexrelname;
"

  run_sql "connections" "
select
  coalesce(state, 'none') as state,
  count(*) as connection_count
from pg_stat_activity
where datname = current_database()
group by coalesce(state, 'none')
order by connection_count desc, state;
"

  run_sql "long_transactions" "
select
  count(*) as long_transaction_count
from pg_stat_activity
where datname = current_database()
  and xact_start is not null
  and now() - xact_start > interval '${LONG_TRANSACTION_SECONDS} seconds';
"

  run_sql "waiting_locks" "
select
  count(*) as waiting_lock_count
from pg_locks
where not granted;
"
}

analyze_snapshot() {
  "$PYTHON_BIN" - "$ARTIFACT_DIR" "$STATUS_FILE" "$RUN_ID" "$LONG_TRANSACTION_SECONDS" "$DEAD_TUPLE_WARN_RATIO" "$DEAD_TUPLE_WARN_MIN" "$CONNECTION_WARN_RATIO" <<'PY'
from __future__ import annotations

import csv
import json
import os
import sys
import time
from pathlib import Path

artifact_dir = Path(sys.argv[1])
status_file = Path(sys.argv[2])
run_id = sys.argv[3]
long_transaction_seconds = int(float(sys.argv[4]))
dead_tuple_warn_ratio = float(sys.argv[5])
dead_tuple_warn_min = int(float(sys.argv[6]))
connection_warn_ratio = float(sys.argv[7])


def read_csv(name: str) -> list[dict[str, str]]:
    path = artifact_dir / f"{name}.csv"
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


blocked: list[str] = []
warnings: list[str] = []

overview = read_csv("database_overview")
max_connections = int(overview[0].get("max_connections") or 0) if overview else 0
database_size_bytes = int(overview[0].get("database_size_bytes") or 0) if overview else 0

expected_tables = read_csv("expected_tables")
missing_tables = [row["name"] for row in expected_tables if row.get("present", "").lower() != "t"]
if missing_tables:
    blocked.append("missing expected tables: " + ", ".join(missing_tables))

connections = read_csv("connections")
total_connections = sum(int(row.get("connection_count") or 0) for row in connections)
if max_connections and total_connections / max_connections >= connection_warn_ratio:
    warnings.append(f"connections {total_connections}/{max_connections} exceed warn ratio {connection_warn_ratio}")

long_transactions = read_csv("long_transactions")
long_transaction_count = int(long_transactions[0].get("long_transaction_count") or 0) if long_transactions else 0
if long_transaction_count:
    blocked.append(f"{long_transaction_count} transactions older than {long_transaction_seconds}s")

waiting_locks = read_csv("waiting_locks")
waiting_lock_count = int(waiting_locks[0].get("waiting_lock_count") or 0) if waiting_locks else 0
if waiting_lock_count:
    blocked.append(f"{waiting_lock_count} waiting locks")

table_stats = read_csv("table_stats")
dead_tuple_warnings = []
for row in table_stats:
    ratio = float(row.get("dead_tuple_ratio") or 0)
    dead = int(float(row.get("n_dead_tup") or 0))
    if dead >= dead_tuple_warn_min and ratio >= dead_tuple_warn_ratio:
        dead_tuple_warnings.append(f"{row.get('relname')} dead={dead} ratio={ratio}")
if dead_tuple_warnings:
    warnings.append("dead tuple warning: " + "; ".join(dead_tuple_warnings[:10]))

state = "blocked" if blocked else "passed_with_warnings" if warnings else "passed"
reason = "; ".join(blocked or warnings)
summary = {
    "run_id": run_id,
    "state": state,
    "stage": "done",
    "reason": reason,
    "trigger": os.environ.get("POSTGRES_OPS_TRIGGER", "manual"),
    "artifact_dir": str(artifact_dir),
    "database_size_bytes": database_size_bytes,
    "max_connections": max_connections,
    "total_connections": total_connections,
    "long_transaction_count": long_transaction_count,
    "waiting_lock_count": waiting_lock_count,
    "missing_tables": missing_tables,
    "warnings": warnings,
    "thresholds": {
        "long_transaction_seconds": long_transaction_seconds,
        "dead_tuple_warn_ratio": dead_tuple_warn_ratio,
        "dead_tuple_warn_min": dead_tuple_warn_min,
        "connection_warn_ratio": connection_warn_ratio,
    },
    "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}
status_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

(artifact_dir / "database-snapshot-summary.md").write_text(
    "\n".join(
        [
            "# PostgreSQL Database Snapshot",
            "",
            f"- State: `{state}`",
            f"- Reason: {reason or '-'}",
            f"- Database size bytes: `{database_size_bytes}`",
            f"- Connections: `{total_connections}/{max_connections}`",
            f"- Long transactions: `{long_transaction_count}`",
            f"- Waiting locks: `{waiting_lock_count}`",
            f"- Missing expected tables: `{', '.join(missing_tables) if missing_tables else '-'}`",
            f"- Warnings: `{'; '.join(warnings) if warnings else '-'}`",
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps(summary, ensure_ascii=False, indent=2))
raise SystemExit(2 if blocked else 0)
PY
}

write_plan

if [[ "$CONFIRM_POSTGRES_DATABASE_SNAPSHOT" != "run" ]]; then
  json_status "dry_run" "planned" "set CONFIRM_POSTGRES_DATABASE_SNAPSHOT=run to collect read-only database snapshot"
  printf 'dry-run database snapshot plan written to %s\n' "$PLAN_FILE"
  exit 0
fi

collect_snapshot
analyze_snapshot
