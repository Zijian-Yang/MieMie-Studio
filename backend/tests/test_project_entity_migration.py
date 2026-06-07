import json
from datetime import datetime

from app.models.character import Character
from app.models.frame import Frame
from app.models.prop import Prop
from app.models.scene import Scene
from app.models.style import Style
from app.models.video import TaskStatus, Video, VideoTask
from app.repositories.project_entities import CHARACTER, FRAME, PROP, SCENE, STYLE, VIDEO
from app.services.migration.backfill_project_entities import (
    backfill_project_entities,
    iter_project_entity_json_files,
)
from app.services.migration.reconcile_project_entities import (
    reconcile_project_entities,
    render_reconcile_markdown,
)


def _write_json(data_root, user_id: str, directory: str, entity) -> None:
    entity_dir = data_root / "users" / user_id / directory
    entity_dir.mkdir(parents=True, exist_ok=True)
    with (entity_dir / f"{entity.id}.json").open("w", encoding="utf-8") as handle:
        json.dump(entity.model_dump(mode="json"), handle, ensure_ascii=False)


def _character(entity_id: str = "character-1", **overrides) -> Character:
    base = {
        "id": entity_id,
        "project_id": "project-1",
        "name": "private character name",
        "description": "private character description",
        "appearance": "private appearance",
        "personality": "private personality",
        "character_prompt": "private character prompt",
        "created_at": datetime(2026, 6, 7, 20, 0, 0),
        "updated_at": datetime(2026, 6, 7, 20, 1, 0),
    }
    base.update(overrides)
    return Character(**base)


def _scene(entity_id: str = "scene-1", **overrides) -> Scene:
    base = {
        "id": entity_id,
        "project_id": "project-1",
        "name": "private scene name",
        "description": "private scene description",
        "scene_prompt": "private scene prompt",
        "selected_group_index": 1,
        "created_at": datetime(2026, 6, 7, 20, 2, 0),
        "updated_at": datetime(2026, 6, 7, 20, 3, 0),
    }
    base.update(overrides)
    return Scene(**base)


def _prop(entity_id: str = "prop-1", **overrides) -> Prop:
    base = {
        "id": entity_id,
        "project_id": "project-1",
        "name": "private prop name",
        "description": "private prop description",
        "prop_prompt": "private prop prompt",
        "created_at": datetime(2026, 6, 7, 20, 4, 0),
        "updated_at": datetime(2026, 6, 7, 20, 5, 0),
    }
    base.update(overrides)
    return Prop(**base)


def _frame(entity_id: str = "frame-1", **overrides) -> Frame:
    base = {
        "id": entity_id,
        "project_id": "project-1",
        "shot_id": "shot-1",
        "shot_number": 2,
        "prompt": "private frame prompt",
        "created_at": datetime(2026, 6, 7, 20, 6, 0),
        "updated_at": datetime(2026, 6, 7, 20, 7, 0),
    }
    base.update(overrides)
    return Frame(**base)


def _video(entity_id: str = "video-1", **overrides) -> Video:
    base = {
        "id": entity_id,
        "project_id": "project-1",
        "shot_id": "shot-1",
        "shot_number": 2,
        "first_frame_url": "https://private.example.test/frame.png",
        "prompt": "private video prompt",
        "video_url": "https://private.example.test/video.mp4",
        "task": VideoTask(task_id="private-provider-task", status=TaskStatus.PROCESSING),
        "created_at": datetime(2026, 6, 7, 20, 8, 0),
        "updated_at": datetime(2026, 6, 7, 20, 9, 0),
    }
    base.update(overrides)
    return Video(**base)


def _style(entity_id: str = "style-1", **overrides) -> Style:
    base = {
        "id": entity_id,
        "project_id": "project-1",
        "name": "private style name",
        "description": "private style description",
        "style_type": "text",
        "text_style_content": "{\"private\":\"style content\"}",
        "is_selected": True,
        "created_at": datetime(2026, 6, 7, 20, 10, 0),
        "updated_at": datetime(2026, 6, 7, 20, 11, 0),
    }
    base.update(overrides)
    return Style(**base)


class _ProjectEntityRepository:
    def __init__(self):
        self.entities = {}
        self.saved = []

    def save(self, entity_kind, entity):
        self.saved.append((entity_kind, entity.id))
        self.entities[(entity_kind, entity.id)] = entity

    def get(self, entity_kind, entity_id):
        return self.entities.get((entity_kind, entity_id))

    def list_for_project(self, entity_kind, project_id):
        return [
            entity
            for (kind, _), entity in self.entities.items()
            if kind == entity_kind and entity.project_id == project_id
        ]

    def list_all(self, entity_kind):
        return [
            entity
            for (kind, _), entity in self.entities.items()
            if kind == entity_kind
        ]

    def delete(self, entity_kind, entity_id):
        self.entities.pop((entity_kind, entity_id), None)

    def mark_deleted(self, entity_kind, entity_id):
        self.delete(entity_kind, entity_id)


