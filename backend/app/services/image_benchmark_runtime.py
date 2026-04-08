"""
图片测评运行时能力

复用图片工作室现有的模型元数据、请求构建与执行能力。
"""

from __future__ import annotations

from dataclasses import asdict
import json
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from app.config import get_config, get_provider_api_key
from app.models.image_benchmark import (
    ImageBenchmarkCellResult,
    ImageBenchmarkDataset,
    ImageBenchmarkOutputImage,
)
from app.models.studio import StudioTask
from app.routers import studio as studio_router


BENCHMARK_TASK_KINDS = {"text_to_image", "image_edit"}
CONFIGURABLE_PARAM_EXCLUDES = {"prompt", "images"}


async def get_image_benchmark_capabilities() -> Dict[str, Any]:
    """获取图片测评可用能力"""

    raw = await studio_router.get_available_models()
    models: Dict[str, Any] = {}
    for model_id, model in (raw.get("models") or {}).items():
        supported_task_kinds = [
            item for item in model.get("supported_task_kinds") or [] if item in BENCHMARK_TASK_KINDS
        ]
        if not supported_task_kinds:
            continue
        next_model = dict(model)
        next_model["supported_task_kinds"] = supported_task_kinds
        next_model["configurable_parameters"] = [
            param
            for param in model.get("parameters") or []
            if param.get("name") not in CONFIGURABLE_PARAM_EXCLUDES
        ]
        models[model_id] = next_model
    return {
        "task_kinds": [
            {"id": "text_to_image", "label": "文生图"},
            {"id": "image_edit", "label": "图片编辑"},
        ],
        "models": models,
    }


def export_dataset_payload(dataset: ImageBenchmarkDataset) -> Dict[str, Any]:
    """导出数据集 JSON 结构"""

    return {
        "schema_version": dataset.schema_version,
        "type": "image_benchmark_dataset",
        "task_kind": dataset.task_kind,
        "name": dataset.name,
        "description": dataset.description,
        "max_image_slot_index": dataset.max_image_slot_index,
        "items": [
            {
                "id": item.id,
                "name": item.name,
                "prompt": item.prompt,
                "negative_prompt": item.negative_prompt,
                "tags": item.tags,
                "image_slots": [
                    {
                        "position": slot.position,
                        "image": slot.image.model_dump(),
                    }
                    for slot in sorted(item.image_slots, key=lambda current: current.position)
                ],
            }
            for item in sorted(dataset.items, key=lambda current: current.sort_order)
        ],
    }


