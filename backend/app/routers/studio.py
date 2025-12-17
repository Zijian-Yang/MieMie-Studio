"""
图片工作室 API 路由

支持的模型：
- wan2.5-i2i-preview: 万相图生图（风格迁移）
- qwen-image-edit-plus: 通义千问图像编辑（单图编辑/多图融合）
"""

import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Any

from app.models.studio import StudioTask, StudioTaskImage, ReferenceItem
from app.models.gallery import GalleryImage
from app.services.storage import storage_service
from app.services.dashscope.image_to_image import ImageToImageService
from app.services.oss import oss_service
from app.config import get_config
from app.models_registry import registry

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
    n: int = 1  # 每次请求生成的图片数量
    group_count: int = 3  # 并发请求数
    references: List[ReferenceItemInput] = []


class TaskUpdateRequest(BaseModel):
    """更新任务请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    model: Optional[str] = None
    prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    n: Optional[int] = None  # 每次请求生成的图片数量
    group_count: Optional[int] = None  # 并发请求数
    references: Optional[List[ReferenceItemInput]] = None


class TaskGenerateRequest(BaseModel):
    """生成图片请求"""
    prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    n: Optional[int] = None  # 每次请求生成的图片数量
    group_count: Optional[int] = None  # 并发请求数（总图片数 = n * group_count）
    # 通用参数
    size: Optional[str] = None  # 输出尺寸
    prompt_extend: Optional[bool] = True  # 智能改写
    watermark: Optional[bool] = False  # 水印
    seed: Optional[int] = None  # 随机种子
    # wan2.6-image 专用参数
    enable_interleave: Optional[bool] = False  # 是否启用图文混合模式
    max_images: Optional[int] = 5  # 图文混合模式下最大生成图片数（1-5）


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
        n=request.n,
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
    """生成任务图片
    
    支持的模型：
    - 图生图模型：wan2.5-i2i-preview, qwen-image-edit-plus
    - 文生图模型：wan2.6-t2i, wan2.5-t2i-preview
    
    多图生图说明：
    - 参考图片按用户选择的顺序传递给 API
    - 用户可以在 prompt 中使用"第一个图"、"第二个图"等引用不同的参考图
    - 例如："第一个图中的人和第二个图中的人在第三个图的场景中坐着"
    
    qwen-image-edit-plus 特点：
    - 1张图片：单图编辑模式
    - 2-3张图片：多图融合模式
    - 支持一次输出1-6张图片
    
    文生图特点：
    - 不需要参考图片，只需要提示词
    """
    from app.config import IMAGE_MODELS
    
    task = storage_service.get_studio_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 更新任务参数
    if request.prompt:
        task.prompt = request.prompt
    if request.negative_prompt:
        task.negative_prompt = request.negative_prompt
    if request.n is not None:
        task.n = request.n
    if request.group_count is not None:
        task.group_count = request.group_count
    
    config = get_config()
    model_name = task.model or "wan2.5-i2i-preview"
    
    # 检查是否是文生图模型
    is_text_to_image = model_name in IMAGE_MODELS
    
    # 收集参考图片URL（图生图模型需要）
    ref_urls = [ref.url for ref in task.references if ref.url]
    if not is_text_to_image and not ref_urls:
        raise HTTPException(status_code=400, detail="没有有效的参考素材图片")
    
    task.status = "generating"
    task.images = []
    storage_service.save_studio_task(task)
    
    # 获取额外参数
    size = request.size
    prompt_extend = request.prompt_extend if request.prompt_extend is not None else True
    watermark = request.watermark if request.watermark is not None else False
    seed = request.seed
    
    try:
        # 根据模型选择不同的生成方式
        if model_name == "wan2.6-image":
            # 使用 wan2.6-image 模型（支持参考图和纯文生图）
            enable_interleave = request.enable_interleave if hasattr(request, 'enable_interleave') else False
            max_images = request.max_images if hasattr(request, 'max_images') else 5
            images = await generate_with_wan26_image(
                task=task,
                ref_urls=ref_urls if ref_urls else None,
                size=size,
                prompt_extend=prompt_extend,
                watermark=watermark,
                seed=seed,
                enable_interleave=enable_interleave,
                max_images=max_images
            )
        elif is_text_to_image:
            # 使用文生图模型
            images = await generate_with_text_to_image(
                task=task,
                model_name=model_name,
                prompt_extend=prompt_extend,
                watermark=watermark,
                seed=seed
            )
        elif model_name == "qwen-image-edit-plus":
            # 使用通义千问图像编辑模型
            images = await generate_with_qwen_image_edit(
                task=task,
                ref_urls=ref_urls,
                api_key=config.dashscope_api_key,
                base_url=config.base_url,
                size=size,
                prompt_extend=prompt_extend,
                watermark=watermark,
                seed=seed
            )
        else:
            # 使用万相图生图模型
            images = await generate_with_wanx_i2i(
                task=task,
                ref_urls=ref_urls
            )
        
        task.images = images
        task.status = "completed"
        storage_service.save_studio_task(task)
        
        return {"task": task}
    except Exception as e:
        task.status = "failed"
        task.error_message = str(e)
        storage_service.save_studio_task(task)
        raise HTTPException(status_code=500, detail=f"图片生成失败: {str(e)}")


async def generate_with_text_to_image(
    task: StudioTask,
    model_name: str,
    prompt_extend: bool = True,
    watermark: bool = False,
    seed: Optional[int] = None
) -> List[StudioTaskImage]:
    """使用文生图模型生成
    
    支持模型：wan2.6-t2i, wan2.5-t2i-preview
    """
    from app.services.dashscope.text_to_image import TextToImageService
    
    t2i_service = TextToImageService()
    n = task.n or 1  # 每次请求生成的图片数量
    
    async def generate_single_group(group_index: int) -> List[StudioTaskImage]:
        """生成单组图片（一次请求生成 n 张）"""
        try:
            urls = await t2i_service.generate_batch(
                prompt=task.prompt,
                negative_prompt=task.negative_prompt or "",
                n=n,
                model=model_name,
                prompt_extend=prompt_extend,
                watermark=watermark,
                seed=seed,
                project_id=task.project_id
            )
            
            images = []
            for i, url in enumerate(urls):
                images.append(StudioTaskImage(
                    group_index=group_index * n + i,
                    url=url,
                    prompt_used=task.prompt
                ))
            return images
        except Exception as e:
            import traceback
            print(f"文生图生成失败: {e}")
            traceback.print_exc()
            # 返回 n 个失败的图片
            return [StudioTaskImage(
                group_index=group_index * n + i,
                url=None,
                prompt_used=task.prompt
            ) for i in range(n)]
    
    # 并发生成 group_count 组
    group_tasks = [generate_single_group(i) for i in range(task.group_count)]
    results = await asyncio.gather(*group_tasks)
    
    # 展平结果列表
    all_images = []
    for group_images in results:
        all_images.extend(group_images)
    return all_images


async def generate_with_wan26_image(
    task: StudioTask,
    ref_urls: Optional[List[str]] = None,
    size: Optional[str] = None,
    prompt_extend: bool = True,
    watermark: bool = False,
    seed: Optional[int] = None,
    enable_interleave: bool = False,
    max_images: int = 5
) -> List[StudioTaskImage]:
    """使用 wan2.6-image 模型生成
    
    支持：
    - 参考图生图 (ref_urls 不为空, enable_interleave=False)
    - 纯文生图 (ref_urls 为空)
    - 图文混合输出 (enable_interleave=True)
    
    参数说明：
    - enable_interleave=False: 参考图模式，n 可选 1-4，默认4
    - enable_interleave=True: 图文混合模式，n 固定为1，max_images 控制最大生成图数(1-5)
    """
    from app.services.dashscope.text_to_image import TextToImageService
    
    t2i_service = TextToImageService()
    n = task.n or 4  # 参考图模式默认4张
    
    # wan2.6-image 限制
    if enable_interleave:
        n = 1  # 图文混合模式固定为1
        # prompt_extend 在图文混合模式下不生效
        prompt_extend = False
    else:
        n = min(n, 4)  # 参考图模式最多4张
    
    async def generate_single_group(group_index: int) -> List[StudioTaskImage]:
        """生成单组图片"""
        try:
            urls = await t2i_service.generate_with_wan26_image(
                prompt=task.prompt,
                image_urls=ref_urls,
                negative_prompt=task.negative_prompt or "",
                n=n,
                size=size or "1280*1280",
                prompt_extend=prompt_extend,
                watermark=watermark,
                seed=seed,
                enable_interleave=enable_interleave,
                max_images=max_images,
                project_id=task.project_id
            )
            
            images = []
            for i, url in enumerate(urls):
                images.append(StudioTaskImage(
                    group_index=group_index * n + i,
                    url=url,
                    prompt_used=task.prompt
                ))
            return images
        except Exception as e:
            import traceback
            print(f"wan2.6-image 生成失败: {e}")
            traceback.print_exc()
            # 返回失败的图片
            return [StudioTaskImage(
                group_index=group_index * n + i,
                url=None,
                prompt_used=task.prompt
            ) for i in range(n)]
    
    # 并发生成 group_count 组
    group_tasks = [generate_single_group(i) for i in range(task.group_count)]
    results = await asyncio.gather(*group_tasks)
    
    # 展平结果列表
    all_images = []
    for group_images in results:
        all_images.extend(group_images)
    return all_images


async def generate_with_wanx_i2i(
    task: StudioTask,
    ref_urls: List[str]
) -> List[StudioTaskImage]:
    """使用万相图生图模型生成
    
    n: 每次请求生成的图片数量
    group_count: 并发请求数
    总图片数 = n * group_count
    """
    i2i_service = ImageToImageService()
    n = task.n or 1  # 每次请求生成的图片数量
    
    async def generate_single_group(group_index: int) -> List[StudioTaskImage]:
        """生成单组图片（一次请求生成 n 张）"""
        try:
            urls = await i2i_service.generate_with_multi_images(
                prompt=task.prompt,
                image_urls=ref_urls,
                negative_prompt=task.negative_prompt,
                n=n  # 传递 n 参数
            )
            # 如果返回单个URL，转为列表
            if isinstance(urls, str):
                urls = [urls]
            
            images = []
            for i, url in enumerate(urls):
                # 上传图片到 OSS
                final_url = url
                if url and oss_service.is_enabled():
                    oss_url = oss_service.upload_image(url, task.project_id)
                    if oss_url != url:
                        final_url = oss_url
                        print(f"[图片工作室] 图片已上传到 OSS: {oss_url[:60]}...")
                
                images.append(StudioTaskImage(
                    group_index=group_index * n + i,  # 全局索引
                    url=final_url,
                    prompt_used=task.prompt
                ))
            return images
        except Exception as e:
            # 返回 n 个失败的图片
            return [StudioTaskImage(
                group_index=group_index * n + i,
                url=None,
                prompt_used=task.prompt
            ) for i in range(n)]
    
    # 并发生成 group_count 组
    group_tasks = [generate_single_group(i) for i in range(task.group_count)]
    results = await asyncio.gather(*group_tasks)
    
    # 展平结果列表
    all_images = []
    for group_images in results:
        all_images.extend(group_images)
    return all_images


async def generate_with_qwen_image_edit(
    task: StudioTask,
    ref_urls: List[str],
    api_key: str,
    base_url: str = "",
    size: Optional[str] = None,
    prompt_extend: bool = True,
    watermark: bool = False,
    seed: Optional[int] = None
) -> List[StudioTaskImage]:
    """使用通义千问图像编辑模型生成
    
    n: 每次请求生成的图片数量（1-6）
    group_count: 并发请求数
    总图片数 = n * group_count
    
    qwen-image-edit-plus 特点：
    - 支持 1-3 张输入图片
    - 支持一次输出 1-6 张图片（通过 n 参数）
    - 支持 size, prompt_extend, watermark, seed 参数
    - size 参数仅当 n=1 时可用
    - 不支持异步接口，只有同步调用
    """
    from app.models_registry.image.qwen_image_edit import QwenImageEditService, QWEN_IMAGE_EDIT_PLUS_MODEL_INFO
    
    # 验证图片数量
    if len(ref_urls) > 3:
        raise ValueError("qwen-image-edit-plus 最多支持3张输入图片")
    
    service = QwenImageEditService(QWEN_IMAGE_EDIT_PLUS_MODEL_INFO)
    service.configure(api_key, base_url)
    
    n = task.n or 1  # 每次请求生成的图片数量
    
    # 验证 n 参数
    if n > 6:
        n = 6  # qwen-image-edit-plus 最多支持一次生成6张
    
    # 如果设置了 size，则 n 必须为 1
    if size and n > 1:
        raise ValueError("设置 size 参数时，生图数量 n 必须为 1")
    
    all_images = []
    image_index = 0
    
    # 并发生成 group_count 组
    async def generate_single_group(group_index: int) -> List[StudioTaskImage]:
        """生成单组图片（一次请求生成 n 张）"""
        nonlocal image_index
        try:
            urls = await service.generate(
                prompt=task.prompt,
                images=ref_urls,
                negative_prompt=task.negative_prompt,
                n=n,
                size=size if n == 1 else None,
                prompt_extend=prompt_extend,
                watermark=watermark,
                seed=seed
            )
            
            images = []
            for i, url in enumerate(urls):
                # 上传图片到 OSS
                final_url = url
                if url and oss_service.is_enabled():
                    oss_url = oss_service.upload_image(url, task.project_id)
                    if oss_url != url:
                        final_url = oss_url
                        print(f"[图片工作室] 图片已上传到 OSS: {oss_url[:60]}...")
                
                images.append(StudioTaskImage(
                    group_index=group_index * n + i,
                    url=final_url,
                    prompt_used=task.prompt
                ))
            return images
        except Exception as e:
            import traceback
            print(f"qwen-image-edit-plus 生成失败: {e}")
            traceback.print_exc()
            # 返回 n 个失败的图片
            return [StudioTaskImage(
                group_index=group_index * n + i,
                url=None,
                prompt_used=task.prompt
            ) for i in range(n)]
    
    # qwen-image-edit-plus 不支持异步，所以需要顺序执行
    for group_idx in range(task.group_count):
        group_images = await generate_single_group(group_idx)
        all_images.extend(group_images)
    
    return all_images


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
    """获取可用的图片工作室模型列表
    
    返回支持的模型：
    - 图生图模型：wan2.5-i2i-preview, qwen-image-edit-plus
    - 文生图模型：wan2.6-t2i, wan2.5-t2i-preview
    """
    from app.models_registry import registry, ModelType
    from app.config import IMAGE_MODELS
    
    result = {}
    
    # 获取所有图生图模型（从 registry）
    i2i_models = registry.list_models(ModelType.IMAGE_TO_IMAGE)
    for model in i2i_models:
        result[model.id] = {
            "id": model.id,
            "name": model.name,
            "description": model.description,
            "model_type": "image_to_image",
            "capabilities": model.capabilities.model_dump() if model.capabilities else {},
            "parameters": [p.model_dump() for p in model.parameters] if model.parameters else [],
        }
    
    # 添加文生图模型（从 IMAGE_MODELS 配置）
    for model_id, model_info in IMAGE_MODELS.items():
        # 判断模型类型
        if model_info.get("supports_reference_images"):
            model_type = "image_generation"  # wan2.6-image 支持参考图和文生图
        else:
            model_type = "text_to_image"
        
        result[model_id] = {
            "id": model_id,
            "name": model_info.get("name", model_id),
            "description": model_info.get("description", ""),
            "model_type": model_type,
            "capabilities": {
                "supports_prompt_extend": model_info.get("supports_prompt_extend", True),
                "supports_watermark": model_info.get("supports_watermark", True),
                "supports_seed": model_info.get("supports_seed", True),
                "supports_negative_prompt": model_info.get("supports_negative_prompt", True),
                "max_n": model_info.get("max_n", 4),
                "supports_reference_images": model_info.get("supports_reference_images", False),
                "supports_interleave": model_info.get("supports_interleave", False),
                "max_reference_images": model_info.get("max_reference_images", 0),
            },
            "parameters": [],
            "common_sizes": model_info.get("common_sizes", []),
        }
    
    return {"models": result}

