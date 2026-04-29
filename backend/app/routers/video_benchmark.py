"""
视频测评与数据集 API
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from app.config import get_user_config_dir, set_user_config_dir
from app.models.video_benchmark import (
    VideoBenchmarkCellResult,
    VideoBenchmarkDataset,
    VideoBenchmarkDatasetItem,
    VideoBenchmarkMediaAsset,
    VideoBenchmarkRun,
    VideoBenchmarkSuite,
)
from app.services.storage import get_current_user_id, set_current_user, storage_service
from app.services.video_benchmark_runtime import (
    VIDEO_BENCHMARK_TASK_KIND,
    execute_video_benchmark_cell,
    export_dataset_payload,
    get_video_benchmark_capabilities,
    merge_effective_params,
    preview_video_benchmark_cell,
    render_html_report,
    render_markdown_report,
)


router = APIRouter()

VIDEO_BENCHMARK_TERMINAL_CELL_STATUSES = {"completed", "failed", "unsupported", "skipped"}
_video_benchmark_run_locks: Dict[str, asyncio.Lock] = {}


class MediaAssetInput(BaseModel):
    url: str
    name: str = ""
    mime_type: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[float] = None
    source_label: Optional[str] = None


class DatasetItemInput(BaseModel):
    id: Optional[str] = None
    name: str = ""
    prompt: str = ""
    negative_prompt: str = ""
    tags: List[str] = []
    first_frame: Optional[MediaAssetInput] = None
    audio: Optional[MediaAssetInput] = None
    duration: Optional[int] = None


class DatasetCreateRequest(BaseModel):
    project_id: str
    name: str
    description: str = ""
    task_kind: str = VIDEO_BENCHMARK_TASK_KIND
    items: List[DatasetItemInput] = []


class DatasetUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    items: Optional[List[DatasetItemInput]] = None


class DatasetImportRequest(BaseModel):
    project_id: str
    data: Dict[str, Any]
    name: Optional[str] = None
    description: Optional[str] = None


class SuiteCreateRequest(BaseModel):
    project_id: str
    name: str
    description: str = ""
    dataset_id: str
    selected_models: List[str] = []
    baseline_params: Dict[str, Any] = {}
    model_overrides: Dict[str, Dict[str, Any]] = {}


class SuiteUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    dataset_id: Optional[str] = None
    selected_models: Optional[List[str]] = None
    baseline_params: Optional[Dict[str, Any]] = None
    model_overrides: Optional[Dict[str, Dict[str, Any]]] = None


class PreviewCellRequest(BaseModel):
    project_id: str
    task_kind: str = VIDEO_BENCHMARK_TASK_KIND
    model_id: str
    case_data: DatasetItemInput
    baseline_params: Dict[str, Any] = {}
    override_params: Dict[str, Any] = {}


def _report_download_response(filename: str, content: str, media_type: str) -> Response:
    ascii_filename = filename.encode("ascii", "ignore").decode("ascii") or "video_benchmark_report"
    encoded_filename = quote(filename)
    return Response(
        content=content.encode("utf-8"),
        media_type=f"{media_type}; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=\"{ascii_filename}\"; filename*=UTF-8''{encoded_filename}",
        },
    )


def _ensure_project_exists(project_id: str) -> None:
    if not storage_service.get_project(project_id):
        raise HTTPException(status_code=404, detail="项目不存在")


def _normalize_media_asset(value: Optional[MediaAssetInput]) -> Optional[VideoBenchmarkMediaAsset]:
    if not value or not value.url:
        return None
    return VideoBenchmarkMediaAsset(**value.model_dump())


def _normalize_dataset_items(items: List[DatasetItemInput]) -> List[VideoBenchmarkDatasetItem]:
    normalized: List[VideoBenchmarkDatasetItem] = []
    for index, item in enumerate(items):
        first_frame = _normalize_media_asset(item.first_frame)
        if item.duration is not None and item.duration <= 0:
            raise HTTPException(status_code=400, detail="样例时长必须为正整数")
        normalized.append(
            VideoBenchmarkDatasetItem(
                id=item.id or VideoBenchmarkDatasetItem().id,
                name=item.name,
                prompt=item.prompt,
                negative_prompt=item.negative_prompt,
                tags=item.tags,
                sort_order=index,
                first_frame=first_frame,
                audio=_normalize_media_asset(item.audio),
                duration=item.duration,
            )
        )
    return normalized


def _analyze_dataset(dataset: VideoBenchmarkDataset) -> Dict[str, List[Dict[str, Any]]]:
    warnings: List[Dict[str, Any]] = []
    blocking_issues: List[Dict[str, Any]] = []
    for item in dataset.items:
        if item.first_frame and item.first_frame.url:
            continue
        item_name = item.name or f"样例 {item.sort_order + 1}"
        issue = {
            "item_id": item.id,
            "item_name": item_name,
            "missing_fields": ["first_frame"],
            "message": "缺首帧图，无法开始首帧生视频测评",
        }
        warnings.append(issue)
        blocking_issues.append(issue)
    return {"warnings": warnings, "blocking_issues": blocking_issues}


def _dataset_response(dataset: VideoBenchmarkDataset) -> Dict[str, Any]:
    validation = _analyze_dataset(dataset)
    return {
        "dataset": dataset,
        "warnings": validation["warnings"],
        "blocking_issues": validation["blocking_issues"],
    }


def _cell_key(case_id: str, model_id: str) -> str:
    return f"{case_id}__{model_id}"


def _get_video_run_lock(run_id: str) -> asyncio.Lock:
    lock = _video_benchmark_run_locks.get(run_id)
    if lock is None:
        lock = asyncio.Lock()
        _video_benchmark_run_locks[run_id] = lock
    return lock


def _ordered_video_dataset_items(run: VideoBenchmarkRun) -> List[Dict[str, Any]]:
    return sorted(
        (run.dataset_snapshot or {}).get("items") or [],
        key=lambda item: item.get("sort_order", 0),
    )


def _pending_video_cell(case_data: Dict[str, Any], model_meta: Dict[str, Any], status: str = "pending") -> VideoBenchmarkCellResult:
    return VideoBenchmarkCellResult(
        case_id=case_data.get("id") or "",
        case_name=case_data.get("name") or "",
        model_id=model_meta["id"],
        model_name=model_meta.get("name") or model_meta["id"],
        status=status,
    )


def _ordered_video_cells(
    run: VideoBenchmarkRun,
    cell_map: Dict[str, VideoBenchmarkCellResult],
) -> List[VideoBenchmarkCellResult]:
    ordered_cells: List[VideoBenchmarkCellResult] = []
    for case_data in _ordered_video_dataset_items(run):
        for model_meta in run.model_snapshots or []:
            cell = cell_map.get(_cell_key(case_data.get("id", ""), model_meta["id"]))
            if cell:
                ordered_cells.append(cell)
    return ordered_cells


def _video_run_stats(run: VideoBenchmarkRun, cells: List[VideoBenchmarkCellResult]) -> Dict[str, Any]:
    pending_count = sum(1 for cell in cells if cell.status == "pending")
    running_count = sum(1 for cell in cells if cell.status == "running")
    completed_count = sum(1 for cell in cells if cell.status == "completed")
    failure_count = sum(1 for cell in cells if cell.status == "failed")
    unsupported_count = sum(1 for cell in cells if cell.status == "unsupported")
    skipped_count = sum(1 for cell in cells if cell.status == "skipped")
    return {
        "case_count": len(_ordered_video_dataset_items(run)),
        "model_count": len(run.model_snapshots or []),
        "cell_count": len(cells),
        "pending_count": pending_count,
        "running_count": running_count,
        "completed_count": completed_count,
        "success_count": completed_count,
        "failure_count": failure_count,
        "unsupported_count": unsupported_count,
        "skipped_count": skipped_count,
        "retried_failure_count": len(run.retry_targets or []),
    }


def _refresh_video_run_status(run: VideoBenchmarkRun) -> VideoBenchmarkRun:
    run.stats = _video_run_stats(run, run.cell_results or [])
    active_count = (run.stats.get("pending_count") or 0) + (run.stats.get("running_count") or 0)
    if active_count > 0:
        run.status = "running"
        run.finished_at = None
    else:
        success_count = run.stats.get("success_count") or 0
        failure_count = run.stats.get("failure_count") or 0
        run.status = "failed" if run.cell_results and success_count == 0 and failure_count > 0 else "completed"
        run.finished_at = run.finished_at or datetime.now()
    run.updated_at = datetime.now()
    return run


def _initial_video_cells(
    dataset_items: List[Dict[str, Any]],
    model_snapshots: List[Dict[str, Any]],
    *,
    retry_target_keys: Optional[set[str]] = None,
    preserved_cells: Optional[List[VideoBenchmarkCellResult]] = None,
) -> List[VideoBenchmarkCellResult]:
    preserved_map = {
        _cell_key(cell.case_id, cell.model_id): cell
        for cell in preserved_cells or []
    }
    cells: List[VideoBenchmarkCellResult] = []
    for case_data in dataset_items:
        for model_meta in model_snapshots:
            key = _cell_key(case_data.get("id", ""), model_meta["id"])
            if retry_target_keys is not None and key not in retry_target_keys:
                cells.append(preserved_map.get(key) or _pending_video_cell(case_data, model_meta, status="skipped"))
                continue
            cells.append(_pending_video_cell(case_data, model_meta))
    return cells


async def _save_video_run_cell(run_id: str, cell: VideoBenchmarkCellResult) -> Optional[VideoBenchmarkRun]:
    async with _get_video_run_lock(run_id):
        run = storage_service.get_video_benchmark_run(run_id)
        if not run:
            return None
        cell_map = {
            _cell_key(existing.case_id, existing.model_id): existing
            for existing in run.cell_results or []
        }
        key = _cell_key(cell.case_id, cell.model_id)
        existing_cell = cell_map.get(key)
        if existing_cell:
            cell.id = existing_cell.id
            cell.created_at = existing_cell.created_at
        cell.updated_at = datetime.now()
        cell_map[key] = cell
        run.cell_results = _ordered_video_cells(run, cell_map)
        _refresh_video_run_status(run)
        storage_service.save_video_benchmark_run(run)
        return run


async def _validate_suite_payload(
    *,
    project_id: str,
    dataset_id: str,
    selected_models: List[str],
) -> tuple[VideoBenchmarkDataset, Dict[str, Any]]:
    _ensure_project_exists(project_id)
    dataset = storage_service.get_video_benchmark_dataset(dataset_id)
    if not dataset or dataset.project_id != project_id:
        raise HTTPException(status_code=404, detail="视频数据集不存在")
    capabilities = await get_video_benchmark_capabilities()
    model_lookup = capabilities["models"]
    for model_id in selected_models:
        model_meta = model_lookup.get(model_id)
        if not model_meta:
            raise HTTPException(status_code=400, detail=f"未知模型或模型不支持首帧生视频：{model_id}")
        if VIDEO_BENCHMARK_TASK_KIND not in (model_meta.get("supported_task_kinds") or []):
            raise HTTPException(status_code=400, detail=f"模型 {model_id} 不支持首帧生视频")
    return dataset, model_lookup


async def _background_run_suite(run_id: str, suite_id: str, user_id: Optional[str], user_config_dir: Optional[str]) -> None:
    set_current_user(user_id)
    set_user_config_dir(user_config_dir)

    run = storage_service.get_video_benchmark_run(run_id)
    suite = storage_service.get_video_benchmark_suite(suite_id)
    if not run or not suite:
        return

    try:
        run.status = "running"
        run.started_at = run.started_at or datetime.now()
        storage_service.save_video_benchmark_run(run)

        dataset_items = sorted(
            (run.dataset_snapshot or {}).get("items") or [],
            key=lambda item: item.get("sort_order", 0),
        )
        model_snapshots = run.model_snapshots or []
        retry_target_keys = {
            _cell_key(item.get("case_id", ""), item.get("model_id", ""))
            for item in run.retry_targets
            if item.get("case_id") and item.get("model_id")
        }
        async def run_cell(index: int, case_data: Dict[str, Any], model_meta: Dict[str, Any]):
            effective_params = merge_effective_params(
                model_meta,
                run.baseline_params,
                (run.model_overrides or {}).get(model_meta["id"]),
                case_data,
            )
            await _save_video_run_cell(
                run_id,
                VideoBenchmarkCellResult(
                    case_id=case_data.get("id") or "",
                    case_name=case_data.get("name") or "",
                    model_id=model_meta["id"],
                    model_name=model_meta.get("name") or model_meta["id"],
                    status="running",
                    effective_params=effective_params,
                ),
            )

            async def save_progress(cell: VideoBenchmarkCellResult) -> None:
                await _save_video_run_cell(run_id, cell)

            cell = await execute_video_benchmark_cell(
                project_id=run.project_id,
                model_meta=model_meta,
                case_data=case_data,
                effective_params=effective_params,
                on_progress=save_progress,
            )
            await _save_video_run_cell(run_id, cell)
            return index, cell

        tasks = []
        index = 0
        for case_data in dataset_items:
            for model_meta in model_snapshots:
                key = _cell_key(case_data.get("id", ""), model_meta["id"])
                if retry_target_keys and key not in retry_target_keys:
                    index += 1
                    continue
                tasks.append(run_cell(index, case_data, model_meta))
                index += 1

        await asyncio.gather(*tasks) if tasks else []
        run = storage_service.get_video_benchmark_run(run_id)
        if not run:
            return
        _refresh_video_run_status(run)
        storage_service.save_video_benchmark_run(run)

        suite.status = "failed" if run.status == "failed" else "completed"
        suite.latest_run_id = run.id
        suite.latest_run_snapshot = {
            "dataset_snapshot": run.dataset_snapshot,
            "model_snapshots": run.model_snapshots,
            "baseline_params": run.baseline_params,
            "model_overrides": run.model_overrides,
            "run_id": run.id,
        }
        storage_service.save_video_benchmark_suite(suite)
    except Exception as exc:
        run.status = "failed"
        run.finished_at = datetime.now()
        run.stats = {
            "case_count": len((run.dataset_snapshot or {}).get("items") or []),
            "model_count": len(run.model_snapshots or []),
            "cell_count": len(run.cell_results or []),
            "error": str(exc),
        }
        storage_service.save_video_benchmark_run(run)
        suite.status = "failed"
        storage_service.save_video_benchmark_suite(suite)
    finally:
        _video_benchmark_run_locks.pop(run_id, None)


@router.get("/capabilities")
async def get_capabilities():
    return await get_video_benchmark_capabilities()


@router.get("/datasets")
async def list_datasets(project_id: str):
    _ensure_project_exists(project_id)
    return {"datasets": storage_service.get_video_benchmark_datasets(project_id)}


@router.post("/datasets")
async def create_dataset(request: DatasetCreateRequest):
    _ensure_project_exists(request.project_id)
    if request.task_kind != VIDEO_BENCHMARK_TASK_KIND:
        raise HTTPException(status_code=400, detail="视频测评 v1 仅支持 image_to_video")
    dataset = VideoBenchmarkDataset(
        project_id=request.project_id,
        name=request.name,
        description=request.description,
        items=_normalize_dataset_items(request.items),
    )
    storage_service.save_video_benchmark_dataset(dataset)
    return _dataset_response(dataset)


@router.get("/datasets/{dataset_id}")
async def get_dataset(dataset_id: str):
    dataset = storage_service.get_video_benchmark_dataset(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="视频数据集不存在")
    return _dataset_response(dataset)


@router.put("/datasets/{dataset_id}")
async def update_dataset(dataset_id: str, request: DatasetUpdateRequest):
    dataset = storage_service.get_video_benchmark_dataset(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="视频数据集不存在")
    if request.name is not None:
        dataset.name = request.name
    if request.description is not None:
        dataset.description = request.description
    if request.items is not None:
        dataset.items = _normalize_dataset_items(request.items)
    storage_service.save_video_benchmark_dataset(dataset)
    return _dataset_response(dataset)


@router.delete("/datasets/{dataset_id}")
async def delete_dataset(dataset_id: str):
    dataset = storage_service.get_video_benchmark_dataset(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="视频数据集不存在")
    suites = storage_service.get_video_benchmark_suites(dataset.project_id)
    if any(suite.dataset_id == dataset_id for suite in suites):
        raise HTTPException(status_code=400, detail="该视频数据集已被测评任务引用，无法删除")
    storage_service.delete_video_benchmark_dataset(dataset_id)
    return {"message": "视频数据集已删除"}


@router.get("/datasets/{dataset_id}/export")
async def export_dataset(dataset_id: str):
    dataset = storage_service.get_video_benchmark_dataset(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="视频数据集不存在")
    return export_dataset_payload(dataset)


@router.post("/datasets/import")
async def import_dataset(request: DatasetImportRequest):
    _ensure_project_exists(request.project_id)
    data = request.data or {}
    if data.get("type") != "video_benchmark_dataset":
        raise HTTPException(status_code=400, detail="导入文件类型不正确")
    if data.get("task_kind") not in (None, VIDEO_BENCHMARK_TASK_KIND):
        raise HTTPException(status_code=400, detail="导入数据集的 task_kind 非法")
    items = [
        DatasetItemInput.model_validate(
            {
                "id": item.get("id"),
                "name": item.get("name") or "",
                "prompt": item.get("prompt") or "",
                "negative_prompt": item.get("negative_prompt") or "",
                "tags": item.get("tags") or [],
                "first_frame": item.get("first_frame"),
                "audio": item.get("audio"),
                "duration": item.get("duration"),
            }
        )
        for item in data.get("items") or []
    ]
    dataset = VideoBenchmarkDataset(
        project_id=request.project_id,
        name=request.name or data.get("name") or "导入视频数据集",
        description=request.description if request.description is not None else (data.get("description") or ""),
        schema_version=str(data.get("schema_version") or "1.0"),
        items=_normalize_dataset_items(items),
    )
    storage_service.save_video_benchmark_dataset(dataset)
    return _dataset_response(dataset)


@router.get("/suites")
async def list_suites(project_id: str):
    _ensure_project_exists(project_id)
    return {"suites": storage_service.get_video_benchmark_suites(project_id)}


@router.post("/suites")
async def create_suite(request: SuiteCreateRequest):
    dataset, _ = await _validate_suite_payload(
        project_id=request.project_id,
        dataset_id=request.dataset_id,
        selected_models=request.selected_models,
    )
    suite = VideoBenchmarkSuite(
        project_id=request.project_id,
        name=request.name,
        description=request.description,
        dataset_id=request.dataset_id,
        selected_models=request.selected_models,
        baseline_params=request.baseline_params,
        model_overrides=request.model_overrides,
        task_kind=dataset.task_kind,
    )
    storage_service.save_video_benchmark_suite(suite)
    return {"suite": suite}


@router.get("/suites/{suite_id}")
async def get_suite(suite_id: str):
    suite = storage_service.get_video_benchmark_suite(suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="视频测评任务不存在")
    return {"suite": suite}


@router.put("/suites/{suite_id}")
async def update_suite(suite_id: str, request: SuiteUpdateRequest):
    suite = storage_service.get_video_benchmark_suite(suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="视频测评任务不存在")
    dataset_id = request.dataset_id or suite.dataset_id
    selected_models = request.selected_models if request.selected_models is not None else suite.selected_models
    dataset, _ = await _validate_suite_payload(
        project_id=suite.project_id,
        dataset_id=dataset_id,
        selected_models=selected_models,
    )
    if request.name is not None:
        suite.name = request.name
    if request.description is not None:
        suite.description = request.description
    suite.dataset_id = dataset_id
    suite.task_kind = dataset.task_kind
    suite.selected_models = selected_models
    if request.baseline_params is not None:
        suite.baseline_params = request.baseline_params
    if request.model_overrides is not None:
        suite.model_overrides = request.model_overrides
    storage_service.save_video_benchmark_suite(suite)
    return {"suite": suite}


@router.delete("/suites/{suite_id}")
async def delete_suite(suite_id: str):
    suite = storage_service.get_video_benchmark_suite(suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="视频测评任务不存在")
    for run in storage_service.get_video_benchmark_runs_by_suite(suite_id):
        storage_service.delete_video_benchmark_run(run.id)
    storage_service.delete_video_benchmark_suite(suite_id)
    return {"message": "视频测评任务已删除"}


@router.post("/suites/{suite_id}/run")
async def run_suite(suite_id: str):
    suite = storage_service.get_video_benchmark_suite(suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="视频测评任务不存在")
    dataset, model_lookup = await _validate_suite_payload(
        project_id=suite.project_id,
        dataset_id=suite.dataset_id,
        selected_models=suite.selected_models,
    )
    validation = _analyze_dataset(dataset)
    if validation["blocking_issues"]:
        return JSONResponse(
            status_code=400,
            content={
                "detail": "视频数据集存在缺首帧样例，无法开始测评",
                "blocking_issues": validation["blocking_issues"],
            },
        )
    model_snapshots = [model_lookup[model_id] for model_id in suite.selected_models]
    dataset_snapshot = dataset.model_dump()
    dataset_items = sorted(dataset_snapshot.get("items") or [], key=lambda item: item.get("sort_order", 0))
    run = VideoBenchmarkRun(
        suite_id=suite.id,
        project_id=suite.project_id,
        dataset_id=dataset.id,
        status="running",
        dataset_snapshot=dataset_snapshot,
        model_snapshots=model_snapshots,
        baseline_params=suite.baseline_params,
        model_overrides=suite.model_overrides,
        cell_results=_initial_video_cells(dataset_items, model_snapshots),
        started_at=datetime.now(),
    )
    _refresh_video_run_status(run)
    storage_service.save_video_benchmark_run(run)

    suite.status = "running"
    suite.latest_run_id = run.id
    suite.latest_run_snapshot = {
        "dataset_snapshot": run.dataset_snapshot,
        "model_snapshots": run.model_snapshots,
        "baseline_params": run.baseline_params,
        "model_overrides": run.model_overrides,
        "run_id": run.id,
    }
    storage_service.save_video_benchmark_suite(suite)

    user_id = get_current_user_id()
    user_config_dir = get_user_config_dir()
    asyncio.create_task(_background_run_suite(run.id, suite.id, user_id, user_config_dir))
    return {"run": run, "suite": suite}


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    run = storage_service.get_video_benchmark_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="视频测评运行记录不存在")
    return {"run": run}


@router.post("/runs/{run_id}/retry-failures")
async def retry_failed_cells(run_id: str):
    source_run = storage_service.get_video_benchmark_run(run_id)
    if not source_run:
        raise HTTPException(status_code=404, detail="视频测评运行记录不存在")
    suite = storage_service.get_video_benchmark_suite(source_run.suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="视频测评任务不存在")

    retryable_cells = [cell for cell in source_run.cell_results if cell.status in {"failed", "unsupported"}]
    if not retryable_cells:
        raise HTTPException(status_code=400, detail="当前运行没有失败或不支持任务可重试")

    preserved_cells = [cell for cell in source_run.cell_results if cell.status not in {"failed", "unsupported"}]
    retry_targets = [
        {"case_id": cell.case_id, "model_id": cell.model_id}
        for cell in retryable_cells
    ]
    retry_target_keys = {
        _cell_key(target["case_id"], target["model_id"])
        for target in retry_targets
    }
    dataset_items = sorted((source_run.dataset_snapshot or {}).get("items") or [], key=lambda item: item.get("sort_order", 0))
    retry_run = VideoBenchmarkRun(
        suite_id=source_run.suite_id,
        project_id=source_run.project_id,
        dataset_id=source_run.dataset_id,
        status="running",
        dataset_snapshot=source_run.dataset_snapshot,
        model_snapshots=source_run.model_snapshots,
        baseline_params=source_run.baseline_params,
        model_overrides=source_run.model_overrides,
        cell_results=_initial_video_cells(
            dataset_items,
            source_run.model_snapshots or [],
            retry_target_keys=retry_target_keys,
            preserved_cells=preserved_cells,
        ),
        retry_source_run_id=source_run.id,
        retry_targets=retry_targets,
        started_at=datetime.now(),
    )
    _refresh_video_run_status(retry_run)
    storage_service.save_video_benchmark_run(retry_run)
    suite.status = "running"
    suite.latest_run_id = retry_run.id
    suite.latest_run_snapshot = {
        "dataset_snapshot": retry_run.dataset_snapshot,
        "model_snapshots": retry_run.model_snapshots,
        "baseline_params": retry_run.baseline_params,
        "model_overrides": retry_run.model_overrides,
        "run_id": retry_run.id,
        "retry_source_run_id": source_run.id,
    }
    storage_service.save_video_benchmark_suite(suite)

    user_id = get_current_user_id()
    user_config_dir = get_user_config_dir()
    asyncio.create_task(_background_run_suite(retry_run.id, suite.id, user_id, user_config_dir))
    return {"run": retry_run, "suite": suite}


@router.post("/runs/{run_id}/export-md-file")
async def export_run_markdown_file(run_id: str):
    run = storage_service.get_video_benchmark_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="视频测评运行记录不存在")
    return _report_download_response(
        filename=f"video_benchmark_{run.id}.md",
        content=render_markdown_report(run.model_dump()),
        media_type="text/markdown",
    )


@router.post("/runs/{run_id}/export-html-file")
async def export_run_html_file(run_id: str):
    run = storage_service.get_video_benchmark_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="视频测评运行记录不存在")
    return _report_download_response(
        filename=f"video_benchmark_{run.id}.html",
        content=render_html_report(run.model_dump()),
        media_type="text/html",
    )


@router.post("/preview-cell")
async def preview_cell(request: PreviewCellRequest):
    if request.task_kind != VIDEO_BENCHMARK_TASK_KIND:
        raise HTTPException(status_code=400, detail="视频测评 v1 仅支持 image_to_video")
    capabilities = await get_video_benchmark_capabilities()
    model_meta = capabilities["models"].get(request.model_id)
    if not model_meta:
        raise HTTPException(status_code=400, detail="未知模型或模型不支持首帧生视频")
    normalized_items = _normalize_dataset_items([request.case_data])
    preview_dataset = VideoBenchmarkDataset(
        project_id=request.project_id,
        name="preview",
        items=normalized_items,
    )
    validation = _analyze_dataset(preview_dataset)
    if validation["blocking_issues"]:
        raise HTTPException(status_code=400, detail="预览样例缺少首帧图")
    case_data = normalized_items[0].model_dump()
    effective_params = merge_effective_params(model_meta, request.baseline_params, request.override_params, case_data)
    try:
        canonical_request, provider_payload, validation_warnings = await preview_video_benchmark_cell(
            project_id=request.project_id,
            model_meta=model_meta,
            case_data=case_data,
            effective_params=effective_params,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "effective_params": effective_params,
        "canonical_request": canonical_request,
        "provider_payload": provider_payload,
        "validation_warnings": validation_warnings,
    }
