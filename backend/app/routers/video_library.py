"""
视频库 API 路由
"""

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional, List
import os
import uuid
import tempfile
import httpx
import cv2
import numpy as np
from io import BytesIO
from datetime import datetime

from app.models.media import VideoItem
from app.models.gallery import GalleryImage
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


@router.post("/{video_id}/extract-last-frame")
async def extract_last_frame(video_id: str, name: Optional[str] = None):
    """
    提取视频尾帧并保存到图库
    
    Args:
        video_id: 视频ID
        name: 保存到图库的名称（可选，默认使用"视频名称_尾帧"）
    
    Returns:
        保存的图库图片信息
    """
    # 检查OSS是否启用
    if not oss_service.is_enabled():
        raise HTTPException(status_code=400, detail="OSS未启用，请先在设置中配置并启用OSS")
    
    # 获取视频信息
    video = storage_service.get_video_item(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    
    try:
        # 下载视频到临时文件
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.get(video.url)
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail=f"无法下载视频: HTTP {response.status_code}")
            
            video_content = response.content
        
        # 创建临时文件保存视频
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_file:
            tmp_file.write(video_content)
            tmp_path = tmp_file.name
        
        try:
            # 使用 OpenCV 提取最后一帧
            cap = cv2.VideoCapture(tmp_path)
            
            if not cap.isOpened():
                raise HTTPException(status_code=400, detail="无法打开视频文件")
            
            # 获取视频总帧数
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total_frames <= 0:
                raise HTTPException(status_code=400, detail="无法获取视频帧数")
            
            # 定位到最后一帧
            cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames - 1)
            
            # 读取最后一帧
            ret, frame = cap.read()
            cap.release()
            
            if not ret or frame is None:
                raise HTTPException(status_code=400, detail="无法提取视频尾帧")
            
            # 将 BGR 转换为 RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # 编码为 JPEG
            _, buffer = cv2.imencode('.jpg', cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR), 
                                     [cv2.IMWRITE_JPEG_QUALITY, 95])
            image_bytes = buffer.tobytes()
            
            # 获取图片尺寸
            height, width = frame.shape[:2]
            
        finally:
            # 删除临时文件
            os.unlink(tmp_path)
        
        # 上传到 OSS
        filename = f"{datetime.now().strftime('%Y%m%d/%H%M%S')}_{uuid.uuid4().hex[:8]}.jpg"
        oss_url = oss_service.upload_bytes(image_bytes, f"gallery/{video.project_id}/{filename}")
        
        # 创建图库图片记录
        image_name = name or f"{video.name}_尾帧"
        gallery_image = GalleryImage(
            project_id=video.project_id,
            name=image_name,
            description=f"从视频《{video.name}》提取的尾帧",
            url=oss_url,
            source="video_library",
            width=width,
            height=height,
            tags=["尾帧", "视频提取"]
        )
        
        storage_service.save_gallery_image(gallery_image)
        
        return {
            "message": "尾帧已保存到图库",
            "image": gallery_image
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[视频尾帧提取] 错误: {e}")
        raise HTTPException(status_code=500, detail=f"提取尾帧失败: {str(e)}")

