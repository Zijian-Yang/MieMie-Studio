"""
图片测评运行时能力

复用图片工作室现有的模型元数据、请求构建与执行能力。
"""

from __future__ import annotations

import base64
import logging
from dataclasses import asdict, dataclass
from html import escape as html_escape
import json
import mimetypes
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException
import asyncio

from app.config import get_config, get_provider_api_key
from app.models.image_benchmark import (
    ImageBenchmarkCellResult,
    ImageBenchmarkDataset,
    ImageBenchmarkOutputImage,
)
from app.models.studio import StudioTask, StudioTaskImage
from app.routers import studio as studio_router
from app.services.oss import oss_service

logger = logging.getLogger(__name__)

BENCHMARK_TASK_KINDS = {"text_to_image", "image_edit", "interactive_edit"}
CONFIGURABLE_PARAM_EXCLUDES = {"prompt", "images"}
BENCHMARK_MANAGED_PARAMS = {"bbox_list", "enable_sequential"}
BENCHMARK_IMAGE_INPUT_DISABLED_PARAMS = {"thinking_mode"}
AUTO_RETRY_INITIAL_DELAY_SECONDS = 2
AUTO_RETRY_MAX_RETRIES = 6
AUTO_RETRY_MAX_DELAY_SECONDS = 64
RETRYABLE_RATE_LIMIT_PATTERNS = [
    "throttling.ratequota",
    "requests rate limit exceeded",
    "rate quota",
    "too many requests",
    "429",
]
EXPORT_INLINE_IMAGE_RETRY_DELAYS_SECONDS = [1, 2, 4, 8]
EXPORT_INLINE_IMAGE_MAX_CONCURRENCY = 8
EXPORT_INLINE_IMAGE_TERMINAL_STATUS_CODES = {400, 401, 403, 404, 405, 410}
EXPORT_INLINE_IMAGE_RETRYABLE_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}


@dataclass
class ImageBenchmarkReportExport:
    content: str
    embedded_image_count: int = 0
    fallback_url_count: int = 0


class ImageBenchmarkExportAssetError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        terminal: bool = False,
        status_code: Optional[int] = None,
    ):
        super().__init__(message)
        self.retryable = retryable
        self.terminal = terminal
        self.status_code = status_code


def _build_auto_retry_delays() -> List[int]:
    return [
        min(AUTO_RETRY_INITIAL_DELAY_SECONDS * (2 ** retry_index), AUTO_RETRY_MAX_DELAY_SECONDS)
        for retry_index in range(AUTO_RETRY_MAX_RETRIES)
    ]


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
        next_model["configurable_parameters"] = _configurable_parameters_for_model(next_model)
        models[model_id] = next_model
    return {
        "task_kinds": [
            {"id": "text_to_image", "label": "文生图"},
            {"id": "image_edit", "label": "图片编辑"},
            {"id": "interactive_edit", "label": "交互式编辑"},
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
                "bbox_list": item.bbox_list,
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


def _markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", "<br/>")


def _html_text(value: Any) -> str:
    return html_escape("" if value is None else str(value), quote=True)


def _render_markdown_image_tag(url: str, width: int) -> str:
    return f'<img src="{_html_text(url)}" width="{width}" />'


def _render_html_image_tag(url: str, alt: str) -> str:
    return f'<img src="{_html_text(url)}" alt="{_html_text(alt)}" />'


def _guess_image_mime_type(url: str, content_type: str) -> str:
    normalized_content_type = (content_type or "").split(";", 1)[0].strip().lower()
    if normalized_content_type.startswith("image/"):
        return normalized_content_type
    guessed, _ = mimetypes.guess_type(urlparse(url).path)
    if guessed and guessed.startswith("image/"):
        return guessed
    return "image/png"


def _is_retryable_export_status(status_code: int) -> bool:
    return status_code in EXPORT_INLINE_IMAGE_RETRYABLE_STATUS_CODES or status_code >= 500


async def _download_image_bytes(
    url: str,
    client: Optional[httpx.AsyncClient] = None,
) -> Tuple[bytes, str]:
    normalized_url = (url or "").strip()
    if not normalized_url:
        raise ImageBenchmarkExportAssetError("图片 URL 为空", terminal=True)

    parsed = urlparse(normalized_url)
    if parsed.scheme not in {"http", "https"}:
        raise ImageBenchmarkExportAssetError(
            f"不支持的图片 URL 协议: {parsed.scheme or '空'}",
            terminal=True,
        )

    request_client = client
    close_client = False
    if request_client is None:
        request_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, read=180.0),
            follow_redirects=True,
        )
        close_client = True

    try:
        response = await request_client.get(normalized_url)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        content_type = exc.response.headers.get("content-type", "")
        raise ImageBenchmarkExportAssetError(
            f"HTTP {status_code}，content-type={content_type or '-'}",
            retryable=_is_retryable_export_status(status_code),
            terminal=status_code in EXPORT_INLINE_IMAGE_TERMINAL_STATUS_CODES,
            status_code=status_code,
        ) from exc
    except httpx.TimeoutException as exc:
        raise ImageBenchmarkExportAssetError("下载超时", retryable=True) from exc
    except httpx.RequestError as exc:
        raise ImageBenchmarkExportAssetError(
            f"下载失败: {exc.__class__.__name__}: {exc}",
            retryable=True,
        ) from exc
    finally:
        if close_client and request_client is not None:
            await request_client.aclose()

    return response.content, response.headers.get("content-type", "")


