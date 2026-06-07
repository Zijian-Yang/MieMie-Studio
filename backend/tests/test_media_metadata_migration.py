import json
from datetime import datetime

from app.models.gallery import GalleryImage
from app.models.media import AudioItem, TextItem, TextItemVersion, VideoItem
from app.services.migration.backfill_media_metadata import (
    backfill_media_metadata,
    iter_media_metadata_json_files,
)
from app.services.migration.reconcile_media_metadata import (
    reconcile_media_metadata,
    render_reconcile_markdown,
)


def _write_json(data_root, user_id: str, domain: str, item) -> None:
    item_dir = data_root / "users" / user_id / domain
    item_dir.mkdir(parents=True, exist_ok=True)
    with (item_dir / f"{item.id}.json").open("w", encoding="utf-8") as handle:
        json.dump(item.model_dump(mode="json"), handle, ensure_ascii=False)


def _gallery_image(image_id: str = "image-1", **overrides) -> GalleryImage:
    base = {
        "id": image_id,
        "project_id": "project-1",
        "name": "private gallery name",
        "description": "private gallery description",
        "url": "https://private.example.test/image.png",
        "prompt_used": "private image prompt",
        "source": "upload",
        "task_id": "task-1",
        "tags": ["private-tag"],
        "created_at": datetime(2026, 6, 7, 9, 0, 0),
        "updated_at": datetime(2026, 6, 7, 9, 1, 0),
    }
    base.update(overrides)
    return GalleryImage(**base)


def _audio_item(audio_id: str = "audio-1", **overrides) -> AudioItem:
    base = {
        "id": audio_id,
        "project_id": "project-1",
        "name": "private audio name",
        "description": "private audio description",
        "url": "https://private.example.test/audio.mp3",
        "file_type": "mp3",
        "file_size": 1234,
        "duration": 3.5,
        "sample_rate": 44100,
        "channels": 2,
        "created_at": datetime(2026, 6, 7, 9, 2, 0),
        "updated_at": datetime(2026, 6, 7, 9, 3, 0),
    }
    base.update(overrides)
    return AudioItem(**base)


def _video_item(video_id: str = "video-1", **overrides) -> VideoItem:
    base = {
        "id": video_id,
        "project_id": "project-1",
        "name": "private video name",
        "description": "private video description",
        "url": "https://private.example.test/video.mp4",
        "file_type": "mp4",
        "file_size": 5678,
        "duration": 5.0,
        "width": 1920,
        "height": 1080,
        "fps": 24,
        "thumbnail_url": "https://private.example.test/video.jpg",
        "created_at": datetime(2026, 6, 7, 9, 4, 0),
        "updated_at": datetime(2026, 6, 7, 9, 5, 0),
    }
    base.update(overrides)
    return VideoItem(**base)


def _text_item(text_id: str = "text-1", **overrides) -> TextItem:
    base = {
        "id": text_id,
        "project_id": "project-1",
        "name": "private text name",
        "content": "private text content",
        "category": "prompt",
        "versions": [
            TextItemVersion(
                id="version-1",
                content="private old content",
                description="private version description",
                created_at=datetime(2026, 6, 7, 8, 0, 0),
            )
        ],
        "created_at": datetime(2026, 6, 7, 9, 6, 0),
        "updated_at": datetime(2026, 6, 7, 9, 7, 0),
    }
    base.update(overrides)
    return TextItem(**base)


class _MediaRepository:
    def __init__(self):
        self.gallery_images = {}
        self.audio_items = {}
        self.video_items = {}

    def save_gallery_image(self, image):
        self.gallery_images[image.id] = image

    def save_audio_item(self, audio):
        self.audio_items[audio.id] = audio

    def save_video_item(self, video):
        self.video_items[video.id] = video

    def list_all_gallery_images(self):
        return list(self.gallery_images.values())

    def list_all_audio_items(self):
        return list(self.audio_items.values())

    def list_all_video_items(self):
        return list(self.video_items.values())


class _TextRepository:
    def __init__(self):
        self.items = {}

    def save(self, item):
        self.items[item.id] = item

    def list_all(self):
        return list(self.items.values())


