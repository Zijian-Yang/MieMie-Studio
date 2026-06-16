from datetime import datetime, timedelta

from app.models.audio_studio import AudioStudioTask, VoiceProfile
from app.repositories.audio_studio import (
    DualAudioStudioRepository,
    FileAudioStudioRepository,
    audio_studio_task_to_row,
    row_to_audio_studio_task,
    row_to_voice_profile,
    voice_profile_to_row,
)
from app.repositories.base import RepositoryWriteError
from app.services.storage import StorageService


def _task(task_id: str, project_id: str = "project-1", **overrides) -> AudioStudioTask:
    base = {
        "id": task_id,
        "project_id": project_id,
        "task_type": "voice_clone",
        "name": f"task {task_id}",
        "text": "hello",
        "voice": "cosyvoice-demo",
        "format": "mp3_22050hz_mono_256kbps",
        "volume": 60,
        "speech_rate": 1.1,
        "pitch_rate": 0.9,
        "audio_url": "https://oss.example.test/sample.wav",
        "prefix": "abc123",
        "result_audio_url": "https://oss.example.test/result.mp3",
        "result_voice_id": "voice-custom-1",
        "audio_duration": 3.25,
        "saved_to_library": True,
        "markers": ["star", "check"],
        "status": "succeeded",
        "error_message": None,
        "request_id": "request-1",
        "created_at": datetime(2026, 6, 17, 8, 0, 0),
        "updated_at": datetime(2026, 6, 17, 8, 5, 0),
    }
    base.update(overrides)
    return AudioStudioTask(**base)


def _profile(profile_id: str, project_id: str = "project-1", **overrides) -> VoiceProfile:
    base = {
        "id": profile_id,
        "project_id": project_id,
        "voice_id": f"voice-{profile_id}",
        "name": f"profile {profile_id}",
        "source": "clone",
        "target_model": "cosyvoice-v3-flash",
        "prefix": "abc123",
        "status": "ok",
        "voice_prompt": "warm narrator",
        "preview_text": "preview",
        "preview_audio_url": "https://oss.example.test/preview.wav",
        "audio_url": "https://oss.example.test/sample.wav",
        "created_at": datetime(2026, 6, 17, 8, 10, 0),
        "updated_at": datetime(2026, 6, 17, 8, 15, 0),
    }
    base.update(overrides)
    return VoiceProfile(**base)


def test_file_audio_studio_repository_preserves_storage_behavior(tmp_path):
    storage = StorageService(str(tmp_path))
    repo = FileAudioStudioRepository(storage)
    older = _task(
        "older",
        created_at=datetime.now() - timedelta(days=2),
        updated_at=datetime.now() - timedelta(days=2),
    )
    newer = _task("newer", created_at=datetime.now(), updated_at=datetime.now())
    other_project = _task(
        "other",
        project_id="project-2",
        created_at=datetime.now() - timedelta(hours=1),
        updated_at=datetime.now(),
    )
    profile = _profile("profile-1", voice_id="voice-lookup")

    repo.save_task(older)
    repo.save_task(newer)
    repo.save_task(other_project)
    repo.save_voice_profile(profile)

    assert repo.get_task("older").id == "older"
    assert repo.get_task("missing") is None
    assert [task.id for task in repo.list_tasks_for_project("project-1")] == ["newer", "older"]
    assert [task.id for task in repo.list_all_tasks()] == ["newer", "other", "older"]
    assert repo.get_voice_profile("profile-1") == profile
    assert repo.get_voice_profile_by_voice_id("voice-lookup") == profile
    assert [item.id for item in repo.list_voice_profiles_for_project("project-1")] == ["profile-1"]

    repo.delete_task("older")
    repo.delete_voice_profile("profile-1")

    assert repo.get_task("older") is None
    assert repo.get_voice_profile("profile-1") is None


