set -Eeuo pipefail
cd /Users/zane/Project/Miemie-studio-ha-lab
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
python3 scripts/postgres_final_cutover_readiness.py --artifact-dir docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r78-server-fallback-all-domain-contract/readiness-precheck --run-id r78-server-fallback-all-domain-contract-20260618-readiness-precheck
grep -q ready_for_final_cutover_sequence docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r78-server-fallback-all-domain-contract/readiness-precheck/status.json
CONFIRM_STAGING_SEQUENCE=run RUN_ID=r78-server-fallback-all-domain-contract-20260618 ARTIFACT_DIR=docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r78-server-fallback-all-domain-contract/sequence TMP_DIR=/tmp/r78-server-fallback-all-domain-contract-20260618/sequence bash scripts/postgres_staging_video_task_sequence.sh
