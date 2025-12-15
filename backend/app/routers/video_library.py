"""
视频库 API 路由
"""

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional, List
import os
import uuid
from datetime import datetime

from app.models.media import VideoItem
from app.services.storage import storage_service
from app.services.oss import oss_service

router = APIRouter()


class VideoUploadRequest(BaseModel):
    """视频上传请求（URL方式）"""
    project_id: str
    urls: List[str]  # 多个URL，一行一个
    names: Optional[List[str]] = None  # 对应的名称


class VideoUpdateRequest(BaseModel):
    """视频更新请求"""
    name: Optional[str] = None
    description: Optional[str] = None


@router.get("")
async def list_videos(project_id: str):
    """获取项目所有视频"""
    videos = storage_service.get_video_items(project_id)
    return {"videos": videos}


@router.get("/{video_id}")
async def get_video(video_id: str):
    """获取单个视频"""
    video = storage_service.get_video_item(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    return video


@router.post("/upload-files")
async def upload_video_files(
    project_id: str,
    files: List[UploadFile] = File(...)
):
    """上传视频文件"""
    if not oss_service.is_enabled():
        raise HTTPException(status_code=400, detail="OSS未配置，无法上传文件")
    
    videos = []
    errors = []
    
    for file in files:
        try:
            # 读取文件内容
            content = await file.read()
            
            # 获取文件扩展名
            ext = os.path.splitext(file.filename or "video.mp4")[1].lower()
            if ext not in [".mp4", ".mov", ".avi", ".webm", ".mkv"]:
                errors.append({"filename": file.filename, "error": "不支持的视频格式"})
                continue
            
            # 上传到OSS
            filename = f"{datetime.now().strftime('%Y%m%d/%H%M%S')}_{uuid.uuid4().hex[:8]}{ext}"
            oss_url = oss_service.upload_bytes(content, f"video_library/{project_id}/{filename}")
            
            # 创建视频记录
            video = VideoItem(
                project_id=project_id,
                name=file.filename or "未命名视频",
                url=oss_url,
                file_type=ext[1:],
                file_size=len(content)
            )
            
            storage_service.save_video_item(video)
            videos.append(video)
            
        except Exception as e:
            errors.append({"filename": file.filename, "error": str(e)})
    
    return {
        "videos": videos,
        "errors": errors,
        "success_count": len(videos),
        "error_count": len(errors)
    }


@router.post("/upload-urls")
async def upload_video_urls(request: VideoUploadRequest):
    """通过URL上传视频"""
    if not oss_service.is_enabled():
        raise HTTPException(status_code=400, detail="OSS未配置，无法上传文件")
    
    videos = []
    errors = []
    
    for i, url in enumerate(request.urls):
        url = url.strip()
        if not url:
            continue
            
        try:
            # 从URL下载并上传到OSS
            ext = os.path.splitext(url.split("?")[0])[1].lower() or ".mp4"
            if not ext.startswith("."):
                ext = f".{ext}"
            
            # upload_from_url 返回 (success, result)
            success, oss_url = oss_service.upload_from_url(
                url, 
                file_type="video_library", 
                extension=ext[1:],
                project_id=request.project_id
            )
            
            if not success:
                errors.append({"url": url, "error": oss_url})
                continue
            
            # 获取名称
            name = request.names[i] if request.names and i < len(request.names) else f"视频 {i+1}"
            
            # 创建视频记录
            video = VideoItem(
                project_id=request.project_id,
                name=name,
                url=oss_url,
                file_type=ext[1:] if ext else "mp4"
            )
            
            storage_service.save_video_item(video)
            videos.append(video)
            
        except Exception as e:
            errors.append({"url": url, "error": str(e)})
    
    return {
        "videos": videos,
        "errors": errors,
        "success_count": len(videos),
        "error_count": len(errors)
    }


@router.put("/{video_id}")
async def update_video(video_id: str, request: VideoUpdateRequest):
    """更新视频信息"""
    video = storage_service.get_video_item(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    
    if request.name is not None:
        video.name = request.name
    if request.description is not None:
        video.description = request.description
    
    video.updated_at = datetime.now()
    storage_service.save_video_item(video)
    
    return video


@router.delete("/{video_id}")
async def delete_video(video_id: str):
    """删除视频"""
    video = storage_service.get_video_item(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    
    storage_service.delete_video_item(video_id)
    return {"message": "视频已删除"}


@router.delete("")
async def delete_all_videos(project_id: str):
    """删除项目所有视频"""
    videos = storage_service.get_video_items(project_id)
    for video in videos:
        storage_service.delete_video_item(video.id)
    return {"message": f"已删除 {len(videos)} 个视频"}

