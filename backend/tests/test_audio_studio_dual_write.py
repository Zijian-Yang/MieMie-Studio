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
        created_at=datetime(2026, 6, 17, 10, 0, 0),
        updated_at=datetime(2026, 6, 17, 10, 1, 0),
    )


def _profile(profile_id: str = "profile-1") -> VoiceProfile:
    return VoiceProfile(
        id=profile_id,
        project_id="project-1",
        voice_id="voice-profile-1",
        source="clone",
        status="ok",
        created_at=datetime(2026, 6, 17, 10, 0, 0),
        updated_at=datetime(2026, 6, 17, 10, 1, 0),
    )


class _ShadowRepository:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.saved_tasks = []
        self.deleted_tasks = []
        self.saved_profiles = []
        self.deleted_profiles = []

    def save_task(self, task):
        if self.fail:
            raise RuntimeError("postgres unavailable")
        self.saved_tasks.append(task.model_copy(deep=True))

    def mark_task_deleted(self, task_id):
        if self.fail:
            raise RuntimeError("postgres unavailable")
        self.deleted_tasks.append(task_id)

    def save_voice_profile(self, profile):
        if self.fail:
            raise RuntimeError("postgres unavailable")
        self.saved_profiles.append(profile.model_copy(deep=True))

    def mark_voice_profile_deleted(self, profile_id):
        if self.fail:
            raise RuntimeError("postgres unavailable")
        self.deleted_profiles.append(profile_id)


def _enable_dual_write(monkeypatch, *, strict: bool = False):
    monkeypatch.setenv("MIEMIE_DATABASE_ENABLED", "true")
    monkeypatch.setenv("MIEMIE_DATABASE_DUAL_WRITE_DOMAINS", "audio_studio")
    monkeypatch.setenv("MIEMIE_DATABASE_WRITE_MODE", "file")
    monkeypatch.setenv("MIEMIE_DATABASE_RECONCILE_STRICT", "true" if strict else "false")


def test_audio_studio_dual_write_is_disabled_by_default(tmp_path, monkeypatch):
    shadow = _ShadowRepository()
    monkeypatch.setattr(
        "app.repositories.audio_studio_runtime.build_audio_studio_shadow_repository",
        lambda user_id: shadow,
    )
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    storage.save_audio_studio_task(_task())
    storage.save_voice_profile(_profile())
    storage.delete_audio_studio_task("task-1")
    storage.delete_voice_profile("profile-1")

    assert shadow.saved_tasks == []
    assert shadow.deleted_tasks == []
    assert shadow.saved_profiles == []
    assert shadow.deleted_profiles == []
    assert storage.get_audio_studio_task("task-1") is None
    assert storage.get_voice_profile("profile-1") is None


def test_audio_studio_dual_write_saves_and_marks_deleted_when_enabled(tmp_path, monkeypatch):
    _enable_dual_write(monkeypatch)
    shadow = _ShadowRepository()
    seen_user_ids = []
    monkeypatch.setattr(
        "app.repositories.audio_studio_runtime.build_audio_studio_shadow_repository",
        lambda user_id: seen_user_ids.append(user_id) or shadow,
    )
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    storage.save_audio_studio_task(_task())
    storage.save_voice_profile(_profile())
    storage.delete_audio_studio_task("task-1")
    storage.delete_voice_profile("profile-1")

    assert seen_user_ids == ["user-1", "user-1", "user-1", "user-1"]
    assert [task.id for task in shadow.saved_tasks] == ["task-1"]
    assert shadow.deleted_tasks == ["task-1"]
    assert [profile.id for profile in shadow.saved_profiles] == ["profile-1"]
    assert shadow.deleted_profiles == ["profile-1"]
    assert storage.get_audio_studio_task("task-1") is None
    assert storage.get_voice_profile("profile-1") is None


def test_audio_studio_dual_write_failure_does_not_break_json_primary(tmp_path, monkeypatch):
    _enable_dual_write(monkeypatch)
    shadow = _ShadowRepository(fail=True)
    monkeypatch.setattr(
        "app.repositories.audio_studio_runtime.build_audio_studio_shadow_repository",
        lambda user_id: shadow,
    )
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    storage.save_audio_studio_task(_task())
    storage.save_voice_profile(_profile())

    assert storage.get_audio_studio_task("task-1") is not None
    assert storage.get_voice_profile("profile-1") is not None


def test_audio_studio_dual_write_strict_failure_propagates_after_json_write(tmp_path, monkeypatch):
    _enable_dual_write(monkeypatch, strict=True)
    shadow = _ShadowRepository(fail=True)
    monkeypatch.setattr(
        "app.repositories.audio_studio_runtime.build_audio_studio_shadow_repository",
        lambda user_id: shadow,
    )
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    with pytest.raises(RuntimeError):
        storage.save_audio_studio_task(_task())
    with pytest.raises(RuntimeError):
        storage.save_voice_profile(_profile())

    assert storage.get_audio_studio_task("task-1") is not None
    assert storage.get_voice_profile("profile-1") is not None
