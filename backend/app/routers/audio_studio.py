"""
音频工作室 API 路由

支持三种任务类型：
1. tts - 文本转语音
2. voice_clone - 声音复刻
3. voice_design - 声音设计
"""

import asyncio
import time
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from app.models.audio_studio import AudioStudioTask, VoiceProfile
from app.services.storage import storage_service, get_current_user_id, set_current_user
from app.services.cosyvoice.tts_service import CosyVoiceTTSService, _get_extension
from app.services.cosyvoice.voice_service import (
    CosyVoiceCloneService, CosyVoiceDesignService, TARGET_MODEL,
)
from app.services.oss import oss_service
from app.config import set_user_config_dir, get_user_config_dir

logger = logging.getLogger(__name__)

router = APIRouter()


def _estimate_audio_duration(audio_data: bytes, fmt: str) -> Optional[float]:
    """从音频二进制数据估算时长（秒）"""
    try:
        if fmt.startswith("wav"):
            import wave, io
            with wave.open(io.BytesIO(audio_data), "rb") as w:
                return w.getnframes() / w.getframerate()
        elif fmt.startswith("pcm"):
            parts = fmt.split("_")  # e.g. pcm_16000hz_mono_16bit
            sample_rate = int(parts[1].replace("hz", ""))
            bits = int(parts[3].replace("bit", ""))
            channels = 2 if "stereo" in fmt else 1
            return len(audio_data) / (sample_rate * channels * bits / 8)
        elif fmt.startswith("mp3"):
            parts = fmt.split("_")  # e.g. mp3_22050hz_mono_256kbps
            bitrate = int(parts[3].replace("kbps", "")) * 1000
            return len(audio_data) * 8 / bitrate
    except Exception as e:
        logger.warning(f"[TTS] 计算音频时长失败: {e}")
    return None


# ─── Request Models ──────────────────────────────────────

class TTSCreateRequest(BaseModel):
    project_id: str
    name: str = ""
    text: str
    voice: str
    format: str = "mp3_22050hz_mono_256kbps"
    volume: int = 50
    speech_rate: float = 1.0
    pitch_rate: float = 1.0
    seed: Optional[int] = None
    language_hints: Optional[str] = None
    instruction: Optional[str] = None
    enable_ssml: bool = False


class VoiceCloneCreateRequest(BaseModel):
    project_id: str
    name: str = ""
    audio_url: str
    prefix: str
    language_hints: Optional[str] = None


class VoiceDesignCreateRequest(BaseModel):
    project_id: str
    name: str = ""
    voice_prompt: str
    preview_text: str
    prefix: str
    sample_rate: int = 24000
    response_format: str = "wav"


# ─── Task CRUD ───────────────────────────────────────────

@router.get("")
async def list_tasks(project_id: str):
    """列出项目所有音频工作室任务"""
    tasks = storage_service.get_audio_studio_tasks(project_id)
    return {"tasks": tasks}


@router.get("/voices")
async def list_voices(project_id: str):
    """列出项目所有自定义音色"""
    profiles = storage_service.get_voice_profiles(project_id)
    return {"voices": profiles}


@router.get("/{task_id}")
async def get_task(task_id: str):
    """获取任务详情"""
    task = storage_service.get_audio_studio_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"task": task}


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    """删除任务"""
    storage_service.delete_audio_studio_task(task_id)
    return {"success": True}


@router.delete("/voices/{profile_id}")
async def delete_voice_profile(profile_id: str):
    """删除自定义音色"""
    profile = storage_service.get_voice_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="音色不存在")
    try:
        clone_service = CosyVoiceCloneService()
        await asyncio.to_thread(clone_service.delete_voice, profile.voice_id)
    except Exception as e:
        logger.warning(f"[音频工作室] 远程删除音色失败: {e}")
    storage_service.delete_voice_profile(profile_id)
    return {"success": True}


# ─── TTS ─────────────────────────────────────────────────

@router.post("/tts")
async def create_tts_task(req: TTSCreateRequest):
    """创建文本转语音任务"""
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="文本不能为空")
    if not req.voice:
        raise HTTPException(status_code=400, detail="请选择音色")

    task = AudioStudioTask(
        project_id=req.project_id,
        task_type="tts",
        name=req.name or f"TTS-{req.voice[:20]}",
        text=req.text,
        voice=req.voice,
        format=req.format,
        volume=req.volume,
        speech_rate=req.speech_rate,
        pitch_rate=req.pitch_rate,
        seed=req.seed,
        language_hints=req.language_hints,
        instruction=req.instruction,
        enable_ssml=req.enable_ssml,
        status="processing",
    )
    storage_service.save_audio_studio_task(task)

    user_id = get_current_user_id()
    user_config_dir = get_user_config_dir()
    asyncio.create_task(_background_tts(task, user_id, user_config_dir))

    return {"task": task}


