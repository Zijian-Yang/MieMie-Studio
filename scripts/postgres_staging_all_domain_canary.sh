#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODE="${1:-${MODE:-all-domain-dual-write-canary}}"
RUN_ID="${RUN_ID:-postgres-staging-all-domain-canary-$(date +%Y%m%d%H%M%S)}"
ARTIFACT_DIR="${ARTIFACT_DIR:-$ROOT_DIR/docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r76-staging-all-domain-canary}"
TMP_DIR="${TMP_DIR:-/tmp/$RUN_ID}"
PROJECT_NAME="${PROJECT_NAME:-miemie-pre}"
ENV_FILE="${ENV_FILE:-compose.env}"
OVERRIDE_FILE="${OVERRIDE_FILE:-docker-compose.pre.override.yml}"
CONFIRM_ALL_DOMAIN_CANARY="${CONFIRM_ALL_DOMAIN_CANARY:-dry-run}"
ALL_DOMAINS="${ALL_DOMAINS:-video_studio_tasks studio_tasks projects media_metadata project_entities benchmark_records user_config sessions audio_studio}"

mkdir -p "$ARTIFACT_DIR" "$TMP_DIR"

STATUS_FILE="$ARTIFACT_DIR/status.json"
COMMAND_LOG="$ARTIFACT_DIR/commands.log"
PLAN_FILE="$ARTIFACT_DIR/all-domain-canary-plan.sh"
: > "$COMMAND_LOG"

if [[ -x "backend/.venv/bin/python" ]]; then
  JSON_PYTHON="backend/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  JSON_PYTHON="python3"
else
  JSON_PYTHON=""
fi

COMPOSE=(docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f "$OVERRIDE_FILE" -p "$PROJECT_NAME")

json_escape() {
  if [[ -n "$JSON_PYTHON" ]]; then
    printf '%s' "$1" | "$JSON_PYTHON" -c 'import json,sys; print(json.dumps(sys.stdin.read())[1:-1])'
  else
    printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
  fi
}

