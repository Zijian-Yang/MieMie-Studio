import json
from pathlib import Path

from app.models.audio_studio import AudioStudioTask, VoiceProfile
from app.services.migration.backfill_audio_studio import backfill_audio_studio
from app.services.migration.reconcile_audio_studio import (
    reconcile_audio_studio,
    render_reconcile_markdown,
)


class InMemoryAudioStudioRepository:
    def __init__(self):
        self.tasks = {}
        self.profiles = {}

    def save_task(self, task):
        self.tasks[task.id] = task

    def get_task(self, task_id):
        return self.tasks.get(task_id)

    def list_tasks_for_project(self, project_id):
        return [task for task in self.tasks.values() if task.project_id == project_id]

    def list_all_tasks(self):
        return list(self.tasks.values())

    def delete_task(self, task_id):
        self.tasks.pop(task_id, None)

    def mark_task_deleted(self, task_id):
        self.delete_task(task_id)

    def save_voice_profile(self, profile):
        self.profiles[profile.id] = profile

    def get_voice_profile(self, profile_id):
        return self.profiles.get(profile_id)

    def get_voice_profile_by_voice_id(self, voice_id):
        return next(
            (profile for profile in self.profiles.values() if profile.voice_id == voice_id),
            None,
        )

    def list_voice_profiles_for_project(self, project_id):
        return [profile for profile in self.profiles.values() if profile.project_id == project_id]

    def list_all_voice_profiles(self):
        return list(self.profiles.values())

    def delete_voice_profile(self, profile_id):
        self.profiles.pop(profile_id, None)

    def mark_voice_profile_deleted(self, profile_id):
        self.delete_voice_profile(profile_id)


def _write_json(path: Path, item) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(item.model_dump(mode="json"), ensure_ascii=False),
        encoding="utf-8",
    )


def _task(task_id: str, *, status: str = "succeeded") -> AudioStudioTask:
    return AudioStudioTask(
        id=task_id,
        project_id="project-1",
        task_type="voice_clone",
        name="Secret task name",
        text="SECRET-TTS-TEXT",
        voice="cosyvoice-secret",
        audio_url="https://oss.example.test/private-source.wav",
        voice_prompt="SECRET-VOICE-PROMPT",
        result_audio_url="https://oss.example.test/private-result.mp3",
        result_voice_id=f"voice-{task_id}",
        status=status,
    )


def _profile(profile_id: str, *, status: str = "ok") -> VoiceProfile:
    return VoiceProfile(
        id=profile_id,
        project_id="project-1",
        voice_id=f"voice-{profile_id}",
        name="Secret profile name",
        source="design",
        target_model="cosyvoice-v3-flash",
        prefix="demo",
        status=status,
        voice_prompt="SECRET-PROFILE-PROMPT",
        preview_text="SECRET-PREVIEW-TEXT",
        preview_audio_url="https://oss.example.test/private-preview.wav",
        audio_url="https://oss.example.test/private-input.wav",
    )


def test_backfill_audio_studio_upserts_tasks_and_voice_profiles(tmp_path):
    data_root = tmp_path / "data"
    user_dir = data_root / "users" / "user-1"
    task = _task("task-1")
    profile = _profile("profile-1")
    _write_json(user_dir / "audio_studio" / "task-1.json", task)
    _write_json(user_dir / "voices" / "profile-1.json", profile)
    (user_dir / "audio_studio" / "broken.json").write_text("{", encoding="utf-8")

    repos = {}

    def repository_factory(user_id):
        repos.setdefault(user_id, InMemoryAudioStudioRepository())
        return repos[user_id]

    summary = backfill_audio_studio(data_root, repository_factory)

    assert summary == {
        "domain": "audio_studio",
        "scanned_users": ["user-1"],
        "json_task_count": 1,
        "json_voice_profile_count": 1,
        "tasks_upserted_count": 1,
        "voice_profiles_upserted_count": 1,
        "failed_count": 1,
        "failures": [
            {
                "user_id": "user-1",
                "kind": "audio_studio_task",
                "file": "broken.json",
                "error": "JSONDecodeError",
            }
        ],
        "ok": False,
    }
    assert repos["user-1"].tasks["task-1"] == task
    assert repos["user-1"].profiles["profile-1"] == profile


def test_reconcile_audio_studio_reports_safe_task_and_voice_profile_drift(tmp_path):
    data_root = tmp_path / "data"
    user_dir = data_root / "users" / "user-1"
    _write_json(user_dir / "audio_studio" / "task-1.json", _task("task-1"))
    _write_json(user_dir / "voices" / "profile-1.json", _profile("profile-1"))

    repo = InMemoryAudioStudioRepository()
    repo.save_task(_task("task-1", status="failed"))
    repo.save_task(_task("task-extra"))
    repo.save_voice_profile(_profile("profile-1", status="deploying"))
    repo.save_voice_profile(_profile("profile-extra"))

    summary = reconcile_audio_studio(data_root, lambda user_id: repo)
    markdown = render_reconcile_markdown(summary)

    assert summary["domain"] == "audio_studio"
    assert summary["json_task_count"] == 1
    assert summary["postgres_task_count"] == 2
    assert summary["json_voice_profile_count"] == 1
    assert summary["postgres_voice_profile_count"] == 2
    assert summary["missing_in_json"] == [
        {"user_id": "user-1", "kind": "audio_studio_task", "id": "task-extra"},
        {"user_id": "user-1", "kind": "voice_profile", "id": "profile-extra"},
    ]
    assert {
        "user_id": "user-1",
        "kind": "audio_studio_task",
        "id": "task-1",
        "field": "status",
        "json": "succeeded",
        "postgres": "failed",
    } in summary["field_differences"]
    assert {
        "user_id": "user-1",
        "kind": "voice_profile",
        "id": "profile-1",
        "field": "status",
        "json": "ok",
        "postgres": "deploying",
    } in summary["field_differences"]
    assert summary["ok"] is False

    for private_value in (
        "SECRET-TTS-TEXT",
        "SECRET-VOICE-PROMPT",
        "SECRET-PROFILE-PROMPT",
        "SECRET-PREVIEW-TEXT",
        "private-result.mp3",
        "private-preview.wav",
    ):
        assert private_value not in json.dumps(summary, ensure_ascii=False)
        assert private_value not in markdown
