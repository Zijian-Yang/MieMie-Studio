set -Eeuo pipefail
cd /opt/miemie-pre
git rev-parse --abbrev-ref HEAD
git status --short
git fetch origin pre
git merge --ff-only origin/pre
test -f scripts/postgres_staging_video_task_sequence.sh
CONFIRM_STAGING_SEQUENCE=run RUN_ID=r53-remote-sequence-live-20260617 ARTIFACT_DIR=/opt/miemie-pre/validation-artifacts/r53-remote-sequence-live-20260617 TMP_DIR=/tmp/r53-remote-sequence-live-20260617 bash scripts/postgres_staging_video_task_sequence.sh
