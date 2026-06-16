set -Eeuo pipefail
cd /Users/zane/Project/Miemie-studio-ha-lab
git rev-parse --abbrev-ref HEAD
git status --short
git fetch origin pre
git merge --ff-only origin/pre
test -f scripts/postgres_staging_video_task_sequence.sh
CONFIRM_STAGING_SEQUENCE=run RUN_ID=r58-server-self-sequence-wrapper-20260617 ARTIFACT_DIR=docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r58-server-self-sequence-wrapper/sequence TMP_DIR=/tmp/r58-server-self-sequence-wrapper-20260617/sequence bash scripts/postgres_staging_video_task_sequence.sh
