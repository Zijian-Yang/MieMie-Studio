from datetime import datetime, timedelta

from app.models.project import Project, ProjectLLMConfig, Script, Shot
from app.repositories.base import RepositoryWriteError
from app.repositories.projects import (
    DualProjectRepository,
    FileProjectRepository,
    project_to_row,
    row_to_project,
)
from app.services.storage import StorageService


def _project(project_id: str, **overrides) -> Project:
    base = {
        "id": project_id,
        "name": f"project {project_id}",
        "description": "description",
        "script": Script(
            title="script",
            shots=[
                Shot(shot_number=1, dialogue="hello"),
                Shot(shot_number=2, dialogue="world"),
            ],
        ),
        "character_ids": ["character-1", "character-2"],
        "scene_ids": ["scene-1"],
        "prop_ids": ["prop-1", "prop-2", "prop-3"],
        "style_ids": ["style-1"],
        "llm_configs": {
            "script": ProjectLLMConfig(
                model="qwen-plus",
                temperature=0.7,
                enable_search=True,
            )
        },
        "created_at": datetime(2026, 6, 7, 8, 0, 0),
        "updated_at": datetime(2026, 6, 7, 8, 31, 0),
    }
    base.update(overrides)
    return Project(**base)


def test_file_project_repository_preserves_storage_behavior(tmp_path):
    storage = StorageService(str(tmp_path))
    repo = FileProjectRepository(storage)
    older_updated_at = datetime.now() - timedelta(days=2)
    older = _project(
        "older",
        created_at=datetime.now() - timedelta(days=1),
        updated_at=older_updated_at,
    )
    newer = _project("newer", created_at=datetime.now(), updated_at=datetime.now())

    repo.save(older)
    repo.save(newer)

    assert repo.get("older").id == "older"
    assert repo.get("missing") is None
    assert repo.get("older").updated_at >= older_updated_at
    assert [project.id for project in repo.list_all()] == ["newer", "older"]

    repo.delete("older")

    assert repo.get("older") is None


def test_project_row_mapping_keeps_index_columns_and_raw_snapshot():
    project = _project("project-1")

    row = project_to_row("user-1", project)

    assert row["id"] == "project-1"
    assert row["user_id"] == "user-1"
    assert row["name"] == "project project-1"
    assert row["description"] == "description"
    assert row["has_script"] is True
    assert row["script_shot_count"] == 2
    assert row["character_count"] == 2
    assert row["scene_count"] == 1
    assert row["prop_count"] == 3
    assert row["style_count"] == 1
    assert row["llm_configs"]["script"]["model"] == "qwen-plus"
    assert row["raw_project_snapshot"]["id"] == "project-1"
    assert row["raw_project_snapshot"]["updated_at"] == "2026-06-07T08:31:00"

    restored = row_to_project(row)

    assert restored == project


class _RecordingRepository:
    def __init__(self, *, fail_on_save: bool = False):
        self.fail_on_save = fail_on_save
        self.saved = []
        self.deleted = []
        self.projects = {}

    def save(self, project):
        if self.fail_on_save:
            raise RepositoryWriteError("postgres unavailable")
        self.saved.append(project.id)
        self.projects[project.id] = project

    def get(self, project_id):
        return self.projects.get(project_id)

    def list_all(self):
        return list(self.projects.values())

    def delete(self, project_id):
        self.deleted.append(project_id)
        self.projects.pop(project_id, None)

    def mark_deleted(self, project_id):
        self.delete(project_id)


def test_dual_project_repository_saves_file_first_and_tolerates_shadow_failure():
    primary = _RecordingRepository()
    shadow = _RecordingRepository(fail_on_save=True)
    repo = DualProjectRepository(primary, shadow, strict_shadow_writes=False)
    project = _project("project-1")

    repo.save(project)

    assert primary.saved == ["project-1"]
    assert shadow.saved == []
    assert repo.get("project-1") == project


def test_dual_project_repository_can_enforce_strict_shadow_writes():
    primary = _RecordingRepository()
    shadow = _RecordingRepository(fail_on_save=True)
    repo = DualProjectRepository(primary, shadow, strict_shadow_writes=True)

    try:
        repo.save(_project("project-1"))
    except RepositoryWriteError as exc:
        assert "postgres unavailable" in str(exc)
    else:
        raise AssertionError("strict dual write should propagate PostgreSQL failures")

    assert primary.saved == ["project-1"]
