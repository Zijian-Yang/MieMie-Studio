"""
图库 API 路由
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from app.models.gallery import GalleryImage
from app.services.storage import storage_service

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

