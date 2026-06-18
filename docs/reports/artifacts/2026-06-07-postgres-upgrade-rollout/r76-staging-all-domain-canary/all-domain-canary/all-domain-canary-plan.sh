#!/usr/bin/env bash
set -Eeuo pipefail

# Planned all-domain provider-free canary. The real run is gated by CONFIRM_ALL_DOMAIN_CANARY=run.
# Domains: video_studio_tasks studio_tasks projects media_metadata project_entities benchmark_records user_config sessions audio_studio
MODE=all-domain-dual-write-canary CONFIRM_ALL_DOMAIN_CANARY=run bash scripts/postgres_staging_all_domain_canary.sh
MODE=all-domain-read-switch-canary CONFIRM_ALL_DOMAIN_CANARY=run bash scripts/postgres_staging_all_domain_canary.sh
MODE=all-domain-rollback-read-switch CONFIRM_ALL_DOMAIN_CANARY=run bash scripts/postgres_staging_all_domain_canary.sh
MODE=all-domain-primary-write-canary CONFIRM_ALL_DOMAIN_CANARY=run bash scripts/postgres_staging_all_domain_canary.sh
MODE=all-domain-rollback-primary-write CONFIRM_ALL_DOMAIN_CANARY=run bash scripts/postgres_staging_all_domain_canary.sh

# This canary runs inside the api container and uses StorageService, UserService, and ConfigManager.
# It never calls DashScope/OSS/provider generation APIs and never writes secrets to artifacts.
