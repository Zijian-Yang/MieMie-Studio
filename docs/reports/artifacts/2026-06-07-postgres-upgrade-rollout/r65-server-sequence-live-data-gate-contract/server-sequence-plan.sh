set -Eeuo pipefail
cd /Users/zane/Project/Miemie-studio-ha-lab
git rev-parse --abbrev-ref HEAD
git status --short
git fetch origin pre
git merge --ff-only origin/pre
test -f scripts/postgres_staging_video_task_sequence.sh
grep -q live-data-gate scripts/postgres_staging_video_task_sequence.sh
test -f scripts/postgres_staging_live_data_gate.sh
CONFIRM_STAGING_SEQUENCE=run RUN_ID=r65-server-sequence-dry-run-20260617 ARTIFACT_DIR=docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r65-server-sequence-live-data-gate-contract/sequence TMP_DIR=/tmp/r65-server-sequence-dry-run-20260617/sequence bash scripts/postgres_staging_video_task_sequence.sh
