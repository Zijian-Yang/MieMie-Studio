set -Eeuo pipefail
cd /opt/miemie-pre
git rev-parse --abbrev-ref HEAD
git status --short
git fetch origin pre
git merge --ff-only origin/pre
test -f scripts/pre_studio_server_postgres_final_exit_sequence.sh
CONFIRM_SERVER_FINAL_EXIT_SEQUENCE=run SERVER_SYNC=none FINAL_EXIT_ROLLBACK_ON_FAILURE=true RUN_ID=r85-remote-final-exit-sequence ARTIFACT_DIR=/opt/miemie-pre/validation-artifacts/r85-remote-final-exit-sequence TMP_DIR=/tmp/r85-remote-final-exit-sequence bash scripts/pre_studio_server_postgres_final_exit_sequence.sh
