from datetime import datetime

from app.models.project import Project
from app.services.storage import StorageService


def _project(project_id: str, **overrides) -> Project:
    base = {
        "id": project_id,
        "name": f"project {project_id}",
        "description": "description",
        "created_at": datetime(2026, 6, 7, 12, 0, 0),
        "updated_at": datetime(2026, 6, 7, 12, 1, 0),
    }
    base.update(overrides)
    return Project(**base)


class _ReadRepository:
    def __init__(self, projects=None, *, fail=False):
        self.projects = {project.id: project for project in (projects or [])}
        self.fail = fail
        self.get_calls = []
        self.list_calls = 0

    def get(self, project_id):
        self.get_calls.append(project_id)
        if self.fail:
            raise RuntimeError("postgres read unavailable")
        return self.projects.get(project_id)

    def list_all(self):
        self.list_calls += 1
        if self.fail:
            raise RuntimeError("postgres read unavailable")
        return sorted(self.projects.values(), key=lambda project: project.updated_at, reverse=True)


def _enable_read_switch(monkeypatch, *, fallback=True):
    monkeypatch.setenv("MIEMIE_DATABASE_ENABLED", "true")
    monkeypatch.setenv("MIEMIE_DATABASE_READ_DOMAINS", "projects")
    monkeypatch.setenv("MIEMIE_DATABASE_READ_MODE", "file")
    monkeypatch.setenv("MIEMIE_DATABASE_JSON_FALLBACK_READ", "true" if fallback else "false")


def test_project_reads_are_file_only_by_default(tmp_path, monkeypatch):
    repo = _ReadRepository([_project("pg-project")])
    monkeypatch.setattr(
        "app.repositories.project_runtime.build_project_read_repository",
        lambda user_id: repo,
    )
    storage = StorageService(str(tmp_path), owner_user_id="user-1")
    storage.save_project(_project("json-project"))

    assert storage.get_project("json-project").id == "json-project"
    assert [project.id for project in storage.list_projects()] == ["json-project"]
    assert repo.get_calls == []
    assert repo.list_calls == 0


def test_project_read_switch_uses_postgres_for_get_and_list(tmp_path, monkeypatch):
    _enable_read_switch(monkeypatch)
    newer = _project("pg-newer", updated_at=datetime(2026, 6, 7, 13, 0, 0))
    older = _project("pg-older", updated_at=datetime(2026, 6, 6, 13, 0, 0))
    repo = _ReadRepository([older, newer])
    monkeypatch.setattr(
        "app.repositories.project_runtime.build_project_read_repository",
        lambda user_id: repo,
    )
    storage = StorageService(str(tmp_path), owner_user_id="user-1")
    storage.save_project(_project("json-project"))

    assert storage.get_project("pg-newer").id == "pg-newer"
    assert [project.id for project in storage.list_projects()] == ["pg-newer", "pg-older"]


def test_project_read_switch_falls_back_to_json_on_postgres_miss(tmp_path, monkeypatch):
    _enable_read_switch(monkeypatch)
    repo = _ReadRepository([])
    monkeypatch.setattr(
        "app.repositories.project_runtime.build_project_read_repository",
        lambda user_id: repo,
    )
    storage = StorageService(str(tmp_path), owner_user_id="user-1")
    storage.save_project(_project("json-project"))

    assert storage.get_project("json-project").id == "json-project"
    assert [project.id for project in storage.list_projects()] == ["json-project"]


def test_project_read_switch_raises_when_fallback_disabled(tmp_path, monkeypatch):
    _enable_read_switch(monkeypatch, fallback=False)
    repo = _ReadRepository(fail=True)
    monkeypatch.setattr(
        "app.repositories.project_runtime.build_project_read_repository",
        lambda user_id: repo,
    )
    storage = StorageService(str(tmp_path), owner_user_id="user-1")
    storage.save_project(_project("json-project"))

    try:
        storage.get_project("json-project")
    except RuntimeError as exc:
        assert "postgres read unavailable" in str(exc)
    else:
        raise AssertionError("PostgreSQL read errors should propagate when fallback is disabled")
