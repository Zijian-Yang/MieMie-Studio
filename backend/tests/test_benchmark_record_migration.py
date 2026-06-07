import json
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
from app.services.migration.backfill_benchmark_records import (
    backfill_benchmark_records,
    iter_benchmark_record_json_files,
)
from app.services.migration.reconcile_benchmark_records import (
    reconcile_benchmark_records,
    render_reconcile_markdown,
)


def _write_json(data_root, user_id: str, directory: str, record) -> None:
    record_dir = data_root / "users" / user_id / directory
    record_dir.mkdir(parents=True, exist_ok=True)
    with (record_dir / f"{record.id}.json").open("w", encoding="utf-8") as handle:
        json.dump(record.model_dump(mode="json"), handle, ensure_ascii=False)


def _image_dataset(record_id: str = "image-dataset-1", **overrides) -> ImageBenchmarkDataset:
    base = {
        "id": record_id,
        "project_id": "project-1",
        "name": "private image dataset",
        "description": "private image dataset description",
        "task_kind": "text_to_image",
        "items": [
            {
                "id": "case-1",
                "name": "private case",
                "prompt": "private prompt",
                "negative_prompt": "private negative",
                "sort_order": 1,
            }
        ],
        "created_at": datetime(2026, 6, 7, 13, 0, 0),
        "updated_at": datetime(2026, 6, 7, 13, 1, 0),
    }
    base.update(overrides)
    return ImageBenchmarkDataset(**base)


def _image_suite(record_id: str = "image-suite-1", **overrides) -> ImageBenchmarkSuite:
    base = {
        "id": record_id,
        "project_id": "project-1",
        "name": "private image suite",
        "description": "private suite description",
        "dataset_id": "image-dataset-1",
        "task_kind": "text_to_image",
        "selected_models": ["private-model"],
        "status": "draft",
        "created_at": datetime(2026, 6, 7, 13, 2, 0),
        "updated_at": datetime(2026, 6, 7, 13, 3, 0),
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
            {
                "case_id": "case-1",
                "case_name": "private case",
                "model_id": "private-model",
                "status": "completed",
                "request_ids": ["private-request-id"],
                "task_ids": ["private-task-id"],
                "canonical_request": {"prompt": "private prompt"},
                "provider_payload": {"api_key": "private-key", "prompt": "private prompt"},
            }
        ],
        "created_at": datetime(2026, 6, 7, 13, 4, 0),
        "updated_at": datetime(2026, 6, 7, 13, 5, 0),
    }
    base.update(overrides)
    return ImageBenchmarkRun(**base)


def _video_dataset(record_id: str = "video-dataset-1", **overrides) -> VideoBenchmarkDataset:
    base = {
        "id": record_id,
        "project_id": "project-1",
        "name": "private video dataset",
        "task_kind": "image_to_video",
        "items": [
            {
                "id": "case-1",
                "name": "private case",
                "prompt": "private video prompt",
                "first_frame": {"url": "https://private.example.test/frame.png"},
            }
        ],
        "created_at": datetime(2026, 6, 7, 13, 6, 0),
        "updated_at": datetime(2026, 6, 7, 13, 7, 0),
    }
    base.update(overrides)
    return VideoBenchmarkDataset(**base)


def _video_suite(record_id: str = "video-suite-1", **overrides) -> VideoBenchmarkSuite:
    base = {
        "id": record_id,
        "project_id": "project-1",
        "name": "private video suite",
        "dataset_id": "video-dataset-1",
        "task_kind": "image_to_video",
        "selected_models": ["private-video-model"],
        "status": "running",
        "created_at": datetime(2026, 6, 7, 13, 8, 0),
        "updated_at": datetime(2026, 6, 7, 13, 9, 0),
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
            {
                "case_id": "case-1",
                "case_name": "private case",
                "model_id": "private-video-model",
                "status": "running",
                "request_ids": ["private-video-request"],
                "task_ids": ["private-video-task"],
                "provider_payload": {"prompt": "private video prompt"},
            }
        ],
        "created_at": datetime(2026, 6, 7, 13, 10, 0),
        "updated_at": datetime(2026, 6, 7, 13, 11, 0),
    }
    base.update(overrides)
    return VideoBenchmarkRun(**base)


class _BenchmarkRecordRepository:
    def __init__(self):
        self.records = {}
        self.saved = []

    def save(self, benchmark_kind, record_kind, record):
        self.saved.append((benchmark_kind, record_kind, record.id))
        self.records[(benchmark_kind, record_kind, record.id)] = record

    def get(self, benchmark_kind, record_kind, record_id):
        return self.records.get((benchmark_kind, record_kind, record_id))

    def list_for_project(self, benchmark_kind, record_kind, project_id):
        return [
            record
            for (bench, kind, _), record in self.records.items()
            if bench == benchmark_kind and kind == record_kind and record.project_id == project_id
        ]

    def list_runs_for_suite(self, benchmark_kind, suite_id):
        return [
            record
            for (bench, kind, _), record in self.records.items()
            if bench == benchmark_kind and kind == RECORD_RUN and record.suite_id == suite_id
        ]

    def list_runs_for_project(self, benchmark_kind, project_id):
        return self.list_for_project(benchmark_kind, RECORD_RUN, project_id)

    def delete(self, benchmark_kind, record_kind, record_id):
        self.records.pop((benchmark_kind, record_kind, record_id), None)

    def mark_deleted(self, benchmark_kind, record_kind, record_id):
        self.delete(benchmark_kind, record_kind, record_id)


class _RepositoryFactory:
    def __init__(self):
        self.repositories = {}

    def __call__(self, user_id):
        if user_id not in self.repositories:
            self.repositories[user_id] = _BenchmarkRecordRepository()
        return self.repositories[user_id]


