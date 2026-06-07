from datetime import datetime

import pytest

from app.models.image_benchmark import ImageBenchmarkDataset, ImageBenchmarkRun, ImageBenchmarkSuite
from app.models.video_benchmark import VideoBenchmarkDataset, VideoBenchmarkRun, VideoBenchmarkSuite
from app.repositories.benchmark_records import (
    BENCHMARK_IMAGE,
    BENCHMARK_VIDEO,
    RECORD_DATASET,
    RECORD_RUN,
    RECORD_SUITE,
)
from app.services.storage import StorageService


def _image_dataset(record_id: str = "image-dataset-1") -> ImageBenchmarkDataset:
    return ImageBenchmarkDataset(
        id=record_id,
        project_id="project-1",
        name="image dataset",
        task_kind="text_to_image",
        items=[{"id": "image-case-1", "name": "case", "prompt": "prompt", "sort_order": 1}],
        created_at=datetime(2026, 6, 7, 12, 0, 0),
        updated_at=datetime(2026, 6, 7, 12, 1, 0),
    )


def _image_suite(record_id: str = "image-suite-1") -> ImageBenchmarkSuite:
    return ImageBenchmarkSuite(
        id=record_id,
        project_id="project-1",
        name="image suite",
        dataset_id="image-dataset-1",
        task_kind="text_to_image",
        selected_models=["wanx"],
        status="draft",
        created_at=datetime(2026, 6, 7, 12, 2, 0),
        updated_at=datetime(2026, 6, 7, 12, 3, 0),
    )


def _image_run(record_id: str = "image-run-1") -> ImageBenchmarkRun:
    return ImageBenchmarkRun(
        id=record_id,
        project_id="project-1",
        suite_id="image-suite-1",
        dataset_id="image-dataset-1",
        task_kind="text_to_image",
        status="completed",
        cell_results=[{"case_id": "image-case-1", "model_id": "wanx", "status": "completed"}],
        created_at=datetime(2026, 6, 7, 12, 4, 0),
        updated_at=datetime(2026, 6, 7, 12, 5, 0),
        started_at=datetime(2026, 6, 7, 12, 4, 30),
        finished_at=datetime(2026, 6, 7, 12, 5, 30),
    )


def _video_dataset(record_id: str = "video-dataset-1") -> VideoBenchmarkDataset:
    return VideoBenchmarkDataset(
        id=record_id,
        project_id="project-1",
        name="video dataset",
        task_kind="image_to_video",
        items=[{"id": "video-case-1", "name": "case", "prompt": "prompt", "sort_order": 1}],
        created_at=datetime(2026, 6, 7, 12, 6, 0),
        updated_at=datetime(2026, 6, 7, 12, 7, 0),
    )


def _video_suite(record_id: str = "video-suite-1") -> VideoBenchmarkSuite:
    return VideoBenchmarkSuite(
        id=record_id,
        project_id="project-1",
        name="video suite",
        dataset_id="video-dataset-1",
        task_kind="image_to_video",
        selected_models=["wanx2.1-i2v"],
        status="running",
        created_at=datetime(2026, 6, 7, 12, 8, 0),
        updated_at=datetime(2026, 6, 7, 12, 9, 0),
    )


def _video_run(record_id: str = "video-run-1") -> VideoBenchmarkRun:
    return VideoBenchmarkRun(
        id=record_id,
        project_id="project-1",
        suite_id="video-suite-1",
        dataset_id="video-dataset-1",
        task_kind="image_to_video",
        status="running",
        cell_results=[{"case_id": "video-case-1", "model_id": "wanx2.1-i2v", "status": "running"}],
        created_at=datetime(2026, 6, 7, 12, 10, 0),
        updated_at=datetime(2026, 6, 7, 12, 11, 0),
        started_at=datetime(2026, 6, 7, 12, 10, 30),
    )


class _ShadowRepository:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.saved = []
        self.deleted = []

    def save(self, benchmark_kind, record_kind, record):
        if self.fail:
            raise RuntimeError("postgres unavailable")
        self.saved.append((benchmark_kind, record_kind, record.model_copy(deep=True)))

    def mark_deleted(self, benchmark_kind, record_kind, record_id):
        if self.fail:
            raise RuntimeError("postgres unavailable")
        self.deleted.append((benchmark_kind, record_kind, record_id))


def _enable_dual_write(monkeypatch, *, strict=False):
    monkeypatch.setenv("MIEMIE_DATABASE_ENABLED", "true")
    monkeypatch.setenv("MIEMIE_DATABASE_DUAL_WRITE_DOMAINS", "benchmark_records")
    monkeypatch.setenv("MIEMIE_DATABASE_WRITE_MODE", "file")
    monkeypatch.setenv("MIEMIE_DATABASE_RECONCILE_STRICT", "true" if strict else "false")