class _RepositoryFactory:
    def __init__(self):
        self.repositories = {}

    def __call__(self, user_id):
        if user_id not in self.repositories:
            self.repositories[user_id] = _ProjectEntityRepository()
        return self.repositories[user_id]


def test_iter_project_entity_json_files_scans_all_editing_domains(tmp_path):
    _write_json(tmp_path, "user-a", "characters", _character("character-a"))
    _write_json(tmp_path, "user-a", "scenes", _scene("scene-a"))
    _write_json(tmp_path, "user-a", "props", _prop("prop-a"))
    _write_json(tmp_path, "user-b", "frames", _frame("frame-b"))
    _write_json(tmp_path, "user-b", "videos", _video("video-b"))
    _write_json(tmp_path, "user-b", "styles", _style("style-b"))
    (tmp_path / "users" / "user-b" / "characters").mkdir(parents=True, exist_ok=True)
    (tmp_path / "users" / "user-b" / "characters" / "broken.json").write_text(
        "{broken",
        encoding="utf-8",
    )

    records = list(iter_project_entity_json_files(tmp_path))

    assert [(record.user_id, record.entity_kind, record.entity.id) for record in records] == [
        ("user-a", CHARACTER, "character-a"),
        ("user-a", SCENE, "scene-a"),
        ("user-a", PROP, "prop-a"),
        ("user-b", FRAME, "frame-b"),
        ("user-b", VIDEO, "video-b"),
        ("user-b", STYLE, "style-b"),
    ]


def test_backfill_project_entities_upserts_json_without_private_payloads(tmp_path):
    _write_json(tmp_path, "user-a", "characters", _character("character-a"))
    _write_json(tmp_path, "user-a", "scenes", _scene("scene-a"))
    _write_json(tmp_path, "user-a", "props", _prop("prop-a"))
    _write_json(tmp_path, "user-a", "frames", _frame("frame-a"))
    _write_json(tmp_path, "user-a", "videos", _video("video-a"))
    _write_json(tmp_path, "user-a", "styles", _style("style-a"))
    factory = _RepositoryFactory()

    summary = backfill_project_entities(tmp_path, factory)

    assert summary["domain"] == "project_entities"
    assert summary["json_count"] == 6
    assert summary["upserted_count"] == 6
    assert summary["json_count_by_kind"] == {
        CHARACTER: 1,
        SCENE: 1,
        PROP: 1,
        FRAME: 1,
        VIDEO: 1,
        STYLE: 1,
    }
    assert summary["ok"] is True
    assert factory.repositories["user-a"].get(CHARACTER, "character-a").id == "character-a"
    assert factory.repositories["user-a"].get(STYLE, "style-a").id == "style-a"

    serialized = json.dumps(summary, ensure_ascii=False)
    assert "private" not in serialized
    assert "https://private" not in serialized
    assert "provider-task" not in serialized


def test_reconcile_project_entities_reports_safe_differences_without_private_payloads(tmp_path):
    _write_json(tmp_path, "user-a", "characters", _character("character-a"))
    _write_json(tmp_path, "user-a", "frames", _frame("missing-frame"))
    _write_json(tmp_path, "user-a", "videos", _video("video-a"))
    factory = _RepositoryFactory()
    repository = factory("user-a")
    repository.save(
        CHARACTER,
        _character(
            "character-a",
            updated_at=datetime(2026, 6, 7, 21, 1, 0),
        ),
    )
    repository.save(FRAME, _frame("missing-in-json"))
    repository.save(
        VIDEO,
        _video(
            "video-a",
            task=VideoTask(task_id="private-provider-task", status=TaskStatus.SUCCEEDED),
        ),
    )

    summary = reconcile_project_entities(tmp_path, factory)
    markdown = render_reconcile_markdown(summary)
    serialized = json.dumps(summary, ensure_ascii=False)

    assert summary["domain"] == "project_entities"
    assert summary["json_count"] == 3
    assert summary["postgres_count"] == 3
    assert summary["missing_in_postgres"] == [
        {"user_id": "user-a", "entity_kind": FRAME, "entity_id": "missing-frame"}
    ]
    assert summary["missing_in_json"] == [
        {"user_id": "user-a", "entity_kind": FRAME, "entity_id": "missing-in-json"}
    ]
    assert {diff["field"] for diff in summary["field_differences"]} == {
        "updated_at",
        "status",
    }
    assert summary["ok"] is False
    assert "private" not in serialized
    assert "https://private" not in serialized
    assert "provider-task" not in markdown
    assert "character-a" in markdown