write_status() {
  local state="$1"
  local stage="$2"
  local reason="${3:-}"
  cat > "$STATUS_FILE" <<JSON
{
  "run_id": "$(json_escape "$RUN_ID")",
  "mode": "$(json_escape "$MODE")",
  "state": "$(json_escape "$state")",
  "stage": "$(json_escape "$stage")",
  "reason": "$(json_escape "$reason")",
  "domains": "$(json_escape "$ALL_DOMAINS")",
  "confirm": "$(json_escape "$CONFIRM_ALL_DOMAIN_CANARY")",
  "artifact_dir": "$(json_escape "$ARTIFACT_DIR")",
  "tmp_dir": "$(json_escape "$TMP_DIR")",
  "updated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
JSON
}

log_cmd() {
  local label="$1"
  shift
  {
    printf '\n## [%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$label"
    printf '+'
    printf ' %q' "$@"
    printf '\n'
  } >> "$COMMAND_LOG"
}

run_logged() {
  local label="$1"
  shift
  log_cmd "$label" "$@"
  "$@" >> "$COMMAND_LOG" 2>&1
}

blocked() {
  local stage="$1"
  local reason="$2"
  write_status "blocked" "$stage" "$reason"
  printf 'blocked: %s\n' "$reason" | tee -a "$COMMAND_LOG" >&2
  exit 2
}

failed() {
  local stage="$1"
  local reason="$2"
  write_status "failed" "$stage" "$reason"
  printf 'failed: %s\n' "$reason" | tee -a "$COMMAND_LOG" >&2
  exit 1
}

env_value() {
  local key="$1"
  if [[ ! -f "$ENV_FILE" ]]; then
    return 1
  fi
  grep -E "^${key}=" "$ENV_FILE" | tail -n 1 | cut -d= -f2- || true
}

set_env_value() {
  local key="$1"
  local value="$2"
  local tmp_file
  tmp_file="$(mktemp "$TMP_DIR/env.XXXXXX")"
  awk -v key="$key" -v value="$value" '
    BEGIN { found = 0 }
    $0 ~ "^" key "=" {
      print key "=" value
      found = 1
      next
    }
    { print }
    END {
      if (!found) {
        print key "=" value
      }
    }
  ' "$ENV_FILE" > "$tmp_file"
  cat "$tmp_file" > "$ENV_FILE"
  rm -f "$tmp_file"
}

redact_env_file() {
  local output="$1"
  if [[ ! -f "$ENV_FILE" ]]; then
    printf 'missing env file: %s\n' "$ENV_FILE" > "$output"
    return
  fi
  grep -E '^(MIEMIE_RUNTIME_GIT_COMMIT|MIEMIE_HOST|MIEMIE_WORKERS|MIEMIE_TASK|MIEMIE_VIDEO|MIEMIE_DATABASE|MIEMIE_POSTGRES)' "$ENV_FILE" \
    | sed -E \
      -e 's/(MIEMIE_POSTGRES_PASSWORD=).*/\1<redacted>/' \
      -e 's#(MIEMIE_DATABASE_URL=postgresql\+psycopg://miemie:)[^@]+#\1<redacted>#' \
    > "$output"
}

repo_head() {
  git rev-parse HEAD 2>/dev/null || printf unknown
}

host_port() {
  local value
  value="$(env_value MIEMIE_HOST_PORT || true)"
  printf '%s' "${value:-18100}"
}

base_url() {
  printf 'http://127.0.0.1:%s' "$(host_port)"
}

write_plan() {
  cat > "$PLAN_FILE" <<PLAN
#!/usr/bin/env bash
set -Eeuo pipefail

# Planned all-domain provider-free canary. The real run is gated by CONFIRM_ALL_DOMAIN_CANARY=run.
# Domains: $ALL_DOMAINS
MODE=all-domain-dual-write-canary CONFIRM_ALL_DOMAIN_CANARY=run bash scripts/postgres_staging_all_domain_canary.sh
MODE=all-domain-read-switch-canary CONFIRM_ALL_DOMAIN_CANARY=run bash scripts/postgres_staging_all_domain_canary.sh
MODE=all-domain-rollback-read-switch CONFIRM_ALL_DOMAIN_CANARY=run bash scripts/postgres_staging_all_domain_canary.sh
MODE=all-domain-primary-write-canary CONFIRM_ALL_DOMAIN_CANARY=run bash scripts/postgres_staging_all_domain_canary.sh
MODE=all-domain-rollback-primary-write CONFIRM_ALL_DOMAIN_CANARY=run bash scripts/postgres_staging_all_domain_canary.sh

# This canary runs inside the api container and uses StorageService, UserService, and ConfigManager.
# It never calls DashScope/OSS/provider generation APIs and never writes secrets to artifacts.
PLAN
}

ensure_preconditions() {
  [[ -f "$ENV_FILE" ]] || blocked "precheck" "missing $ENV_FILE"
  [[ -f docker-compose.yml ]] || blocked "precheck" "missing docker-compose.yml"
  [[ -f "$OVERRIDE_FILE" ]] || blocked "precheck" "missing $OVERRIDE_FILE"
  [[ -n "$JSON_PYTHON" ]] || blocked "precheck" "python3 unavailable"
  command -v docker >/dev/null 2>&1 || blocked "precheck" "docker CLI unavailable"
  docker info >/dev/null 2>"$ARTIFACT_DIR/docker-info.err" || blocked "precheck" "docker daemon unavailable; see docker-info.err"
  "${COMPOSE[@]}" version > "$ARTIFACT_DIR/docker-compose-version.txt" 2>&1 || blocked "precheck" "docker compose unavailable"
}

configure_mode() {
  set_env_value MIEMIE_RUNTIME_GIT_COMMIT "$(repo_head)"
  set_env_value MIEMIE_DATABASE_ENABLED true
  set_env_value MIEMIE_DATABASE_WRITE_MODE file
  set_env_value MIEMIE_DATABASE_READ_MODE file
  set_env_value MIEMIE_DATABASE_JSON_FALLBACK_READ true
  set_env_value MIEMIE_DATABASE_JSON_ARCHIVE_WRITES false
  set_env_value MIEMIE_DATABASE_RECONCILE_STRICT true

  case "$MODE" in
    all-domain-dual-write-canary)
      set_env_value MIEMIE_DATABASE_DUAL_WRITE_DOMAINS "$ALL_DOMAINS"
      set_env_value MIEMIE_DATABASE_READ_DOMAINS ""
      set_env_value MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS ""
      ;;
    all-domain-read-switch-canary)
      set_env_value MIEMIE_DATABASE_DUAL_WRITE_DOMAINS "$ALL_DOMAINS"
      set_env_value MIEMIE_DATABASE_READ_DOMAINS "$ALL_DOMAINS"
      set_env_value MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS ""
      ;;
    all-domain-rollback-read-switch)
      set_env_value MIEMIE_DATABASE_DUAL_WRITE_DOMAINS "$ALL_DOMAINS"
      set_env_value MIEMIE_DATABASE_READ_DOMAINS ""
      set_env_value MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS ""
      ;;
    all-domain-primary-write-canary)
      set_env_value MIEMIE_DATABASE_DUAL_WRITE_DOMAINS ""
      set_env_value MIEMIE_DATABASE_READ_DOMAINS "$ALL_DOMAINS"
      set_env_value MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS "$ALL_DOMAINS"
      ;;
    all-domain-rollback-primary-write)
      set_env_value MIEMIE_DATABASE_DUAL_WRITE_DOMAINS "$ALL_DOMAINS"
      set_env_value MIEMIE_DATABASE_READ_DOMAINS ""
      set_env_value MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS ""
      ;;
    *)
      blocked "precheck" "unsupported MODE=$MODE"
      ;;
  esac

  redact_env_file "$ARTIFACT_DIR/compose.env.$MODE.sanitized"
}

