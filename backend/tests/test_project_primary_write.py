from datetime import datetime

from app.models.project import Project
from app.services.storage import StorageService


def _project(project_id: str = "project-1") -> Project:
    return Project(
        id=project_id,
        name="S4 project",
        description="description",
        created_at=datetime(2026, 6, 7, 14, 0, 0),
        updated_at=datetime(2026, 6, 7, 14, 1, 0),
    )


class _PrimaryRepository:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.saved = []
        self.deleted = []

    def save(self, project):
        if self.fail:
            raise RuntimeError("postgres primary unavailable")
        self.saved.append(project.model_copy(deep=True))

    def mark_deleted(self, project_id):
        if self.fail:
            raise RuntimeError("postgres primary unavailable")
        self.deleted.append(project_id)


def _enable_primary_write(monkeypatch, *, archive=False):
    monkeypatch.setenv("MIEMIE_DATABASE_ENABLED", "true")
    monkeypatch.setenv("MIEMIE_DATABASE_WRITE_MODE", "file")
    monkeypatch.setenv("MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS", "projects")
    monkeypatch.setenv("MIEMIE_DATABASE_JSON_ARCHIVE_WRITES", "true" if archive else "false")


def test_project_primary_write_is_disabled_by_default(tmp_path, monkeypatch):
    repo = _PrimaryRepository()
    monkeypatch.setattr(
        "app.repositories.project_runtime.build_project_primary_repository",
        lambda user_id: repo,
    )
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    storage.save_project(_project())

    assert repo.saved == []
    assert storage.get_project("project-1") is not None


def test_project_primary_write_saves_postgres_without_json_archive(tmp_path, monkeypatch):
    _enable_primary_write(monkeypatch, archive=False)
    repo = _PrimaryRepository()
    monkeypatch.setattr(
        "app.repositories.project_runtime.build_project_primary_repository",
        lambda user_id: repo,
    )
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    storage.save_project(_project())
    storage.delete_project("project-1")

    assert [project.id for project in repo.saved] == ["project-1"]
    assert repo.saved[0].updated_at != datetime(2026, 6, 7, 14, 1, 0)
    assert repo.deleted == ["project-1"]
    assert storage._get_project_from_file("project-1") is None


def test_project_primary_write_can_keep_json_archive_mirror(tmp_path, monkeypatch):
    _enable_primary_write(monkeypatch, archive=True)
    repo = _PrimaryRepository()
    monkeypatch.setattr(
        "app.repositories.project_runtime.build_project_primary_repository",
        lambda user_id: repo,
    )
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    storage.save_project(_project())
    assert storage._get_project_from_file("project-1") is not None

    storage.delete_project("project-1")

    assert repo.deleted == ["project-1"]
    assert storage._get_project_from_file("project-1") is None


def test_project_primary_write_failure_does_not_write_json(tmp_path, monkeypatch):
    _enable_primary_write(monkeypatch, archive=True)
    repo = _PrimaryRepository(fail=True)
    monkeypatch.setattr(
        "app.repositories.project_runtime.build_project_primary_repository",
        lambda user_id: repo,
    )
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    try:
        storage.save_project(_project())
    except RuntimeError as exc:
        assert "postgres primary unavailable" in str(exc)
    else:
        raise AssertionError("PostgreSQL primary write failures should propagate")

    assert storage._get_project_from_file("project-1") is None
