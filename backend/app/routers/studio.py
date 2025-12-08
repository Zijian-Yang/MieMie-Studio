"""
图片工作室 API 路由
"""

import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from app.models.studio import StudioTask, StudioTaskImage, ReferenceItem
from app.models.gallery import GalleryImage
from app.services.storage import storage_service
from app.services.dashscope.image_to_image import ImageToImageService
from app.config import get_config

router = APIRouter()


class ReferenceItemInput(BaseModel):
    """参考素材输入"""
    type: str  # character, scene, prop, gallery
    id: str


class TaskCreateRequest(BaseModel):
    """创建任务请求"""
    project_id: str
    name: str
    description: str = ""
    model: str = "wan2.5-i2i-preview"
    prompt: str = ""
    negative_prompt: str = ""
    group_count: int = 3
    references: List[ReferenceItemInput] = []


class TaskUpdateRequest(BaseModel):
    """更新任务请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    model: Optional[str] = None
    prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    group_count: Optional[int] = None
    references: Optional[List[ReferenceItemInput]] = None


class TaskGenerateRequest(BaseModel):
    """生成图片请求"""
    prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    group_count: Optional[int] = None


class SaveToGalleryRequest(BaseModel):
    """保存到图库请求"""
    image_ids: List[str]  # 要保存的图片ID列表


def get_reference_url(ref_type: str, ref_id: str) -> tuple[str, str]:
    """获取参考素材的URL和名称"""
    if ref_type == "character":
        character = storage_service.get_character(ref_id)
        if character and character.image_groups:
            selected_idx = character.selected_group_index
            if selected_idx < len(character.image_groups):
                group = character.image_groups[selected_idx]
                return group.front_url or "", character.name
    elif ref_type == "scene":
        scene = storage_service.get_scene(ref_id)
        if scene and scene.image_groups:
            selected_idx = scene.selected_group_index
            if selected_idx < len(scene.image_groups):
                return scene.image_groups[selected_idx].url or "", scene.name
    elif ref_type == "prop":
        prop = storage_service.get_prop(ref_id)
        if prop and prop.image_groups:
            selected_idx = prop.selected_group_index
            if selected_idx < len(prop.image_groups):
                return prop.image_groups[selected_idx].url or "", prop.name
    elif ref_type == "gallery":
        image = storage_service.get_gallery_image(ref_id)
        if image:
            return image.url, image.name
    return "", ""


@router.get("")
async def list_studio_tasks(project_id: str):
    """获取项目所有图片工作室任务"""
    tasks = storage_service.get_studio_tasks_by_project(project_id)
    return {"tasks": tasks}


@router.post("")
async def create_studio_task(request: TaskCreateRequest):
    """创建图片工作室任务"""
    # 获取参考素材的详细信息
    references = []
    for ref in request.references:
        url, name = get_reference_url(ref.type, ref.id)
        references.append(ReferenceItem(
            type=ref.type,
            id=ref.id,
            name=name,
            url=url
        ))
    
    task = StudioTask(
        project_id=request.project_id,
        name=request.name,
        description=request.description,
        model=request.model,
        prompt=request.prompt,
        negative_prompt=request.negative_prompt,
        group_count=request.group_count,
        references=references,
        status="pending"
    )
    storage_service.save_studio_task(task)
    return task


@router.get("/{task_id}")
async def get_studio_task(task_id: str):
    """获取任务详情"""
    task = storage_service.get_studio_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.put("/{task_id}")
async def update_studio_task(task_id: str, request: TaskUpdateRequest):
    """更新任务信息"""
    task = storage_service.get_studio_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    update_data = request.model_dump(exclude_unset=True)
    
    # 如果更新了参考素材，需要重新获取URL
    if "references" in update_data and update_data["references"] is not None:
        references = []
        for ref in update_data["references"]:
            url, name = get_reference_url(ref.type, ref.id)
            references.append(ReferenceItem(
                type=ref.type,
                id=ref.id,
                name=name,
                url=url
            ))
        task.references = references
        del update_data["references"]
    
    for key, value in update_data.items():
        if value is not None:
            setattr(task, key, value)
    
    storage_service.save_studio_task(task)
    return task


@router.post("/{task_id}/generate")
async def generate_task_images(task_id: str, request: TaskGenerateRequest):
    """生成任务图片（多图生图）
    
    多图生图说明：
    - 参考图片按用户选择的顺序传递给 API
    - 用户可以在 prompt 中使用"第一个图"、"第二个图"等引用不同的参考图
    - 例如："第一个图中的人和第二个图中的人在第三个图的场景中坐着"
    """
    task = storage_service.get_studio_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 更新任务参数
    if request.prompt:
        task.prompt = request.prompt
    if request.negative_prompt:
        task.negative_prompt = request.negative_prompt
    if request.group_count:
        task.group_count = request.group_count
    
    # 收集参考图片URL（保持用户选择的顺序！）
    ref_urls = [ref.url for ref in task.references if ref.url]
    if not ref_urls:
        raise HTTPException(status_code=400, detail="没有有效的参考素材图片")
    
    task.status = "generating"
    task.images = []
    storage_service.save_studio_task(task)
    
    i2i_service = ImageToImageService()
    
    async def generate_single(group_index: int) -> StudioTaskImage:
        """生成单张图片"""
        try:
            # 使用所有参考图进行多图生图，保持顺序
            url = await i2i_service.generate_with_multi_images(
                prompt=task.prompt,
                image_urls=ref_urls,  # 传递所有参考图URL，顺序与用户选择一致
                negative_prompt=task.negative_prompt
            )
            return StudioTaskImage(
                group_index=group_index,
                url=url,
                prompt_used=task.prompt
            )
        except Exception as e:
            return StudioTaskImage(
                group_index=group_index,
                url=None,
                prompt_used=task.prompt
            )
    
    try:
        # 并发生成
        tasks = [generate_single(i) for i in range(task.group_count)]
        images = await asyncio.gather(*tasks)
        
        task.images = list(images)
        task.status = "completed"
        storage_service.save_studio_task(task)
        
        return {"task": task}
    except Exception as e:
        task.status = "failed"
        task.error_message = str(e)
        storage_service.save_studio_task(task)
        raise HTTPException(status_code=500, detail=f"图片生成失败: {str(e)}")


@router.post("/{task_id}/save-to-gallery")
async def save_task_images_to_gallery(task_id: str, request: SaveToGalleryRequest):
    """将任务中的图片保存到图库"""
    task = storage_service.get_studio_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    saved_images = []
    for image in task.images:
        if image.id in request.image_ids and image.url:
            gallery_image = GalleryImage(
                project_id=task.project_id,
                name=f"{task.name} - 第{image.group_index + 1}组",
                description=task.description,
                url=image.url,
                prompt_used=image.prompt_used,
                source="studio",
                task_id=task_id
            )
            storage_service.save_gallery_image(gallery_image)
            saved_images.append(gallery_image)
            
            # 标记为已选中
            image.is_selected = True
    
    storage_service.save_studio_task(task)
    return {"saved_images": saved_images}


@router.delete("/{task_id}")
async def delete_studio_task(task_id: str):
    """删除任务"""
    task = storage_service.get_studio_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    storage_service.delete_studio_task(task_id)
    return {"message": "任务已删除"}


@router.delete("/project/{project_id}/all")
async def delete_all_studio_tasks(project_id: str):
    """删除项目所有任务"""
    tasks = storage_service.get_studio_tasks_by_project(project_id)
    for task in tasks:
        storage_service.delete_studio_task(task.id)
    return {"message": f"已删除 {len(tasks)} 个任务"}


@router.get("/models/available")
async def get_available_models():
    """获取可用的模型列表"""
    from app.config import IMAGE_EDIT_MODELS
    return {"models": list(IMAGE_EDIT_MODELS.keys())}