def render_markdown_report(run: Dict[str, Any]) -> str:
    """渲染 Markdown 报告"""

    dataset_items = (run.get("dataset_snapshot") or {}).get("items") or []
    model_snapshots = run.get("model_snapshots") or []
    cell_results = run.get("cell_results") or []
    model_ids = [model["id"] for model in model_snapshots]

    result_map = {
        (cell.get("case_id"), cell.get("model_id")): cell
        for cell in cell_results
    }

    lines = [
        "# 图片测评报告",
        "",
        f"- Run ID: {run.get('id')}",
        f"- 数据集: {(run.get('dataset_snapshot') or {}).get('name', '')}",
        f"- 任务类型: {run.get('task_kind')}",
        f"- 状态: {run.get('status')}",
        f"- 创建时间: {run.get('created_at')}",
        f"- 开始时间: {run.get('started_at') or ''}",
        f"- 完成时间: {run.get('finished_at') or ''}",
        "",
        "## 矩阵概览",
        "",
    ]

    header_cells = ["样例", "Prompt", "输入图"] + [model.get("name") or model.get("id") for model in model_snapshots]
    lines.append("| " + " | ".join(header_cells) + " |")
    lines.append("| " + " | ".join(["---"] * len(header_cells)) + " |")

    for item in dataset_items:
        input_images = _extract_case_input_images(item)
        input_html = "<br/>".join(
            f'<img src="{image.get("url")}" width="96" />'
            for image in input_images
            if image.get("url")
        )
        row_cells = [
            str(item.get("name") or ""),
            str(item.get("prompt") or "").replace("\n", "<br/>"),
            input_html,
        ]
        for model_id in model_ids:
            cell = result_map.get((item.get("id"), model_id), {})
            output_images = cell.get("output_images") or []
            image_html = "<br/>".join(
                f'<img src="{image.get("url")}" width="128" />'
                for image in output_images
                if image.get("url")
            )
            status = cell.get("status") or "pending"
            if not image_html:
                image_html = cell.get("error_message") or status
            row_cells.append(image_html)
        lines.append("| " + " | ".join(row_cells) + " |")

    lines.extend(
        [
            "",
            "## 明细表",
            "",
            "| Case | Model | Status | 输入图 | 输出图 | Effective Params | Request IDs | Error |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for cell in cell_results:
        case_snapshot = next((item for item in dataset_items if item.get("id") == cell.get("case_id")), {})
        input_urls = "<br/>".join(image.get("url", "") for image in _extract_case_input_images(case_snapshot))
        output_urls = "<br/>".join(image.get("url", "") for image in cell.get("output_images") or [])
        lines.append(
            "| "
            + " | ".join(
                [
                    str(cell.get("case_name") or ""),
                    str(cell.get("model_name") or cell.get("model_id") or ""),
                    str(cell.get("status") or ""),
                    input_urls.replace("|", "\\|"),
                    output_urls.replace("|", "\\|"),
                    json.dumps(cell.get("effective_params") or {}, ensure_ascii=False).replace("|", "\\|"),
                    ", ".join(cell.get("request_ids") or []),
                    str(cell.get("error_message") or "").replace("|", "\\|"),
                ]
            )
            + " |"
        )

    lines.extend(["", "## Payload 附录", ""])
    for cell in cell_results:
        lines.append(f"### {cell.get('case_name') or cell.get('case_id')} / {cell.get('model_name') or cell.get('model_id')}")
        lines.append("")
        lines.append("#### Canonical Request")
        lines.append("```json")
        lines.append(json.dumps(cell.get("canonical_request") or {}, ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("")
        lines.append("#### Provider Payload")
        lines.append("```json")
        lines.append(json.dumps(cell.get("provider_payload") or {}, ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def _configurable_parameters_for_model(model_meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    return model_meta.get("configurable_parameters") or [
        param
        for param in model_meta.get("parameters") or []
        if param.get("name") not in CONFIGURABLE_PARAM_EXCLUDES
    ]


def _default_params_for_model(model_meta: Dict[str, Any]) -> Dict[str, Any]:
    defaults: Dict[str, Any] = {}
    for param in _configurable_parameters_for_model(model_meta):
        if param.get("default") is not None:
            defaults[param["name"]] = param["default"]
    if "n" in {param.get("name") for param in _configurable_parameters_for_model(model_meta)}:
        defaults.setdefault("n", 1)
    return defaults


def merge_effective_params(
    model_meta: Dict[str, Any],
    baseline_params: Optional[Dict[str, Any]],
    override_params: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """合并某个模型的最终参数"""

    configurable_names = {param.get("name") for param in _configurable_parameters_for_model(model_meta)}
    effective_params = _default_params_for_model(model_meta)
    for source in (baseline_params or {}, override_params or {}):
        for key, value in source.items():
            if key in configurable_names and value is not None:
                effective_params[key] = value
    return effective_params


def _extract_case_input_images(case_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    image_slots = list(case_data.get("image_slots") or [])
    if image_slots:
        return [
            slot.get("image") or {}
            for slot in sorted(image_slots, key=lambda current: current.get("position", 0))
            if isinstance(slot, dict) and (slot.get("image") or {}).get("url")
        ]
    return [image for image in case_data.get("input_images") or [] if image.get("url")]


def _extract_case_ref_urls(case_data: Dict[str, Any]) -> List[str]:
    return [image.get("url") for image in _extract_case_input_images(case_data) if image.get("url")]


async def preview_benchmark_cell(
    *,
    project_id: str,
    task_kind: str,
    model_id: str,
    case_data: Dict[str, Any],
    effective_params: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
    """预览单个测评单元的 payload"""

    ref_urls = _extract_case_ref_urls(case_data)
    if task_kind == "text_to_image" and ref_urls:
        raise HTTPException(status_code=400, detail="文生图样例不能包含输入图片")
    if task_kind == "image_edit" and not ref_urls:
        raise HTTPException(status_code=400, detail="图片编辑样例至少需要 1 张输入图片")

    if model_id in studio_router.WAN27_MODELS and ref_urls:
        await studio_router._inspect_and_validate_wan27_images(ref_urls)

    canonical, provider_payload, warnings = studio_router._build_provider_payload(
        model_name=model_id,
        prompt=case_data.get("prompt") or "",
        negative_prompt=case_data.get("negative_prompt") or "",
        task_kind=task_kind,
        ref_urls=ref_urls,
        n=int(effective_params.get("n") or 1),
        size=effective_params.get("size"),
        prompt_extend=(
            effective_params.get("prompt_extend")
            if effective_params.get("prompt_extend") is not None
            else True
        ),
        watermark=bool(effective_params.get("watermark") or False),
        seed=effective_params.get("seed"),
        enable_interleave=bool(effective_params.get("enable_interleave") or False),
        max_images=int(effective_params.get("max_images") or 5),
        enable_sequential=False,
        thinking_mode=None,
        bbox_list=None,
        color_palette=[],
        size_mode=effective_params.get("size_mode"),
        size_preset=effective_params.get("size_preset"),
        custom_width=effective_params.get("custom_width"),
        custom_height=effective_params.get("custom_height"),
    )
    canonical.project_id = project_id
    return asdict(canonical), provider_payload, warnings


async def execute_benchmark_cell(
    *,
    project_id: str,
    task_kind: str,
    model_meta: Dict[str, Any],
    case_data: Dict[str, Any],
    effective_params: Dict[str, Any],
) -> ImageBenchmarkCellResult:
    """执行单个测评单元"""

    model_id = model_meta["id"]
    model_name = model_meta.get("name") or model_id
    try:
        canonical_request, provider_payload, warnings = await preview_benchmark_cell(
            project_id=project_id,
            task_kind=task_kind,
            model_id=model_id,
            case_data=case_data,
            effective_params=effective_params,
        )
    except HTTPException as exc:
        return ImageBenchmarkCellResult(
            case_id=case_data.get("id") or "",
            case_name=case_data.get("name") or "",
            model_id=model_id,
            model_name=model_name,
            status="unsupported",
            error_message=str(exc.detail),
            effective_params=effective_params,
        )

    ref_urls = _extract_case_ref_urls(case_data)
    task = StudioTask(
        project_id=project_id,
        name=case_data.get("name") or "",
        model=model_id,
        model_id=model_id,
        provider=canonical_request.get("provider") or "wan",
        task_kind=canonical_request.get("task_kind") or task_kind,
        prompt=case_data.get("prompt") or "",
        negative_prompt=case_data.get("negative_prompt") or "",
        n=int(effective_params.get("n") or 1),
        group_count=1,
        size=effective_params.get("size"),
        prompt_extend=(
            effective_params.get("prompt_extend")
            if effective_params.get("prompt_extend") is not None
            else True
        ),
        watermark=bool(effective_params.get("watermark") or False),
        seed=effective_params.get("seed"),
        enable_interleave=bool(effective_params.get("enable_interleave") or False),
        max_images=int(effective_params.get("max_images") or 5),
        enable_sequential=False,
        thinking_mode=None,
        bbox_list=[],
        color_palette=[],
        size_mode=effective_params.get("size_mode"),
        size_preset=effective_params.get("size_preset"),
        custom_width=effective_params.get("custom_width"),
        custom_height=effective_params.get("custom_height"),
        references=[],
        input_assets=canonical_request.get("input_assets") or {},
        normalized_params=canonical_request.get("normalized_params") or {},
        provider_payload_snapshot=provider_payload,
        status="generating",
    )

    config = get_config()
    provider_api_key = get_provider_api_key("wan")
    request_ids: List[str] = []
    task_ids: List[str] = []
    provider_result_meta: Dict[str, Any] = {}

    try:
        if model_id in studio_router.WAN27_MODELS:
            images, task_ids, request_ids, provider_result_meta = await studio_router.generate_with_wan27_image(
                task=task,
                api_key=provider_api_key,
                base_url=config.base_url,
                ref_urls=ref_urls,
                size=task.size,
                enable_sequential=False,
                thinking_mode=None,
                bbox_list=None,
                color_palette=[],
                watermark=task.watermark,
                seed=task.seed,
            )
        elif model_id == "wan2.6-image":
            images, request_ids = await studio_router.generate_with_wan26_image(
                task=task,
                ref_urls=ref_urls or None,
                size=task.size,
                prompt_extend=task.prompt_extend,
                watermark=task.watermark,
                seed=task.seed,
                enable_interleave=task.enable_interleave,
                max_images=task.max_images,
            )
        elif model_id in ("qwen-image-max", "qwen-image-plus"):
            images, request_ids = await studio_router.generate_with_qwen_image(
                task=task,
                api_key=provider_api_key,
                base_url=config.base_url,
                model_name=model_id,
                size=task.size,
                prompt_extend=task.prompt_extend,
                watermark=task.watermark,
                seed=task.seed,
            )
        elif model_id in ("qwen-image-edit-plus", "qwen-image-edit-max"):
            images, request_ids = await studio_router.generate_with_qwen_image_edit(
                task=task,
                ref_urls=ref_urls,
                api_key=provider_api_key,
                base_url=config.base_url,
                model_name=model_id,
                size=task.size,
                prompt_extend=task.prompt_extend,
                watermark=task.watermark,
                seed=task.seed,
            )
        elif model_id in ("qwen-image-2.0-pro", "qwen-image-2.0"):
            images, request_ids = await studio_router.generate_with_qwen_image_2(
                task=task,
                ref_urls=ref_urls,
                api_key=provider_api_key,
                base_url=config.base_url,
                model_name=model_id,
                size=task.size,
                prompt_extend=task.prompt_extend,
                watermark=task.watermark,
                seed=task.seed,
            )
        elif model_id in {"wan2.6-t2i", "wan2.5-t2i-preview"}:
            images, request_ids = await studio_router.generate_with_text_to_image(
                task=task,
                model_name=model_id,
                prompt_extend=task.prompt_extend,
                watermark=task.watermark,
                seed=task.seed,
                size=task.size,
            )
        else:
            images, request_ids = await studio_router.generate_with_wanx_i2i(
                task=task,
                ref_urls=ref_urls,
                size=task.size,
                prompt_extend=task.prompt_extend,
                seed=task.seed,
            )
    except Exception as exc:
        return ImageBenchmarkCellResult(
            case_id=case_data.get("id") or "",
            case_name=case_data.get("name") or "",
            model_id=model_id,
            model_name=model_name,
            status="failed",
            error_message=str(exc),
            request_ids=request_ids,
            task_ids=task_ids,
            validation_warnings=warnings,
            effective_params=effective_params,
            canonical_request=canonical_request,
            provider_payload=provider_payload,
            provider_result_meta=provider_result_meta,
        )

    valid_images = [image for image in images if image.url]
    group_errors = getattr(task, "_group_errors", [])
    error_detail = "; ".join(dict.fromkeys(group_errors)) if group_errors else ""
    if not images or not valid_images:
        status = "failed"
        error_message = error_detail or "未生成有效图片"
    elif len(valid_images) < len(images):
        status = "completed"
        error_message = error_detail or f"部分生成失败：{len(valid_images)}/{len(images)} 张成功"
    else:
        status = "completed"
        error_message = None

    return ImageBenchmarkCellResult(
        case_id=case_data.get("id") or "",
        case_name=case_data.get("name") or "",
        model_id=model_id,
        model_name=model_name,
        status=status,
        output_images=[
            ImageBenchmarkOutputImage(url=image.url, prompt_used=image.prompt_used)
            for image in images
        ],
        error_message=error_message,
        request_ids=request_ids,
        task_ids=task_ids,
        validation_warnings=warnings,
        effective_params=effective_params,
        canonical_request=canonical_request,
        provider_payload=provider_payload,
        provider_result_meta=provider_result_meta,
    )
