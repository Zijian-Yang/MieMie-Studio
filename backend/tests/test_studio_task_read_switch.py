from datetime import datetime

from app.models.studio import StudioTask
from app.services.storage import StorageService


def _task(task_id: str, project_id: str = "project-1", **overrides) -> StudioTask:
    base = {
        "id": task_id,
        "project_id": project_id,
        "name": f"task {task_id}",
        "task_kind": "image_edit",
        "provider": "wan",
        "status": "generating",
        "created_at": datetime(2026, 6, 7, 11, 0, 0),
        "updated_at": datetime(2026, 6, 7, 11, 1, 0),
    }
    base.update(overrides)
    return StudioTask(**base)


class _ReadRepository:
    def __init__(self, tasks=None, *, fail=False):
        self.tasks = {task.id: task for task in (tasks or [])}
        self.fail = fail
        self.get_calls = []
        self.project_calls = []

    def get(self, task_id):
        self.get_calls.append(task_id)
        if self.fail:
            raise RuntimeError("postgres read unavailable")
        return self.tasks.get(task_id)

    def list_for_project(self, project_id):
        self.project_calls.append(project_id)
        if self.fail:
            raise RuntimeError("postgres read unavailable")
        return sorted(
            [task for task in self.tasks.values() if task.project_id == project_id],
            key=lambda task: task.created_at,
            reverse=True,
        )


def _enable_read_switch(monkeypatch, *, fallback=True):
    monkeypatch.setenv("MIEMIE_DATABASE_ENABLED", "true")
    monkeypatch.setenv("MIEMIE_DATABASE_READ_DOMAINS", "studio_tasks")
    monkeypatch.setenv("MIEMIE_DATABASE_READ_MODE", "file")
    monkeypatch.setenv("MIEMIE_DATABASE_JSON_FALLBACK_READ", "true" if fallback else "false")


def test_studio_task_reads_are_file_only_by_default(tmp_path, monkeypatch):
    repo = _ReadRepository([_task("pg-task")])
    monkeypatch.setattr(
        "app.repositories.studio_task_runtime.build_studio_task_read_repository",
        lambda user_id: repo,
    )
    storage = StorageService(str(tmp_path), owner_user_id="user-1")
    storage.save_studio_task(_task("json-task"))

    assert storage.get_studio_task("json-task").id == "json-task"
    assert storage.get_studio_tasks_by_project("project-1")[0].id == "json-task"
    assert repo.get_calls == []
    assert repo.project_calls == []


def test_studio_task_read_switch_uses_postgres_for_get_and_project_list(tmp_path, monkeypatch):
    _enable_read_switch(monkeypatch)
    newer = _task("pg-newer", created_at=datetime(2026, 6, 7, 12, 0, 0))
    other = _task(
        "pg-other",
        project_id="project-2",
        created_at=datetime(2026, 6, 7, 11, 30, 0),
    )
    older = _task("pg-older", created_at=datetime(2026, 6, 6, 12, 0, 0))
    repo = _ReadRepository([older, newer, other])
    monkeypatch.setattr(
        "app.repositories.studio_task_runtime.build_studio_task_read_repository",
        lambda user_id: repo,
    )
    storage = StorageService(str(tmp_path), owner_user_id="user-1")
    storage.save_studio_task(_task("json-task"))

    assert storage.get_studio_task("pg-newer").id == "pg-newer"
    assert [task.id for task in storage.get_studio_tasks_by_project("project-1")] == [
        "pg-newer",
        "pg-older",
    ]


def test_studio_task_read_switch_falls_back_to_json_on_postgres_miss(tmp_path, monkeypatch):
    _enable_read_switch(monkeypatch)
    repo = _ReadRepository([])
    monkeypatch.setattr(
        "app.repositories.studio_task_runtime.build_studio_task_read_repository",
        lambda user_id: repo,
    )
    storage = StorageService(str(tmp_path), owner_user_id="user-1")
    storage.save_studio_task(_task("json-task"))

    assert storage.get_studio_task("json-task").id == "json-task"
    assert [task.id for task in storage.get_studio_tasks_by_project("project-1")] == ["json-task"]


def test_studio_task_read_switch_raises_when_fallback_disabled(tmp_path, monkeypatch):
    _enable_read_switch(monkeypatch, fallback=False)
    repo = _ReadRepository(fail=True)
    monkeypatch.setattr(
        "app.repositories.studio_task_runtime.build_studio_task_read_repository",
        lambda user_id: repo,
    )
    storage = StorageService(str(tmp_path), owner_user_id="user-1")
    storage.save_studio_task(_task("json-task"))

    try:
        storage.get_studio_task("json-task")
    except RuntimeError as exc:
        assert "postgres read unavailable" in str(exc)
    else:
        raise AssertionError("PostgreSQL read errors should propagate when fallback is disabled")
