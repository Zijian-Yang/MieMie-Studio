"""
音频库 API 路由
"""

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional, List
import os
import uuid
from datetime import datetime

from app.models.media import AudioItem
from app.services.storage import storage_service
from app.services.oss import oss_service

router = APIRouter()


class AudioUploadRequest(BaseModel):
    """音频上传请求（URL方式）"""
    project_id: str
    urls: List[str]  # 多个URL，一行一个
    names: Optional[List[str]] = None  # 对应的名称


class AudioUpdateRequest(BaseModel):
    """音频更新请求"""
    name: Optional[str] = None
    description: Optional[str] = None


@router.get("")
async def list_audio(project_id: str):
    """获取项目所有音频"""
    audios = storage_service.get_audio_items(project_id)
    return {"audios": audios}


@router.get("/{audio_id}")
async def get_audio(audio_id: str):
    """获取单个音频"""
    audio = storage_service.get_audio_item(audio_id)
    if not audio:
        raise HTTPException(status_code=404, detail="音频不存在")
    return audio


@router.post("/upload-files")
async def upload_audio_files(
    project_id: str,
    files: List[UploadFile] = File(...)
):
    """上传音频文件"""
    if not oss_service.is_enabled():
        raise HTTPException(status_code=400, detail="OSS未配置，无法上传文件")
    
    audios = []
    errors = []
    
    for file in files:
        try:
            # 读取文件内容
            content = await file.read()
            
            # 获取文件扩展名
            ext = os.path.splitext(file.filename or "audio.mp3")[1].lower()
            if ext not in [".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"]:
                errors.append({"filename": file.filename, "error": "不支持的音频格式"})
                continue
            
            # 上传到OSS
            filename = f"{datetime.now().strftime('%Y%m%d/%H%M%S')}_{uuid.uuid4().hex[:8]}{ext}"
            oss_url = oss_service.upload_bytes(content, f"audio/{project_id}/{filename}")
            
            # 创建音频记录
            audio = AudioItem(
                project_id=project_id,
                name=file.filename or "未命名音频",
                url=oss_url,
                file_type=ext[1:],
                file_size=len(content)
            )
            
            storage_service.save_audio_item(audio)
            audios.append(audio)
            
        except Exception as e:
            errors.append({"filename": file.filename, "error": str(e)})
    
    return {
        "audios": audios,
        "errors": errors,
        "success_count": len(audios),
        "error_count": len(errors)
    }


@router.post("/upload-urls")
async def upload_audio_urls(request: AudioUploadRequest):
    """通过URL上传音频"""
    if not oss_service.is_enabled():
        raise HTTPException(status_code=400, detail="OSS未配置，无法上传文件")
    
    audios = []
    errors = []
    
    for i, url in enumerate(request.urls):
        url = url.strip()
        if not url:
            continue
            
        try:
            # 从URL下载并上传到OSS
            ext = os.path.splitext(url.split("?")[0])[1].lower() or ".mp3"
            filename = f"{datetime.now().strftime('%Y%m%d/%H%M%S')}_{uuid.uuid4().hex[:8]}{ext}"
            oss_url = oss_service.upload_from_url(url, f"audio/{request.project_id}/{filename}")
            
            # 获取名称
            name = request.names[i] if request.names and i < len(request.names) else f"音频 {i+1}"
            
            # 创建音频记录
            audio = AudioItem(
                project_id=request.project_id,
                name=name,
                url=oss_url,
                file_type=ext[1:] if ext else "mp3"
            )
            
            storage_service.save_audio_item(audio)
            audios.append(audio)
            
        except Exception as e:
            errors.append({"url": url, "error": str(e)})
    
    return {
        "audios": audios,
        "errors": errors,
        "success_count": len(audios),
        "error_count": len(errors)
    }


@router.put("/{audio_id}")
async def update_audio(audio_id: str, request: AudioUpdateRequest):
    """更新音频信息"""
    audio = storage_service.get_audio_item(audio_id)
    if not audio:
        raise HTTPException(status_code=404, detail="音频不存在")
    
    if request.name is not None:
        audio.name = request.name
    if request.description is not None:
        audio.description = request.description
    
    audio.updated_at = datetime.now()
    storage_service.save_audio_item(audio)
    
    return audio


@router.delete("/{audio_id}")
async def delete_audio(audio_id: str):
    """删除音频"""
    audio = storage_service.get_audio_item(audio_id)
    if not audio:
        raise HTTPException(status_code=404, detail="音频不存在")
    
    storage_service.delete_audio_item(audio_id)
    return {"message": "音频已删除"}


@router.delete("")
async def delete_all_audio(project_id: str):
    """删除项目所有音频"""
    audios = storage_service.get_audio_items(project_id)
    for audio in audios:
        storage_service.delete_audio_item(audio.id)
    return {"message": f"已删除 {len(audios)} 个音频"}