def test_iter_benchmark_record_json_files_scans_image_and_video_domains(tmp_path):
    _write_json(tmp_path, "user-a", "image_benchmark_datasets", _image_dataset("image-dataset-a"))
    _write_json(tmp_path, "user-a", "image_benchmark_suites", _image_suite("image-suite-a"))
    _write_json(tmp_path, "user-a", "image_benchmark_runs", _image_run("image-run-a"))
    _write_json(tmp_path, "user-b", "video_benchmark_datasets", _video_dataset("video-dataset-b"))
    _write_json(tmp_path, "user-b", "video_benchmark_suites", _video_suite("video-suite-b"))
    _write_json(tmp_path, "user-b", "video_benchmark_runs", _video_run("video-run-b"))
    broken_dir = tmp_path / "users" / "user-b" / "image_benchmark_runs"
    broken_dir.mkdir(parents=True, exist_ok=True)
    (broken_dir / "broken.json").write_text("{broken", encoding="utf-8")

    records = list(iter_benchmark_record_json_files(tmp_path))

    assert [(record.user_id, record.benchmark_kind, record.record_kind, record.record.id) for record in records] == [
        ("user-a", BENCHMARK_IMAGE, RECORD_DATASET, "image-dataset-a"),
        ("user-a", BENCHMARK_IMAGE, RECORD_SUITE, "image-suite-a"),
        ("user-a", BENCHMARK_IMAGE, RECORD_RUN, "image-run-a"),
        ("user-b", BENCHMARK_VIDEO, RECORD_DATASET, "video-dataset-b"),
        ("user-b", BENCHMARK_VIDEO, RECORD_SUITE, "video-suite-b"),
        ("user-b", BENCHMARK_VIDEO, RECORD_RUN, "video-run-b"),
    ]


def test_backfill_benchmark_records_upserts_json_without_private_payloads(tmp_path):
    _write_json(tmp_path, "user-a", "image_benchmark_datasets", _image_dataset())
    _write_json(tmp_path, "user-a", "image_benchmark_suites", _image_suite())
    _write_json(tmp_path, "user-a", "image_benchmark_runs", _image_run())
    _write_json(tmp_path, "user-a", "video_benchmark_datasets", _video_dataset())
    _write_json(tmp_path, "user-a", "video_benchmark_suites", _video_suite())
    _write_json(tmp_path, "user-a", "video_benchmark_runs", _video_run())
    factory = _RepositoryFactory()

    summary = backfill_benchmark_records(tmp_path, factory)

    assert summary["domain"] == "benchmark_records"
    assert summary["json_count"] == 6
    assert summary["upserted_count"] == 6
    assert summary["json_count_by_kind"] == {
        f"{BENCHMARK_IMAGE}:{RECORD_DATASET}": 1,
        f"{BENCHMARK_IMAGE}:{RECORD_SUITE}": 1,
        f"{BENCHMARK_IMAGE}:{RECORD_RUN}": 1,
        f"{BENCHMARK_VIDEO}:{RECORD_DATASET}": 1,
        f"{BENCHMARK_VIDEO}:{RECORD_SUITE}": 1,
        f"{BENCHMARK_VIDEO}:{RECORD_RUN}": 1,
    }
    assert summary["ok"] is True
    assert factory.repositories["user-a"].get(BENCHMARK_IMAGE, RECORD_DATASET, "image-dataset-1").id == "image-dataset-1"
    assert factory.repositories["user-a"].get(BENCHMARK_VIDEO, RECORD_RUN, "video-run-1").id == "video-run-1"

    serialized = json.dumps(summary, ensure_ascii=False)
    assert "private" not in serialized
    assert "prompt" not in serialized
    assert "request" not in serialized
    assert "task-id" not in serialized
    assert "https://" not in serialized


def test_reconcile_benchmark_records_reports_safe_differences_without_private_payloads(tmp_path):
    _write_json(tmp_path, "user-a", "image_benchmark_datasets", _image_dataset())
    _write_json(tmp_path, "user-a", "image_benchmark_runs", _image_run("missing-run"))
    _write_json(tmp_path, "user-a", "video_benchmark_runs", _video_run())
    factory = _RepositoryFactory()
    repository = factory("user-a")
    repository.save(
        BENCHMARK_IMAGE,
        RECORD_DATASET,
        _image_dataset(updated_at=datetime(2026, 6, 7, 14, 1, 0)),
    )
    repository.save(BENCHMARK_IMAGE, RECORD_RUN, _image_run("missing-in-json"))
    repository.save(
        BENCHMARK_VIDEO,
        RECORD_RUN,
        _video_run(status="completed"),
    )

    summary = reconcile_benchmark_records(tmp_path, factory)
    markdown = render_reconcile_markdown(summary)
    serialized = json.dumps(summary, ensure_ascii=False)

    assert summary["domain"] == "benchmark_records"
    assert summary["json_count"] == 3
    assert summary["postgres_count"] == 3
    assert summary["missing_in_postgres"] == [
        {
            "user_id": "user-a",
            "benchmark_kind": BENCHMARK_IMAGE,
            "record_kind": RECORD_RUN,
            "record_id": "missing-run",
        }
    ]
    assert summary["missing_in_json"] == [
        {
            "user_id": "user-a",
            "benchmark_kind": BENCHMARK_IMAGE,
            "record_kind": RECORD_RUN,
            "record_id": "missing-in-json",
        }
    ]
    assert {diff["field"] for diff in summary["field_differences"]} == {
        "updated_at",
        "status",
    }
    assert summary["ok"] is False
    assert "private" not in serialized
    assert "prompt" not in serialized
    assert "request" not in serialized
    assert "task-id" not in serialized
    assert "https://" not in serialized
    assert "private" not in markdown
    assert "prompt" not in markdown
