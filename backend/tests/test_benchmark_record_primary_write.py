from datetime import datetime

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
        created_at=datetime(2026, 6, 7, 14, 0, 0),
        updated_at=datetime(2026, 6, 7, 14, 1, 0),
    )


def _image_suite(record_id: str = "image-suite-1") -> ImageBenchmarkSuite:
    return ImageBenchmarkSuite(
        id=record_id,
        project_id="project-1",
        name="image suite",
        dataset_id="image-dataset-1",
        task_kind="text_to_image",
        created_at=datetime(2026, 6, 7, 14, 2, 0),
        updated_at=datetime(2026, 6, 7, 14, 3, 0),
    )


def _image_run(record_id: str = "image-run-1") -> ImageBenchmarkRun:
    return ImageBenchmarkRun(
        id=record_id,
        project_id="project-1",
        suite_id="image-suite-1",
        dataset_id="image-dataset-1",
        task_kind="text_to_image",
        created_at=datetime(2026, 6, 7, 14, 4, 0),
        updated_at=datetime(2026, 6, 7, 14, 5, 0),
    )


def _video_dataset(record_id: str = "video-dataset-1") -> VideoBenchmarkDataset:
    return VideoBenchmarkDataset(
        id=record_id,
        project_id="project-1",
        name="video dataset",
        task_kind="image_to_video",
        created_at=datetime(2026, 6, 7, 14, 6, 0),
        updated_at=datetime(2026, 6, 7, 14, 7, 0),
    )


def _video_suite(record_id: str = "video-suite-1") -> VideoBenchmarkSuite:
    return VideoBenchmarkSuite(
        id=record_id,
        project_id="project-1",
        name="video suite",
        dataset_id="video-dataset-1",
        task_kind="image_to_video",
        created_at=datetime(2026, 6, 7, 14, 8, 0),
        updated_at=datetime(2026, 6, 7, 14, 9, 0),
    )


def _video_run(record_id: str = "video-run-1") -> VideoBenchmarkRun:
    return VideoBenchmarkRun(
        id=record_id,
        project_id="project-1",
        suite_id="video-suite-1",
        dataset_id="video-dataset-1",
        task_kind="image_to_video",
        created_at=datetime(2026, 6, 7, 14, 10, 0),
        updated_at=datetime(2026, 6, 7, 14, 11, 0),
    )


class _PrimaryRepository:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.saved = []
        self.deleted = []

    def _maybe_fail(self):
        if self.fail:
            raise RuntimeError("postgres benchmark primary unavailable")

    def save(self, benchmark_kind, record_kind, record):
        self._maybe_fail()
        self.saved.append((benchmark_kind, record_kind, record.model_copy(deep=True)))

    def mark_deleted(self, benchmark_kind, record_kind, record_id):
        self._maybe_fail()
        self.deleted.append((benchmark_kind, record_kind, record_id))


def _enable_primary_write(monkeypatch, *, archive=False):
    monkeypatch.setenv("MIEMIE_DATABASE_ENABLED", "true")
    monkeypatch.setenv("MIEMIE_DATABASE_WRITE_MODE", "file")
    monkeypatch.setenv("MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS", "benchmark_records")
    monkeypatch.setenv("MIEMIE_DATABASE_JSON_ARCHIVE_WRITES", "true" if archive else "false")


def _patch_primary_repository(monkeypatch, repository, seen_user_ids=None):
    if seen_user_ids is None:
        seen_user_ids = []
    monkeypatch.setattr(
        "app.repositories.benchmark_record_runtime.build_benchmark_record_primary_repository",
        lambda user_id: seen_user_ids.append(user_id) or repository,
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


def test_benchmark_record_primary_write_is_disabled_by_default(tmp_path, monkeypatch):
    primary = _PrimaryRepository()
    _patch_primary_repository(monkeypatch, primary)
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    storage.save_image_benchmark_dataset(_image_dataset())
    storage.save_video_benchmark_run(_video_run())

    assert primary.saved == []
    assert storage.get_image_benchmark_dataset("image-dataset-1") is not None
    assert storage.get_video_benchmark_run("video-run-1") is not None


def test_benchmark_record_primary_write_saves_postgres_without_json_archive(tmp_path, monkeypatch):
    _enable_primary_write(monkeypatch, archive=False)
    primary = _PrimaryRepository()
    seen_user_ids = _patch_primary_repository(monkeypatch, primary)
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    _save_all(storage)
    _delete_all(storage)

    assert seen_user_ids == ["user-1"] * 12
    assert [(benchmark, kind, record.id) for benchmark, kind, record in primary.saved] == [
        (BENCHMARK_IMAGE, RECORD_DATASET, "image-dataset-1"),
        (BENCHMARK_IMAGE, RECORD_SUITE, "image-suite-1"),
        (BENCHMARK_IMAGE, RECORD_RUN, "image-run-1"),
        (BENCHMARK_VIDEO, RECORD_DATASET, "video-dataset-1"),
        (BENCHMARK_VIDEO, RECORD_SUITE, "video-suite-1"),
        (BENCHMARK_VIDEO, RECORD_RUN, "video-run-1"),
    ]
    assert primary.saved[0][2].updated_at != datetime(2026, 6, 7, 14, 1, 0)
    assert primary.deleted == [
        (BENCHMARK_IMAGE, RECORD_DATASET, "image-dataset-1"),
        (BENCHMARK_IMAGE, RECORD_SUITE, "image-suite-1"),
        (BENCHMARK_IMAGE, RECORD_RUN, "image-run-1"),
        (BENCHMARK_VIDEO, RECORD_DATASET, "video-dataset-1"),
        (BENCHMARK_VIDEO, RECORD_SUITE, "video-suite-1"),
        (BENCHMARK_VIDEO, RECORD_RUN, "video-run-1"),
    ]
    assert storage.get_image_benchmark_dataset("image-dataset-1") is None
    assert storage.get_video_benchmark_run("video-run-1") is None


def test_benchmark_record_primary_write_can_keep_json_archive_mirror(tmp_path, monkeypatch):
    _enable_primary_write(monkeypatch, archive=True)
    primary = _PrimaryRepository()
    _patch_primary_repository(monkeypatch, primary)
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    storage.save_image_benchmark_dataset(_image_dataset())
    storage.save_video_benchmark_run(_video_run())
    assert storage.get_image_benchmark_dataset("image-dataset-1") is not None
    assert storage.get_video_benchmark_run("video-run-1") is not None

    storage.delete_image_benchmark_dataset("image-dataset-1")
    storage.delete_video_benchmark_run("video-run-1")

    assert primary.deleted == [
        (BENCHMARK_IMAGE, RECORD_DATASET, "image-dataset-1"),
        (BENCHMARK_VIDEO, RECORD_RUN, "video-run-1"),
    ]
    assert storage.get_image_benchmark_dataset("image-dataset-1") is None
    assert storage.get_video_benchmark_run("video-run-1") is None


def test_benchmark_record_primary_write_failure_does_not_write_json(tmp_path, monkeypatch):
    _enable_primary_write(monkeypatch, archive=True)
    primary = _PrimaryRepository(fail=True)
    _patch_primary_repository(monkeypatch, primary)
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    try:
        storage.save_image_benchmark_dataset(_image_dataset())
    except RuntimeError as exc:
        assert "postgres benchmark primary unavailable" in str(exc)
    else:
        raise AssertionError("PostgreSQL primary write failures should propagate")

    assert storage.get_image_benchmark_dataset("image-dataset-1") is None