async def _background_tts(task: AudioStudioTask, user_id, user_config_dir):
    """后台执行 TTS 合成"""
    set_current_user(user_id)
    if user_config_dir:
        set_user_config_dir(user_config_dir)
    try:
        tts_service = CosyVoiceTTSService()
        audio_data, request_id = await asyncio.to_thread(
            tts_service.synthesize,
            text=task.text,
            voice=task.voice,
            format=task.format,
            volume=task.volume,
            speech_rate=task.speech_rate,
            pitch_rate=task.pitch_rate,
            seed=task.seed,
            language_hints=task.language_hints,
            instruction=task.instruction,
            enable_ssml=task.enable_ssml,
        )

        ext = _get_extension(task.format)
        audio_url = None
        if oss_service.is_enabled():
            success, result = await asyncio.to_thread(
                oss_service.upload_from_bytes,
                audio_data, "audio", ext, task.project_id,
            )
            if success:
                audio_url = result
            else:
                logger.warning(f"[TTS] OSS 上传失败: {result}")

        if not audio_url:
            import os
            from pathlib import Path
            assets_dir = Path(__file__).parent.parent.parent / "data" / "assets" / "audio"
            assets_dir.mkdir(parents=True, exist_ok=True)
            file_name = f"{task.id}.{ext}"
            file_path = assets_dir / file_name
            with open(file_path, "wb") as f:
                f.write(audio_data)
            audio_url = f"/assets/audio/{file_name}"

        task.result_audio_url = audio_url
        task.request_id = request_id
        task.audio_duration = _estimate_audio_duration(audio_data, task.format)
        task.status = "succeeded"

    except Exception as e:
        logger.error(f"[TTS] 合成失败: {e}", exc_info=True)
        task.status = "failed"
        task.error_message = str(e)

    storage_service.save_audio_studio_task(task)


# ─── Voice Clone ─────────────────────────────────────────

@router.post("/voice-clone")
async def create_voice_clone_task(req: VoiceCloneCreateRequest):
    """创建声音复刻任务"""
    if not req.audio_url:
        raise HTTPException(status_code=400, detail="请选择音频文件")
    if not req.prefix:
        raise HTTPException(status_code=400, detail="请输入音色名称前缀")

    task = AudioStudioTask(
        project_id=req.project_id,
        task_type="voice_clone",
        name=req.name or f"复刻-{req.prefix}",
        audio_url=req.audio_url,
        prefix=req.prefix,
        clone_language_hints=req.language_hints,
        status="processing",
    )
    storage_service.save_audio_studio_task(task)

    user_id = get_current_user_id()
    user_config_dir = get_user_config_dir()
    asyncio.create_task(_background_voice_clone(task, req, user_id, user_config_dir))

    return {"task": task}


async def _background_voice_clone(
    task: AudioStudioTask,
    req: VoiceCloneCreateRequest,
    user_id, user_config_dir,
):
    """后台执行声音复刻"""
    set_current_user(user_id)
    if user_config_dir:
        set_user_config_dir(user_config_dir)
    try:
        clone_service = CosyVoiceCloneService()
        voice_id, request_id = await asyncio.to_thread(
            clone_service.create_voice,
            prefix=req.prefix,
            url=req.audio_url,
            language_hints=req.language_hints,
        )

        task.result_voice_id = voice_id
        task.request_id = request_id

        profile = VoiceProfile(
            project_id=req.project_id,
            voice_id=voice_id,
            name=req.name or req.prefix,
            source="clone",
            target_model=TARGET_MODEL,
            prefix=req.prefix,
            status="deploying",
            audio_url=req.audio_url,
        )
        storage_service.save_voice_profile(profile)

        max_attempts = 30
        for attempt in range(max_attempts):
            await asyncio.sleep(10)
            try:
                info = await asyncio.to_thread(clone_service.query_voice, voice_id)
                status = info.get("status", "")
                logger.info(f"[声音复刻] 轮询 {attempt+1}/{max_attempts}: {status}")

                if status == "OK":
                    profile.status = "ok"
                    storage_service.save_voice_profile(profile)
                    task.status = "succeeded"
                    storage_service.save_audio_studio_task(task)
                    return
                elif status == "UNDEPLOYED":
                    profile.status = "undeployed"
                    storage_service.save_voice_profile(profile)
                    raise RuntimeError("音色审核未通过 (UNDEPLOYED)")
            except RuntimeError:
                raise
            except Exception as e:
                logger.warning(f"[声音复刻] 轮询异常: {e}")

        raise RuntimeError("音色创建超时，请稍后查询状态")

    except Exception as e:
        logger.error(f"[声音复刻] 失败: {e}", exc_info=True)
        task.status = "failed"
        task.error_message = str(e)

    storage_service.save_audio_studio_task(task)


