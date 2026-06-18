from datetime import datetime

import pytest

from app.models.audio_studio import AudioStudioTask, VoiceProfile
from app.services.storage import StorageService


def _task(task_id: str = "task-1") -> AudioStudioTask:
    return AudioStudioTask(
        id=task_id,
        project_id="project-1",
        task_type="tts",
        voice="cosyvoice-demo",
        status="succeeded",
        result_voice_id="voice-task-1",
        created_at=datetime(2026, 6, 18, 13, 0, 0),
        updated_at=datetime(2026, 6, 18, 13, 1, 0),
    )


def _profile(profile_id: str = "profile-1") -> VoiceProfile:
    return VoiceProfile(
        id=profile_id,
        project_id="project-1",
        voice_id="voice-profile-1",
        source="clone",
        status="ok",
        created_at=datetime(2026, 6, 18, 13, 0, 0),
        updated_at=datetime(2026, 6, 18, 13, 1, 0),
    )


class _PrimaryRepository:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.saved_tasks = []
        self.deleted_tasks = []
        self.saved_profiles = []
        self.deleted_profiles = []

    def save_task(self, task):
        if self.fail:
            raise RuntimeError("postgres primary unavailable")
        self.saved_tasks.append(task.model_copy(deep=True))

    def mark_task_deleted(self, task_id):
        if self.fail:
            raise RuntimeError("postgres primary unavailable")
        self.deleted_tasks.append(task_id)

    def save_voice_profile(self, profile):
        if self.fail:
            raise RuntimeError("postgres primary unavailable")
        self.saved_profiles.append(profile.model_copy(deep=True))

    def mark_voice_profile_deleted(self, profile_id):
        if self.fail:
            raise RuntimeError("postgres primary unavailable")
        self.deleted_profiles.append(profile_id)


def _enable_primary_write(monkeypatch, *, archive: bool = False):
    monkeypatch.setenv("MIEMIE_DATABASE_ENABLED", "true")
    monkeypatch.setenv("MIEMIE_DATABASE_WRITE_MODE", "file")
    monkeypatch.setenv("MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS", "audio_studio")
    monkeypatch.setenv("MIEMIE_DATABASE_JSON_ARCHIVE_WRITES", "true" if archive else "false")


def test_audio_studio_primary_write_is_disabled_by_default(tmp_path, monkeypatch):
    repo = _PrimaryRepository()
    monkeypatch.setattr(
        "app.repositories.audio_studio_runtime.build_audio_studio_primary_repository",
        lambda user_id: repo,
    )
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    storage.save_audio_studio_task(_task())
    storage.save_voice_profile(_profile())

    assert repo.saved_tasks == []
    assert repo.saved_profiles == []
    assert storage.get_audio_studio_task("task-1") is not None
    assert storage.get_voice_profile("profile-1") is not None


def test_audio_studio_primary_write_saves_postgres_without_json_archive(tmp_path, monkeypatch):
    _enable_primary_write(monkeypatch, archive=False)
    repo = _PrimaryRepository()
    monkeypatch.setattr(
        "app.repositories.audio_studio_runtime.build_audio_studio_primary_repository",
        lambda user_id: repo,
    )
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    storage.save_audio_studio_task(_task())
    storage.save_voice_profile(_profile())
    storage.delete_audio_studio_task("task-1")
    storage.delete_voice_profile("profile-1")

    assert [task.id for task in repo.saved_tasks] == ["task-1"]
    assert repo.saved_tasks[0].updated_at != datetime(2026, 6, 18, 13, 1, 0)
    assert repo.deleted_tasks == ["task-1"]
    assert [profile.id for profile in repo.saved_profiles] == ["profile-1"]
    assert repo.saved_profiles[0].updated_at != datetime(2026, 6, 18, 13, 1, 0)
    assert repo.deleted_profiles == ["profile-1"]
    assert storage._get_audio_studio_task_from_file("task-1") is None
    assert storage._get_voice_profile_from_file("profile-1") is None


def test_audio_studio_primary_write_can_keep_json_archive_mirror(tmp_path, monkeypatch):
    _enable_primary_write(monkeypatch, archive=True)
    repo = _PrimaryRepository()
    monkeypatch.setattr(
        "app.repositories.audio_studio_runtime.build_audio_studio_primary_repository",
        lambda user_id: repo,
    )
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    storage.save_audio_studio_task(_task())
    storage.save_voice_profile(_profile())
    assert storage._get_audio_studio_task_from_file("task-1") is not None
    assert storage._get_voice_profile_from_file("profile-1") is not None

    storage.delete_audio_studio_task("task-1")
    storage.delete_voice_profile("profile-1")

    assert repo.deleted_tasks == ["task-1"]
    assert repo.deleted_profiles == ["profile-1"]
    assert storage._get_audio_studio_task_from_file("task-1") is None
    assert storage._get_voice_profile_from_file("profile-1") is None


def test_audio_studio_primary_write_failure_does_not_write_json(tmp_path, monkeypatch):
    _enable_primary_write(monkeypatch, archive=True)
    repo = _PrimaryRepository(fail=True)
    monkeypatch.setattr(
        "app.repositories.audio_studio_runtime.build_audio_studio_primary_repository",
        lambda user_id: repo,
    )
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    with pytest.raises(RuntimeError, match="postgres primary unavailable"):
        storage.save_audio_studio_task(_task())
    with pytest.raises(RuntimeError, match="postgres primary unavailable"):
        storage.save_voice_profile(_profile())

    assert storage._get_audio_studio_task_from_file("task-1") is None
    assert storage._get_voice_profile_from_file("profile-1") is None
