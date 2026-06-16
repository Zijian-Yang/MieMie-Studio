from datetime import datetime, timedelta

from app.models.image_benchmark import ImageBenchmarkDataset, ImageBenchmarkRun, ImageBenchmarkSuite
from app.models.video_benchmark import VideoBenchmarkDataset, VideoBenchmarkRun, VideoBenchmarkSuite
from app.repositories.benchmark_records import (
    BENCHMARK_IMAGE,
    BENCHMARK_VIDEO,
    RECORD_DATASET,
    RECORD_RUN,
    RECORD_SUITE,
    FileBenchmarkRecordRepository,
    benchmark_record_to_row,
    row_to_benchmark_record,
)
from app.services.storage import StorageService


def _image_dataset(record_id: str = "image-dataset-1", **overrides) -> ImageBenchmarkDataset:
    base = {
        "id": record_id,
        "project_id": "project-1",
        "name": "image dataset",
        "description": "description",
        "task_kind": "text_to_image",
        "items": [
            {"id": "case-1", "name": "case", "prompt": "prompt", "sort_order": 1},
        ],
        "created_at": datetime(2026, 6, 7, 12, 0, 0),
        "updated_at": datetime(2026, 6, 7, 12, 1, 0),
    }
    base.update(overrides)
    return ImageBenchmarkDataset(**base)


def _image_suite(record_id: str = "image-suite-1", **overrides) -> ImageBenchmarkSuite:
    base = {
        "id": record_id,
        "project_id": "project-1",
        "name": "image suite",
        "dataset_id": "image-dataset-1",
        "task_kind": "text_to_image",
        "selected_models": ["wanx"],
        "status": "draft",
        "created_at": datetime(2026, 6, 7, 12, 2, 0),
        "updated_at": datetime(2026, 6, 7, 12, 3, 0),
    }
    base.update(overrides)
    return ImageBenchmarkSuite(**base)


def _image_run(record_id: str = "image-run-1", **overrides) -> ImageBenchmarkRun:
    base = {
        "id": record_id,
        "project_id": "project-1",
        "suite_id": "image-suite-1",
        "dataset_id": "image-dataset-1",
        "task_kind": "text_to_image",
        "status": "completed",
        "cell_results": [
            {"case_id": "case-1", "model_id": "wanx", "status": "completed"},
        ],
        "created_at": datetime(2026, 6, 7, 12, 4, 0),
        "updated_at": datetime(2026, 6, 7, 12, 5, 0),
        "started_at": datetime(2026, 6, 7, 12, 4, 30),
        "finished_at": datetime(2026, 6, 7, 12, 5, 30),
    }
    base.update(overrides)
    return ImageBenchmarkRun(**base)


def _video_dataset(record_id: str = "video-dataset-1", **overrides) -> VideoBenchmarkDataset:
    base = {
        "id": record_id,
        "project_id": "project-1",
        "name": "video dataset",
        "task_kind": "image_to_video",
        "items": [
            {"id": "case-1", "name": "case", "prompt": "prompt", "sort_order": 1},
            {"id": "case-2", "name": "case two", "prompt": "prompt two", "sort_order": 2},
        ],
        "created_at": datetime(2026, 6, 7, 12, 6, 0),
        "updated_at": datetime(2026, 6, 7, 12, 7, 0),
    }
    base.update(overrides)
    return VideoBenchmarkDataset(**base)


def _video_suite(record_id: str = "video-suite-1", **overrides) -> VideoBenchmarkSuite:
    base = {
        "id": record_id,
        "project_id": "project-1",
        "name": "video suite",
        "dataset_id": "video-dataset-1",
        "task_kind": "image_to_video",
        "selected_models": ["wanx2.1-i2v"],
        "status": "running",
        "created_at": datetime(2026, 6, 7, 12, 8, 0),
        "updated_at": datetime(2026, 6, 7, 12, 9, 0),
    }
    base.update(overrides)
    return VideoBenchmarkSuite(**base)


def _video_run(record_id: str = "video-run-1", **overrides) -> VideoBenchmarkRun:
    base = {
        "id": record_id,
        "project_id": "project-1",
        "suite_id": "video-suite-1",
        "dataset_id": "video-dataset-1",
        "task_kind": "image_to_video",
        "status": "running",
        "cell_results": [
            {"case_id": "case-1", "model_id": "wanx2.1-i2v", "status": "running"},
            {"case_id": "case-2", "model_id": "wanx2.1-i2v", "status": "pending"},
        ],
        "created_at": datetime(2026, 6, 7, 12, 10, 0),
        "updated_at": datetime(2026, 6, 7, 12, 11, 0),
        "started_at": datetime(2026, 6, 7, 12, 10, 30),
    }
    base.update(overrides)
    return VideoBenchmarkRun(**base)