# ─── Voice Design ────────────────────────────────────────

@router.post("/voice-design")
async def create_voice_design_task(req: VoiceDesignCreateRequest):
    """创建声音设计任务"""
    if not req.voice_prompt:
        raise HTTPException(status_code=400, detail="请输入声音描述")
    if not req.preview_text:
        raise HTTPException(status_code=400, detail="请输入试听文本")
    if not req.prefix:
        raise HTTPException(status_code=400, detail="请输入音色名称前缀")

    task = AudioStudioTask(
        project_id=req.project_id,
        task_type="voice_design",
        name=req.name or f"设计-{req.prefix}",
        voice_prompt=req.voice_prompt,
        preview_text=req.preview_text,
        prefix=req.prefix,
        design_sample_rate=req.sample_rate,
        design_response_format=req.response_format,
        status="processing",
    )
    storage_service.save_audio_studio_task(task)

    user_id = get_current_user_id()
    user_config_dir = get_user_config_dir()
    asyncio.create_task(_background_voice_design(task, req, user_id, user_config_dir))

    return {"task": task}


async def _background_voice_design(
    task: AudioStudioTask,
    req: VoiceDesignCreateRequest,
    user_id, user_config_dir,
):
    """后台执行声音设计"""
    set_current_user(user_id)
    if user_config_dir:
        set_user_config_dir(user_config_dir)
    try:
        design_service = CosyVoiceDesignService()
        voice_id, preview_bytes, request_id = await design_service.create_voice(
            voice_prompt=req.voice_prompt,
            preview_text=req.preview_text,
            prefix=req.prefix,
            sample_rate=req.sample_rate,
            response_format=req.response_format,
        )

        preview_url = None
        ext = req.response_format or "wav"
        if preview_bytes and oss_service.is_enabled():
            success, result = await asyncio.to_thread(
                oss_service.upload_from_bytes,
                preview_bytes, "audio", ext, task.project_id,
            )
            if success:
                preview_url = result

        if not preview_url and preview_bytes:
            from pathlib import Path
            assets_dir = Path(__file__).parent.parent.parent / "data" / "assets" / "audio"
            assets_dir.mkdir(parents=True, exist_ok=True)
            file_name = f"{task.id}_preview.{ext}"
            file_path = assets_dir / file_name
            with open(file_path, "wb") as f:
                f.write(preview_bytes)
            preview_url = f"/assets/audio/{file_name}"

        task.result_voice_id = voice_id
        task.result_audio_url = preview_url
        task.request_id = request_id
        if preview_bytes:
            task.audio_duration = _estimate_audio_duration(
                preview_bytes, req.response_format or "wav"
            )
        task.status = "succeeded"

        profile = VoiceProfile(
            project_id=req.project_id,
            voice_id=voice_id,
            name=req.name or req.prefix,
            source="design",
            target_model=TARGET_MODEL,
            prefix=req.prefix,
            status="ok",
            voice_prompt=req.voice_prompt,
            preview_text=req.preview_text,
            preview_audio_url=preview_url,
        )
        storage_service.save_voice_profile(profile)

    except Exception as e:
        logger.error(f"[声音设计] 失败: {e}", exc_info=True)
        task.status = "failed"
        task.error_message = str(e)

    storage_service.save_audio_studio_task(task)


# ─── Save to Library ─────────────────────────────────────

@router.post("/{task_id}/save-to-library")
async def save_to_library(task_id: str):
    """将 TTS 结果保存到音频库"""
    from app.models.media import AudioItem

    task = storage_service.get_audio_studio_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not task.result_audio_url:
        raise HTTPException(status_code=400, detail="该任务没有生成音频")

    ext = _get_extension(task.format) if task.task_type == "tts" else "wav"
    audio_item = AudioItem(
        project_id=task.project_id,
        name=task.name or f"TTS-{task.id[:8]}",
        url=task.result_audio_url,
        file_type=ext,
        file_size=0,
    )
    storage_service.save_audio_item(audio_item)

    task.saved_to_library = True
    storage_service.save_audio_studio_task(task)

    return {"success": True, "audio_item": audio_item}
