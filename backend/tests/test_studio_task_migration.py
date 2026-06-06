import json
from datetime import datetime

from app.models.studio import StudioTask, StudioTaskImage
from app.services.migration.backfill_studio_tasks import (
    backfill_studio_tasks,
    iter_studio_json_tasks,
)
from app.services.migration.reconcile_studio_tasks import (
    reconcile_studio_tasks,
    render_reconcile_markdown,
)


def _write_task(data_root, user_id: str, task: StudioTask) -> None:
    task_dir = data_root / "users" / user_id / "studio"
    task_dir.mkdir(parents=True, exist_ok=True)
    with (task_dir / f"{task.id}.json").open("w", encoding="utf-8") as handle:
        json.dump(task.model_dump(mode="json"), handle, ensure_ascii=False)


def _task(task_id: str, **overrides) -> StudioTask:
    base = {
        "id": task_id,
        "project_id": "project-1",
        "name": "private task name",
        "task_kind": "image_edit",
        "provider": "wan",
        "status": "generating",
        "prompt": "private prompt body must stay out of reports",
        "provider_payload_snapshot": {"prompt": "private provider payload"},
        "input_assets": {"source_image": ["https://private.example/image.png"]},
        "images": [
            StudioTaskImage(
                group_index=0,
                url="https://private.example/generated.png",
                is_selected=True,
            )
        ],
        "last_task_id": "dashscope-task-1",
        "last_request_id": "request-1",
        "created_at": datetime(2026, 6, 7, 9, 0, 0),
        "updated_at": datetime(2026, 6, 7, 9, 1, 0),
    }
    base.update(overrides)
    return StudioTask(**base)


class _PerUserRepository:
    def __init__(self):
        self.tasks = {}
        self.saved = []

    def save(self, task):
        self.saved.append(task.id)
        self.tasks[task.id] = task

    def get(self, task_id):
        return self.tasks.get(task_id)

    def list_for_project(self, project_id):
        return [task for task in self.tasks.values() if task.project_id == project_id]

    def list_all(self):
        return list(self.tasks.values())

    def delete(self, task_id):
        self.tasks.pop(task_id, None)

    def mark_deleted(self, task_id):
        self.delete(task_id)


class _RepositoryFactory:
    def __init__(self):
        self.repositories = {}

    def __call__(self, user_id):
        if user_id not in self.repositories:
            self.repositories[user_id] = _PerUserRepository()
        return self.repositories[user_id]


def test_iter_studio_json_tasks_scans_all_user_task_files(tmp_path):
    _write_task(tmp_path, "user-a", _task("task-a"))
    _write_task(tmp_path, "user-b", _task("task-b", project_id="project-2"))
    (tmp_path / "users" / "user-b" / "studio" / "broken.json").write_text(
        "{broken",
        encoding="utf-8",
    )

    records = list(iter_studio_json_tasks(tmp_path))

    assert [(record.user_id, record.task.id) for record in records] == [
        ("user-a", "task-a"),
        ("user-b", "task-b"),
    ]


def test_backfill_studio_tasks_upserts_json_without_leaking_private_fields(tmp_path):
    _write_task(tmp_path, "user-a", _task("task-a"))
    _write_task(tmp_path, "user-b", _task("task-b", project_id="project-2"))
    factory = _RepositoryFactory()

    summary = backfill_studio_tasks(tmp_path, factory)

    assert summary["domain"] == "studio_tasks"
    assert summary["json_count"] == 2
    assert summary["upserted_count"] == 2
    assert summary["failed_count"] == 0
    assert summary["ok"] is True
    assert factory.repositories["user-a"].get("task-a").project_id == "project-1"
    assert factory.repositories["user-b"].get("task-b").project_id == "project-2"
    assert "private prompt" not in json.dumps(summary, ensure_ascii=False)
    assert "private.example" not in json.dumps(summary, ensure_ascii=False)


def test_reconcile_studio_tasks_reports_safe_differences_without_private_data(tmp_path):
    _write_task(tmp_path, "user-a", _task("task-a"))
    _write_task(tmp_path, "user-a", _task("missing-in-pg"))
    factory = _RepositoryFactory()
    factory("user-a").save(
        _task(
            "task-a",
            status="failed",
            updated_at=datetime(2026, 6, 7, 9, 2, 0),
            last_task_id="dashscope-task-2",
        )
    )
    factory("user-a").save(_task("missing-in-json"))

    summary = reconcile_studio_tasks(tmp_path, factory)
    markdown = render_reconcile_markdown(summary)
    serialized = json.dumps(summary, ensure_ascii=False)

    assert summary["domain"] == "studio_tasks"
    assert summary["json_count"] == 2
    assert summary["postgres_count"] == 2
    assert summary["missing_in_postgres"] == [{"user_id": "user-a", "task_id": "missing-in-pg"}]
    assert summary["missing_in_json"] == [{"user_id": "user-a", "task_id": "missing-in-json"}]
    assert {diff["field"] for diff in summary["field_differences"]} == {
        "status",
        "updated_at",
        "last_task_id",
    }
    assert summary["ok"] is False
    assert "private prompt" not in serialized
    assert "private.example" not in serialized
    assert "private provider" not in markdown
    assert "task-a" in markdown
