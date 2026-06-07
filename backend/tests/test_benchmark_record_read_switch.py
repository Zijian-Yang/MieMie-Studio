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


def _image_dataset(record_id: str, *, project_id: str = "project-1") -> ImageBenchmarkDataset:
    return ImageBenchmarkDataset(
        id=record_id,
        project_id=project_id,
        name=f"image dataset {record_id}",
        task_kind="text_to_image",
        items=[{"id": "image-case-1", "name": "case", "prompt": "prompt", "sort_order": 1}],
        created_at=datetime(2026, 6, 7, 13, 0, 0),
        updated_at=datetime(2026, 6, 7, 13, 1, 0),
    )


def _image_suite(record_id: str, *, project_id: str = "project-1") -> ImageBenchmarkSuite:
    return ImageBenchmarkSuite(
        id=record_id,
        project_id=project_id,
        name=f"image suite {record_id}",
        dataset_id="image-dataset-1",
        task_kind="text_to_image",
        selected_models=["wanx"],
        status="draft",
        created_at=datetime(2026, 6, 7, 13, 2, 0),
        updated_at=datetime(2026, 6, 7, 13, 3, 0),
    )


def _image_run(record_id: str, *, project_id: str = "project-1", suite_id: str = "image-suite-1") -> ImageBenchmarkRun:
    return ImageBenchmarkRun(
        id=record_id,
        project_id=project_id,
        suite_id=suite_id,
        dataset_id="image-dataset-1",
        task_kind="text_to_image",
        status="completed",
        cell_results=[{"case_id": "image-case-1", "model_id": "wanx", "status": "completed"}],
        created_at=datetime(2026, 6, 7, 13, 4, 0),
        updated_at=datetime(2026, 6, 7, 13, 5, 0),
    )


def _video_dataset(record_id: str, *, project_id: str = "project-1") -> VideoBenchmarkDataset:
    return VideoBenchmarkDataset(
        id=record_id,
        project_id=project_id,
        name=f"video dataset {record_id}",
        task_kind="image_to_video",
        items=[{"id": "video-case-1", "name": "case", "prompt": "prompt", "sort_order": 1}],
        created_at=datetime(2026, 6, 7, 13, 6, 0),
        updated_at=datetime(2026, 6, 7, 13, 7, 0),
    )


def _video_suite(record_id: str, *, project_id: str = "project-1") -> VideoBenchmarkSuite:
    return VideoBenchmarkSuite(
        id=record_id,
        project_id=project_id,
        name=f"video suite {record_id}",
        dataset_id="video-dataset-1",
        task_kind="image_to_video",
        selected_models=["wanx2.1-i2v"],
        status="running",
        created_at=datetime(2026, 6, 7, 13, 8, 0),
        updated_at=datetime(2026, 6, 7, 13, 9, 0),
    )


def _video_run(record_id: str, *, project_id: str = "project-1", suite_id: str = "video-suite-1") -> VideoBenchmarkRun:
    return VideoBenchmarkRun(
        id=record_id,
        project_id=project_id,
        suite_id=suite_id,
        dataset_id="video-dataset-1",
        task_kind="image_to_video",
        status="running",
        cell_results=[{"case_id": "video-case-1", "model_id": "wanx2.1-i2v", "status": "running"}],
        created_at=datetime(2026, 6, 7, 13, 10, 0),
        updated_at=datetime(2026, 6, 7, 13, 11, 0),
    )


class _ReadRepository:
    def __init__(self, records=None, *, fail=False):
        self.records = {
            (benchmark_kind, record_kind, record.id): record
            for benchmark_kind, record_kind, record in (records or [])
        }
        self.fail = fail
        self.calls = []

    def _maybe_fail(self):
        if self.fail:
            raise RuntimeError("postgres benchmark read unavailable")

    def get(self, benchmark_kind, record_kind, record_id):
        self.calls.append(("get", benchmark_kind, record_kind, record_id))
        self._maybe_fail()
        return self.records.get((benchmark_kind, record_kind, record_id))

    def list_for_project(self, benchmark_kind, record_kind, project_id):
        self.calls.append(("list_for_project", benchmark_kind, record_kind, project_id))
        self._maybe_fail()
        return [
            record
            for (benchmark, kind, _), record in self.records.items()
            if benchmark == benchmark_kind and kind == record_kind and record.project_id == project_id
        ]

    def list_runs_for_suite(self, benchmark_kind, suite_id):
        self.calls.append(("list_runs_for_suite", benchmark_kind, suite_id))
        self._maybe_fail()
        return [
            record
            for (benchmark, kind, _), record in self.records.items()
            if benchmark == benchmark_kind and kind == RECORD_RUN and record.suite_id == suite_id
        ]


def _enable_read_switch(monkeypatch, *, fallback=True):
    monkeypatch.setenv("MIEMIE_DATABASE_ENABLED", "true")
    monkeypatch.setenv("MIEMIE_DATABASE_READ_DOMAINS", "benchmark_records")
    monkeypatch.setenv("MIEMIE_DATABASE_READ_MODE", "file")
    monkeypatch.setenv("MIEMIE_DATABASE_JSON_FALLBACK_READ", "true" if fallback else "false")


def _patch_read_repository(monkeypatch, repository):
    monkeypatch.setattr(
        "app.repositories.benchmark_record_runtime.build_benchmark_record_read_repository",
        lambda user_id: repository,
    )


