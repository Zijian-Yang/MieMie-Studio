from datetime import datetime

from app.models.studio import StudioTask
from app.services.storage import StorageService


def _task(task_id: str = "task-1") -> StudioTask:
    return StudioTask(
        id=task_id,
        project_id="project-1",
        task_kind="image_edit",
        status="generating",
        created_at=datetime(2026, 6, 7, 10, 0, 0),
        updated_at=datetime(2026, 6, 7, 10, 1, 0),
    )


class _ShadowRepository:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.saved = []
        self.deleted = []

    def save(self, task):
        if self.fail:
            raise RuntimeError("postgres unavailable")
        self.saved.append(task.model_copy(deep=True))

    def mark_deleted(self, task_id):
        if self.fail:
            raise RuntimeError("postgres unavailable")
        self.deleted.append(task_id)


def _enable_dual_write(monkeypatch):
    monkeypatch.setenv("MIEMIE_DATABASE_ENABLED", "true")
    monkeypatch.setenv("MIEMIE_DATABASE_DUAL_WRITE_DOMAINS", "studio_tasks")
    monkeypatch.setenv("MIEMIE_DATABASE_WRITE_MODE", "file")
    monkeypatch.setenv("MIEMIE_DATABASE_RECONCILE_STRICT", "false")


def test_studio_task_dual_write_is_disabled_by_default(tmp_path, monkeypatch):
    shadow = _ShadowRepository()
    monkeypatch.setattr(
        "app.repositories.studio_task_runtime.build_studio_task_shadow_repository",
        lambda user_id: shadow,
    )
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    storage.save_studio_task(_task())
    storage.delete_studio_task("task-1")

    assert shadow.saved == []
    assert shadow.deleted == []
    assert storage.get_studio_task("task-1") is None


def test_studio_task_dual_write_saves_and_marks_deleted_when_enabled(tmp_path, monkeypatch):
    _enable_dual_write(monkeypatch)
    shadow = _ShadowRepository()
    seen_user_ids = []
    monkeypatch.setattr(
        "app.repositories.studio_task_runtime.build_studio_task_shadow_repository",
        lambda user_id: seen_user_ids.append(user_id) or shadow,
    )
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    storage.save_studio_task(_task())
    storage.delete_studio_task("task-1")

    assert seen_user_ids == ["user-1", "user-1"]
    assert [task.id for task in shadow.saved] == ["task-1"]
    assert shadow.deleted == ["task-1"]
    assert storage.get_studio_task("task-1") is None


def test_studio_task_dual_write_failure_does_not_break_json_primary(tmp_path, monkeypatch):
    _enable_dual_write(monkeypatch)
    shadow = _ShadowRepository(fail=True)
    monkeypatch.setattr(
        "app.repositories.studio_task_runtime.build_studio_task_shadow_repository",
        lambda user_id: shadow,
    )
    storage = StorageService(str(tmp_path), owner_user_id="user-1")
    task = _task()

    storage.save_studio_task(task)

    assert storage.get_studio_task("task-1") is not None
