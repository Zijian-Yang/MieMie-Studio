from datetime import datetime

from app.models.media import VideoStudioTask
from app.services.storage import StorageService


def _task(task_id: str = "task-1") -> VideoStudioTask:
    return VideoStudioTask(
        id=task_id,
        project_id="project-1",
        task_type="text_to_video",
        task_kind="text_to_video",
        status="processing",
        submit_state="submitted",
        created_at=datetime(2026, 6, 7, 13, 0, 0),
        updated_at=datetime(2026, 6, 7, 13, 1, 0),
    )


class _PrimaryRepository:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.saved = []
        self.deleted = []

    def save(self, task):
        if self.fail:
            raise RuntimeError("postgres primary unavailable")
        self.saved.append(task.model_copy(deep=True))

    def mark_deleted(self, task_id):
        if self.fail:
            raise RuntimeError("postgres primary unavailable")
        self.deleted.append(task_id)


def _enable_primary_write(monkeypatch, *, archive=False):
    monkeypatch.setenv("MIEMIE_DATABASE_ENABLED", "true")
    monkeypatch.setenv("MIEMIE_DATABASE_WRITE_MODE", "file")
    monkeypatch.setenv("MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS", "video_studio_tasks")
    monkeypatch.setenv("MIEMIE_DATABASE_JSON_ARCHIVE_WRITES", "true" if archive else "false")


def test_video_studio_task_primary_write_is_disabled_by_default(tmp_path, monkeypatch):
    repo = _PrimaryRepository()
    monkeypatch.setattr(
        "app.repositories.video_studio_task_runtime.build_video_studio_task_primary_repository",
        lambda user_id: repo,
    )
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    storage.save_video_studio_task(_task())

    assert repo.saved == []
    assert storage.get_video_studio_task("task-1") is not None


def test_video_studio_task_primary_write_saves_postgres_without_json_archive(tmp_path, monkeypatch):
    _enable_primary_write(monkeypatch, archive=False)
    repo = _PrimaryRepository()
    monkeypatch.setattr(
        "app.repositories.video_studio_task_runtime.build_video_studio_task_primary_repository",
        lambda user_id: repo,
    )
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    storage.save_video_studio_task(_task())
    storage.delete_video_studio_task("task-1")

    assert [task.id for task in repo.saved] == ["task-1"]
    assert repo.saved[0].updated_at != datetime(2026, 6, 7, 13, 1, 0)
    assert repo.deleted == ["task-1"]
    assert storage._get_video_studio_task_from_file("task-1") is None


def test_video_studio_task_primary_write_can_keep_json_archive_mirror(tmp_path, monkeypatch):
    _enable_primary_write(monkeypatch, archive=True)
    repo = _PrimaryRepository()
    monkeypatch.setattr(
        "app.repositories.video_studio_task_runtime.build_video_studio_task_primary_repository",
        lambda user_id: repo,
    )
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    storage.save_video_studio_task(_task())
    assert storage._get_video_studio_task_from_file("task-1") is not None

    storage.delete_video_studio_task("task-1")

    assert repo.deleted == ["task-1"]
    assert storage._get_video_studio_task_from_file("task-1") is None


def test_video_studio_task_primary_write_failure_does_not_write_json(tmp_path, monkeypatch):
    _enable_primary_write(monkeypatch, archive=True)
    repo = _PrimaryRepository(fail=True)
    monkeypatch.setattr(
        "app.repositories.video_studio_task_runtime.build_video_studio_task_primary_repository",
        lambda user_id: repo,
    )
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    try:
        storage.save_video_studio_task(_task())
    except RuntimeError as exc:
        assert "postgres primary unavailable" in str(exc)
    else:
        raise AssertionError("PostgreSQL primary write failures should propagate")

    assert storage._get_video_studio_task_from_file("task-1") is None
