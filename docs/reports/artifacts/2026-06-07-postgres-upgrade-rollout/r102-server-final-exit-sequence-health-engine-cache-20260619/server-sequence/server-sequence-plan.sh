set -Eeuo pipefail
cd /opt/miemie-pre
git rev-parse --abbrev-ref HEAD
git status --short
git fetch origin pre
git merge --ff-only origin/pre
test -f scripts/postgres_staging_video_task_sequence.sh
grep -q live-data-gate scripts/postgres_staging_video_task_sequence.sh
grep -q all-domain-dual-write-canary scripts/postgres_staging_video_task_sequence.sh
grep -q all-domain-read-switch-canary scripts/postgres_staging_video_task_sequence.sh
grep -q all-domain-rollback-read-switch scripts/postgres_staging_video_task_sequence.sh
grep -q all-domain-primary-write-canary scripts/postgres_staging_video_task_sequence.sh
grep -q all-domain-rollback-primary-write scripts/postgres_staging_video_task_sequence.sh
test -f scripts/postgres_staging_live_data_gate.sh
test -f scripts/postgres_staging_all_domain_canary.sh
python3 scripts/postgres_final_cutover_readiness.py --artifact-dir validation-artifacts/r102-server-final-exit-sequence-health-engine-cache-20260619/server-sequence/readiness-precheck --run-id r102-server-final-exit-sequence-health-engine-cache-20260619-server-sequence-readiness-precheck
grep -q ready_for_final_cutover_sequence validation-artifacts/r102-server-final-exit-sequence-health-engine-cache-20260619/server-sequence/readiness-precheck/status.json
CONFIRM_STAGING_SEQUENCE=run RUN_ID=r102-server-final-exit-sequence-health-engine-cache-20260619-server-sequence ARTIFACT_DIR=validation-artifacts/r102-server-final-exit-sequence-health-engine-cache-20260619/server-sequence/sequence TMP_DIR=/tmp/r102-server-final-exit-sequence-health-engine-cache-20260619/server-sequence/sequence bash scripts/postgres_staging_video_task_sequence.sh