def _patch_shadow_repository(monkeypatch, shadow, seen_user_ids=None):
    if seen_user_ids is None:
        seen_user_ids = []
    monkeypatch.setattr(
        "app.repositories.benchmark_record_runtime.build_benchmark_record_shadow_repository",
        lambda user_id: seen_user_ids.append(user_id) or shadow,
    )
    return seen_user_ids


def _save_all(storage: StorageService) -> None:
    storage.save_image_benchmark_dataset(_image_dataset())
    storage.save_image_benchmark_suite(_image_suite())
    storage.save_image_benchmark_run(_image_run())
    storage.save_video_benchmark_dataset(_video_dataset())
    storage.save_video_benchmark_suite(_video_suite())
    storage.save_video_benchmark_run(_video_run())


def _delete_all(storage: StorageService) -> None:
    storage.delete_image_benchmark_dataset("image-dataset-1")
    storage.delete_image_benchmark_suite("image-suite-1")
    storage.delete_image_benchmark_run("image-run-1")
    storage.delete_video_benchmark_dataset("video-dataset-1")
    storage.delete_video_benchmark_suite("video-suite-1")
    storage.delete_video_benchmark_run("video-run-1")


def test_benchmark_record_dual_write_is_disabled_by_default(tmp_path, monkeypatch):
    shadow = _ShadowRepository()
    _patch_shadow_repository(monkeypatch, shadow)
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    _save_all(storage)
    _delete_all(storage)

    assert shadow.saved == []
    assert shadow.deleted == []


def test_benchmark_record_dual_write_saves_and_marks_deleted_when_enabled(tmp_path, monkeypatch):
    _enable_dual_write(monkeypatch)
    shadow = _ShadowRepository()
    seen_user_ids = _patch_shadow_repository(monkeypatch, shadow)
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    _save_all(storage)
    _delete_all(storage)

    assert seen_user_ids == ["user-1"] * 12
    assert [(benchmark, kind, record.id) for benchmark, kind, record in shadow.saved] == [
        (BENCHMARK_IMAGE, RECORD_DATASET, "image-dataset-1"),
        (BENCHMARK_IMAGE, RECORD_SUITE, "image-suite-1"),
        (BENCHMARK_IMAGE, RECORD_RUN, "image-run-1"),
        (BENCHMARK_VIDEO, RECORD_DATASET, "video-dataset-1"),
        (BENCHMARK_VIDEO, RECORD_SUITE, "video-suite-1"),
        (BENCHMARK_VIDEO, RECORD_RUN, "video-run-1"),
    ]
    assert shadow.saved[0][2].updated_at != datetime(2026, 6, 7, 12, 1, 0)
    assert shadow.deleted == [
        (BENCHMARK_IMAGE, RECORD_DATASET, "image-dataset-1"),
        (BENCHMARK_IMAGE, RECORD_SUITE, "image-suite-1"),
        (BENCHMARK_IMAGE, RECORD_RUN, "image-run-1"),
        (BENCHMARK_VIDEO, RECORD_DATASET, "video-dataset-1"),
        (BENCHMARK_VIDEO, RECORD_SUITE, "video-suite-1"),
        (BENCHMARK_VIDEO, RECORD_RUN, "video-run-1"),
    ]
    assert storage.get_image_benchmark_dataset("image-dataset-1") is None
    assert storage.get_video_benchmark_run("video-run-1") is None


def test_benchmark_record_shadow_failure_does_not_break_json_primary(tmp_path, monkeypatch):
    _enable_dual_write(monkeypatch)
    shadow = _ShadowRepository(fail=True)
    _patch_shadow_repository(monkeypatch, shadow)
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    storage.save_image_benchmark_dataset(_image_dataset())
    storage.save_video_benchmark_run(_video_run())

    assert storage.get_image_benchmark_dataset("image-dataset-1") is not None
    assert storage.get_video_benchmark_run("video-run-1") is not None


def test_benchmark_record_shadow_failure_can_be_strict(tmp_path, monkeypatch):
    _enable_dual_write(monkeypatch, strict=True)
    shadow = _ShadowRepository(fail=True)
    _patch_shadow_repository(monkeypatch, shadow)
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    with pytest.raises(RuntimeError, match="postgres unavailable"):
        storage.save_image_benchmark_dataset(_image_dataset())

    assert storage.get_image_benchmark_dataset("image-dataset-1") is not None
