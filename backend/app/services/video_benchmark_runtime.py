"""
视频测评运行时能力
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import datetime
from html import escape as html_escape
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from app.models.video_benchmark import (
    VideoBenchmarkCellResult,
    VideoBenchmarkDataset,
    VideoBenchmarkOutputVideo,
)
from app.services.oss import oss_service
from app.services.video_adapters import (
    NormalizedVideoTaskRequest,
    get_video_adapter,
    infer_provider,
)
from app.services.video_capabilities import get_video_capabilities


VIDEO_BENCHMARK_TASK_KIND = "image_to_video"
VIDEO_BENCHMARK_POLL_INTERVAL_SECONDS = 5
VIDEO_BENCHMARK_MAX_POLL_ATTEMPTS = 720
VIDEO_BENCHMARK_MAX_GROUP_COUNT = 5
VIDEO_BENCHMARK_MANAGED_PARAMS = {"group_count"}


def _group_count_param() -> Dict[str, Any]:
    return {
        "name": "group_count",
        "label": "生成数量",
        "type": "integer",
        "description": "每个样例在该模型下生成的视频条数。视频测评会为每条结果单独提交一次厂商任务。",
        "help": {
            "summary": "控制每个 case × model 生成多少条视频。",
            "limits": [f"支持 1 到 {VIDEO_BENCHMARK_MAX_GROUP_COUNT} 条"],
            "how_to_choose": ["快速横评时保持 1", "需要比较稳定性或挑选更好结果时设置为 2 到 5"],
        },
        "required": False,
        "default": 1,
        "constraint": {
            "min_value": 1,
            "max_value": VIDEO_BENCHMARK_MAX_GROUP_COUNT,
        },
        "group": "generation",
        "advanced": False,
        "order": 0,
    }


async def get_video_benchmark_capabilities() -> Dict[str, Any]:
    """获取视频测评可用能力"""

    raw = get_video_capabilities()
    models: Dict[str, Any] = {}
    for model_id, model in (raw.get("models") or {}).items():
        if VIDEO_BENCHMARK_TASK_KIND not in (model.get("supported_task_kinds") or []):
            continue
        next_model = dict(model)
        next_model["supported_task_kinds"] = [VIDEO_BENCHMARK_TASK_KIND]
        image_profile = dict((next_model.get("task_profiles") or {}).get(VIDEO_BENCHMARK_TASK_KIND) or {})
        profile_parameters = list(image_profile.get("parameters") or [])
        existing_names = {param.get("name") for param in profile_parameters}
        if "group_count" not in existing_names:
            profile_parameters = [_group_count_param(), *profile_parameters]
        image_profile["parameters"] = profile_parameters
        image_profile["default_values"] = {
            "group_count": 1,
            **(image_profile.get("default_values") or {}),
        }
        next_model["configurable_parameters"] = profile_parameters
        next_model["task_profiles"] = {VIDEO_BENCHMARK_TASK_KIND: image_profile}
        models[model_id] = next_model
    return {
        "task_kinds": [{"id": VIDEO_BENCHMARK_TASK_KIND, "label": "首帧生视频"}],
        "models": models,
    }


def export_dataset_payload(dataset: VideoBenchmarkDataset) -> Dict[str, Any]:
    """导出视频测评数据集 JSON 结构"""

    return {
        "schema_version": dataset.schema_version,
        "type": "video_benchmark_dataset",
        "task_kind": dataset.task_kind,
        "name": dataset.name,
        "description": dataset.description,
        "items": [
            {
                "id": item.id,
                "name": item.name,
                "prompt": item.prompt,
                "negative_prompt": item.negative_prompt,
                "tags": item.tags,
                "first_frame": item.first_frame.model_dump() if item.first_frame else None,
                "audio": item.audio.model_dump() if item.audio else None,
                "duration": item.duration,
            }
            for item in sorted(dataset.items, key=lambda current: current.sort_order)
        ],
    }


def _profile_for_model(model_meta: Dict[str, Any]) -> Dict[str, Any]:
    return (model_meta.get("task_profiles") or {}).get(VIDEO_BENCHMARK_TASK_KIND) or {}


def _default_params_for_model(model_meta: Dict[str, Any]) -> Dict[str, Any]:
    profile = _profile_for_model(model_meta)
    defaults = dict(profile.get("default_values") or {})
    for param in profile.get("parameters") or []:
        name = param.get("name")
        if name and param.get("default") is not None and name not in defaults:
            defaults[name] = param.get("default")
    return defaults


def merge_effective_params(
    model_meta: Dict[str, Any],
    baseline_params: Optional[Dict[str, Any]],
    override_params: Optional[Dict[str, Any]],
    case_data: Dict[str, Any],
) -> Dict[str, Any]:
    """合并模型默认、suite 配置、模型 override 与样例级 duration。"""

    effective = _default_params_for_model(model_meta)
    for source in (baseline_params or {}, override_params or {}):
        for key, value in source.items():
            if value is not None:
                effective[key] = value
    if case_data.get("duration") is not None:
        effective["duration"] = int(case_data["duration"])
    return effective


def _case_asset_url(case_data: Dict[str, Any], key: str) -> Optional[str]:
    asset = case_data.get(key)
    if isinstance(asset, dict):
        return asset.get("url")
    return None


def _normalize_group_count(effective_params: Dict[str, Any]) -> int:
    raw = effective_params.get("group_count", 1)
    try:
        group_count = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("生成数量必须是整数") from exc
    if not (1 <= group_count <= VIDEO_BENCHMARK_MAX_GROUP_COUNT):
        raise ValueError(f"生成数量必须在 1 到 {VIDEO_BENCHMARK_MAX_GROUP_COUNT} 之间")
    effective_params["group_count"] = group_count
    return group_count


def build_normalized_request(
    *,
    project_id: str,
    model_meta: Dict[str, Any],
    case_data: Dict[str, Any],
    effective_params: Dict[str, Any],
) -> NormalizedVideoTaskRequest:
    model_id = model_meta["id"]
    provider = model_meta.get("provider") or infer_provider(model_id, VIDEO_BENCHMARK_TASK_KIND)
    input_assets = {
        "first_frame": [_case_asset_url(case_data, "first_frame")] if _case_asset_url(case_data, "first_frame") else [],
        "audio": [_case_asset_url(case_data, "audio")] if _case_asset_url(case_data, "audio") else [],
    }
    return NormalizedVideoTaskRequest(
        project_id=project_id,
        task_kind=VIDEO_BENCHMARK_TASK_KIND,
        provider=provider,
        model_id=model_id,
        prompt=case_data.get("prompt") or "",
        negative_prompt=case_data.get("negative_prompt") or "",
        input_assets=input_assets,
        normalized_params=dict(effective_params),
    )


def _provider_request(request: NormalizedVideoTaskRequest) -> NormalizedVideoTaskRequest:
    provider_params = {
        key: value
        for key, value in request.normalized_params.items()
        if key not in VIDEO_BENCHMARK_MANAGED_PARAMS
    }
    return replace(request, normalized_params=provider_params)


async def preview_video_benchmark_cell(
    *,
    project_id: str,
    model_meta: Dict[str, Any],
    case_data: Dict[str, Any],
    effective_params: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
    """预览单个视频测评单元的 canonical request 和厂商 payload"""

    _normalize_group_count(effective_params)
    request = build_normalized_request(
        project_id=project_id,
        model_meta=model_meta,
        case_data=case_data,
        effective_params=effective_params,
    )
    adapter_request = _provider_request(request)
    adapter = get_video_adapter(adapter_request.provider)
    await adapter.validate(adapter_request)
    provider_payload = adapter.build_provider_payload(adapter_request)
    return asdict(request), provider_payload, []


def _merge_unique_ids(existing: List[str], incoming: List[str]) -> List[str]:
    seen = set(existing)
    merged = list(existing)
    for item in incoming:
        if not item or item in seen:
            continue
        seen.add(item)
        merged.append(item)
    return merged


async def _persist_video_url(url: str, project_id: str) -> str:
    if oss_service.should_persist_generated_url(url):
        return await oss_service.ensure_video_persisted_async(url, project_id, strict=True)
    return url


async def execute_video_benchmark_cell(
    *,
    project_id: str,
    model_meta: Dict[str, Any],
    case_data: Dict[str, Any],
    effective_params: Dict[str, Any],
) -> VideoBenchmarkCellResult:
    """执行单个视频测评单元"""

    model_id = model_meta["id"]
    model_name = model_meta.get("name") or model_id
    try:
        group_count = _normalize_group_count(effective_params)
    except ValueError as exc:
        return VideoBenchmarkCellResult(
            case_id=case_data.get("id") or "",
            case_name=case_data.get("name") or "",
            model_id=model_id,
            model_name=model_name,
            status="unsupported",
            error_message=str(exc),
            effective_params=effective_params,
        )
    request = build_normalized_request(
        project_id=project_id,
        model_meta=model_meta,
        case_data=case_data,
        effective_params=effective_params,
    )
    canonical_request = asdict(request)
    adapter_request = _provider_request(request)
    adapter = get_video_adapter(adapter_request.provider)
    try:
        await adapter.validate(adapter_request)
        provider_payload = adapter.build_provider_payload(adapter_request)
        warnings: List[str] = []
    except (HTTPException, ValueError) as exc:
        message = exc.detail if isinstance(exc, HTTPException) else str(exc)
        return VideoBenchmarkCellResult(
            case_id=case_data.get("id") or "",
            case_name=case_data.get("name") or "",
            model_id=model_id,
            model_name=model_name,
            status="unsupported",
            error_message=str(message),
            effective_params=effective_params,
            canonical_request=canonical_request,
        )

    request_ids: List[str] = []
    task_ids: List[str] = []
    provider_result_meta: Dict[str, Any] = {}

    try:
        submit_results = list(await asyncio.gather(*[
            adapter.submit(adapter_request, seed_offset=index)
            for index in range(group_count)
        ]))
        task_ids = [result.task_id for result in submit_results if result.task_id]
        request_ids = [result.request_id for result in submit_results if result.request_id]
        first_payload = next((result.provider_payload for result in submit_results if result.provider_payload), None)
        if first_payload:
            provider_payload = first_payload
        first_result = submit_results[0] if submit_results else None
        provider_result_meta = {
            "provider": request.provider,
            "key_profile": (first_result.key_profile if first_result else None) or request.key_profile,
            "group_count": group_count,
            "submitted_at": datetime.now().isoformat(),
            "request_id": first_result.request_id if first_result else None,
            "tasks": {
                result.task_id: {
                    "provider": request.provider,
                    "key_profile": result.key_profile or request.key_profile,
                    "request_id": result.request_id,
                    "submitted_at": datetime.now().isoformat(),
                }
                for result in submit_results
                if result.task_id
            },
        }
    except Exception as exc:
        return VideoBenchmarkCellResult(
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

    final_status = "failed"
    final_error: Optional[str] = None
    output_videos: List[VideoBenchmarkOutputVideo] = []
    for task_id in task_ids:
        task_completed = False
        for attempt in range(VIDEO_BENCHMARK_MAX_POLL_ATTEMPTS):
            status_result = await adapter.fetch(adapter_request, task_id)
            request_ids = _merge_unique_ids(request_ids, [status_result.request_id] if status_result.request_id else [])
            task_meta = (provider_result_meta.get("tasks") or {}).setdefault(task_id, {})
            task_meta.update(
                {
                    "key_profile": status_result.key_profile or task_meta.get("key_profile"),
                    "usage": status_result.usage or {},
                    "error_code": status_result.error_code,
                    "error_message": status_result.error_message,
                    "raw_output": status_result.raw_output or {},
                    "finished_at": datetime.now().isoformat(),
                }
            )
            provider_result_meta.update(
                {
                    "key_profile": status_result.key_profile or provider_result_meta.get("key_profile"),
                    "usage": status_result.usage or {},
                    "error_code": status_result.error_code,
                    "error_message": status_result.error_message,
                    "raw_output": status_result.raw_output or {},
                    "finished_at": datetime.now().isoformat(),
                }
            )
            normalized_status = str(status_result.status).upper()
            if normalized_status == "SUCCEEDED" and status_result.video_url:
                try:
                    persisted_url = await _persist_video_url(status_result.video_url, project_id)
                except Exception as exc:
                    final_status = "failed"
                    final_error = str(exc)
                    break
                output_videos.append(VideoBenchmarkOutputVideo(url=persisted_url))
                task_completed = True
                break
            if normalized_status == "FAILED":
                final_status = "failed"
                final_error = status_result.error_message or status_result.error_code or "视频生成失败"
                break
            if attempt < VIDEO_BENCHMARK_MAX_POLL_ATTEMPTS - 1:
                await asyncio.sleep(VIDEO_BENCHMARK_POLL_INTERVAL_SECONDS)
        else:
            final_status = "failed"
            final_error = "视频生成轮询超时"

        if not task_completed:
            break

    if len(output_videos) == group_count:
        final_status = "completed"

    return VideoBenchmarkCellResult(
        case_id=case_data.get("id") or "",
        case_name=case_data.get("name") or "",
        model_id=model_id,
        model_name=model_name,
        status=final_status,
        output_videos=output_videos,
        error_message=final_error,
        request_ids=request_ids,
        task_ids=task_ids,
        validation_warnings=warnings,
        effective_params=effective_params,
        canonical_request=canonical_request,
        provider_payload=provider_payload,
        provider_result_meta=provider_result_meta,
    )


def _markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", "<br/>")


def _html_text(value: Any) -> str:
    return html_escape("" if value is None else str(value), quote=True)


def render_markdown_report(run: Dict[str, Any]) -> str:
    dataset = run.get("dataset_snapshot") or {}
    model_lookup = {model.get("id"): model for model in run.get("model_snapshots") or []}
    lines = [
        "# 视频测评报告",
        "",
        f"- 任务类型：{run.get('task_kind') or VIDEO_BENCHMARK_TASK_KIND}",
        f"- 样例数：{(run.get('stats') or {}).get('case_count', 0)}",
        f"- 模型数：{(run.get('stats') or {}).get('model_count', 0)}",
        "",
        "| 样例 | 模型 | 状态 | 时长 | 输出视频 | 错误 |",
        "|---|---|---|---:|---|---|",
    ]
    case_lookup = {item.get("id"): item for item in dataset.get("items") or []}
    for cell in run.get("cell_results") or []:
        case_data = case_lookup.get(cell.get("case_id")) or {}
        model = model_lookup.get(cell.get("model_id")) or {}
        videos = [
            video.get("url")
            for video in cell.get("output_videos") or []
            if video.get("url")
        ]
        video_links = "<br/>".join(f"[视频{index + 1}]({url})" for index, url in enumerate(videos))
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(cell.get("case_name") or case_data.get("name") or cell.get("case_id")),
                    _markdown_cell(cell.get("model_name") or model.get("name") or cell.get("model_id")),
                    _markdown_cell(cell.get("status")),
                    _markdown_cell((cell.get("effective_params") or {}).get("duration")),
                    _markdown_cell(video_links),
                    _markdown_cell(cell.get("error_message") or ""),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def render_html_report(run: Dict[str, Any]) -> str:
    dataset = run.get("dataset_snapshot") or {}
    model_lookup = {model.get("id"): model for model in run.get("model_snapshots") or []}
    case_lookup = {item.get("id"): item for item in dataset.get("items") or []}
    rows = []
    for cell in run.get("cell_results") or []:
        case_data = case_lookup.get(cell.get("case_id")) or {}
        model = model_lookup.get(cell.get("model_id")) or {}
        videos = []
        for video in cell.get("output_videos") or []:
            url = video.get("url")
            if url:
                videos.append(f'<video controls preload="metadata" src="{_html_text(url)}"></video>')
        rows.append(
            "<tr>"
            f"<td>{_html_text(cell.get('case_name') or case_data.get('name') or cell.get('case_id'))}</td>"
            f"<td>{_html_text(cell.get('model_name') or model.get('name') or cell.get('model_id'))}</td>"
            f"<td>{_html_text(cell.get('status'))}</td>"
            f"<td>{_html_text((cell.get('effective_params') or {}).get('duration'))}</td>"
            f"<td>{''.join(videos)}</td>"
            f"<td>{_html_text(cell.get('error_message') or '')}</td>"
            "</tr>"
        )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>视频测评报告</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; vertical-align: top; }}
    video {{ width: 240px; max-width: 100%; }}
  </style>
</head>
<body>
  <h1>视频测评报告</h1>
  <p>样例数：{_html_text((run.get('stats') or {}).get('case_count', 0))}，模型数：{_html_text((run.get('stats') or {}).get('model_count', 0))}</p>
  <table>
    <thead><tr><th>样例</th><th>模型</th><th>状态</th><th>时长</th><th>输出视频</th><th>错误</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</body>
</html>"""
