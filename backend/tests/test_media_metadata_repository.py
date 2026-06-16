from datetime import datetime, timedelta

from app.models.gallery import GalleryImage
from app.models.media import AudioItem, TextItem, TextItemVersion, VideoItem
from app.repositories.media_assets import (
    FileMediaAssetRepository,
    FileTextItemRepository,
    audio_item_to_media_row,
    gallery_image_to_media_row,
    row_to_audio_item,
    row_to_gallery_image,
    row_to_text_item,
    row_to_video_item,
    text_item_to_row,
    video_item_to_media_row,
)
from app.services.storage import StorageService


def _gallery_image(image_id: str = "image-1") -> GalleryImage:
    return GalleryImage(
        id=image_id,
        project_id="project-1",
        name="cover",
        description="description",
        url="https://oss.example.test/image.png",
        prompt_used="draw a city",
        source="upload",
        task_id="task-1",
        tags=["cover", "city"],
        created_at=datetime(2026, 6, 7, 9, 0, 0),
        updated_at=datetime(2026, 6, 7, 9, 1, 0),
    )


def _audio_item(audio_id: str = "audio-1") -> AudioItem:
    return AudioItem(
        id=audio_id,
        project_id="project-1",
        name="voice",
        description="voice line",
        url="https://oss.example.test/voice.mp3",
        file_type="mp3",
        file_size=1234,
        duration=3.5,
        sample_rate=44100,
        channels=2,
        created_at=datetime(2026, 6, 7, 9, 2, 0),
        updated_at=datetime(2026, 6, 7, 9, 3, 0),
    )


def _video_item(video_id: str = "video-1") -> VideoItem:
    return VideoItem(
        id=video_id,
        project_id="project-1",
        name="clip",
        description="clip description",
        url="https://oss.example.test/clip.mp4",
        file_type="mp4",
        file_size=5678,
        duration=5.0,
        width=1920,
        height=1080,
        fps=24,
        thumbnail_url="https://oss.example.test/clip.jpg",
        created_at=datetime(2026, 6, 7, 9, 4, 0),
        updated_at=datetime(2026, 6, 7, 9, 5, 0),
    )


def _text_item(text_id: str = "text-1") -> TextItem:
    return TextItem(
        id=text_id,
        project_id="project-1",
        name="prompt",
        content="hello world",
        category="prompt",
        versions=[
            TextItemVersion(
                id="version-1",
                content="hello",
                description="initial",
                created_at=datetime(2026, 6, 7, 8, 0, 0),
            )
        ],
        created_at=datetime(2026, 6, 7, 9, 6, 0),
        updated_at=datetime(2026, 6, 7, 9, 7, 0),
    )


def test_media_row_mapping_keeps_shared_metadata_and_raw_snapshots():
    gallery = _gallery_image()
    audio = _audio_item()
    video = _video_item()

    gallery_row = gallery_image_to_media_row("user-1", gallery)
    audio_row = audio_item_to_media_row("user-1", audio)
    video_row = video_item_to_media_row("user-1", video)

    assert gallery_row["asset_kind"] == "gallery_image"
    assert gallery_row["url"] == gallery.url
    assert gallery_row["tags"] == ["cover", "city"]
    assert gallery_row["prompt_used"] == "draw a city"
    assert gallery_row["raw_media_snapshot"]["id"] == "image-1"
    assert row_to_gallery_image(gallery_row) == gallery

    assert audio_row["asset_kind"] == "audio"
    assert audio_row["sample_rate"] == 44100
    assert audio_row["channels"] == 2
    assert row_to_audio_item(audio_row) == audio

    assert video_row["asset_kind"] == "video"
    assert video_row["width"] == 1920
    assert video_row["height"] == 1080
    assert video_row["thumbnail_url"] == video.thumbnail_url
    assert row_to_video_item(video_row) == video


def test_text_row_mapping_keeps_content_versions_and_raw_snapshot():
    text = _text_item()

    row = text_item_to_row("user-1", text)

    assert row["id"] == "text-1"
    assert row["user_id"] == "user-1"
    assert row["category"] == "prompt"
    assert row["content"] == "hello world"
    assert row["version_count"] == 1
    assert row["raw_text_snapshot"]["versions"][0]["id"] == "version-1"
    assert row_to_text_item(row) == text


def test_file_media_asset_repository_preserves_storage_behavior(tmp_path):
    storage = StorageService(str(tmp_path))
    repo = FileMediaAssetRepository(storage)
    older = _gallery_image(
        "older",
    )
    older.created_at = datetime(2026, 6, 5, 9, 0, 0)
    newer = _gallery_image("newer")

    repo.save_gallery_image(older)
    repo.save_gallery_image(newer)

    assert repo.get_gallery_image("older").id == "older"
    assert repo.get_gallery_image("missing") is None
    assert [image.id for image in repo.list_gallery_images_for_project("project-1")] == [
        "newer",
        "older",
    ]

    repo.delete_gallery_image("older")

    assert repo.get_gallery_image("older") is None


def test_file_text_item_repository_preserves_storage_behavior(tmp_path):
    storage = StorageService(str(tmp_path))
    repo = FileTextItemRepository(storage)
    older = _text_item("older")
    older.created_at = datetime(2026, 6, 5, 9, 6, 0)
    newer = _text_item("newer")

    repo.save(newer)
    repo.save(older)

    assert repo.get("newer").id == "newer"
    assert repo.get("missing") is None
    assert [item.id for item in repo.list_for_project("project-1")] == ["newer", "older"]

    repo.delete("newer")

    assert repo.get("newer") is None
