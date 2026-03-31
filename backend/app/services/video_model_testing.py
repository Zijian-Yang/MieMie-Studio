"""
视频模型真实验证服务

功能：
1. 扫描用户现有 OSS 资产
2. 生成稳定的模型测试素材 manifest
3. 按 capability schema 执行真实模型验证
4. 输出 JSON / Markdown 报告
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

import httpx
from PIL import Image

from app.config import get_config, get_provider_api_key, set_user_config_dir
from app.models.media import VideoStudioTask
from app.models.project import Project
from app.services.dashscope.vace_video_edit import VaceVideoEditService
from app.services.storage import set_current_user, storage_service
from app.services.user_service import get_user_service
from app.services.video_adapters import (
    NormalizedVideoTaskRequest,
    get_video_adapter,
)
from app.services.video_capabilities import get_video_capabilities


VERIFICATION_PROJECT_NAME = "__模型验证__"
REPORT_DIR = Path(__file__).parent.parent.parent / "logs" / "model_verification"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".m4v", ".webm"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
LEGACY_TASK_TYPE_MAP = {
    "image_to_video": "image_to_video",
    "reference_to_video": "reference_to_video",
    "text_to_video": "text_to_video",
    "keyframe_to_video": "keyframe_to_video",
    "video_repainting": "video_repainting",
    "video_edit_local": "video_edit",
    "video_edit_global": "video_edit_global",
}


@dataclass
class VerificationCase:
    provider: str
    key_profile: str
    model_id: str
    task_kind: str
    variant: str
    request: NormalizedVideoTaskRequest
    fixture_role_summary: Dict[str, Any]


def _sha_key_fingerprint(value: str) -> str:
    if not value:
        return ""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _ensure_report_dir() -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    return REPORT_DIR


def _user_data_path(user_id: str) -> Path:
    return get_user_service().get_user_data_path(user_id)


def _manifest_path(user_id: str) -> Path:
    return _user_data_path(user_id) / "model_test_manifest.json"


def _set_user_context(user_id: str) -> Path:
    set_current_user(user_id)
    user_dir = _user_data_path(user_id)
    set_user_config_dir(str(user_dir))
    return user_dir


def _iter_json_records(base_dir: Path, category: str) -> Iterable[tuple[Path, dict]]:
    category_dir = base_dir / category
    if not category_dir.exists():
        return []
    result = []
    for file_path in sorted(category_dir.glob("*.json")):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                result.append((file_path, json.load(f)))
        except Exception:
            continue
    return result


def _configured_bucket_host() -> str:
    config = get_config()
    if not config.oss.bucket_name or not config.oss.endpoint_host:
        return ""
    return f"{config.oss.bucket_name}.{config.oss.endpoint_host}"


def _is_persistent_oss_url(url: str, bucket_host: str) -> bool:
    if not url or not bucket_host:
        return False
    parsed = urlparse(url)
    if not parsed.netloc:
        return False
    if parsed.netloc.startswith("dashscope-result-"):
        return False
    return parsed.netloc == bucket_host


def _pick_by_ext(url: str, allowed_exts: set[str]) -> bool:
    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in allowed_exts)


async def _download_bytes(url: str, timeout: float = 60.0) -> bytes:
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, read=max(timeout, 120.0))) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content


async def _validate_image_url(url: str) -> dict:
    content = await _download_bytes(url, timeout=30.0)
    image = Image.open(BytesIO(content))
    width, height = image.size
    return {
        "url": url,
        "width": width,
        "height": height,
        "format": (image.format or "").upper(),
        "file_size": len(content),
    }


async def _validate_audio_url(url: str) -> dict:
    content = await _download_bytes(url, timeout=60.0)
    suffix = Path(urlparse(url).path).suffix or ".mp3"
    tmp_file = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp_file.write(content)
    tmp_file.close()
    try:
        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                tmp_file.name,
            ],
            capture_output=True,
            text=True,
        )
        duration = float(probe.stdout.strip() or 0.0) if probe.returncode == 0 else 0.0
        return {
            "url": url,
            "duration": duration,
            "file_size": len(content),
            "format": suffix.lstrip(".").lower(),
        }
    finally:
        os.unlink(tmp_file.name)


async def _validate_video_url(url: str) -> dict:
    service = VaceVideoEditService()
    metadata = await service.validate_source_video(url)
    metadata["url"] = url
    return metadata


async def generate_model_test_manifest(user_id: str, refresh: bool = True) -> dict:
    base_dir = _set_user_context(user_id)
    manifest_file = _manifest_path(user_id)

    if manifest_file.exists() and not refresh:
        with open(manifest_file, "r", encoding="utf-8") as f:
            return json.load(f)

    bucket_host = _configured_bucket_host()
    if not bucket_host:
        raise ValueError("当前用户未配置可用的 OSS Bucket，无法生成测试素材 manifest")

    gallery_urls: List[str] = []
    video_library_urls: List[str] = []
    audio_urls: List[str] = []
    local_edit_candidates: List[dict] = []
    first_frame_urls: List[str] = []
    last_frame_urls: List[str] = []
    reference_video_urls: List[str] = []

    for _, data in _iter_json_records(base_dir, "gallery"):
        url = data.get("url")
        if _is_persistent_oss_url(url, bucket_host) and _pick_by_ext(url, IMAGE_EXTS):
            gallery_urls.append(url)

    for _, data in _iter_json_records(base_dir, "video_library"):
        url = data.get("url")
        if _is_persistent_oss_url(url, bucket_host) and _pick_by_ext(url, VIDEO_EXTS):
            video_library_urls.append(url)

    for _, data in _iter_json_records(base_dir, "audio"):
        url = data.get("url")
        if _is_persistent_oss_url(url, bucket_host) and _pick_by_ext(url, AUDIO_EXTS):
            audio_urls.append(url)

    for _, data in _iter_json_records(base_dir, "video_studio"):
        first = data.get("first_frame_url")
        last = data.get("last_frame_url")
        source = data.get("source_video_url")
        mask = data.get("mask_image_url")
        reference_image = data.get("reference_image_url")
        audio = data.get("audio_url")
        refs = data.get("reference_video_urls") or []
        if _is_persistent_oss_url(first, bucket_host) and _pick_by_ext(first, IMAGE_EXTS):
            first_frame_urls.append(first)
        if _is_persistent_oss_url(last, bucket_host) and _pick_by_ext(last, IMAGE_EXTS):
            last_frame_urls.append(last)
        for ref in refs:
            if _is_persistent_oss_url(ref, bucket_host):
                if _pick_by_ext(ref, VIDEO_EXTS):
                    reference_video_urls.append(ref)
                elif _pick_by_ext(ref, IMAGE_EXTS):
                    gallery_urls.append(ref)
        if _is_persistent_oss_url(audio, bucket_host) and _pick_by_ext(audio, AUDIO_EXTS):
            audio_urls.append(audio)
        if (
            _is_persistent_oss_url(source, bucket_host)
            and _pick_by_ext(source, VIDEO_EXTS)
            and _is_persistent_oss_url(mask, bucket_host)
            and _pick_by_ext(mask, IMAGE_EXTS)
        ):
            local_edit_candidates.append(
                {
                    "source_video_url": source,
                    "mask_image_url": mask,
                    "reference_image_url": reference_image if _is_persistent_oss_url(reference_image, bucket_host) else None,
                }
            )

    seen_images = list(dict.fromkeys(gallery_urls + first_frame_urls + last_frame_urls))
    seen_videos = list(dict.fromkeys(video_library_urls + reference_video_urls))
    seen_audios = list(dict.fromkeys(audio_urls))

    if not seen_images:
        raise ValueError("未找到可用于测试的持久化 OSS 图片")
    if not seen_videos:
        raise ValueError("未找到可用于测试的持久化 OSS 视频")
    if not seen_audios:
        raise ValueError("未找到可用于测试的持久化 OSS 音频")
    if not local_edit_candidates:
        raise ValueError("未找到可用于局部编辑测试的 source_video + mask 组合")

    validated_first = await _validate_image_url(first_frame_urls[0] if first_frame_urls else seen_images[0])
    validated_last = await _validate_image_url(last_frame_urls[0] if last_frame_urls else seen_images[min(1, len(seen_images) - 1)])

    reference_images: List[dict] = []
    for url in seen_images:
        try:
            reference_images.append(await _validate_image_url(url))
        except Exception:
            continue
        if len(reference_images) >= 4:
            break
    if not reference_images:
        raise ValueError("未找到通过预检的参考图片")

    reference_videos: List[dict] = []
    for url in seen_videos:
        try:
            reference_videos.append(await _validate_video_url(url))
        except Exception:
            continue
        if len(reference_videos) >= 3:
            break
    if not reference_videos:
        raise ValueError("未找到通过预检的参考视频")

    driver_audio = None
    for url in seen_audios:
        try:
            driver_audio = await _validate_audio_url(url)
            break
        except Exception:
            continue
    if driver_audio is None:
        raise ValueError("未找到通过预检的驱动音频")

    local_edit_fixture = None
    for candidate in local_edit_candidates:
        try:
            source = await _validate_video_url(candidate["source_video_url"])
            service = VaceVideoEditService()
            await service.validate_mask_image(candidate["mask_image_url"], source["width"], source["height"])
            reference_image = candidate["reference_image_url"]
            if reference_image:
                validated_reference = await _validate_image_url(reference_image)
            else:
                validated_reference = reference_images[0]
            local_edit_fixture = {
                "local_edit_source_video": source,
                "local_edit_mask_image": {"url": candidate["mask_image_url"]},
                "local_edit_reference_image": validated_reference,
            }
            break
        except Exception:
            continue
    if local_edit_fixture is None:
        raise ValueError("未找到通过预检的局部编辑素材组合")

    manifest = {
        "generated_at": datetime.now().isoformat(),
        "user_id": user_id,
        "bucket_host": bucket_host,
        "roles": {
            "first_frame_image": validated_first,
            "last_frame_image": validated_last,
            "reference_images": reference_images,
            "reference_videos": reference_videos,
            "base_videos": reference_videos[:2],
            "local_edit_source_video": local_edit_fixture["local_edit_source_video"],
            "local_edit_mask_image": local_edit_fixture["local_edit_mask_image"],
            "local_edit_reference_image": local_edit_fixture["local_edit_reference_image"],
            "driver_audio": driver_audio,
        },
    }

    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return manifest


def _ensure_verification_project(user_id: str) -> Project:
    _set_user_context(user_id)
    for project in storage_service.list_projects():
        if project.name == VERIFICATION_PROJECT_NAME:
            return project
    project = Project(name=VERIFICATION_PROJECT_NAME, description="视频模型真实验证专用项目")
    storage_service.save_project(project)
    return project


def _default_prompt(task_kind: str, variant: str) -> str:
    if task_kind == "text_to_video":
        return "工业机械臂在现代仓储车间中执行精准开柜门动作，镜头稳定，主体清晰。"
    if task_kind == "image_to_video":
        return "让画面中的主体产生自然连续运动，镜头稳定，细节清晰。"
    if task_kind == "keyframe_to_video":
        return "在首尾帧之间生成平滑过渡，保持主体一致。"
    if task_kind == "reference_to_video":
        return "参考输入素材的主体和运动特征，生成自然稳定的视频。"
    if task_kind == "video_edit_global":
        return "保留原视频镜头与背景，按要求完成整段视频编辑。"
    if task_kind == "video_repainting":
        return "保持原视频动作和节奏，完成稳定重绘。"
    if task_kind == "video_edit_local":
        return "将白色蒙版区域替换为参考图中的机械臂，仅修改蒙版区域。"
    return f"{task_kind}-{variant}"


def _build_request_from_manifest(
    project_id: str,
    provider: str,
    key_profile: str,
    model_id: str,
    task_kind: str,
    task_profile: dict,
    variant: str,
    manifest: dict,
) -> VerificationCase:
    roles = manifest["roles"]
    params = dict(task_profile.get("default_values") or {})
    if provider == "kling":
        params.setdefault("mode", "std")
        params.setdefault("watermark", True)
        if task_kind in {"text_to_video", "reference_to_video"}:
            params.setdefault("aspect_ratio", "16:9")
    elif provider == "vidu":
        params.setdefault("resolution", "720P")
        params.setdefault("watermark", True)
    else:
        params.setdefault("watermark", True)
    prompt = _default_prompt(task_kind, variant)
    narrative_mode = "single"
    input_assets: Dict[str, Any] = {}
    fixture_role_summary: Dict[str, Any] = {}

    if task_kind == "text_to_video":
        if provider == "kling" and variant == "multi_shot_intelligence":
            narrative_mode = "multi_shot_intelligence"
        elif provider == "kling" and variant == "multi_shot_customize":
            narrative_mode = "multi_shot_customize"
            params["multi_prompt_segments"] = [
                {"prompt": "镜头一：机械臂接近柜门把手。", "duration": 3},
                {"prompt": "镜头二：机械臂平稳打开柜门。", "duration": 3},
            ]
        fixture_role_summary = {}
    elif task_kind == "image_to_video":
        input_assets["first_frame"] = [roles["first_frame_image"]["url"]]
        fixture_role_summary = {"first_frame": roles["first_frame_image"]["url"]}
        if model_id == "wan2.2-s2v":
            input_assets["audio"] = [roles["driver_audio"]["url"]]
            fixture_role_summary["audio"] = roles["driver_audio"]["url"]
    elif task_kind == "keyframe_to_video":
        input_assets["first_frame"] = [roles["first_frame_image"]["url"]]
        input_assets["last_frame"] = [roles["last_frame_image"]["url"]]
        fixture_role_summary = {
            "first_frame": roles["first_frame_image"]["url"],
            "last_frame": roles["last_frame_image"]["url"],
        }
    elif task_kind == "reference_to_video":
        input_assets["reference_images"] = [roles["reference_images"][0]["url"]]
        fixture_role_summary = {"reference_images": [roles["reference_images"][0]["url"]]}
        if variant == "video_plus_image":
            input_assets["reference_videos"] = [roles["reference_videos"][0]["url"]]
            fixture_role_summary["reference_videos"] = [roles["reference_videos"][0]["url"]]
    elif task_kind == "video_edit_global":
        input_assets["base_video"] = [roles["base_videos"][0]["url"]]
        fixture_role_summary = {"base_video": roles["base_videos"][0]["url"]}
        if variant == "base_plus_reference":
            input_assets["reference_images"] = [roles["reference_images"][0]["url"]]
            fixture_role_summary["reference_images"] = [roles["reference_images"][0]["url"]]
    elif task_kind == "video_repainting":
        input_assets["source_video"] = [roles["local_edit_source_video"]["url"]]
        input_assets["reference_images"] = [roles["local_edit_reference_image"]["url"]]
        params.setdefault("control_condition", "depth")
        params.setdefault("strength", 0.7)
        fixture_role_summary = {
            "source_video": roles["local_edit_source_video"]["url"],
            "reference_images": [roles["local_edit_reference_image"]["url"]],
        }
    elif task_kind == "video_edit_local":
        input_assets["source_video"] = [roles["local_edit_source_video"]["url"]]
        input_assets["mask_image"] = [roles["local_edit_mask_image"]["url"]]
        input_assets["reference_images"] = [roles["local_edit_reference_image"]["url"]]
        params.setdefault("mask_frame_id", 1)
        params.setdefault("mask_type", "tracking")
        params.setdefault("expand_ratio", 0.08)
        params.setdefault("expand_mode", "hull")
        fixture_role_summary = {
            "source_video": roles["local_edit_source_video"]["url"],
            "mask_image": roles["local_edit_mask_image"]["url"],
            "reference_images": [roles["local_edit_reference_image"]["url"]],
        }

    request = NormalizedVideoTaskRequest(
        project_id=project_id,
        task_kind=task_kind,
        provider=provider,
        key_profile=key_profile,
        model_id=model_id,
        prompt=prompt,
        narrative_mode=narrative_mode,
        input_assets=input_assets,
        normalized_params=params,
    )
    return VerificationCase(
        provider=provider,
        key_profile=key_profile,
        model_id=model_id,
        task_kind=task_kind,
        variant=variant,
        request=request,
        fixture_role_summary=fixture_role_summary,
    )


def build_verification_cases(manifest: dict, project_id: str, provider: str, key_profile: str, scope: str) -> List[VerificationCase]:
    capabilities = get_video_capabilities()
    cases: List[VerificationCase] = []
    for model_id, model in capabilities["models"].items():
        if provider != "all" and model["provider"] != provider:
            continue
        for task_kind in model.get("supported_task_kinds", []):
            task_profile = (model.get("task_profiles") or {}).get(task_kind)
            if not task_profile:
                continue
            verification_profiles = task_profile.get("verification_profiles") or {"smoke": ["default"], "full": ["default"]}
            variants = verification_profiles.get(scope, verification_profiles.get("smoke", ["default"]))
            for variant in variants:
                cases.append(
                    _build_request_from_manifest(
                        project_id=project_id,
                        provider=model["provider"],
                        key_profile=key_profile,
                        model_id=model_id,
                        task_kind=task_kind,
                        task_profile=task_profile,
                        variant=variant,
                        manifest=manifest,
                    )
                )
    return cases


async def _poll_until_finished(
    request: NormalizedVideoTaskRequest,
    task_id: str,
    timeout_seconds: int,
) -> tuple[Any, float]:
    adapter = get_video_adapter(request.provider)
    started = datetime.now()
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    while True:
        result = await adapter.fetch(request, task_id)
        if str(result.status).upper() in {"SUCCEEDED", "FAILED"}:
            elapsed = (datetime.now() - started).total_seconds()
            return result, elapsed
        if asyncio.get_event_loop().time() >= deadline:
            raise TimeoutError(f"任务超时: {task_id}")
        await asyncio.sleep(10)


async def run_video_model_verification(
    *,
    user_id: str,
    provider: str,
    key_profile: str,
    scope: str,
    timeout_minutes: int = 20,
    refresh_manifest: bool = True,
) -> dict:
    _set_user_context(user_id)
    manifest = await generate_model_test_manifest(user_id, refresh=refresh_manifest)
    project = _ensure_verification_project(user_id)
    cases = build_verification_cases(manifest, project.id, provider, key_profile, scope)
    if not cases:
        raise ValueError("未生成任何测试用例，请检查 provider / capability 配置")

    report_rows: List[dict] = []
    timeout_seconds = max(timeout_minutes, 1) * 60

    for case in cases:
        adapter = get_video_adapter(case.provider)
        key_fingerprint = _sha_key_fingerprint(
            get_provider_api_key(case.provider, override_profile=case.key_profile)
        )
        task = VideoStudioTask(
            project_id=project.id,
            name=f"[验证]{case.provider}/{case.model_id}/{case.task_kind}/{case.variant}",
            task_type=LEGACY_TASK_TYPE_MAP.get(case.task_kind, case.task_kind),
            task_kind=case.task_kind,
            provider=case.provider,
            key_profile=case.key_profile,
            model_id=case.model_id,
            model=case.model_id,
            narrative_mode=case.request.narrative_mode,
            input_assets=case.request.input_assets,
            normalized_params=case.request.normalized_params,
            prompt=case.request.prompt,
            status="processing",
        )
        storage_service.save_video_studio_task(task)

        row = {
            "provider": case.provider,
            "key_profile": case.key_profile,
            "key_fingerprint": key_fingerprint,
            "model_id": case.model_id,
            "task_kind": case.task_kind,
            "variant": case.variant,
            "task_record_id": task.id,
            "fixture_role_summary": case.fixture_role_summary,
            "status": "FAILED",
            "oss_url": None,
            "request_id": None,
            "task_id": None,
            "elapsed_seconds": None,
            "error_code": None,
            "error_message": None,
        }

        try:
            await adapter.validate(case.request)
            submit_result = await adapter.submit(case.request)
            task.task_ids = [submit_result.task_id]
            task.request_ids = [submit_result.request_id] if submit_result.request_id else []
            task.provider_payload_snapshot = submit_result.provider_payload
            task.provider_result_meta = {
                submit_result.task_id: {
                    "provider": case.provider,
                    "key_profile": submit_result.key_profile or case.key_profile,
                    "request_id": submit_result.request_id,
                    "submitted_at": datetime.now().isoformat(),
                }
            }
            storage_service.save_video_studio_task(task)

            result, elapsed = await _poll_until_finished(case.request, submit_result.task_id, timeout_seconds)
            task.updated_at = datetime.now()
            row["task_id"] = submit_result.task_id
            row["request_id"] = result.request_id or submit_result.request_id
            row["elapsed_seconds"] = round(elapsed, 2)
            row["error_code"] = result.error_code
            row["error_message"] = result.error_message
            task.provider_result_meta[submit_result.task_id] = {
                **task.provider_result_meta.get(submit_result.task_id, {}),
                "request_id": result.request_id or submit_result.request_id,
                "error_code": result.error_code,
                "error_message": result.error_message,
                "finished_at": datetime.now().isoformat(),
            }

            if str(result.status).upper() == "SUCCEEDED" and result.video_url:
                task.status = "succeeded"
                task.video_urls = [result.video_url]
                task.selected_video_url = result.video_url
                row["status"] = "SUCCEEDED"
                row["oss_url"] = result.video_url
            else:
                task.status = "failed"
                task.error_message = result.error_message or "任务失败"
                row["status"] = "FAILED"
            storage_service.save_video_studio_task(task)
        except Exception as exc:
            task.status = "failed"
            task.error_message = str(exc)
            task.updated_at = datetime.now()
            storage_service.save_video_studio_task(task)
            row["error_message"] = str(exc)

        report_rows.append(row)

    report = {
        "generated_at": datetime.now().isoformat(),
        "user_id": user_id,
        "provider": provider,
        "key_profile": key_profile,
        "scope": scope,
        "case_count": len(report_rows),
        "success_count": sum(1 for row in report_rows if row["status"] == "SUCCEEDED"),
        "failure_count": sum(1 for row in report_rows if row["status"] != "SUCCEEDED"),
        "manifest_path": str(_manifest_path(user_id)),
        "rows": report_rows,
    }

    report_dir = _ensure_report_dir()
    prefix = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = report_dir / f"{prefix}_{provider}_{key_profile}_{scope}.json"
    md_path = report_dir / f"{prefix}_{provider}_{key_profile}_{scope}.md"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(render_markdown_report(report))

    report["json_report"] = str(json_path)
    report["markdown_report"] = str(md_path)
    return report


def render_markdown_report(report: dict) -> str:
    lines = [
        "# 视频模型真实验证报告",
        "",
        f"- 生成时间: {report['generated_at']}",
        f"- 用户: {report['user_id']}",
        f"- Provider: {report['provider']}",
        f"- Key Profile: {report['key_profile']}",
        f"- Scope: {report['scope']}",
        f"- 成功: {report['success_count']}",
        f"- 失败: {report['failure_count']}",
        "",
        "| Provider | Key | Model | Task | Variant | Status | Request ID | OSS URL | Error |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in report["rows"]:
        lines.append(
            f"| {row['provider']} | {row['key_profile']} | {row['model_id']} | {row['task_kind']} | "
            f"{row['variant']} | {row['status']} | {row.get('request_id') or ''} | "
            f"{row.get('oss_url') or ''} | {row.get('error_message') or ''} |"
        )
    lines.append("")
    return "\n".join(lines)


def select_default_user_id() -> str:
    users_root = Path(__file__).parent.parent.parent / "data" / "users"
    candidates: List[tuple[int, str]] = []
    for user_dir in users_root.iterdir():
        if not user_dir.is_dir():
            continue
        score = 0
        for category in ("gallery", "video_library", "audio", "video_studio"):
            category_dir = user_dir / category
            score += len(list(category_dir.glob("*.json"))) if category_dir.exists() else 0
        candidates.append((score, user_dir.name))
    if not candidates:
        raise ValueError("未找到任何用户数据目录")
    candidates.sort(reverse=True)
    return candidates[0][1]