class _RepositoryFactory:
    def __init__(self, repository_cls):
        self.repository_cls = repository_cls
        self.repositories = {}

    def __call__(self, user_id):
        if user_id not in self.repositories:
            self.repositories[user_id] = self.repository_cls()
        return self.repositories[user_id]


def test_iter_media_metadata_json_files_scans_all_library_domains(tmp_path):
    _write_json(tmp_path, "user-a", "gallery", _gallery_image("image-a"))
    _write_json(tmp_path, "user-a", "audio", _audio_item("audio-a"))
    _write_json(tmp_path, "user-b", "video_library", _video_item("video-b"))
    _write_json(tmp_path, "user-b", "text_library", _text_item("text-b"))
    (tmp_path / "users" / "user-b" / "gallery").mkdir(parents=True, exist_ok=True)
    (tmp_path / "users" / "user-b" / "gallery" / "broken.json").write_text(
        "{broken",
        encoding="utf-8",
    )

    records = list(iter_media_metadata_json_files(tmp_path))

    assert [(record.user_id, record.domain, record.item.id) for record in records] == [
        ("user-a", "gallery", "image-a"),
        ("user-a", "audio", "audio-a"),
        ("user-b", "video_library", "video-b"),
        ("user-b", "text_library", "text-b"),
    ]


def test_backfill_media_metadata_upserts_json_without_private_payloads(tmp_path):
    _write_json(tmp_path, "user-a", "gallery", _gallery_image("image-a"))
    _write_json(tmp_path, "user-a", "audio", _audio_item("audio-a"))
    _write_json(tmp_path, "user-a", "video_library", _video_item("video-a"))
    _write_json(tmp_path, "user-a", "text_library", _text_item("text-a"))
    media_factory = _RepositoryFactory(_MediaRepository)
    text_factory = _RepositoryFactory(_TextRepository)

    summary = backfill_media_metadata(tmp_path, media_factory, text_factory)

    assert summary["domain"] == "media_metadata"
    assert summary["json_count"] == 4
    assert summary["upserted_count"] == 4
    assert summary["json_count_by_domain"] == {
        "audio": 1,
        "gallery": 1,
        "text_library": 1,
        "video_library": 1,
    }
    assert summary["ok"] is True
    assert media_factory.repositories["user-a"].gallery_images["image-a"].id == "image-a"
    assert text_factory.repositories["user-a"].items["text-a"].id == "text-a"

    serialized = json.dumps(summary, ensure_ascii=False)
    assert "private" not in serialized
    assert "https://private" not in serialized


def test_reconcile_media_metadata_reports_safe_differences_without_private_payloads(tmp_path):
    _write_json(tmp_path, "user-a", "gallery", _gallery_image("image-a"))
    _write_json(tmp_path, "user-a", "audio", _audio_item("missing-audio"))
    _write_json(tmp_path, "user-a", "text_library", _text_item("text-a"))
    media_factory = _RepositoryFactory(_MediaRepository)
    text_factory = _RepositoryFactory(_TextRepository)
    media_repo = media_factory("user-a")
    text_repo = text_factory("user-a")
    media_repo.save_gallery_image(
        _gallery_image(
            "image-a",
            file_size=9999,
            updated_at=datetime(2026, 6, 7, 9, 9, 0),
        )
    )
    media_repo.save_video_item(_video_item("missing-video"))
    text_repo.save(_text_item("text-a", versions=[]))

    summary = reconcile_media_metadata(tmp_path, media_factory, text_factory)
    markdown = render_reconcile_markdown(summary)
    serialized = json.dumps(summary, ensure_ascii=False)

    assert summary["domain"] == "media_metadata"
    assert summary["json_count"] == 3
    assert summary["postgres_count"] == 3
    assert summary["missing_in_postgres"] == [
        {"user_id": "user-a", "domain": "audio", "item_id": "missing-audio"}
    ]
    assert summary["missing_in_json"] == [
        {"user_id": "user-a", "domain": "video_library", "item_id": "missing-video"}
    ]
    assert {diff["field"] for diff in summary["field_differences"]} == {
        "updated_at",
        "version_count",
    }
    assert summary["ok"] is False
    assert "private" not in serialized
    assert "https://private" not in serialized
    assert "private" not in markdown
    assert "image-a" in markdown
