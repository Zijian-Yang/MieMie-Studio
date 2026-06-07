import json
from datetime import datetime

from app.models.project import Project, ProjectLLMConfig, Script, Shot
from app.services.migration.backfill_projects import (
    backfill_projects,
    iter_project_json_files,
)
from app.services.migration.reconcile_projects import (
    reconcile_projects,
    render_reconcile_markdown,
)


def _write_project(data_root, user_id: str, project: Project) -> None:
    project_dir = data_root / "users" / user_id / "projects"
    project_dir.mkdir(parents=True, exist_ok=True)
    with (project_dir / f"{project.id}.json").open("w", encoding="utf-8") as handle:
        json.dump(project.model_dump(mode="json"), handle, ensure_ascii=False)


def _project(project_id: str, **overrides) -> Project:
    base = {
        "id": project_id,
        "name": "private project name must stay out of reports",
        "description": "private description must stay out of reports",
        "script": Script(
            title="private script title",
            original_content="private original script",
            processed_content="private processed script",
            shots=[
                Shot(shot_number=1, dialogue="private dialogue"),
                Shot(shot_number=2, dialogue="private dialogue 2"),
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
        "created_at": datetime(2026, 6, 7, 10, 0, 0),
        "updated_at": datetime(2026, 6, 7, 10, 1, 0),
    }
    base.update(overrides)
    return Project(**base)


class _PerUserRepository:
    def __init__(self):
        self.projects = {}
        self.saved = []

    def save(self, project):
        self.saved.append(project.id)
        self.projects[project.id] = project

    def get(self, project_id):
        return self.projects.get(project_id)

    def list_all(self):
        return list(self.projects.values())

    def delete(self, project_id):
        self.projects.pop(project_id, None)

    def mark_deleted(self, project_id):
        self.delete(project_id)


class _RepositoryFactory:
    def __init__(self):
        self.repositories = {}

    def __call__(self, user_id):
        if user_id not in self.repositories:
            self.repositories[user_id] = _PerUserRepository()
        return self.repositories[user_id]


def test_iter_project_json_files_scans_all_user_project_files(tmp_path):
    _write_project(tmp_path, "user-a", _project("project-a"))
    _write_project(tmp_path, "user-b", _project("project-b"))
    (tmp_path / "users" / "user-b" / "projects" / "broken.json").write_text(
        "{broken",
        encoding="utf-8",
    )

    records = list(iter_project_json_files(tmp_path))

    assert [(record.user_id, record.project.id) for record in records] == [
        ("user-a", "project-a"),
        ("user-b", "project-b"),
    ]


def test_backfill_projects_upserts_json_without_leaking_private_fields(tmp_path):
    _write_project(tmp_path, "user-a", _project("project-a"))
    _write_project(tmp_path, "user-b", _project("project-b"))
    factory = _RepositoryFactory()

    summary = backfill_projects(tmp_path, factory)

    assert summary["domain"] == "projects"
    assert summary["json_count"] == 2
    assert summary["upserted_count"] == 2
    assert summary["failed_count"] == 0
    assert summary["ok"] is True
    assert factory.repositories["user-a"].get("project-a").id == "project-a"
    assert factory.repositories["user-b"].get("project-b").id == "project-b"
    serialized = json.dumps(summary, ensure_ascii=False)
    assert "private project" not in serialized
    assert "private script" not in serialized
    assert "private dialogue" not in serialized


def test_reconcile_projects_reports_safe_differences_without_private_data(tmp_path):
    _write_project(tmp_path, "user-a", _project("project-a"))
    _write_project(tmp_path, "user-a", _project("missing-in-pg"))
    factory = _RepositoryFactory()
    factory("user-a").save(
        _project(
            "project-a",
            character_ids=["character-1"],
            updated_at=datetime(2026, 6, 7, 10, 2, 0),
        )
    )
    factory("user-a").save(_project("missing-in-json"))

    summary = reconcile_projects(tmp_path, factory)
    markdown = render_reconcile_markdown(summary)
    serialized = json.dumps(summary, ensure_ascii=False)

    assert summary["domain"] == "projects"
    assert summary["json_count"] == 2
    assert summary["postgres_count"] == 2
    assert summary["missing_in_postgres"] == [
        {"user_id": "user-a", "project_id": "missing-in-pg"}
    ]
    assert summary["missing_in_json"] == [
        {"user_id": "user-a", "project_id": "missing-in-json"}
    ]
    assert {diff["field"] for diff in summary["field_differences"]} == {
        "updated_at",
        "character_count",
    }
    assert summary["ok"] is False
    assert "private project" not in serialized
    assert "private script" not in serialized
    assert "private dialogue" not in markdown
    assert "project-a" in markdown
