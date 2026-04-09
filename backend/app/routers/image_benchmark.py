"""
图片测评与数据集 API
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, model_validator

from app.config import get_user_config_dir, set_user_config_dir
from app.models.image_benchmark import (
    ImageBenchmarkDataset,
    ImageBenchmarkDatasetImage,
    ImageBenchmarkDatasetItem,
    ImageBenchmarkImageSlot,
    ImageBenchmarkRun,
    ImageBenchmarkSuite,
)
from app.services.image_benchmark_runtime import (
    execute_benchmark_cell,
    export_dataset_payload,
    get_image_benchmark_capabilities,
    merge_effective_params,
    preview_benchmark_cell,
    render_markdown_report,
)
from app.services.storage import get_current_user_id, set_current_user, storage_service

router = APIRouter()


class DatasetImageInput(BaseModel):
    url: str
    name: str = ""
    mime_type: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    source_label: Optional[str] = None


class DatasetImageSlotInput(BaseModel):
    position: int
    image: DatasetImageInput


class DatasetItemInput(BaseModel):
    id: Optional[str] = None
    name: str = ""
    prompt: str = ""
    negative_prompt: str = ""
    tags: List[str] = []
    image_slots: List[DatasetImageSlotInput] = []
    input_images: List[DatasetImageInput] = []

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_input_images(cls, value: Any):
        if not isinstance(value, dict):
            return value
        if value.get("image_slots"):
            return value
        legacy_images = value.get("input_images") or []
        if legacy_images:
            value = dict(value)
            value["image_slots"] = [
                {
                    "position": index + 1,
                    "image": image,
                }
                for index, image in enumerate(legacy_images)
                if image and image.get("url")
            ]
        return value


class DatasetCreateRequest(BaseModel):
    project_id: str
    name: str
    description: str = ""
    task_kind: str
    max_image_slot_index: Optional[int] = None
    items: List[DatasetItemInput] = []


class DatasetUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    max_image_slot_index: Optional[int] = None
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
    task_kind: str
    model_id: str
    case_data: DatasetItemInput
    baseline_params: Dict[str, Any] = {}
    override_params: Dict[str, Any] = {}


def _ensure_project_exists(project_id: str) -> None:
    if not storage_service.get_project(project_id):
        raise HTTPException(status_code=404, detail="项目不存在")


def _normalize_dataset_image(image: DatasetImageInput) -> ImageBenchmarkDatasetImage:
    return ImageBenchmarkDatasetImage(
        url=image.url,
        name=image.name,
        mime_type=image.mime_type,
        width=image.width,
        height=image.height,
        source_label=image.source_label,
    )


def _normalize_image_slots(item: DatasetItemInput) -> List[ImageBenchmarkImageSlot]:
    normalized_slots: List[ImageBenchmarkImageSlot] = []
    seen_positions: set[int] = set()
    for slot in item.image_slots or []:
        if slot.position <= 0:
            raise HTTPException(status_code=400, detail="图片槽位 position 必须从 1 开始")
        if slot.position in seen_positions:
            raise HTTPException(status_code=400, detail=f"样例 {item.name or '未命名样例'} 存在重复的图片槽位 position={slot.position}")
        seen_positions.add(slot.position)
        if not slot.image or not slot.image.url:
            continue
        normalized_slots.append(
            ImageBenchmarkImageSlot(
                position=slot.position,
                image=_normalize_dataset_image(slot.image),
            )
        )
    normalized_slots.sort(key=lambda current: current.position)
    return normalized_slots


def _normalize_dataset_items(task_kind: str, items: List[DatasetItemInput]) -> List[ImageBenchmarkDatasetItem]:
    normalized_items: List[ImageBenchmarkDatasetItem] = []
    for index, item in enumerate(items):
        image_slots = _normalize_image_slots(item)
        if task_kind == "text_to_image" and image_slots:
            raise HTTPException(status_code=400, detail="text_to_image 数据集不能包含输入图片")
        normalized_items.append(
            ImageBenchmarkDatasetItem(
                id=item.id or ImageBenchmarkDatasetItem().id,
                name=item.name,
                prompt=item.prompt,
                negative_prompt=item.negative_prompt,
                sort_order=index,
                tags=item.tags,
                image_slots=image_slots,
            )
        )
    return normalized_items


def _resolve_dataset_max_image_slot_index(
    items: List[ImageBenchmarkDatasetItem],
    requested_max_index: Optional[int],
) -> int:
    inferred_max = 0
    for item in items:
        if item.image_slots:
            inferred_max = max(inferred_max, max(slot.position for slot in item.image_slots))
    return max(inferred_max, int(requested_max_index or 0))


def _analyze_dataset(task_kind: str, items: List[ImageBenchmarkDatasetItem]) -> Dict[str, List[Dict[str, Any]]]:
    warnings: List[Dict[str, Any]] = []
    blocking_issues: List[Dict[str, Any]] = []

    if task_kind != "image_edit":
        return {"warnings": warnings, "blocking_issues": blocking_issues}

    for item in items:
        item_name = item.name or f"样例 {item.sort_order + 1}"
        positions = sorted(slot.position for slot in item.image_slots if slot.image.url)

        if not positions:
            issue = {
                "item_id": item.id,
                "item_name": item_name,
                "missing_positions": [1],
                "message": "未填写任何输入图",
            }
            warnings.append(issue)
            blocking_issues.append(issue)
            continue

        max_filled_position = max(positions)
        missing_positions = [position for position in range(1, max_filled_position + 1) if position not in positions]
        if missing_positions:
            issue = {
                "item_id": item.id,
                "item_name": item_name,
                "missing_positions": missing_positions,
                "message": f"缺少输入图位置：{', '.join(str(position) for position in missing_positions)}",
            }
            warnings.append(issue)
            blocking_issues.append(issue)

    return {"warnings": warnings, "blocking_issues": blocking_issues}


def _dataset_response(dataset: ImageBenchmarkDataset) -> Dict[str, Any]:
    validation = _analyze_dataset(dataset.task_kind, dataset.items)
    return {
        "dataset": dataset,
        "warnings": validation["warnings"],
        "blocking_issues": validation["blocking_issues"],
    }


def _cell_key(case_id: str, model_id: str) -> str:
    return f"{case_id}__{model_id}"


async def _validate_suite_payload(
    *,
    project_id: str,
    dataset_id: str,
    selected_models: List[str],
) -> tuple[ImageBenchmarkDataset, Dict[str, Any]]:
    _ensure_project_exists(project_id)
    dataset = storage_service.get_image_benchmark_dataset(dataset_id)
    if not dataset or dataset.project_id != project_id:
        raise HTTPException(status_code=404, detail="数据集不存在")
    capabilities = await get_image_benchmark_capabilities()
    model_lookup = capabilities["models"]
    for model_id in selected_models:
        model_meta = model_lookup.get(model_id)
        if not model_meta:
            raise HTTPException(status_code=400, detail=f"未知模型：{model_id}")
        if dataset.task_kind not in (model_meta.get("supported_task_kinds") or []):
            raise HTTPException(status_code=400, detail=f"模型 {model_id} 不支持任务类型 {dataset.task_kind}")
    return dataset, model_lookup


async def _background_run_suite(run_id: str, suite_id: str, user_id: Optional[str], user_config_dir: Optional[str]) -> None:
    set_current_user(user_id)
    set_user_config_dir(user_config_dir)

    run = storage_service.get_image_benchmark_run(run_id)
    suite = storage_service.get_image_benchmark_suite(suite_id)
    if not run or not suite:
        return

    try:
        run.status = "running"
        run.started_at = run.started_at or datetime.now()
        storage_service.save_image_benchmark_run(run)

        dataset_snapshot = run.dataset_snapshot or {}
        model_snapshots = run.model_snapshots or []
        dataset_items = sorted(dataset_snapshot.get("items") or [], key=lambda item: item.get("sort_order", 0))

        global_semaphore = asyncio.Semaphore(4)
        model_semaphores = {
            model["id"]: asyncio.Semaphore(max(1, int((model.get("capabilities") or {}).get("max_concurrent") or 1)))
            for model in model_snapshots
        }

        retry_target_keys = {
            _cell_key(target.get("case_id", ""), target.get("model_id", ""))
            for target in (run.retry_targets or [])
            if target.get("case_id") and target.get("model_id")
        }
        existing_results_map = {
            _cell_key(cell.case_id, cell.model_id): cell
            for cell in run.cell_results
        }

        async def run_cell(index: int, case_data: Dict[str, Any], model_meta: Dict[str, Any]):
            effective_params = merge_effective_params(
                model_meta,
                run.baseline_params,
                (run.model_overrides or {}).get(model_meta["id"]),
            )
            async with global_semaphore, model_semaphores[model_meta["id"]]:
                cell = await execute_benchmark_cell(
                    project_id=run.project_id,
                    task_kind=run.task_kind,
                    model_meta=model_meta,
                    case_data=case_data,
                    effective_params=effective_params,
                )
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

        results = await asyncio.gather(*tasks) if tasks else []
        retried_cells_map = {
            _cell_key(cell.case_id, cell.model_id): cell
            for _, cell in sorted(results, key=lambda item: item[0])
        }
        merged_cells_map = {
            **existing_results_map,
            **retried_cells_map,
        }

        ordered_cells = []
        for case_data in dataset_items:
            for model_meta in model_snapshots:
                key = _cell_key(case_data.get("id", ""), model_meta["id"])
                cell = merged_cells_map.get(key)
                if cell:
                    ordered_cells.append(cell)

        run.cell_results = ordered_cells
        run.finished_at = datetime.now()
        success_count = sum(1 for cell in ordered_cells if cell.status == "completed")
        failure_count = sum(1 for cell in ordered_cells if cell.status == "failed")
        unsupported_count = sum(1 for cell in ordered_cells if cell.status == "unsupported")
        skipped_count = sum(1 for cell in ordered_cells if cell.status == "skipped")
        run.stats = {
            "case_count": len(dataset_items),
            "model_count": len(model_snapshots),
            "cell_count": len(ordered_cells),
            "success_count": success_count,
            "failure_count": failure_count,
            "unsupported_count": unsupported_count,
            "skipped_count": skipped_count,
            "retried_failure_count": len(retry_target_keys),
        }
        run.status = "failed" if ordered_cells and success_count == 0 and failure_count > 0 else "completed"
        storage_service.save_image_benchmark_run(run)

        suite.status = "failed" if run.status == "failed" else "completed"
        suite.latest_run_id = run.id
        suite.latest_run_snapshot = {
            "dataset_snapshot": run.dataset_snapshot,
            "model_snapshots": run.model_snapshots,
            "baseline_params": run.baseline_params,
            "model_overrides": run.model_overrides,
            "run_id": run.id,
        }
        storage_service.save_image_benchmark_suite(suite)
    except Exception as exc:
        run.status = "failed"
        run.finished_at = datetime.now()
        run.stats = {
            "case_count": len((run.dataset_snapshot or {}).get("items") or []),
            "model_count": len(run.model_snapshots or []),
            "cell_count": len(run.cell_results or []),
            "error": str(exc),
        }
        storage_service.save_image_benchmark_run(run)
        suite.status = "failed"
        storage_service.save_image_benchmark_suite(suite)


@router.get("/capabilities")
async def get_capabilities():
    return await get_image_benchmark_capabilities()


@router.get("/datasets")
async def list_datasets(project_id: str):
    _ensure_project_exists(project_id)
    return {"datasets": storage_service.get_image_benchmark_datasets(project_id)}


@router.post("/datasets")
async def create_dataset(request: DatasetCreateRequest):
    _ensure_project_exists(request.project_id)
    if request.task_kind not in {"text_to_image", "image_edit"}:
        raise HTTPException(status_code=400, detail="数据集任务类型仅支持 text_to_image / image_edit")

    items = _normalize_dataset_items(request.task_kind, request.items)
    dataset = ImageBenchmarkDataset(
        project_id=request.project_id,
        name=request.name,
        description=request.description,
        task_kind=request.task_kind,  # type: ignore[arg-type]
        max_image_slot_index=_resolve_dataset_max_image_slot_index(items, request.max_image_slot_index),
        items=items,
    )
    storage_service.save_image_benchmark_dataset(dataset)
    return _dataset_response(dataset)


@router.get("/datasets/{dataset_id}")
async def get_dataset(dataset_id: str):
    dataset = storage_service.get_image_benchmark_dataset(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")
    return _dataset_response(dataset)


@router.put("/datasets/{dataset_id}")
async def update_dataset(dataset_id: str, request: DatasetUpdateRequest):
    dataset = storage_service.get_image_benchmark_dataset(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")

    if request.name is not None:
        dataset.name = request.name
    if request.description is not None:
        dataset.description = request.description
    if request.items is not None:
        dataset.items = _normalize_dataset_items(dataset.task_kind, request.items)
    if request.max_image_slot_index is not None or request.items is not None:
        dataset.max_image_slot_index = _resolve_dataset_max_image_slot_index(dataset.items, request.max_image_slot_index or dataset.max_image_slot_index)
    storage_service.save_image_benchmark_dataset(dataset)
    return _dataset_response(dataset)


@router.post("/datasets/{dataset_id}/validate")
async def validate_dataset(dataset_id: str):
    dataset = storage_service.get_image_benchmark_dataset(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")
    validation = _analyze_dataset(dataset.task_kind, dataset.items)
    return validation


@router.delete("/datasets/{dataset_id}")
async def delete_dataset(dataset_id: str):
    dataset = storage_service.get_image_benchmark_dataset(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")
    suites = storage_service.get_image_benchmark_suites(dataset.project_id)
    if any(suite.dataset_id == dataset_id for suite in suites):
        raise HTTPException(status_code=400, detail="该数据集已被测评任务引用，无法删除")
    storage_service.delete_image_benchmark_dataset(dataset_id)
    return {"message": "数据集已删除"}


@router.post("/datasets/import")
async def import_dataset(request: DatasetImportRequest):
    _ensure_project_exists(request.project_id)
    data = request.data or {}
    if data.get("type") != "image_benchmark_dataset":
        raise HTTPException(status_code=400, detail="导入文件类型不正确")
    task_kind = data.get("task_kind")
    if task_kind not in {"text_to_image", "image_edit"}:
        raise HTTPException(status_code=400, detail="导入数据集的 task_kind 非法")

    items = []
    for item in data.get("items") or []:
        normalized_item = {
            "id": item.get("id"),
            "name": item.get("name") or "",
            "prompt": item.get("prompt") or "",
            "negative_prompt": item.get("negative_prompt") or "",
            "tags": item.get("tags") or [],
            "image_slots": item.get("image_slots") or [],
            "input_images": item.get("input_images") or [],
        }
        items.append(DatasetItemInput.model_validate(normalized_item))

    normalized_items = _normalize_dataset_items(task_kind, items)
    dataset = ImageBenchmarkDataset(
        project_id=request.project_id,
        name=request.name or data.get("name") or "导入数据集",
        description=request.description if request.description is not None else (data.get("description") or ""),
        task_kind=task_kind,  # type: ignore[arg-type]
        schema_version=str(data.get("schema_version") or "2.0"),
        max_image_slot_index=_resolve_dataset_max_image_slot_index(
            normalized_items,
            data.get("max_image_slot_index"),
        ),
        items=normalized_items,
    )
    storage_service.save_image_benchmark_dataset(dataset)
    return _dataset_response(dataset)


@router.get("/datasets/{dataset_id}/export")
async def export_dataset(dataset_id: str):
    dataset = storage_service.get_image_benchmark_dataset(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")
    return export_dataset_payload(dataset)


@router.get("/suites")
async def list_suites(project_id: str):
    _ensure_project_exists(project_id)
    return {"suites": storage_service.get_image_benchmark_suites(project_id)}


@router.post("/suites")
async def create_suite(request: SuiteCreateRequest):
    dataset, _ = await _validate_suite_payload(
        project_id=request.project_id,
        dataset_id=request.dataset_id,
        selected_models=request.selected_models,
    )
    suite = ImageBenchmarkSuite(
        project_id=request.project_id,
        name=request.name,
        description=request.description,
        dataset_id=request.dataset_id,
        task_kind=dataset.task_kind,
        selected_models=request.selected_models,
        baseline_params={"n": 1, **request.baseline_params},
        model_overrides=request.model_overrides,
    )
    storage_service.save_image_benchmark_suite(suite)
    return {"suite": suite}


@router.get("/suites/{suite_id}")
async def get_suite(suite_id: str):
    suite = storage_service.get_image_benchmark_suite(suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="测评任务不存在")
    return {"suite": suite}


@router.put("/suites/{suite_id}")
async def update_suite(suite_id: str, request: SuiteUpdateRequest):
    suite = storage_service.get_image_benchmark_suite(suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="测评任务不存在")
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
        suite.baseline_params = {"n": 1, **request.baseline_params}
    if request.model_overrides is not None:
        suite.model_overrides = request.model_overrides
    storage_service.save_image_benchmark_suite(suite)
    return {"suite": suite}


@router.delete("/suites/{suite_id}")
async def delete_suite(suite_id: str):
    suite = storage_service.get_image_benchmark_suite(suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="测评任务不存在")
    for run in storage_service.get_image_benchmark_runs_by_suite(suite_id):
        storage_service.delete_image_benchmark_run(run.id)
    storage_service.delete_image_benchmark_suite(suite_id)
    return {"message": "测评任务已删除"}


@router.post("/suites/{suite_id}/run")
async def run_suite(suite_id: str):
    suite = storage_service.get_image_benchmark_suite(suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="测评任务不存在")
    dataset, model_lookup = await _validate_suite_payload(
        project_id=suite.project_id,
        dataset_id=suite.dataset_id,
        selected_models=suite.selected_models,
    )
    validation = _analyze_dataset(dataset.task_kind, dataset.items)
    if validation["blocking_issues"]:
        return JSONResponse(
            status_code=400,
            content={
                "detail": "数据集存在图片槽位空缺，无法开始测评",
                "blocking_issues": validation["blocking_issues"],
            },
        )

    model_snapshots = [model_lookup[model_id] for model_id in suite.selected_models]
    run = ImageBenchmarkRun(
        suite_id=suite.id,
        project_id=suite.project_id,
        dataset_id=dataset.id,
        task_kind=dataset.task_kind,
        status="running",
        dataset_snapshot=dataset.model_dump(),
        model_snapshots=model_snapshots,
        baseline_params=suite.baseline_params,
        model_overrides=suite.model_overrides,
        started_at=datetime.now(),
    )
    storage_service.save_image_benchmark_run(run)

    suite.status = "running"
    suite.latest_run_id = run.id
    suite.latest_run_snapshot = {
        "dataset_snapshot": run.dataset_snapshot,
        "model_snapshots": run.model_snapshots,
        "baseline_params": run.baseline_params,
        "model_overrides": run.model_overrides,
        "run_id": run.id,
    }
    storage_service.save_image_benchmark_suite(suite)

    user_id = get_current_user_id()
    user_config_dir = get_user_config_dir()
    asyncio.create_task(_background_run_suite(run.id, suite.id, user_id, user_config_dir))
    return {"run": run, "suite": suite}


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    run = storage_service.get_image_benchmark_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    return {"run": run}


@router.post("/runs/{run_id}/export-md")
async def export_run_markdown(run_id: str):
    run = storage_service.get_image_benchmark_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    content = render_markdown_report(run.model_dump())
    return {
        "filename": f"image_benchmark_{run.id}.md",
        "content": content,
    }


@router.post("/runs/{run_id}/retry-failures")
async def retry_failed_cells(run_id: str):
    source_run = storage_service.get_image_benchmark_run(run_id)
    if not source_run:
        raise HTTPException(status_code=404, detail="运行记录不存在")

    suite = storage_service.get_image_benchmark_suite(source_run.suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="测评任务不存在")

    failed_cells = [cell for cell in source_run.cell_results if cell.status == "failed"]
    if not failed_cells:
        raise HTTPException(status_code=400, detail="当前运行没有失败任务可重试")

    preserved_cells = [cell for cell in source_run.cell_results if cell.status != "failed"]
    retry_targets = [
        {"case_id": cell.case_id, "model_id": cell.model_id}
        for cell in failed_cells
    ]

    retry_run = ImageBenchmarkRun(
        suite_id=source_run.suite_id,
        project_id=source_run.project_id,
        dataset_id=source_run.dataset_id,
        task_kind=source_run.task_kind,
        status="running",
        dataset_snapshot=source_run.dataset_snapshot,
        model_snapshots=source_run.model_snapshots,
        baseline_params=source_run.baseline_params,
        model_overrides=source_run.model_overrides,
        cell_results=preserved_cells,
        retry_source_run_id=source_run.id,
        retry_targets=retry_targets,
        started_at=datetime.now(),
    )
    storage_service.save_image_benchmark_run(retry_run)

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
    storage_service.save_image_benchmark_suite(suite)

    user_id = get_current_user_id()
    user_config_dir = get_user_config_dir()
    asyncio.create_task(_background_run_suite(retry_run.id, suite.id, user_id, user_config_dir))
    return {"run": retry_run, "suite": suite}


@router.post("/preview-cell")
async def preview_cell(request: PreviewCellRequest):
    capabilities = await get_image_benchmark_capabilities()
    model_meta = capabilities["models"].get(request.model_id)
    if not model_meta:
        raise HTTPException(status_code=400, detail="未知模型")
    effective_params = merge_effective_params(model_meta, request.baseline_params, request.override_params)
    canonical_request, provider_payload, validation_warnings = await preview_benchmark_cell(
        project_id=request.project_id,
        task_kind=request.task_kind,
        model_id=request.model_id,
        case_data=request.case_data.model_dump(),
        effective_params=effective_params,
    )
    return {
        "effective_params": effective_params,
        "canonical_request": canonical_request,
        "provider_payload": provider_payload,
        "validation_warnings": validation_warnings,
    }