health_check() {
  local label="$1"
  local url
  url="$(base_url)/api/health"
  log_cmd "health-$label" curl -sS -D "$ARTIFACT_DIR/health-$label.headers" -o "$ARTIFACT_DIR/health-$label.json" "$url"
  curl -sS -D "$ARTIFACT_DIR/health-$label.headers" -o "$ARTIFACT_DIR/health-$label.json" --connect-timeout 10 --max-time 20 "$url" \
    >> "$COMMAND_LOG" 2>&1
}

wait_for_health() {
  local label="$1"
  local attempts="${2:-30}"
  for _ in $(seq 1 "$attempts"); do
    if health_check "$label"; then
      return 0
    fi
    sleep 2
  done
  return 1
}

roll_runtime_for_mode() {
  configure_mode
  run_logged "docker-compose-up-runtime-$MODE" "${COMPOSE[@]}" up -d api worker worker-video
  wait_for_health "$MODE" 45 || failed "health" "runtime did not become healthy for $MODE"
}

run_provider_free_canary() {
  log_cmd "provider-free-canary" "${COMPOSE[@]}" exec -T -e CANARY_MODE="$MODE" -e CANARY_RUN_ID="$RUN_ID" api /opt/venv/bin/python -
  "${COMPOSE[@]}" exec -T \
    -e CANARY_MODE="$MODE" \
    -e CANARY_RUN_ID="$RUN_ID" \
    api /opt/venv/bin/python - <<'PY' > "$ARTIFACT_DIR/provider-free-canary.json"
import json
import os
from datetime import datetime
from pathlib import Path

from app.config import AppConfig, ConfigManager
from app.models.audio_studio import AudioStudioTask, VoiceProfile
from app.models.character import Character
from app.models.frame import Frame
from app.models.gallery import GalleryImage
from app.models.image_benchmark import ImageBenchmarkDataset, ImageBenchmarkRun, ImageBenchmarkSuite
from app.models.media import AudioItem, TextItem, VideoItem, VideoStudioTask
from app.models.project import Project, Script, Shot
from app.models.prop import Prop
from app.models.scene import Scene
from app.models.studio import StudioTask
from app.models.style import Style
from app.models.video import TaskStatus, Video, VideoTask
from app.models.video_benchmark import VideoBenchmarkDataset, VideoBenchmarkRun, VideoBenchmarkSuite
from app.services.storage import get_user_storage, set_current_user
from app.services.user_service import UserService


mode = os.environ["CANARY_MODE"]
run_id = os.environ["CANARY_RUN_ID"].replace("/", "-")
safe_run_id = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in run_id)
username = f"canary_{safe_run_id[:40]}"
login_secret = "canary-pass-12345"


def assert_exists(label, value):
    if value is None:
        raise AssertionError(f"{label} was not readable after save")


def assert_missing(label, value):
    if value is not None:
        raise AssertionError(f"{label} was still readable after delete")


service = UserService()
registered = service.register(username, login_secret)
if registered is None:
    login_existing = service.login(username, login_secret)
    if login_existing is None:
        raise AssertionError("canary user registration/login failed")
    token, user = login_existing
else:
    login_result = service.login(username, login_secret)
    if login_result is None:
        raise AssertionError("canary user login failed after registration")
    token, user = login_result

set_current_user(user.id)
storage = get_user_storage(user.id)
project_id = f"project-{safe_run_id}"
shot_id = f"shot-{safe_run_id}"

