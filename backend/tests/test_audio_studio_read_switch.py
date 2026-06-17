from datetime import datetime

import pytest

from app.models.audio_studio import AudioStudioTask, VoiceProfile
from app.services.storage import StorageService


def _task(
    task_id: str,
    project_id: str = "project-1",
    *,
    created_at: datetime | None = None,
) -> AudioStudioTask:
    created_at = created_at or datetime(2026, 6, 18, 10, 0, 0)
    return AudioStudioTask(
        id=task_id,
        project_id=project_id,
        task_type="tts",
        voice="cosyvoice-demo",
        status="succeeded",
        result_voice_id=f"voice-{task_id}",
        created_at=created_at,
        updated_at=created_at,
    )


def _profile(
    profile_id: str,
    project_id: str = "project-1",
    *,
    voice_id: str | None = None,
    created_at: datetime | None = None,
) -> VoiceProfile:
    created_at = created_at or datetime(2026, 6, 18, 10, 0, 0)
    return VoiceProfile(
        id=profile_id,
        project_id=project_id,
        voice_id=voice_id or f"voice-{profile_id}",
        source="clone",
        status="ok",
        created_at=created_at,
        updated_at=created_at,
    )


class _ReadRepository:
    def __init__(self, tasks=None, profiles=None, *, fail: bool = False):
        self.tasks = {task.id: task for task in (tasks or [])}
        self.profiles = {profile.id: profile for profile in (profiles or [])}
        self.fail = fail
        self.task_get_calls = []
        self.task_project_calls = []
        self.profile_get_calls = []
        self.profile_project_calls = []
        self.voice_id_calls = []

    def get_task(self, task_id):
        self.task_get_calls.append(task_id)
        if self.fail:
            raise RuntimeError("postgres read unavailable")
        return self.tasks.get(task_id)

    def list_tasks_for_project(self, project_id):
        self.task_project_calls.append(project_id)
        if self.fail:
            raise RuntimeError("postgres read unavailable")
        return sorted(
            [task for task in self.tasks.values() if task.project_id == project_id],
            key=lambda task: task.created_at,
            reverse=True,
        )

    def get_voice_profile(self, profile_id):
        self.profile_get_calls.append(profile_id)
        if self.fail:
            raise RuntimeError("postgres read unavailable")
        return self.profiles.get(profile_id)

    def list_voice_profiles_for_project(self, project_id):
        self.profile_project_calls.append(project_id)
        if self.fail:
            raise RuntimeError("postgres read unavailable")
        return sorted(
            [profile for profile in self.profiles.values() if profile.project_id == project_id],
            key=lambda profile: profile.created_at,
            reverse=True,
        )

    def get_voice_profile_by_voice_id(self, voice_id):
        self.voice_id_calls.append(voice_id)
        if self.fail:
            raise RuntimeError("postgres read unavailable")
        for profile in self.profiles.values():
            if profile.voice_id == voice_id:
                return profile
        return None


def _enable_read_switch(monkeypatch, *, fallback: bool = True):
    monkeypatch.setenv("MIEMIE_DATABASE_ENABLED", "true")
    monkeypatch.setenv("MIEMIE_DATABASE_READ_DOMAINS", "audio_studio")
    monkeypatch.setenv("MIEMIE_DATABASE_READ_MODE", "file")
    monkeypatch.setenv("MIEMIE_DATABASE_JSON_FALLBACK_READ", "true" if fallback else "false")


def test_audio_studio_reads_are_file_only_by_default(tmp_path, monkeypatch):
    repo = _ReadRepository(tasks=[_task("pg-task")], profiles=[_profile("pg-profile")])
    monkeypatch.setattr(
        "app.repositories.audio_studio_runtime.build_audio_studio_read_repository",
        lambda user_id: repo,
    )
    storage = StorageService(str(tmp_path), owner_user_id="user-1")
    storage.save_audio_studio_task(_task("json-task"))
    storage.save_voice_profile(_profile("json-profile", voice_id="json-voice"))

    assert storage.get_audio_studio_task("json-task").id == "json-task"
    assert [task.id for task in storage.get_audio_studio_tasks("project-1")] == ["json-task"]
    assert storage.get_voice_profile("json-profile").id == "json-profile"
    assert [profile.id for profile in storage.get_voice_profiles("project-1")] == ["json-profile"]
    assert storage.get_voice_profile_by_voice_id("json-voice").id == "json-profile"
    assert repo.task_get_calls == []
    assert repo.task_project_calls == []
    assert repo.profile_get_calls == []
    assert repo.profile_project_calls == []
    assert repo.voice_id_calls == []


