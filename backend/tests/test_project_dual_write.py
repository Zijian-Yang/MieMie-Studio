from datetime import datetime

from app.models.project import Project
from app.services.storage import StorageService


def _project(project_id: str = "project-1") -> Project:
    return Project(
        id=project_id,
        name="project",
        description="description",
        created_at=datetime(2026, 6, 7, 11, 0, 0),
        updated_at=datetime(2026, 6, 7, 11, 1, 0),
    )


class _ShadowRepository:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.saved = []
        self.deleted = []

    def save(self, project):
        if self.fail:
            raise RuntimeError("postgres unavailable")
        self.saved.append(project.model_copy(deep=True))

    def mark_deleted(self, project_id):
        if self.fail:
            raise RuntimeError("postgres unavailable")
        self.deleted.append(project_id)


def _enable_dual_write(monkeypatch):
    monkeypatch.setenv("MIEMIE_DATABASE_ENABLED", "true")
    monkeypatch.setenv("MIEMIE_DATABASE_DUAL_WRITE_DOMAINS", "projects")
    monkeypatch.setenv("MIEMIE_DATABASE_WRITE_MODE", "file")
    monkeypatch.setenv("MIEMIE_DATABASE_RECONCILE_STRICT", "false")


def test_project_dual_write_is_disabled_by_default(tmp_path, monkeypatch):
    shadow = _ShadowRepository()
    monkeypatch.setattr(
        "app.repositories.project_runtime.build_project_shadow_repository",
        lambda user_id: shadow,
    )
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    storage.save_project(_project())
    storage.delete_project("project-1")

    assert shadow.saved == []
    assert shadow.deleted == []
    assert storage.get_project("project-1") is None


def test_project_dual_write_saves_and_marks_deleted_when_enabled(tmp_path, monkeypatch):
    _enable_dual_write(monkeypatch)
    shadow = _ShadowRepository()
    seen_user_ids = []
    monkeypatch.setattr(
        "app.repositories.project_runtime.build_project_shadow_repository",
        lambda user_id: seen_user_ids.append(user_id) or shadow,
    )
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    storage.save_project(_project())
    storage.delete_project("project-1")

    assert seen_user_ids == ["user-1", "user-1"]
    assert [project.id for project in shadow.saved] == ["project-1"]
    assert shadow.saved[0].updated_at != datetime(2026, 6, 7, 11, 1, 0)
    assert shadow.deleted == ["project-1"]
    assert storage.get_project("project-1") is None


def test_project_dual_write_failure_does_not_break_json_primary(tmp_path, monkeypatch):
    _enable_dual_write(monkeypatch)
    shadow = _ShadowRepository(fail=True)
    monkeypatch.setattr(
        "app.repositories.project_runtime.build_project_shadow_repository",
        lambda user_id: shadow,
    )
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    storage.save_project(_project())

    assert storage.get_project("project-1") is not None