project = Project(
    id=project_id,
    name=f"PostgreSQL all-domain canary {mode}",
    description="provider-free database canary",
    script=Script(
        title="canary script",
        shots=[
            Shot(
                id=shot_id,
                shot_number=1,
                dialogue="canary",
                duration=2.0,
            )
        ],
    ),
)
storage.save_project(project)
assert_exists("project", storage.get_project(project_id))

character = Character(id=f"character-{safe_run_id}", project_id=project_id, name="canary character")
scene = Scene(id=f"scene-{safe_run_id}", project_id=project_id, name="canary scene")
prop = Prop(id=f"prop-{safe_run_id}", project_id=project_id, name="canary prop")
frame = Frame(id=f"frame-{safe_run_id}", project_id=project_id, shot_id=shot_id, shot_number=1)
video = Video(
    id=f"video-{safe_run_id}",
    project_id=project_id,
    shot_id=shot_id,
    shot_number=1,
    first_frame_url="https://example.test/canary-frame.png",
    video_url="https://example.test/canary-video.mp4",
    task=VideoTask(task_id=f"provider-task-{safe_run_id}", status=TaskStatus.PROCESSING),
)
style = Style(id=f"style-{safe_run_id}", project_id=project_id, name="canary style", style_type="text")
for saver, getter, entity_id, entity in [
    (storage.save_character, storage.get_character, character.id, character),
    (storage.save_scene, storage.get_scene, scene.id, scene),
    (storage.save_prop, storage.get_prop, prop.id, prop),
    (storage.save_frame, storage.get_frame, frame.id, frame),
    (storage.save_video, storage.get_video, video.id, video),
    (storage.save_style, storage.get_style, style.id, style),
]:
    saver(entity)
    assert_exists(entity_id, getter(entity_id))

gallery = GalleryImage(id=f"gallery-{safe_run_id}", project_id=project_id, name="canary image", url="https://example.test/canary.png")
audio_item = AudioItem(id=f"audio-{safe_run_id}", project_id=project_id, name="canary audio", url="https://example.test/canary.mp3")
video_item = VideoItem(id=f"video-item-{safe_run_id}", project_id=project_id, name="canary video item", url="https://example.test/canary-library.mp4")
text_item = TextItem(id=f"text-{safe_run_id}", project_id=project_id, name="canary text", content="canary")
for saver, getter, entity_id, entity in [
    (storage.save_gallery_image, storage.get_gallery_image, gallery.id, gallery),
    (storage.save_audio_item, storage.get_audio_item, audio_item.id, audio_item),
    (storage.save_video_item, storage.get_video_item, video_item.id, video_item),
    (storage.save_text_item, storage.get_text_item, text_item.id, text_item),
]:
    saver(entity)
    assert_exists(entity_id, getter(entity_id))

studio_task = StudioTask(id=f"studio-task-{safe_run_id}", project_id=project_id, name="canary image task", prompt="provider-free canary")
video_task = VideoStudioTask(id=f"video-studio-task-{safe_run_id}", project_id=project_id, name="canary video task", task_type="text_to_video", prompt="provider-free canary")
audio_task = AudioStudioTask(id=f"audio-studio-task-{safe_run_id}", project_id=project_id, name="canary audio task", text="provider-free canary")
voice_profile = VoiceProfile(id=f"voice-profile-{safe_run_id}", project_id=project_id, voice_id=f"voice-{safe_run_id}", name="canary voice")
for saver, getter, entity_id, entity in [
    (storage.save_studio_task, storage.get_studio_task, studio_task.id, studio_task),
    (storage.save_video_studio_task, storage.get_video_studio_task, video_task.id, video_task),
    (storage.save_audio_studio_task, storage.get_audio_studio_task, audio_task.id, audio_task),
    (storage.save_voice_profile, storage.get_voice_profile, voice_profile.id, voice_profile),
]:
    saver(entity)
    assert_exists(entity_id, getter(entity_id))