def test_audio_studio_row_mapping_keeps_index_columns_and_raw_snapshot():
    task = _task("task-1")

    row = audio_studio_task_to_row("user-1", task)

    assert row["id"] == "task-1"
    assert row["user_id"] == "user-1"
    assert row["project_id"] == "project-1"
    assert row["task_type"] == "voice_clone"
    assert row["status"] == "succeeded"
    assert row["voice"] == "cosyvoice-demo"
    assert row["result_voice_id"] == "voice-custom-1"
    assert row["saved_to_library"] is True
    assert row["markers"] == ["star", "check"]
    assert row["raw_task_snapshot"]["id"] == "task-1"
    assert row["raw_task_snapshot"]["created_at"] == "2026-06-17T08:00:00"

    restored = row_to_audio_studio_task(row)

    assert restored == task


def test_voice_profile_row_mapping_keeps_voice_lookup_columns_and_snapshot():
    profile = _profile("profile-1")

    row = voice_profile_to_row("user-1", profile)

    assert row["id"] == "profile-1"
    assert row["user_id"] == "user-1"
    assert row["project_id"] == "project-1"
    assert row["voice_id"] == "voice-profile-1"
    assert row["source"] == "clone"
    assert row["target_model"] == "cosyvoice-v3-flash"
    assert row["prefix"] == "abc123"
    assert row["status"] == "ok"
    assert row["raw_profile_snapshot"]["id"] == "profile-1"
    assert row["raw_profile_snapshot"]["voice_id"] == "voice-profile-1"

    restored = row_to_voice_profile(row)

    assert restored == profile


class _RecordingAudioRepository:
    def __init__(self, *, fail_on_save: bool = False):
        self.fail_on_save = fail_on_save
        self.saved_tasks = []
        self.saved_profiles = []
        self.deleted_tasks = []
        self.deleted_profiles = []
        self.tasks = {}
        self.profiles = {}

    def save_task(self, task):
        if self.fail_on_save:
            raise RepositoryWriteError("postgres unavailable")
        self.saved_tasks.append(task.id)
        self.tasks[task.id] = task

    def get_task(self, task_id):
        return self.tasks.get(task_id)

    def list_tasks_for_project(self, project_id):
        return [task for task in self.tasks.values() if task.project_id == project_id]

    def list_all_tasks(self):
        return list(self.tasks.values())

    def delete_task(self, task_id):
        self.deleted_tasks.append(task_id)
        self.tasks.pop(task_id, None)

    def mark_task_deleted(self, task_id):
        self.delete_task(task_id)

    def save_voice_profile(self, profile):
        if self.fail_on_save:
            raise RepositoryWriteError("postgres unavailable")
        self.saved_profiles.append(profile.id)
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
        self.deleted_profiles.append(profile_id)
        self.profiles.pop(profile_id, None)

    def mark_voice_profile_deleted(self, profile_id):
        self.delete_voice_profile(profile_id)


def test_dual_audio_studio_repository_saves_file_first_and_tolerates_shadow_failure():
    primary = _RecordingAudioRepository()
    shadow = _RecordingAudioRepository(fail_on_save=True)
    repo = DualAudioStudioRepository(primary, shadow, strict_shadow_writes=False)
    task = _task("task-1")
    profile = _profile("profile-1")

    repo.save_task(task)
    repo.save_voice_profile(profile)

    assert primary.saved_tasks == ["task-1"]
    assert primary.saved_profiles == ["profile-1"]
    assert shadow.saved_tasks == []
    assert shadow.saved_profiles == []
    assert repo.get_task("task-1") == task
    assert repo.get_voice_profile("profile-1") == profile


def test_dual_audio_studio_repository_can_enforce_strict_shadow_writes():
    primary = _RecordingAudioRepository()
    shadow = _RecordingAudioRepository(fail_on_save=True)
    repo = DualAudioStudioRepository(primary, shadow, strict_shadow_writes=True)

    try:
        repo.save_task(_task("task-1"))
    except RepositoryWriteError as exc:
        assert "postgres unavailable" in str(exc)
    else:
        raise AssertionError("strict dual write should propagate PostgreSQL failures")

    assert primary.saved_tasks == ["task-1"]
