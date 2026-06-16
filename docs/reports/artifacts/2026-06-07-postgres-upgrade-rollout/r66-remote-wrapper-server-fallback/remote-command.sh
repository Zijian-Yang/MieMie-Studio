set -Eeuo pipefail
cd /opt/miemie-pre
git rev-parse --abbrev-ref HEAD
git status --short
git fetch origin pre
git merge --ff-only origin/pre
test -f scripts/pre_studio_server_postgres_sequence.sh
CONFIRM_SERVER_SEQUENCE=run SERVER_SYNC=none RUN_ID=r66-remote-wrapper-server-fallback-20260617 ARTIFACT_DIR=/opt/miemie-pre/validation-artifacts/r66-remote-wrapper-server-fallback-20260617 TMP_DIR=/tmp/r66-remote-wrapper-server-fallback-20260617 bash scripts/pre_studio_server_postgres_sequence.sh
