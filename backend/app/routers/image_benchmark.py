"""
图片测评与数据集 API
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import threading
from datetime import datetime
from pathlib import Path
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
from app.services.oss import oss_service
from app.services.storage import get_current_user_id, set_current_user, storage_service
from app.services.user_service import get_user_service

router = APIRouter()

_share_index_lock = threading.RLock()


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
    bbox_list: List[List[List[int]]] = []

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
    migrate_images_to_oss: bool = False


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


def _share_index_path() -> Path:
    return Path(get_user_service().data_dir) / "image_benchmark_share_index.json"


def _read_share_index() -> Dict[str, Dict[str, Any]]:
    path = _share_index_path()
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_share_index(data: Dict[str, Dict[str, Any]]) -> None:
    path = _share_index_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.flush()
        os.fsync(file.fileno())
    os.replace(str(tmp_path), str(path))


def _upsert_share_index(token: str, owner_user_id: str, suite_id: str) -> None:
    with _share_index_lock:
        index = _read_share_index()
        index[token] = {
            "owner_user_id": owner_user_id,
            "suite_id": suite_id,
            "updated_at": datetime.now().isoformat(),
        }
        _write_share_index(index)


def _remove_share_index(token: Optional[str]) -> None:
    if not token:
        return
    with _share_index_lock:
        index = _read_share_index()
        if token in index:
            del index[token]
            _write_share_index(index)


def _lookup_share_index(token: str) -> Dict[str, Any]:
    with _share_index_lock:
        data = _read_share_index().get(token)
    if not data:
        raise HTTPException(status_code=404, detail="分享链接不存在或已关闭")
    return data


def _public_share_url(token: str) -> str:
    return f"/image-benchmark/share/{token}"


def _public_api_share_url(token: str) -> str:
    return f"/api/image-benchmark/public/shares/{token}"


def _sanitize_public_cell(cell: ImageBenchmarkCellResult) -> Dict[str, Any]:
    return {
        "id": cell.id,
        "case_id": cell.case_id,
        "case_name": cell.case_name,
        "model_id": cell.model_id,
        "model_name": cell.model_name,
        "status": cell.status,
        "output_images": [image.model_dump() for image in cell.output_images],
        "error_message": cell.error_message,
        "validation_warnings": cell.validation_warnings,
        "attempt_count": cell.attempt_count,
        "auto_retry_count": cell.auto_retry_count,
        "created_at": cell.created_at,
        "updated_at": cell.updated_at,
    }


def _sanitize_public_run(run: ImageBenchmarkRun) -> Dict[str, Any]:
    return {
        "id": run.id,
        "suite_id": run.suite_id,
        "project_id": run.project_id,
        "dataset_id": run.dataset_id,
        "task_kind": run.task_kind,
        "status": run.status,
        "dataset_snapshot": run.dataset_snapshot,
        "model_snapshots": [
            {
                "id": model.get("id"),
                "name": model.get("name"),
                "description": model.get("description"),
            }
            for model in run.model_snapshots
        ],
        "cell_results": [_sanitize_public_cell(cell) for cell in run.cell_results],
        "stats": run.stats,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
    }


def _public_suite_payload(suite: ImageBenchmarkSuite, run: ImageBenchmarkRun) -> Dict[str, Any]:
    return {
        "suite": {
            "id": suite.id,
            "name": suite.name,
            "description": suite.description,
            "task_kind": suite.task_kind,
            "status": suite.status,
            "latest_run_id": suite.latest_run_id,
            "updated_at": suite.updated_at,
        },
        "run": _sanitize_public_run(run),
    }


def _markdown_cell(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", "<br/>")


def _render_public_markdown(suite: ImageBenchmarkSuite, run: ImageBenchmarkRun) -> str:
    run_data = _sanitize_public_run(run)
    dataset_items = sorted((run_data.get("dataset_snapshot") or {}).get("items") or [], key=lambda item: item.get("sort_order", 0))
    model_snapshots = run_data.get("model_snapshots") or []
    result_map = {
        (cell.get("case_id"), cell.get("model_id")): cell
        for cell in run_data.get("cell_results") or []
    }

    lines = [
        f"# {suite.name}",
        "",
        suite.description or "",
        "",
        f"- 任务类型: {run.task_kind}",
        f"- 状态: {run.status}",
        f"- 样例数: {(run.stats or {}).get('case_count', 0)}",
        f"- 模型数: {(run.stats or {}).get('model_count', 0)}",
        "",
        "## 测评结果",
        "",
    ]
    headers = ["样例", "Prompt", "输入图"] + [model.get("name") or model.get("id") for model in model_snapshots]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

    for item in dataset_items:
        input_images = [
            image
            for slot in sorted(item.get("image_slots") or [], key=lambda current: current.get("position", 0))
            for image in [slot.get("image") or {}]
            if image.get("url")
        ]
        if not input_images:
            input_images = [image for image in item.get("input_images") or [] if image.get("url")]
        input_html = "<br/>".join(f'<img src="{image.get("url")}" width="160" />' for image in input_images)
        row = [
            _markdown_cell(item.get("name")),
            _markdown_cell(item.get("prompt")),
            input_html,
        ]
        for model in model_snapshots:
            cell = result_map.get((item.get("id"), model.get("id")), {})
            output_images = cell.get("output_images") or []
            output_html = "<br/>".join(
                f'<img src="{image.get("url")}" width="220" />'
                for image in output_images
                if image.get("url")
            )
            row.append(output_html or _markdown_cell(cell.get("error_message") or cell.get("status") or "未运行"))
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(line for line in lines if line is not None)


def _load_public_share(token: str) -> tuple[ImageBenchmarkSuite, ImageBenchmarkRun]:
    share = _lookup_share_index(token)
    owner_user_id = share.get("owner_user_id")
    suite_id = share.get("suite_id")
    if not owner_user_id or not suite_id:
        raise HTTPException(status_code=404, detail="分享链接不存在或已关闭")

    set_current_user(owner_user_id)
    set_user_config_dir(str(get_user_service().get_user_data_path(owner_user_id)))
    try:
        suite = storage_service.get_image_benchmark_suite(suite_id)
        if not suite or not suite.share_enabled or suite.share_token != token:
            raise HTTPException(status_code=404, detail="分享链接不存在或已关闭")
        if not suite.latest_run_id:
            raise HTTPException(status_code=404, detail="该分享暂无运行结果")
        run = storage_service.get_image_benchmark_run(suite.latest_run_id)
        if not run:
            raise HTTPException(status_code=404, detail="运行记录不存在")
        return suite, run
    finally:
        set_current_user(None)
        set_user_config_dir(None)


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
                bbox_list=item.bbox_list or [],
            )
        )
    return normalized_items


async def _migrate_dataset_images_to_current_oss(
    project_id: str,
    items: List[ImageBenchmarkDatasetItem],
) -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "enabled": bool(oss_service.is_enabled()),
        "attempted": 0,
        "succeeded": 0,
        "failed": 0,
        "skipped": 0,
        "errors": [],
    }
    if not report["enabled"]:
        report["skipped"] = sum(1 for item in items for slot in item.image_slots if slot.image.url)
        return report

    migrated_url_cache: Dict[str, str] = {}
    failed_url_cache: Dict[str, str] = {}
    for item in items:
        for slot in item.image_slots:
            original_url = slot.image.url
            if not original_url:
                continue
            if not oss_service.should_persist_remote_url(original_url):
                report["skipped"] += 1
                continue
            if original_url in migrated_url_cache:
                slot.image.url = migrated_url_cache[original_url]
                report["skipped"] += 1
                continue
            if original_url in failed_url_cache:
                report["skipped"] += 1
                continue

            report["attempted"] += 1
            try:
                result = await oss_service.ensure_image_persisted_async(
                    original_url,
                    project_id,
                    strict=True,
                )
                migrated_url_cache[original_url] = result
                slot.image.url = result
                report["succeeded"] += 1
            except Exception as exc:
                failed_url_cache[original_url] = str(exc)
                report["failed"] += 1
                report["errors"].append(
                    {
                        "item_id": item.id,
                        "item_name": item.name,
                        "position": slot.position,
                        "url": original_url,
                        "error": str(exc),
                    }
                )
    return report


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

    if task_kind not in {"image_edit", "interactive_edit"}:
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

        if task_kind == "interactive_edit":
            bbox_list = item.bbox_list or []
            expected_count = len(positions)
            if len(bbox_list) != expected_count:
                issue = {
                    "item_id": item.id,
                    "item_name": item_name,
                    "missing_positions": [],
                    "message": f"bbox_list 长度需与输入图数量一致：当前 {len(bbox_list)}，应为 {expected_count}",
                }
                warnings.append(issue)
                blocking_issues.append(issue)
                continue
            for index, box_group in enumerate(bbox_list, start=1):
                if len(box_group) > 2:
                    issue = {
                        "item_id": item.id,
                        "item_name": item_name,
                        "missing_positions": [],
                        "message": f"图{index}最多支持 2 个框选区域",
                    }
                    warnings.append(issue)
                    blocking_issues.append(issue)
                for box in box_group:
                    if len(box) != 4:
                        issue = {
                            "item_id": item.id,
                            "item_name": item_name,
                            "missing_positions": [],
                            "message": f"图{index}存在无效框选坐标，格式必须为 [x1, y1, x2, y2]",
                        }
                        warnings.append(issue)
                        blocking_issues.append(issue)
                        break

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
                run.task_kind,
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


@router.get("/public/shares/{token}")
async def get_public_share(token: str):
    suite, run = _load_public_share(token)
    return _public_suite_payload(suite, run)


@router.get("/public/shares/{token}/markdown")
async def get_public_share_markdown(token: str):
    suite, run = _load_public_share(token)
    return {
        "filename": f"image_benchmark_{suite.id}.md",
        "content": _render_public_markdown(suite, run),
    }


@router.get("/datasets")
async def list_datasets(project_id: str):
    _ensure_project_exists(project_id)
    return {"datasets": storage_service.get_image_benchmark_datasets(project_id)}


@router.post("/datasets")
async def create_dataset(request: DatasetCreateRequest):
    _ensure_project_exists(request.project_id)
    if request.task_kind not in {"text_to_image", "image_edit", "interactive_edit"}:
        raise HTTPException(status_code=400, detail="数据集任务类型仅支持 text_to_image / image_edit / interactive_edit")

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
    if task_kind not in {"text_to_image", "image_edit", "interactive_edit"}:
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
            "bbox_list": item.get("bbox_list") or [],
        }
        items.append(DatasetItemInput.model_validate(normalized_item))

    normalized_items = _normalize_dataset_items(task_kind, items)
    migration_report = None
    if request.migrate_images_to_oss:
        migration_report = await _migrate_dataset_images_to_current_oss(request.project_id, normalized_items)
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
    response = _dataset_response(dataset)
    if migration_report is not None:
        response["migration_report"] = migration_report
    return response


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


@router.post("/suites/{suite_id}/share")
async def enable_suite_share(suite_id: str):
    suite = storage_service.get_image_benchmark_suite(suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="测评任务不存在")
    if not suite.latest_run_id or not storage_service.get_image_benchmark_run(suite.latest_run_id):
        raise HTTPException(status_code=400, detail="当前测评暂无运行结果，无法分享")

    owner_user_id = get_current_user_id()
    if not owner_user_id:
        raise HTTPException(status_code=401, detail="未登录")

    if not suite.share_token or (not suite.share_enabled and suite.share_disabled_at is not None):
        _remove_share_index(suite.share_token)
        with _share_index_lock:
            index = _read_share_index()
            token = secrets.token_urlsafe(24)
            while token in index:
                token = secrets.token_urlsafe(24)
        suite.share_token = token

    suite.share_enabled = True
    suite.share_created_at = suite.share_created_at or datetime.now()
    suite.share_disabled_at = None
    storage_service.save_image_benchmark_suite(suite)
    _upsert_share_index(suite.share_token, owner_user_id, suite.id)
    return {
        "suite": suite,
        "share_url": _public_share_url(suite.share_token),
        "public_api_url": _public_api_share_url(suite.share_token),
    }


@router.delete("/suites/{suite_id}/share")
async def disable_suite_share(suite_id: str):
    suite = storage_service.get_image_benchmark_suite(suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="测评任务不存在")
    _remove_share_index(suite.share_token)
    suite.share_enabled = False
    suite.share_disabled_at = datetime.now()
    storage_service.save_image_benchmark_suite(suite)
    return {"suite": suite}


@router.delete("/suites/{suite_id}")
async def delete_suite(suite_id: str):
    suite = storage_service.get_image_benchmark_suite(suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="测评任务不存在")
    _remove_share_index(suite.share_token)
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
    migration_report = await _migrate_dataset_images_to_current_oss(suite.project_id, dataset.items)
    if migration_report["succeeded"] > 0:
        dataset.updated_at = datetime.now()
        storage_service.save_image_benchmark_dataset(dataset)
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

    retryable_cells = [cell for cell in source_run.cell_results if cell.status in {"failed", "unsupported"}]
    if not retryable_cells:
        raise HTTPException(status_code=400, detail="当前运行没有失败或不支持任务可重试")

    preserved_cells = [cell for cell in source_run.cell_results if cell.status not in {"failed", "unsupported"}]
    retry_targets = [
        {"case_id": cell.case_id, "model_id": cell.model_id}
        for cell in retryable_cells
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
    if request.task_kind not in (model_meta.get("supported_task_kinds") or []):
        raise HTTPException(status_code=400, detail=f"模型 {request.model_id} 不支持任务类型 {request.task_kind}")
    effective_params = merge_effective_params(model_meta, request.baseline_params, request.override_params, request.task_kind)
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