async def _download_image_as_data_url(
    url: str,
    client: Optional[httpx.AsyncClient] = None,
) -> str:
    normalized_url = (url or "").strip()
    if normalized_url.startswith("data:"):
        return normalized_url

    content, content_type = await _download_image_bytes(normalized_url, client=client)
    mime_type = _guess_image_mime_type(normalized_url, content_type)
    payload = base64.b64encode(content).decode("ascii")
    return f"data:{mime_type};base64,{payload}"


async def _download_image_as_data_url_with_retries(
    url: str,
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
) -> str:
    max_attempts = len(EXPORT_INLINE_IMAGE_RETRY_DELAYS_SECONDS) + 1
    last_error: Optional[Exception] = None

    for attempt_index in range(max_attempts):
        try:
            async with semaphore:
                return await _download_image_as_data_url(url, client=client)
        except ImageBenchmarkExportAssetError as exc:
            last_error = exc
            if exc.terminal or not exc.retryable or attempt_index >= max_attempts - 1:
                raise
            logger.warning(
                "图片测评导出图片下载失败，准备重试: url=%s attempt=%s/%s error=%s",
                url,
                attempt_index + 1,
                max_attempts,
                exc,
            )
        except ValueError as exc:
            last_error = exc
            raise

        await asyncio.sleep(EXPORT_INLINE_IMAGE_RETRY_DELAYS_SECONDS[attempt_index])

    if last_error:
        raise last_error
    raise ImageBenchmarkExportAssetError("图片下载失败", retryable=False)


def _collect_report_image_urls(run: Dict[str, Any]) -> List[str]:
    urls: List[str] = []
    dataset_items = (run.get("dataset_snapshot") or {}).get("items") or []
    for item in dataset_items:
        urls.extend(
            (image.get("url") or "").strip()
            for image in _extract_case_input_images(item)
            if image.get("url")
        )
    for cell in run.get("cell_results") or []:
        urls.extend(
            (image.get("url") or "").strip()
            for image in cell.get("output_images") or []
            if image.get("url")
        )

    unique_urls: List[str] = []
    seen: set[str] = set()
    for url in urls:
        if not url or url in seen:
            continue
        seen.add(url)
        unique_urls.append(url)
    return unique_urls


async def _build_inline_image_map(run: Dict[str, Any]) -> Tuple[Dict[str, str], int, int]:
    image_urls = _collect_report_image_urls(run)
    if not image_urls:
        return {}, 0, 0

    logger.info(
        "图片测评导出开始内嵌图片: run_id=%s image_count=%s concurrency=%s",
        run.get("id"),
        len(image_urls),
        EXPORT_INLINE_IMAGE_MAX_CONCURRENCY,
    )
    semaphore = asyncio.Semaphore(EXPORT_INLINE_IMAGE_MAX_CONCURRENCY)

    async def resolve_image(url: str, client: httpx.AsyncClient) -> Tuple[str, str, Optional[Exception]]:
        try:
            resolved = await _download_image_as_data_url_with_retries(url, client=client, semaphore=semaphore)
            return url, resolved, None
        except Exception as exc:
            return url, url, exc

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(30.0, read=180.0),
        follow_redirects=True,
    ) as client:
        resolved_items = await asyncio.gather(*(resolve_image(url, client) for url in image_urls))

    asset_map: Dict[str, str] = {}
    fallback_url_count = 0
    for original_url, resolved_url, error in resolved_items:
        asset_map[original_url] = resolved_url
        if error is not None:
            fallback_url_count += 1
            logger.warning("图片测评导出内嵌图片失败: url=%s error=%s", original_url, error)

    embedded_image_count = sum(
        1
        for original_url, resolved_url in asset_map.items()
        if resolved_url.startswith("data:") and not original_url.startswith("data:")
    )
    logger.info(
        "图片测评导出完成内嵌图片: run_id=%s embedded=%s fallback=%s",
        run.get("id"),
        embedded_image_count,
        fallback_url_count,
    )
    return asset_map, embedded_image_count, fallback_url_count