def test_audio_studio_read_switch_uses_postgres_for_get_and_project_lists(tmp_path, monkeypatch):
    _enable_read_switch(monkeypatch)
    newer_task = _task("pg-task-newer", created_at=datetime(2026, 6, 18, 12, 0, 0))
    older_task = _task("pg-task-older", created_at=datetime(2026, 6, 18, 9, 0, 0))
    other_task = _task("pg-task-other", project_id="project-2")
    newer_profile = _profile(
        "pg-profile-newer",
        voice_id="pg-voice-newer",
        created_at=datetime(2026, 6, 18, 12, 0, 0),
    )
    older_profile = _profile(
        "pg-profile-older",
        voice_id="pg-voice-older",
        created_at=datetime(2026, 6, 18, 9, 0, 0),
    )
    other_profile = _profile("pg-profile-other", project_id="project-2", voice_id="pg-voice-other")
    repo = _ReadRepository(
        tasks=[newer_task, older_task, other_task],
        profiles=[newer_profile, older_profile, other_profile],
    )
    monkeypatch.setattr(
        "app.repositories.audio_studio_runtime.build_audio_studio_read_repository",
        lambda user_id: repo,
    )
    storage = StorageService(str(tmp_path), owner_user_id="user-1")
    storage.save_audio_studio_task(_task("json-task"))
    storage.save_voice_profile(_profile("json-profile", voice_id="json-voice"))

    assert storage.get_audio_studio_task("pg-task-newer").id == "pg-task-newer"
    assert [task.id for task in storage.get_audio_studio_tasks("project-1")] == [
        "pg-task-newer",
        "pg-task-older",
    ]
    assert storage.get_voice_profile("pg-profile-newer").id == "pg-profile-newer"
    assert [profile.id for profile in storage.get_voice_profiles("project-1")] == [
        "pg-profile-newer",
        "pg-profile-older",
    ]
    assert storage.get_voice_profile_by_voice_id("pg-voice-older").id == "pg-profile-older"


def test_audio_studio_read_switch_falls_back_to_json_on_postgres_miss(tmp_path, monkeypatch):
    _enable_read_switch(monkeypatch)
    repo = _ReadRepository()
    monkeypatch.setattr(
        "app.repositories.audio_studio_runtime.build_audio_studio_read_repository",
        lambda user_id: repo,
    )
    storage = StorageService(str(tmp_path), owner_user_id="user-1")
    storage.save_audio_studio_task(_task("json-task"))
    storage.save_voice_profile(_profile("json-profile", voice_id="json-voice"))

    assert storage.get_audio_studio_task("json-task").id == "json-task"
    assert [task.id for task in storage.get_audio_studio_tasks("project-1")] == ["json-task"]
    assert storage.get_voice_profile("json-profile").id == "json-profile"
    assert [profile.id for profile in storage.get_voice_profiles("project-1")] == ["json-profile"]
    assert storage.get_voice_profile_by_voice_id("json-voice").id == "json-profile"


def test_audio_studio_read_switch_raises_when_fallback_disabled(tmp_path, monkeypatch):
    _enable_read_switch(monkeypatch, fallback=False)
    repo = _ReadRepository(fail=True)
    monkeypatch.setattr(
        "app.repositories.audio_studio_runtime.build_audio_studio_read_repository",
        lambda user_id: repo,
    )
    storage = StorageService(str(tmp_path), owner_user_id="user-1")
    storage.save_audio_studio_task(_task("json-task"))
    storage.save_voice_profile(_profile("json-profile", voice_id="json-voice"))

    with pytest.raises(RuntimeError, match="postgres read unavailable"):
        storage.get_audio_studio_task("json-task")
    with pytest.raises(RuntimeError, match="postgres read unavailable"):
        storage.get_voice_profile("json-profile")
    with pytest.raises(RuntimeError, match="postgres read unavailable"):
        storage.get_voice_profile_by_voice_id("json-voice")
