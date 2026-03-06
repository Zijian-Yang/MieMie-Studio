"""
图片工作室 API 路由

支持的模型：
- wan2.5-i2i-preview: 万相图生图（风格迁移）
- qwen-image-edit-plus/max: 通义千问图像编辑（单图编辑/多图融合）
- qwen-image-2.0-pro/2.0: 千问图像2.0（文生图+图像编辑融合）

架构说明：
- /generate 端点通过 asyncio.create_task() 在后台执行生成，立即返回 generating 状态
- 前端通过轮询 GET /{task_id} 获取生成进度和结果
- 底层 API 差异由各 generate_with_* 函数内部处理
"""

import asyncio
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Any, Tuple

from app.models.studio import StudioTask, StudioTaskImage, ReferenceItem
from app.models.gallery import GalleryImage
from app.services.storage import storage_service, set_current_user, get_current_user_id
from app.services.dashscope.image_to_image import ImageToImageService
from app.services.oss import oss_service
from app.config import get_config, set_user_config_dir, get_user_config_dir

logger = logging.getLogger(__name__)

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
    # 高级生成参数
    size: Optional[str] = None  # 输出尺寸
    prompt_extend: Optional[bool] = None  # 智能改写
    watermark: Optional[bool] = None  # 水印
    seed: Optional[int] = None  # 随机种子
    # wan2.6-image 专用参数
    enable_interleave: Optional[bool] = None  # 图文混合模式
    max_images: Optional[int] = None  # 图文混合模式下最大生成图数


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
            ref_type = ref["type"] if isinstance(ref, dict) else ref.type
            ref_id = ref["id"] if isinstance(ref, dict) else ref.id
            url, name = get_reference_url(ref_type, ref_id)
            references.append(ReferenceItem(
                type=ref_type,
                id=ref_id,
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


class ImageMarkerRequest(BaseModel):
    """更新图片标记"""
    image_id: str
    markers: List[str]  # star, flag, check, cross


@router.post("/{task_id}/markers")
async def update_image_markers(task_id: str, request: ImageMarkerRequest):
    """更新任务中某张图片的标记"""
    VALID_MARKERS = {"star", "flag", "check", "cross"}
    task = storage_service.get_studio_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    for img in task.images:
        if img.id == request.image_id:
            img.markers = [m for m in request.markers if m in VALID_MARKERS]
            storage_service.save_studio_task(task)
            return {"success": True, "markers": img.markers}
    raise HTTPException(status_code=404, detail="图片不存在")


@router.post("/{task_id}/generate")
async def generate_task_images(task_id: str, request: TaskGenerateRequest):
    """启动图片生成（立即返回，后台执行）

    前端通过轮询 GET /{task_id} 获取生成进度和结果。
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
    if request.size is not None:
        task.size = request.size
    if request.prompt_extend is not None:
        task.prompt_extend = request.prompt_extend
    if request.watermark is not None:
        task.watermark = request.watermark
    if request.seed is not None:
        task.seed = request.seed
    if request.enable_interleave is not None:
        task.enable_interleave = request.enable_interleave
    if request.max_images is not None:
        task.max_images = request.max_images

    model_name = task.model or "wan2.5-i2i-preview"
    is_text_to_image = model_name in IMAGE_MODELS
    ref_urls = [ref.url for ref in task.references if ref.url]

    # --- 同步验证（在返回前完成）---
    enable_interleave = request.enable_interleave if hasattr(request, 'enable_interleave') else False
    if model_name == "wan2.6-image" and not enable_interleave and not ref_urls:
        raise HTTPException(
            status_code=400,
            detail="wan2.6-image 在非图文混合模式下需要参考图，请添加参考素材或开启图文混合模式"
        )
    if not is_text_to_image and model_name not in (
        "wan2.6-image", "qwen-image-max", "qwen-image-plus",
        "qwen-image-edit-plus", "qwen-image-edit-max",
        "qwen-image-2.0-pro", "qwen-image-2.0",
    ) and not ref_urls:
        raise HTTPException(status_code=400, detail="该模型需要参考素材图片")

    # 设置生成状态
    task.status = "generating"
    task.images = []
    task.error_message = None
    storage_service.save_studio_task(task)

    # 捕获用户上下文（后台任务需要）
    user_id = get_current_user_id()
    user_config_dir = get_user_config_dir()
    config = get_config()

    size = request.size if request.size is not None else task.size
    prompt_extend = request.prompt_extend if request.prompt_extend is not None else task.prompt_extend
    watermark = request.watermark if request.watermark is not None else task.watermark
    seed = request.seed if request.seed is not None else task.seed
    max_images = request.max_images if hasattr(request, 'max_images') else 5

    # 后台执行生成，立即返回
    asyncio.create_task(_background_generate(
        task=task,
        model_name=model_name,
        is_text_to_image=is_text_to_image,
        ref_urls=ref_urls,
        config=config,
        user_id=user_id,
        user_config_dir=user_config_dir,
        size=size,
        prompt_extend=prompt_extend,
        watermark=watermark,
        seed=seed,
        enable_interleave=enable_interleave,
        max_images=max_images,
    ))

    return {"task": task}


async def _background_generate(
    task: StudioTask,
    model_name: str,
    is_text_to_image: bool,
    ref_urls: List[str],
    config,
    user_id: Optional[str],
    user_config_dir: Optional[str],
    size: Optional[str],
    prompt_extend: bool,
    watermark: bool,
    seed: Optional[int],
    enable_interleave: bool,
    max_images: int,
):
    """后台生成任务——由 asyncio.create_task 调度，不阻塞请求。"""
    # 恢复用户上下文，使 storage_service / get_config 使用正确的用户目录
    set_current_user(user_id)
    set_user_config_dir(user_config_dir)

    try:
        request_ids: List[str] = []

        if model_name == "wan2.6-image":
            images, request_ids = await generate_with_wan26_image(
                task=task,
                ref_urls=ref_urls if ref_urls else None,
                size=size,
                prompt_extend=prompt_extend,
                watermark=watermark,
                seed=seed,
                enable_interleave=enable_interleave,
                max_images=max_images,
            )
        elif is_text_to_image:
            images, request_ids = await generate_with_text_to_image(
                task=task,
                model_name=model_name,
                prompt_extend=prompt_extend,
                watermark=watermark,
                seed=seed,
                size=size,
            )
        elif model_name in ("qwen-image-max", "qwen-image-plus"):
            images, request_ids = await generate_with_qwen_image(
                task=task,
                api_key=config.dashscope_api_key,
                base_url=config.base_url,
                model_name=model_name,
                size=size,
                prompt_extend=prompt_extend,
                watermark=watermark,
                seed=seed,
            )
        elif model_name in ("qwen-image-edit-plus", "qwen-image-edit-max"):
            images, request_ids = await generate_with_qwen_image_edit(
                task=task,
                ref_urls=ref_urls,
                api_key=config.dashscope_api_key,
                base_url=config.base_url,
                model_name=model_name,
                size=size,
                prompt_extend=prompt_extend,
                watermark=watermark,
                seed=seed,
            )
        elif model_name in ("qwen-image-2.0-pro", "qwen-image-2.0"):
            images, request_ids = await generate_with_qwen_image_2(
                task=task,
                ref_urls=ref_urls,
                api_key=config.dashscope_api_key,
                base_url=config.base_url,
                model_name=model_name,
                size=size,
                prompt_extend=prompt_extend,
                watermark=watermark,
                seed=seed,
            )
        else:
            images, request_ids = await generate_with_wanx_i2i(task=task, ref_urls=ref_urls)

        task.images = images
        task.request_ids = request_ids

        valid_images = [img for img in images if img.url]
        group_errors = getattr(task, '_group_errors', [])
        error_detail = ""
        if group_errors:
            unique_errors = list(set(group_errors))
            error_detail = unique_errors[0] if len(unique_errors) == 1 else "; ".join(unique_errors[:3])

        if not images:
            task.status = "failed"
            task.error_message = error_detail or "未生成任何图片，请检查参数或参考图后重试"
        elif not valid_images:
            task.status = "failed"
            task.error_message = error_detail or "所有生成任务均失败，请检查参数或参考图后重试"
        elif len(valid_images) < len(images):
            task.status = "completed"
            task.error_message = (
                f"部分生成失败（{len(valid_images)}/{len(images)} 张成功）: {error_detail}"
                if error_detail
                else f"部分生成失败：{len(valid_images)}/{len(images)} 张成功"
            )
        else:
            task.status = "completed"
            task.error_message = None

    except Exception as e:
        logger.error(f"后台生成失败 [{task.id}]: {e}", exc_info=True)
        task.status = "failed"
        task.error_message = str(e)
    finally:
        storage_service.save_studio_task(task)


async def generate_with_text_to_image(
    task: StudioTask,
    model_name: str,
    prompt_extend: bool = True,
    watermark: bool = False,
    seed: Optional[int] = None,
    size: Optional[str] = None
) -> Tuple[List[StudioTaskImage], List[str]]:
    """使用文生图模型生成
    
    支持模型：wan2.6-t2i, wan2.5-t2i-preview
    
    Returns:
        (images, request_ids)
    """
    from app.services.dashscope.text_to_image import TextToImageService
    
    t2i_service = TextToImageService()
    n = task.n or 1
    group_count = task.group_count or 3
    
    print(f"[文生图] 开始生成: n={n}, group_count={group_count}, total={n * group_count}")
    
    width = None
    height = None
    if size:
        try:
            parts = size.split('*')
            if len(parts) == 2:
                width = int(parts[0])
                height = int(parts[1])
        except ValueError:
            pass
    
    collected_request_ids: List[str] = []
    
    async def generate_single_group(group_index: int) -> tuple[List[StudioTaskImage], bool, str, str, str]:
        """Returns: (图片列表, 是否成功, 错误信息, task_id, request_id)"""
        try:
            result = await t2i_service.generate_batch(
                prompt=task.prompt,
                negative_prompt=task.negative_prompt or "",
                width=width,
                height=height,
                n=n,
                model=model_name,
                prompt_extend=prompt_extend,
                watermark=watermark,
                seed=seed,
                project_id=task.project_id
            )
            
            images = []
            for i, url in enumerate(result.urls):
                images.append(StudioTaskImage(
                    group_index=group_index * n + i,
                    url=url,
                    prompt_used=task.prompt
                ))
            return images, True, "", result.task_id or "", result.request_id or ""
        except Exception as e:
            import traceback
            error_msg = str(e)
            print(f"文生图生成失败 (组{group_index}): {e}")
            traceback.print_exc()
            return [], False, error_msg, "", ""
    
    print(f"[文生图] 开始并发生成 {group_count} 组...")
    group_tasks = [generate_single_group(i) for i in range(group_count)]
    results = await asyncio.gather(*group_tasks)
    
    all_images = []
    failed_groups = []
    
    for i, (images, success, error_msg, tid, rid) in enumerate(results):
        if success:
            all_images.extend(images)
            if rid:
                collected_request_ids.append(rid)
        else:
            failed_groups.append((i, error_msg))
    
    if failed_groups:
        print(f"[文生图] {len(failed_groups)} 个组失败，回退到串行重试...")
        max_retries = 3
        
        for group_index, original_error in failed_groups:
            retry_success = False
            
            for retry in range(max_retries):
                wait_time = 2 * (retry + 1)
                print(f"[文生图] 组{group_index} 等待 {wait_time}s 后重试 ({retry + 1}/{max_retries})...")
                await asyncio.sleep(wait_time)
                
                images, success, error_msg, tid, rid = await generate_single_group(group_index)
                if success:
                    all_images.extend(images)
                    retry_success = True
                    if rid:
                        collected_request_ids.append(rid)
                    print(f"[文生图] 组{group_index} 重试成功")
                    break
            
            if not retry_success:
                print(f"[文生图] 组{group_index} 重试全部失败")
                for i in range(n):
                    all_images.append(StudioTaskImage(
                        group_index=group_index * n + i,
                        url=None,
                        prompt_used=task.prompt
                    ))
    
    all_images.sort(key=lambda img: img.group_index)
    
    success_count = sum(1 for img in all_images if img.url)
    print(f"[文生图] 生成完成: 共 {len(all_images)} 张图片，成功 {success_count} 张")
    print(f"[文生图] request_ids: {collected_request_ids}")
    return all_images, collected_request_ids


async def generate_with_wan26_image(
    task: StudioTask,
    ref_urls: Optional[List[str]] = None,
    size: Optional[str] = None,
    prompt_extend: bool = True,
    watermark: bool = False,
    seed: Optional[int] = None,
    enable_interleave: bool = False,
    max_images: int = 5
) -> Tuple[List[StudioTaskImage], List[str]]:
    """使用 wan2.6-image 模型生成

    Returns:
        (images, request_ids)
    """
    from app.services.dashscope.text_to_image import TextToImageService
    
    t2i_service = TextToImageService()
    n = task.n or 4
    
    if enable_interleave:
        n = 1
        prompt_extend = False
    else:
        n = min(n, 4)
    
    group_errors: List[str] = []
    collected_request_ids: List[str] = []
    
    async def generate_single_group(group_index: int) -> List[StudioTaskImage]:
        try:
            urls, rid = await t2i_service.generate_with_wan26_image(
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
            if rid:
                collected_request_ids.append(rid)
            
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
            group_errors.append(str(e))
            return [StudioTaskImage(
                group_index=group_index * n + i,
                url=None,
                prompt_used=task.prompt
            ) for i in range(n)]
    
    group_tasks = [generate_single_group(i) for i in range(task.group_count)]
    results = await asyncio.gather(*group_tasks)
    
    all_images = []
    for group_images in results:
        all_images.extend(group_images)
    
    if group_errors:
        task._group_errors = group_errors
    return all_images, collected_request_ids


async def generate_with_wanx_i2i(
    task: StudioTask,
    ref_urls: List[str]
) -> Tuple[List[StudioTaskImage], List[str]]:
    """使用万相图生图模型生成

    Returns:
        (images, request_ids)
    """
    i2i_service = ImageToImageService()
    n = task.n or 1
    
    group_errors: List[str] = []
    collected_request_ids: List[str] = []
    
    async def generate_single_group(group_index: int) -> List[StudioTaskImage]:
        try:
            urls, rid = await i2i_service.generate_with_multi_images(
                prompt=task.prompt,
                image_urls=ref_urls,
                negative_prompt=task.negative_prompt,
                n=n,
                project_id=task.project_id
            )
            if rid:
                collected_request_ids.append(rid)
            if isinstance(urls, str):
                urls = [urls]
            
            images = []
            for i, url in enumerate(urls):
                images.append(StudioTaskImage(
                    group_index=group_index * n + i,
                    url=url,
                    prompt_used=task.prompt
                ))
            return images
        except Exception as e:
            group_errors.append(str(e))
            return [StudioTaskImage(
                group_index=group_index * n + i,
                url=None,
                prompt_used=task.prompt
            ) for i in range(n)]
    
    group_tasks = [generate_single_group(i) for i in range(task.group_count)]
    results = await asyncio.gather(*group_tasks)
    
    all_images = []
    for group_images in results:
        all_images.extend(group_images)
    
    if group_errors:
        task._group_errors = group_errors
    return all_images, collected_request_ids


async def generate_with_qwen_image_edit(
    task: StudioTask,
    ref_urls: List[str],
    api_key: str,
    base_url: str = "",
    model_name: str = "qwen-image-edit-max",
    size: Optional[str] = None,
    prompt_extend: bool = True,
    watermark: bool = False,
    seed: Optional[int] = None
) -> Tuple[List[StudioTaskImage], List[str]]:
    """使用通义千问图像编辑模型生成（plus/max 共用）

    Returns:
        (images, request_ids)
    """
    from app.models_registry.image.qwen_image_edit import (
        QwenImageEditService, QWEN_IMAGE_EDIT_PLUS_MODEL_INFO, QWEN_IMAGE_EDIT_MAX_MODEL_INFO
    )
    
    if len(ref_urls) > 3:
        raise ValueError(f"{model_name} 最多支持3张输入图片")
    
    model_info = QWEN_IMAGE_EDIT_MAX_MODEL_INFO if model_name == "qwen-image-edit-max" else QWEN_IMAGE_EDIT_PLUS_MODEL_INFO
    service = QwenImageEditService(model_info)
    service.configure(api_key, base_url)
    
    n = task.n or 1
    if n > 6:
        n = 6
    
    all_images = []
    group_errors: List[str] = []
    collected_request_ids: List[str] = []
    
    async def generate_single_group(group_index: int) -> List[StudioTaskImage]:
        try:
            urls, rid = await service.generate(
                prompt=task.prompt,
                images=ref_urls,
                negative_prompt=task.negative_prompt,
                n=n,
                size=size,
                prompt_extend=prompt_extend,
                watermark=watermark,
                seed=seed,
                project_id=task.project_id
            )
            if rid:
                collected_request_ids.append(rid)
            
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
            print(f"{model_name} 生成失败: {e}")
            traceback.print_exc()
            group_errors.append(str(e))
            return [StudioTaskImage(
                group_index=group_index * n + i,
                url=None,
                prompt_used=task.prompt
            ) for i in range(n)]
    
    for group_idx in range(task.group_count):
        group_images = await generate_single_group(group_idx)
        all_images.extend(group_images)
    
    if group_errors:
        task._group_errors = group_errors
    return all_images, collected_request_ids


async def generate_with_qwen_image(
    task: StudioTask,
    api_key: str,
    base_url: str = "",
    model_name: str = "qwen-image-max",
    size: Optional[str] = None,
    prompt_extend: bool = True,
    watermark: bool = False,
    seed: Optional[int] = None
) -> Tuple[List[StudioTaskImage], List[str]]:
    """使用千问文生图模型生成（max/plus 共用）

    Returns:
        (images, request_ids)
    """
    from app.models_registry.image.qwen_image import (
        QwenImageService, QWEN_IMAGE_MAX_MODEL_INFO, QWEN_IMAGE_PLUS_MODEL_INFO
    )
    
    model_info = QWEN_IMAGE_MAX_MODEL_INFO if model_name == "qwen-image-max" else QWEN_IMAGE_PLUS_MODEL_INFO
    service = QwenImageService(model_info)
    service.configure(api_key, base_url)
    
    all_images = []
    group_errors: List[str] = []
    collected_request_ids: List[str] = []
    
    async def generate_single(group_index: int) -> List[StudioTaskImage]:
        try:
            urls, rid = await service.generate(
                prompt=task.prompt,
                negative_prompt=task.negative_prompt or "",
                size=size or "1664*928",
                prompt_extend=prompt_extend,
                watermark=watermark,
                seed=seed,
            )
            if rid:
                collected_request_ids.append(rid)
            
            final_urls = []
            for url in urls:
                if oss_service.is_enabled():
                    try:
                        import httpx as _httpx
                        async with _httpx.AsyncClient(timeout=30.0) as client:
                            resp = await client.get(url)
                            if resp.status_code == 200:
                                success, oss_url = oss_service.upload_from_bytes(
                                    resp.content, "image", "png", task.project_id
                                )
                                if success:
                                    final_urls.append(oss_url)
                                    continue
                    except Exception:
                        pass
                final_urls.append(url)
            
            return [StudioTaskImage(
                group_index=group_index,
                url=u,
                prompt_used=task.prompt
            ) for u in final_urls]
        except Exception as e:
            import traceback
            print(f"{model_name} 生成失败: {e}")
            traceback.print_exc()
            group_errors.append(str(e))
            return [StudioTaskImage(
                group_index=group_index,
                url=None,
                prompt_used=task.prompt
            )]
    
    group_tasks = [generate_single(i) for i in range(task.group_count)]
    results = await asyncio.gather(*group_tasks)
    
    for group_images in results:
        all_images.extend(group_images)
    
    if group_errors:
        task._group_errors = group_errors
    return all_images, collected_request_ids


async def generate_with_qwen_image_2(
    task: StudioTask,
    ref_urls: List[str],
    api_key: str,
    base_url: str = "",
    model_name: str = "qwen-image-2.0-pro",
    size: Optional[str] = None,
    prompt_extend: bool = True,
    watermark: bool = False,
    seed: Optional[int] = None,
) -> Tuple[List[StudioTaskImage], List[str]]:
    """使用千问图像 2.0 模型生成（文生图 + 图像编辑融合）

    Returns:
        (images, request_ids)
    """
    from app.models_registry.image.qwen_image_2 import (
        QwenImage2Service, QWEN_IMAGE_2_PRO_MODEL_INFO, QWEN_IMAGE_2_MODEL_INFO
    )

    model_info = (
        QWEN_IMAGE_2_PRO_MODEL_INFO
        if model_name == "qwen-image-2.0-pro"
        else QWEN_IMAGE_2_MODEL_INFO
    )
    service = QwenImage2Service(model_info)
    service.configure(api_key, base_url)

    n = task.n or 1
    if n > 6:
        n = 6

    all_images: List[StudioTaskImage] = []
    group_errors: List[str] = []
    collected_request_ids: List[str] = []

    images_input = ref_urls if ref_urls else None

    async def generate_single(group_index: int) -> List[StudioTaskImage]:
        try:
            urls, rid = await service.generate(
                prompt=task.prompt,
                images=images_input,
                negative_prompt=task.negative_prompt or "",
                n=n,
                size=size or "1024*1024",
                prompt_extend=prompt_extend,
                watermark=watermark,
                seed=seed,
            )
            if rid:
                collected_request_ids.append(rid)

            final_urls: list[str] = []
            for url in urls:
                if oss_service.is_enabled():
                    try:
                        import httpx as _httpx
                        async with _httpx.AsyncClient(timeout=30.0) as client:
                            resp = await client.get(url)
                            if resp.status_code == 200:
                                success, oss_url = oss_service.upload_from_bytes(
                                    resp.content, "image", "png", task.project_id
                                )
                                if success:
                                    final_urls.append(oss_url)
                                    continue
                    except Exception:
                        pass
                final_urls.append(url)

            return [
                StudioTaskImage(
                    group_index=group_index, url=u, prompt_used=task.prompt
                )
                for u in final_urls
            ]
        except Exception as e:
            import traceback
            logger.error(f"{model_name} 生成失败: {e}")
            traceback.print_exc()
            group_errors.append(str(e))
            return [
                StudioTaskImage(
                    group_index=group_index, url=None, prompt_used=task.prompt
                )
            ]

    group_tasks = [generate_single(i) for i in range(task.group_count)]
    results = await asyncio.gather(*group_tasks)

    for group_images in results:
        all_images.extend(group_images)

    if group_errors:
        task._group_errors = group_errors
    return all_images, collected_request_ids


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
    - 图生图模型：wan2.5-i2i-preview, qwen-image-edit-plus, qwen-image-edit-max
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
            "common_sizes": model.get_common_sizes_for_frontend(),
        }
    
    # 获取 registry 中的文生图模型
    t2i_models = registry.list_models(ModelType.TEXT_TO_IMAGE)
    for model in t2i_models:
        result[model.id] = {
            "id": model.id,
            "name": model.name,
            "description": model.description,
            "model_type": "text_to_image",
            "capabilities": model.capabilities.model_dump() if model.capabilities else {},
            "parameters": [p.model_dump() for p in model.parameters] if model.parameters else [],
            "common_sizes": model.get_common_sizes_for_frontend(),
        }
    
    # 添加文生图模型（从 IMAGE_MODELS 配置，兼容旧代码）
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