def test_benchmark_record_reads_are_file_only_by_default(tmp_path, monkeypatch):
    repository = _ReadRepository([(BENCHMARK_IMAGE, RECORD_DATASET, _image_dataset("pg-image-dataset"))])
    _patch_read_repository(monkeypatch, repository)
    storage = StorageService(str(tmp_path), owner_user_id="user-1")
    storage.save_image_benchmark_dataset(_image_dataset("json-image-dataset"))
    storage.save_image_benchmark_run(_image_run("json-image-run"))

    assert storage.get_image_benchmark_dataset("json-image-dataset").id == "json-image-dataset"
    assert [item.id for item in storage.get_image_benchmark_datasets("project-1")] == ["json-image-dataset"]
    assert [item.id for item in storage.get_image_benchmark_runs_by_suite("image-suite-1")] == ["json-image-run"]
    assert repository.calls == []


def test_benchmark_record_read_switch_uses_postgres_for_get_and_lists(tmp_path, monkeypatch):
    _enable_read_switch(monkeypatch)
    repository = _ReadRepository(
        [
            (BENCHMARK_IMAGE, RECORD_DATASET, _image_dataset("pg-image-dataset")),
            (BENCHMARK_IMAGE, RECORD_SUITE, _image_suite("pg-image-suite")),
            (BENCHMARK_IMAGE, RECORD_RUN, _image_run("pg-image-run")),
            (BENCHMARK_VIDEO, RECORD_DATASET, _video_dataset("pg-video-dataset")),
            (BENCHMARK_VIDEO, RECORD_SUITE, _video_suite("pg-video-suite")),
            (BENCHMARK_VIDEO, RECORD_RUN, _video_run("pg-video-run")),
        ]
    )
    _patch_read_repository(monkeypatch, repository)
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    assert storage.get_image_benchmark_dataset("pg-image-dataset").id == "pg-image-dataset"
    assert [item.id for item in storage.get_image_benchmark_datasets("project-1")] == ["pg-image-dataset"]
    assert storage.get_image_benchmark_suite("pg-image-suite").id == "pg-image-suite"
    assert [item.id for item in storage.get_image_benchmark_suites("project-1")] == ["pg-image-suite"]
    assert storage.get_image_benchmark_run("pg-image-run").id == "pg-image-run"
    assert [item.id for item in storage.get_image_benchmark_runs_by_project("project-1")] == ["pg-image-run"]
    assert [item.id for item in storage.get_image_benchmark_runs_by_suite("image-suite-1")] == ["pg-image-run"]
    assert storage.get_video_benchmark_dataset("pg-video-dataset").id == "pg-video-dataset"
    assert [item.id for item in storage.get_video_benchmark_datasets("project-1")] == ["pg-video-dataset"]
    assert storage.get_video_benchmark_suite("pg-video-suite").id == "pg-video-suite"
    assert [item.id for item in storage.get_video_benchmark_suites("project-1")] == ["pg-video-suite"]
    assert storage.get_video_benchmark_run("pg-video-run").id == "pg-video-run"
    assert [item.id for item in storage.get_video_benchmark_runs_by_project("project-1")] == ["pg-video-run"]
    assert [item.id for item in storage.get_video_benchmark_runs_by_suite("video-suite-1")] == ["pg-video-run"]


def test_benchmark_record_read_switch_falls_back_to_json_on_miss_or_empty_list(tmp_path, monkeypatch):
    _enable_read_switch(monkeypatch)
    repository = _ReadRepository()
    _patch_read_repository(monkeypatch, repository)
    storage = StorageService(str(tmp_path), owner_user_id="user-1")
    storage.save_image_benchmark_dataset(_image_dataset("json-image-dataset"))
    storage.save_image_benchmark_run(_image_run("json-image-run"))
    storage.save_video_benchmark_dataset(_video_dataset("json-video-dataset"))
    storage.save_video_benchmark_run(_video_run("json-video-run"))

    assert storage.get_image_benchmark_dataset("json-image-dataset").id == "json-image-dataset"
    assert [item.id for item in storage.get_image_benchmark_datasets("project-1")] == ["json-image-dataset"]
    assert [item.id for item in storage.get_image_benchmark_runs_by_suite("image-suite-1")] == ["json-image-run"]
    assert storage.get_video_benchmark_dataset("json-video-dataset").id == "json-video-dataset"
    assert [item.id for item in storage.get_video_benchmark_datasets("project-1")] == ["json-video-dataset"]
    assert [item.id for item in storage.get_video_benchmark_runs_by_suite("video-suite-1")] == ["json-video-run"]


def test_benchmark_record_read_switch_raises_when_fallback_disabled(tmp_path, monkeypatch):
    _enable_read_switch(monkeypatch, fallback=False)
    repository = _ReadRepository(fail=True)
    _patch_read_repository(monkeypatch, repository)
    storage = StorageService(str(tmp_path), owner_user_id="user-1")
    storage.save_image_benchmark_dataset(_image_dataset("json-image-dataset"))

    try:
        storage.get_image_benchmark_dataset("json-image-dataset")
    except RuntimeError as exc:
        assert "postgres benchmark read unavailable" in str(exc)
    else:
        raise AssertionError("PostgreSQL read errors should propagate when fallback is disabled")
