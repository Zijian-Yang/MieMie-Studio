"""
图库 API 路由
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, List
import uuid
import asyncio

from app.models.gallery import GalleryImage
from app.services.storage import storage_service
from app.services.oss import oss_service
from app.config import get_config

router = APIRouter()


class GalleryImageCreateRequest(BaseModel):
    """创建图库图片请求"""
    project_id: str
    name: str
    description: str = ""
    url: str
    prompt_used: Optional[str] = None
    source: str = "studio"
    task_id: Optional[str] = None
    tags: List[str] = []


class GalleryImageUpdateRequest(BaseModel):
    """更新图库图片请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None


class BatchSaveRequest(BaseModel):
    """批量保存到图库请求"""
    project_id: str
    images: List[GalleryImageCreateRequest]


class UploadUrlsRequest(BaseModel):
    """通过URL上传图片请求"""
    project_id: str
    urls: List[str]  # 图片URL列表


class OSSStatusResponse(BaseModel):
    """OSS状态响应"""
    enabled: bool
    configured: bool


@router.get("/oss-status")
async def get_oss_status():
    """获取OSS配置状态"""
    config = get_config().oss
    return OSSStatusResponse(
        enabled=config.enabled,
        configured=bool(config.access_key_id and config.access_key_secret and config.bucket_name)
    )


@router.post("/upload-files")
async def upload_files(
    project_id: str = Form(...),
    files: List[UploadFile] = File(...)
):
    """
    上传多个图片文件到OSS并保存到图库
    需要启用OSS功能
    """
    # 检查OSS是否启用
    if not oss_service.is_enabled():
        raise HTTPException(status_code=400, detail="OSS未启用，请先在设置中配置并启用OSS")
    
    uploaded_images = []
    errors = []
    
    for file in files:
        try:
            # 读取文件内容
            content = await file.read()
            
            # 获取文件扩展名
            filename = file.filename or "image.png"
            ext = filename.split('.')[-1].lower() if '.' in filename else 'png'
            if ext not in ['png', 'jpg', 'jpeg', 'gif', 'webp']:
                ext = 'png'
            
            # 生成唯一文件名
            object_name = f"gallery/{uuid.uuid4().hex[:8]}.{ext}"
            
            # 上传到OSS
            success, result = oss_service.upload_from_bytes(content, "image", ext, project_id)
            
            if not success:
                errors.append({"filename": filename, "error": result})
                continue
            
            # 创建图库记录
            image = GalleryImage(
                project_id=project_id,
                name=filename.rsplit('.', 1)[0] if '.' in filename else filename,
                description="用户上传",
                url=result,
                source="upload"
            )
            storage_service.save_gallery_image(image)
            uploaded_images.append(image)
            
        except Exception as e:
            errors.append({"filename": file.filename, "error": str(e)})
    
    return {
        "images": uploaded_images,
        "success_count": len(uploaded_images),
        "error_count": len(errors),
        "errors": errors
    }


@router.post("/upload-urls")
async def upload_from_urls(request: UploadUrlsRequest):
    """
    从URL列表下载图片并上传到OSS保存到图库
    需要启用OSS功能
    """
    # 检查OSS是否启用
    if not oss_service.is_enabled():
        raise HTTPException(status_code=400, detail="OSS未启用，请先在设置中配置并启用OSS")
    
    uploaded_images = []
    errors = []
    
    for idx, url in enumerate(request.urls):
        url = url.strip()
        if not url:
            continue
            
        try:
            # 从URL上传到OSS
            success, result = oss_service.upload_from_url(url, "image", "png", request.project_id)
            
            if not success:
                errors.append({"url": url, "error": result})
                continue
            
            # 从URL提取文件名
            url_filename = url.split('/')[-1].split('?')[0]
            name = url_filename.rsplit('.', 1)[0] if '.' in url_filename else f"图片_{idx + 1}"
            
            # 创建图库记录
            image = GalleryImage(
                project_id=request.project_id,
                name=name,
                description=f"从URL导入: {url[:50]}...",
                url=result,
                source="upload"
            )
            storage_service.save_gallery_image(image)
            uploaded_images.append(image)
            
        except Exception as e:
            errors.append({"url": url, "error": str(e)})
    
    return {
        "images": uploaded_images,
        "success_count": len(uploaded_images),
        "error_count": len(errors),
        "errors": errors
    }


@router.get("")
async def list_gallery_images(project_id: str):
    """获取项目图库所有图片"""
    images = storage_service.get_gallery_images_by_project(project_id)
    return {"images": images}


@router.post("")
async def create_gallery_image(request: GalleryImageCreateRequest):
    """创建图库图片"""
    image = GalleryImage(
        project_id=request.project_id,
        name=request.name,
        description=request.description,
        url=request.url,
        prompt_used=request.prompt_used,
        source=request.source,
        task_id=request.task_id,
        tags=request.tags
    )
    storage_service.save_gallery_image(image)
    return image


@router.post("/batch")
async def batch_save_to_gallery(request: BatchSaveRequest):
    """批量保存图片到图库"""
    saved_images = []
    for img_data in request.images:
        image = GalleryImage(
            project_id=request.project_id,
            name=img_data.name,
            description=img_data.description,
            url=img_data.url,
            prompt_used=img_data.prompt_used,
            source=img_data.source,
            task_id=img_data.task_id,
            tags=img_data.tags
        )
        storage_service.save_gallery_image(image)
        saved_images.append(image)
    return {"images": saved_images}


@router.get("/{image_id}")
async def get_gallery_image(image_id: str):
    """获取图库图片详情"""
    image = storage_service.get_gallery_image(image_id)
    if not image:
        raise HTTPException(status_code=404, detail="图片不存在")
    return image


@router.put("/{image_id}")
async def update_gallery_image(image_id: str, request: GalleryImageUpdateRequest):
    """更新图库图片信息"""
    image = storage_service.get_gallery_image(image_id)
    if not image:
        raise HTTPException(status_code=404, detail="图片不存在")
    
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            setattr(image, key, value)
    
    storage_service.save_gallery_image(image)
    return image


@router.delete("/{image_id}")
async def delete_gallery_image(image_id: str):
    """删除图库图片"""
    image = storage_service.get_gallery_image(image_id)
    if not image:
        raise HTTPException(status_code=404, detail="图片不存在")
    
    storage_service.delete_gallery_image(image_id)
    return {"message": "图片已删除"}


@router.delete("/project/{project_id}/all")
async def delete_all_gallery_images(project_id: str):
    """删除项目所有图库图片"""
    images = storage_service.get_gallery_images_by_project(project_id)
    for image in images:
        storage_service.delete_gallery_image(image.id)
    return {"message": f"已删除 {len(images)} 张图片"}

