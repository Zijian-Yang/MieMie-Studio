"""Backfill project editing entity JSON files into PostgreSQL repositories."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

from app.models.character import Character
from app.models.frame import Frame
from app.models.prop import Prop
from app.models.scene import Scene
from app.models.style import Style
from app.models.video import Video
from app.repositories.base import ProjectEntityRepository
from app.repositories.project_entities import CHARACTER, FRAME, PROP, SCENE, STYLE, VIDEO


RepositoryFactory = Callable[[str], ProjectEntityRepository]
ProjectEntityItem = Character | Scene | Prop | Frame | Video | Style

ENTITY_DIRECTORIES: dict[str, str] = {
    CHARACTER: "characters",
    SCENE: "scenes",
    PROP: "props",
    FRAME: "frames",
    VIDEO: "videos",
    STYLE: "styles",
}
ENTITY_MODELS: dict[str, type[ProjectEntityItem]] = {
    CHARACTER: Character,
    SCENE: Scene,
    PROP: Prop,
    FRAME: Frame,
    VIDEO: Video,
    STYLE: Style,
}
ENTITY_ORDER = (CHARACTER, SCENE, PROP, FRAME, VIDEO, STYLE)


@dataclass(frozen=True)
class ProjectEntityJsonRecord:
    user_id: str
    entity_kind: str
    entity: ProjectEntityItem
    source_path: Path


def iter_project_entity_json_files(
    data_root: str | Path,
    *,
    on_error: Optional[Callable[[str, str, Path, Exception], None]] = None,
) -> Iterable[ProjectEntityJsonRecord]:
    """Yield valid per-user project editing entities from JSON directories."""

    users_dir = Path(data_root) / "users"
    if not users_dir.exists():
        return

    for user_dir in sorted(path for path in users_dir.iterdir() if path.is_dir()):
        for entity_kind in ENTITY_ORDER:
            entity_dir = user_dir / ENTITY_DIRECTORIES[entity_kind]
            if not entity_dir.exists():
                continue
            model = ENTITY_MODELS[entity_kind]
            for entity_path in sorted(entity_dir.glob("*.json")):
                try:
                    with entity_path.open("r", encoding="utf-8") as handle:
                        data = json.load(handle)
                    yield ProjectEntityJsonRecord(
                        user_id=user_dir.name,
                        entity_kind=entity_kind,
                        entity=model(**data),
                        source_path=entity_path,
                    )
                except Exception as exc:
                    if on_error:
                        on_error(user_dir.name, entity_kind, entity_path, exc)


def backfill_project_entities(
    data_root: str | Path,
    repository_factory: RepositoryFactory,
) -> dict:
    """Upsert all valid per-user project editing entity JSON into PostgreSQL."""

    failures: list[dict] = []
    scanned_users: set[str] = set()
    counts_by_kind = {entity_kind: 0 for entity_kind in ENTITY_ORDER}
    upserted_count = 0

    def record_load_failure(user_id: str, entity_kind: str, entity_path: Path, exc: Exception) -> None:
        failures.append(
            {
                "user_id": user_id,
                "entity_kind": entity_kind,
                "entity_file": entity_path.name,
                "error": exc.__class__.__name__,
            }
        )

    for record in iter_project_entity_json_files(data_root, on_error=record_load_failure):
        scanned_users.add(record.user_id)
        counts_by_kind[record.entity_kind] += 1
        try:
            repository_factory(record.user_id).save(record.entity_kind, record.entity)
            upserted_count += 1
        except Exception as exc:
            failures.append(
                {
                    "user_id": record.user_id,
                    "entity_kind": record.entity_kind,
                    "entity_id": record.entity.id,
                    "error": exc.__class__.__name__,
                }
            )

    json_count = sum(counts_by_kind.values())
    return {
        "domain": "project_entities",
        "scanned_users": sorted(scanned_users),
        "json_count": json_count,
        "json_count_by_kind": counts_by_kind,
        "upserted_count": upserted_count,
        "failed_count": len(failures),
        "failures": failures,
        "ok": len(failures) == 0,
    }


def write_backfill_summary(summary: dict, output_path: str | Path) -> Path:
    """Write a sanitized backfill summary JSON file."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return path
