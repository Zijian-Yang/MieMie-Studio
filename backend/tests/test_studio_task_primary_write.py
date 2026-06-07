from datetime import datetime

from app.models.studio import StudioTask
from app.services.storage import StorageService


def _task(task_id: str = "task-1") -> StudioTask:
    return StudioTask(
        id=task_id,
        project_id="project-1",
        name="S4 image task",
        task_kind="text_to_image",
        status="generating",
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
    monkeypatch.setenv("MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS", "studio_tasks")
    monkeypatch.setenv("MIEMIE_DATABASE_JSON_ARCHIVE_WRITES", "true" if archive else "false")


def test_studio_task_primary_write_is_disabled_by_default(tmp_path, monkeypatch):
    repo = _PrimaryRepository()
    monkeypatch.setattr(
        "app.repositories.studio_task_runtime.build_studio_task_primary_repository",
        lambda user_id: repo,
    )
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    storage.save_studio_task(_task())

    assert repo.saved == []
    assert storage.get_studio_task("task-1") is not None


def test_studio_task_primary_write_saves_postgres_without_json_archive(tmp_path, monkeypatch):
    _enable_primary_write(monkeypatch, archive=False)
    repo = _PrimaryRepository()
    monkeypatch.setattr(
        "app.repositories.studio_task_runtime.build_studio_task_primary_repository",
        lambda user_id: repo,
    )
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    storage.save_studio_task(_task())
    storage.delete_studio_task("task-1")

    assert [task.id for task in repo.saved] == ["task-1"]
    assert repo.saved[0].updated_at != datetime(2026, 6, 7, 13, 1, 0)
    assert repo.deleted == ["task-1"]
    assert storage._get_studio_task_from_file("task-1") is None


def test_studio_task_primary_write_can_keep_json_archive_mirror(tmp_path, monkeypatch):
    _enable_primary_write(monkeypatch, archive=True)
    repo = _PrimaryRepository()
    monkeypatch.setattr(
        "app.repositories.studio_task_runtime.build_studio_task_primary_repository",
        lambda user_id: repo,
    )
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    storage.save_studio_task(_task())
    assert storage._get_studio_task_from_file("task-1") is not None

    storage.delete_studio_task("task-1")

    assert repo.deleted == ["task-1"]
    assert storage._get_studio_task_from_file("task-1") is None


def test_studio_task_primary_write_failure_does_not_write_json(tmp_path, monkeypatch):
    _enable_primary_write(monkeypatch, archive=True)
    repo = _PrimaryRepository(fail=True)
    monkeypatch.setattr(
        "app.repositories.studio_task_runtime.build_studio_task_primary_repository",
        lambda user_id: repo,
    )
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    try:
        storage.save_studio_task(_task())
    except RuntimeError as exc:
        assert "postgres primary unavailable" in str(exc)
    else:
        raise AssertionError("PostgreSQL primary write failures should propagate")

    assert storage._get_studio_task_from_file("task-1") is None