def test_benchmark_record_row_mapping_keeps_safe_indexes_and_raw_snapshots():
    cases = [
        (BENCHMARK_IMAGE, RECORD_DATASET, _image_dataset(), {"item_count": 1, "cell_count": 0}),
        (BENCHMARK_IMAGE, RECORD_SUITE, _image_suite(), {"dataset_id": "image-dataset-1", "status": "draft"}),
        (BENCHMARK_IMAGE, RECORD_RUN, _image_run(), {"suite_id": "image-suite-1", "status": "completed", "cell_count": 1}),
        (BENCHMARK_VIDEO, RECORD_DATASET, _video_dataset(), {"item_count": 2, "cell_count": 0}),
        (BENCHMARK_VIDEO, RECORD_SUITE, _video_suite(), {"dataset_id": "video-dataset-1", "status": "running"}),
        (BENCHMARK_VIDEO, RECORD_RUN, _video_run(), {"suite_id": "video-suite-1", "status": "running", "cell_count": 2}),
    ]

    for benchmark_kind, record_kind, record, expected in cases:
        row = benchmark_record_to_row("user-1", benchmark_kind, record_kind, record)

        assert row["id"] == record.id
        assert row["benchmark_kind"] == benchmark_kind
        assert row["record_kind"] == record_kind
        assert row["user_id"] == "user-1"
        assert row["project_id"] == "project-1"
        assert row["task_kind"] == record.task_kind
        assert row["raw_record_snapshot"]["id"] == record.id
        assert row["raw_record_snapshot"]["updated_at"] == record.updated_at.isoformat()
        for key, value in expected.items():
            assert row[key] == value
        assert row_to_benchmark_record(row) == record


def test_file_benchmark_record_repository_preserves_storage_behavior(tmp_path):
    storage = StorageService(str(tmp_path))
    repo = FileBenchmarkRecordRepository(storage)
    older_run = _image_run("older-run", created_at=datetime(2026, 6, 5, 12, 4, 0))
    newer_run = _image_run("newer-run")

    repo.save(BENCHMARK_IMAGE, RECORD_DATASET, _image_dataset())
    repo.save(BENCHMARK_IMAGE, RECORD_SUITE, _image_suite())
    repo.save(BENCHMARK_IMAGE, RECORD_RUN, older_run)
    repo.save(BENCHMARK_IMAGE, RECORD_RUN, newer_run)
    repo.save(BENCHMARK_VIDEO, RECORD_DATASET, _video_dataset())
    repo.save(BENCHMARK_VIDEO, RECORD_SUITE, _video_suite())
    repo.save(BENCHMARK_VIDEO, RECORD_RUN, _video_run())

    assert repo.get(BENCHMARK_IMAGE, RECORD_DATASET, "image-dataset-1").id == "image-dataset-1"
    assert [item.id for item in repo.list_for_project(BENCHMARK_IMAGE, RECORD_DATASET, "project-1")] == [
        "image-dataset-1"
    ]
    assert repo.get(BENCHMARK_IMAGE, RECORD_SUITE, "image-suite-1").id == "image-suite-1"
    assert [item.id for item in repo.list_for_project(BENCHMARK_IMAGE, RECORD_SUITE, "project-1")] == [
        "image-suite-1"
    ]
    assert [item.id for item in repo.list_runs_for_suite(BENCHMARK_IMAGE, "image-suite-1")] == [
        "newer-run",
        "older-run",
    ]
    assert [item.id for item in repo.list_runs_for_project(BENCHMARK_IMAGE, "project-1")] == [
        "newer-run",
        "older-run",
    ]
    assert repo.get(BENCHMARK_VIDEO, RECORD_DATASET, "video-dataset-1").id == "video-dataset-1"
    assert repo.get(BENCHMARK_VIDEO, RECORD_SUITE, "video-suite-1").id == "video-suite-1"
    assert repo.get(BENCHMARK_VIDEO, RECORD_RUN, "video-run-1").id == "video-run-1"

    repo.delete(BENCHMARK_IMAGE, RECORD_DATASET, "image-dataset-1")
    repo.delete(BENCHMARK_VIDEO, RECORD_RUN, "video-run-1")

    assert repo.get(BENCHMARK_IMAGE, RECORD_DATASET, "image-dataset-1") is None
    assert repo.get(BENCHMARK_VIDEO, RECORD_RUN, "video-run-1") is None