image_dataset = ImageBenchmarkDataset(id=f"image-dataset-{safe_run_id}", project_id=project_id, name="canary image dataset", task_kind="text_to_image")
image_suite = ImageBenchmarkSuite(id=f"image-suite-{safe_run_id}", project_id=project_id, name="canary image suite", dataset_id=image_dataset.id, task_kind="text_to_image")
image_run = ImageBenchmarkRun(id=f"image-run-{safe_run_id}", project_id=project_id, suite_id=image_suite.id, dataset_id=image_dataset.id, task_kind="text_to_image")
video_dataset = VideoBenchmarkDataset(id=f"video-dataset-{safe_run_id}", project_id=project_id, name="canary video dataset")
video_suite = VideoBenchmarkSuite(id=f"video-suite-{safe_run_id}", project_id=project_id, name="canary video suite", dataset_id=video_dataset.id)
video_run = VideoBenchmarkRun(id=f"video-run-{safe_run_id}", project_id=project_id, suite_id=video_suite.id, dataset_id=video_dataset.id)
for saver, getter, entity_id, entity in [
    (storage.save_image_benchmark_dataset, storage.get_image_benchmark_dataset, image_dataset.id, image_dataset),
    (storage.save_image_benchmark_suite, storage.get_image_benchmark_suite, image_suite.id, image_suite),
    (storage.save_image_benchmark_run, storage.get_image_benchmark_run, image_run.id, image_run),
    (storage.save_video_benchmark_dataset, storage.get_video_benchmark_dataset, video_dataset.id, video_dataset),
    (storage.save_video_benchmark_suite, storage.get_video_benchmark_suite, video_suite.id, video_suite),
    (storage.save_video_benchmark_run, storage.get_video_benchmark_run, video_run.id, video_run),
]:
    saver(entity)
    assert_exists(entity_id, getter(entity_id))

config_manager = ConfigManager(str(Path("backend/data/users") / user.id))
config_manager.save(AppConfig(api_region="singapore"))
assert config_manager.load().api_region == "singapore"
assert service.get_user_by_token(token).id == user.id

delete_pairs = [
    (storage.delete_image_benchmark_run, storage.get_image_benchmark_run, image_run.id),
    (storage.delete_image_benchmark_suite, storage.get_image_benchmark_suite, image_suite.id),
    (storage.delete_image_benchmark_dataset, storage.get_image_benchmark_dataset, image_dataset.id),
    (storage.delete_video_benchmark_run, storage.get_video_benchmark_run, video_run.id),
    (storage.delete_video_benchmark_suite, storage.get_video_benchmark_suite, video_suite.id),
    (storage.delete_video_benchmark_dataset, storage.get_video_benchmark_dataset, video_dataset.id),
    (storage.delete_voice_profile, storage.get_voice_profile, voice_profile.id),
    (storage.delete_audio_studio_task, storage.get_audio_studio_task, audio_task.id),
    (storage.delete_video_studio_task, storage.get_video_studio_task, video_task.id),
    (storage.delete_studio_task, storage.get_studio_task, studio_task.id),
    (storage.delete_text_item, storage.get_text_item, text_item.id),
    (storage.delete_video_item, storage.get_video_item, video_item.id),
    (storage.delete_audio_item, storage.get_audio_item, audio_item.id),
    (storage.delete_gallery_image, storage.get_gallery_image, gallery.id),
    (storage.delete_style, storage.get_style, style.id),
    (storage.delete_video, storage.get_video, video.id),
    (storage.delete_frame, storage.get_frame, frame.id),
    (storage.delete_prop, storage.get_prop, prop.id),
    (storage.delete_scene, storage.get_scene, scene.id),
    (storage.delete_character, storage.get_character, character.id),
    (storage.delete_project, storage.get_project, project_id),
]
for deleter, getter, entity_id in delete_pairs:
    deleter(entity_id)
    assert_missing(entity_id, getter(entity_id))

service.logout(token)
set_current_user(None)

print(json.dumps({
    "ok": True,
    "mode": mode,
    "user_id": user.id,
    "project_id": project_id,
    "domains": [
        "video_studio_tasks",
        "studio_tasks",
        "projects",
        "media_metadata",
        "project_entities",
        "benchmark_records",
        "user_config",
        "sessions",
        "audio_studio",
    ],
    "provider_calls": 0,
    "checked_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
}, ensure_ascii=False))
PY
}

main() {
  write_plan
  if [[ "$CONFIRM_ALL_DOMAIN_CANARY" != "run" ]]; then
    write_status "dry_run" "planned" "set CONFIRM_ALL_DOMAIN_CANARY=run to execute"
    printf 'dry-run all-domain canary plan written to %s\n' "$PLAN_FILE"
    exit 0
  fi

  ensure_preconditions
  write_status "running" "configure-$MODE" ""
  roll_runtime_for_mode
  write_status "running" "provider-free-canary" ""
  run_provider_free_canary || failed "provider-free-canary" "all-domain provider-free canary failed"
  write_status "passed" "done" ""
}

main "$@"