def _resolve_report_image_url(url: Optional[str], asset_map: Dict[str, str]) -> str:
    normalized_url = (url or "").strip()
    if not normalized_url:
        return ""
    return asset_map.get(normalized_url, normalized_url)


async def render_markdown_report(
    run: Dict[str, Any],
    inline_images: bool = False,
) -> ImageBenchmarkReportExport:
    """渲染 Markdown 报告"""

    dataset_items = (run.get("dataset_snapshot") or {}).get("items") or []
    model_snapshots = run.get("model_snapshots") or []
    cell_results = run.get("cell_results") or []
    model_ids = [model["id"] for model in model_snapshots]
    asset_map, embedded_image_count, fallback_url_count = (
        await _build_inline_image_map(run) if inline_images else ({}, 0, 0)
    )

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
            _render_markdown_image_tag(_resolve_report_image_url(image.get("url"), asset_map), 96)
            for image in input_images
            if image.get("url")
        )
        row_cells = [
            _markdown_cell(item.get("name")),
            _markdown_cell(item.get("prompt")),
            input_html,
        ]
        for model_id in model_ids:
            cell = result_map.get((item.get("id"), model_id), {})
            output_images = cell.get("output_images") or []
            image_html = "<br/>".join(
                _render_markdown_image_tag(_resolve_report_image_url(image.get("url"), asset_map), 128)
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
        input_urls = "<br/>".join(_markdown_cell(image.get("url", "")) for image in _extract_case_input_images(case_snapshot))
        output_urls = "<br/>".join(_markdown_cell(image.get("url", "")) for image in cell.get("output_images") or [])
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(cell.get("case_name")),
                    _markdown_cell(cell.get("model_name") or cell.get("model_id")),
                    _markdown_cell(cell.get("status")),
                    input_urls,
                    output_urls,
                    json.dumps(cell.get("effective_params") or {}, ensure_ascii=False).replace("|", "\\|"),
                    _markdown_cell(", ".join(cell.get("request_ids") or [])),
                    _markdown_cell(cell.get("error_message")),
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
    return ImageBenchmarkReportExport(
        content="\n".join(lines),
        embedded_image_count=embedded_image_count,
        fallback_url_count=fallback_url_count,
    )


async def render_html_report(
    run: Dict[str, Any],
    suite: Optional[Dict[str, Any]] = None,
    inline_images: bool = False,
) -> ImageBenchmarkReportExport:
    """渲染 HTML 报告"""

    dataset_items = sorted(
        (run.get("dataset_snapshot") or {}).get("items") or [],
        key=lambda item: item.get("sort_order", 0),
    )
    model_snapshots = run.get("model_snapshots") or []
    result_map = {
        (cell.get("case_id"), cell.get("model_id")): cell
        for cell in run.get("cell_results") or []
    }
    asset_map, embedded_image_count, fallback_url_count = (
        await _build_inline_image_map(run) if inline_images else ({}, 0, 0)
    )

    headers = ["样例", "Prompt", "输入图"] + [model.get("name") or model.get("id") for model in model_snapshots]
    table_head = "".join(f"<th>{_html_text(header)}</th>" for header in headers)

    rows: List[str] = []
    for item in dataset_items:
        input_images_html = "".join(
            _render_html_image_tag(
                _resolve_report_image_url(image.get("url"), asset_map),
                image.get("name") or "输入图",
            )
            for image in _extract_case_input_images(item)
            if image.get("url")
        )

        model_cells: List[str] = []
        for model in model_snapshots:
            cell = result_map.get((item.get("id"), model.get("id")), {})
            images_html = "".join(
                _render_html_image_tag(
                    _resolve_report_image_url(image.get("url"), asset_map),
                    image.get("prompt_used") or "输出图",
                )
                for image in cell.get("output_images") or []
                if image.get("url")
            )
            error_html = (
                f'<div class="error">{_html_text(cell.get("error_message"))}</div>'
                if cell.get("error_message")
                else ""
            )
            if not images_html and not error_html:
                images_html = '<span class="muted">未运行</span>'
            model_cells.append(
                f'<div class="status">{_html_text(cell.get("status") or "pending")}</div>'
                f'<div class="images">{images_html}</div>'
                f"{error_html}"
            )

        row = [
            _html_text(item.get("name") or "未命名样例"),
            f'<div class="prompt">{_html_text(item.get("prompt"))}</div>',
            f'<div class="images">{input_images_html}</div>',
            *model_cells,
        ]
        rows.append(f"<tr>{''.join(f'<td>{cell_html}</td>' for cell_html in row)}</tr>")

    content = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{_html_text((suite or {}).get("name") or "图片测评报告")}</title>
  <style>
    body {{ margin: 0; padding: 24px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #1f1f1f; background: #f5f5f5; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; }}
    .meta {{ display: flex; flex-wrap: wrap; gap: 16px; margin: 16px 0 24px; color: #666; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; }}
    th, td {{ border: 1px solid #ddd; padding: 12px; vertical-align: top; min-width: 180px; }}
    th {{ background: #fafafa; position: sticky; top: 0; z-index: 1; }}
    .prompt {{ white-space: pre-wrap; max-width: 360px; }}
    .images {{ display: flex; flex-wrap: wrap; gap: 10px; }}
    img {{ max-width: 240px; max-height: 240px; object-fit: contain; border-radius: 6px; background: #eee; }}
    .status {{ display: inline-block; margin-bottom: 8px; padding: 2px 8px; border-radius: 6px; background: #eef4ff; color: #1d4ed8; font-size: 12px; }}
    .error {{ margin-top: 8px; color: #c00; white-space: pre-wrap; }}
    .muted {{ color: #999; }}
  </style>
</head>
<body>
  <h1>{_html_text((suite or {}).get("name") or "图片测评报告")}</h1>
  <div>{_html_text((suite or {}).get("description") or "")}</div>
  <div class="meta">
    <span>Run ID: {_html_text(run.get("id"))}</span>
    <span>状态: {_html_text(run.get("status"))}</span>
    <span>样例数: {_html_text((run.get("stats") or {}).get("case_count", 0))}</span>
    <span>模型数: {_html_text((run.get("stats") or {}).get("model_count", 0))}</span>
    <span>成功单元: {_html_text((run.get("stats") or {}).get("success_count", 0))}</span>
    <span>失败单元: {_html_text((run.get("stats") or {}).get("failure_count", 0))}</span>
  </div>
  <table>
    <thead><tr>{table_head}</tr></thead>
    <tbody>{"".join(rows)}</tbody>
  </table>
</body>
</html>"""
    return ImageBenchmarkReportExport(
        content=content,
        embedded_image_count=embedded_image_count,
        fallback_url_count=fallback_url_count,
    )


def _configurable_parameters_for_model(model_meta: Dict[str, Any], task_kind: Optional[str] = None) -> List[Dict[str, Any]]:
    params = model_meta.get("configurable_parameters") or [
        param
        for param in model_meta.get("parameters") or []
        if param.get("name") not in CONFIGURABLE_PARAM_EXCLUDES
    ]
    if str(model_meta.get("id") or "").startswith("wan2.7-image"):
        params = [param for param in params if param.get("name") != "size"]
        existing_names = {param.get("name") for param in params}
        params = params + [
            param for param in studio_router.get_wan27_size_mode_parameters()
            if param.get("name") not in existing_names
        ]
    if task_kind:
        excluded = set(BENCHMARK_MANAGED_PARAMS)
        if task_kind != "text_to_image":
            excluded.update(BENCHMARK_IMAGE_INPUT_DISABLED_PARAMS)
        params = [param for param in params if param.get("name") not in excluded]
    return params


def _default_params_for_model(model_meta: Dict[str, Any], task_kind: Optional[str] = None) -> Dict[str, Any]:
    defaults: Dict[str, Any] = {}
    for param in _configurable_parameters_for_model(model_meta, task_kind):
        if param.get("default") is not None:
            defaults[param["name"]] = param["default"]
    if "n" in {param.get("name") for param in _configurable_parameters_for_model(model_meta, task_kind)}:
        defaults.setdefault("n", 1)
    return defaults


def merge_effective_params(
    model_meta: Dict[str, Any],
    baseline_params: Optional[Dict[str, Any]],
    override_params: Optional[Dict[str, Any]],
    task_kind: Optional[str] = None,
) -> Dict[str, Any]:
    """合并某个模型的最终参数"""

    configurable_names = {param.get("name") for param in _configurable_parameters_for_model(model_meta, task_kind)}
    effective_params = _default_params_for_model(model_meta, task_kind)
    for source in (baseline_params or {}, override_params or {}):
        for key, value in source.items():
            if key in configurable_names and value is not None:
                effective_params[key] = value
    return effective_params


def _extract_effective_color_palette(effective_params: Dict[str, Any]) -> List[Dict[str, str]]:
    value = effective_params.get("color_palette")
    if not value:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="颜色主题必须是 JSON 数组") from exc
    if not isinstance(value, list):
        raise HTTPException(status_code=400, detail="颜色主题必须是数组")
    return studio_router._serialize_color_palette(value)


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


def _extract_case_bbox_list(case_data: Dict[str, Any]) -> Optional[List[List[List[int]]]]:
    value = case_data.get("bbox_list")
    return value if isinstance(value, list) else None


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
    bbox_list = _extract_case_bbox_list(case_data)
    normalized_bbox_list = bbox_list if task_kind == "interactive_edit" else None
    if task_kind == "text_to_image" and ref_urls:
        raise HTTPException(status_code=400, detail="文生图样例不能包含输入图片")
    if task_kind in {"image_edit", "interactive_edit"} and not ref_urls:
        raise HTTPException(status_code=400, detail="图片编辑样例至少需要 1 张输入图片")
    if task_kind == "interactive_edit" and bbox_list is None:
        raise HTTPException(status_code=400, detail="交互式编辑样例需要 bbox_list")

    color_palette = _extract_effective_color_palette(effective_params)
    if model_id in studio_router.WAN27_MODELS and ref_urls:
        image_metadata = await studio_router._inspect_and_validate_wan27_images(ref_urls)
        if task_kind == "interactive_edit":
            normalized_bbox_list = studio_router._normalize_bbox_list(normalized_bbox_list, image_metadata)

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
        bbox_list=normalized_bbox_list,
        color_palette=color_palette,
        size_mode=effective_params.get("size_mode"),
        size_preset=effective_params.get("size_preset"),
        custom_width=effective_params.get("custom_width"),
        custom_height=effective_params.get("custom_height"),
    )
    canonical.project_id = project_id
    return asdict(canonical), provider_payload, warnings


def _is_retryable_rate_limit_error(error_message: Optional[str]) -> bool:
    if not error_message:
        return False
    lowered = error_message.lower()
    return any(pattern in lowered for pattern in RETRYABLE_RATE_LIMIT_PATTERNS)


def _merge_unique_ids(existing: List[str], incoming: List[str]) -> List[str]:
    seen = set(existing)
    merged = list(existing)
    for item in incoming:
        if not item or item in seen:
            continue
        seen.add(item)
        merged.append(item)
    return merged


async def _ensure_benchmark_images_persisted(
    images: List[StudioTaskImage],
    project_id: str,
    model_id: str = "",
    request_ids: Optional[List[str]] = None,
    task_ids: Optional[List[str]] = None,
) -> List[str]:
    """在测评结果写入前，统一将输出图片转存到当前 OSS。"""
    if not images or not oss_service.is_enabled():
        return []

    migrated_url_cache: Dict[str, str] = {}
    failed_url_cache: Dict[str, str] = {}
    errors: List[str] = []

    for image in images:
        original_url = image.url
        if not original_url:
            continue
        if not oss_service.should_persist_generated_url(original_url):
            continue
        if original_url in migrated_url_cache:
            image.url = migrated_url_cache[original_url]
            continue
        if original_url in failed_url_cache:
            image.url = None
            continue

        try:
            persisted_url = await oss_service.ensure_image_persisted_async(
                original_url,
                project_id,
                strict=True,
            )
            migrated_url_cache[original_url] = persisted_url
            image.url = persisted_url
        except Exception as exc:
            failed_url_cache[original_url] = str(exc)
            image.url = None
            parsed = urlparse(original_url)
            logger.warning(
                "[OSS][image_benchmark] persist failed model_id=%s project_id=%s request_ids=%s task_ids=%s original_host=%s oss_enabled=%s reason=%s",
                model_id or "unknown",
                project_id or "_global",
                ",".join(request_ids or []) or "-",
                ",".join(task_ids or []) or "-",
                parsed.netloc or "unknown",
                oss_service.is_enabled(),
                str(exc),
            )
            errors.append(str(exc))

    return errors


async def _execute_benchmark_cell_once(
    *,
    project_id: str,
    task_kind: str,
    model_meta: Dict[str, Any],
    case_data: Dict[str, Any],
    effective_params: Dict[str, Any],
) -> ImageBenchmarkCellResult:
    """执行单个测评单元（单次尝试）"""

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
    canonical_size = (canonical_request.get("normalized_params") or {}).get("size") or (provider_payload.get("parameters") or {}).get("size")
    normalized_params = canonical_request.get("normalized_params") or {}
    provider_parameters = provider_payload.get("parameters") or {}
    normalized_bbox_list = (
        normalized_params.get("bbox_list")
        if "bbox_list" in normalized_params
        else provider_parameters.get("bbox_list")
    ) if (canonical_request.get("task_kind") or task_kind) == "interactive_edit" else []
    normalized_color_palette = (canonical_request.get("normalized_params") or {}).get("color_palette") or []
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
        size=canonical_size,
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
        bbox_list=normalized_bbox_list if task_kind == "interactive_edit" else [],
        color_palette=normalized_color_palette,
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
                size=canonical_size,
                enable_sequential=False,
                thinking_mode=None,
                bbox_list=normalized_bbox_list if task.task_kind == "interactive_edit" else None,
                color_palette=normalized_color_palette,
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

    persist_errors = await _ensure_benchmark_images_persisted(
        images,
        project_id,
        model_id=model_id,
        request_ids=request_ids,
        task_ids=task_ids,
    )
    valid_images = [image for image in images if image.url]
    group_errors = getattr(task, "_group_errors", [])
    if persist_errors:
        group_errors = group_errors + persist_errors
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


async def execute_benchmark_cell(
    *,
    project_id: str,
    task_kind: str,
    model_meta: Dict[str, Any],
    case_data: Dict[str, Any],
    effective_params: Dict[str, Any],
) -> ImageBenchmarkCellResult:
    """执行单个测评单元，遇到限流错误时自动重试"""

    last_result: Optional[ImageBenchmarkCellResult] = None
    accumulated_request_ids: List[str] = []
    accumulated_task_ids: List[str] = []
    retry_delays = _build_auto_retry_delays()
    total_attempts = len(retry_delays) + 1
    for attempt_index in range(total_attempts):
        result = await _execute_benchmark_cell_once(
            project_id=project_id,
            task_kind=task_kind,
            model_meta=model_meta,
            case_data=case_data,
            effective_params=effective_params,
        )
        accumulated_request_ids = _merge_unique_ids(accumulated_request_ids, result.request_ids or [])
        accumulated_task_ids = _merge_unique_ids(accumulated_task_ids, result.task_ids or [])
        result.request_ids = accumulated_request_ids
        result.task_ids = accumulated_task_ids
        result.attempt_count = attempt_index + 1
        result.auto_retry_count = attempt_index
        result.provider_result_meta = {
            **(result.provider_result_meta or {}),
            "auto_retry": {
                "attempt_count": attempt_index + 1,
                "retry_count": attempt_index,
                "rate_limit_retried": attempt_index > 0,
                "retry_delays_seconds": retry_delays,
                "request_ids": accumulated_request_ids,
                "task_ids": accumulated_task_ids,
            },
        }

        if result.status != "failed" or not _is_retryable_rate_limit_error(result.error_message):
            return result

        last_result = result
        if attempt_index >= len(retry_delays):
            break
        await asyncio.sleep(retry_delays[attempt_index])

    return last_result or ImageBenchmarkCellResult(
        case_id=case_data.get("id") or "",
        case_name=case_data.get("name") or "",
        model_id=model_meta["id"],
        model_name=model_meta.get("name") or model_meta["id"],
        status="failed",
        error_message="未知错误",
        effective_params=effective_params,
    )
