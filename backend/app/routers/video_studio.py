"""
视频工作室 API 路由
支持两种任务类型：
1. 图生视频（image_to_video）：基于首帧图生成视频
2. 视频生视频（reference_to_video）：基于参考视频生成新视频
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.models.media import VideoStudioTask
from app.services.storage import storage_service
from app.services.dashscope.image_to_video import ImageToVideoService
from app.services.dashscope.reference_to_video import ReferenceToVideoService
from app.services.oss import oss_service

router = APIRouter()


class VideoStudioTaskCreateRequest(BaseModel):
    """创建视频生成任务请求
    
    支持两种任务类型：
    1. image_to_video（图生视频）：使用 first_frame_url
    2. reference_to_video（视频生视频）：使用 reference_video_urls
    
    图生视频参数说明（根据官方文档）：
    - resolution: 分辨率档位，wan2.5/2.6 支持 480P/720P/1080P（默认1080P）
    - duration: 视频时长，wan2.6 支持 5/10/15 秒，wan2.5 支持 5/10 秒，wanx2.1 支持 3/4/5 秒
    - prompt_extend: 智能改写，默认 True
    - watermark: 水印标识（右下角"AI生成"），默认 False
    - audio: 自动配音（仅 wan2.5/2.6 支持），默认 True
    - audio_url: 自定义音频URL（传入时 audio 参数无效）
    - seed: 随机种子，范围 [0, 2147483647]
    - shot_type: 镜头类型（仅 wan2.6 支持），single/multi
    
    视频生视频参数说明（wan2.6-r2v）：
    - size: 分辨率（宽*高格式，如 1920*1080）
    - duration: 视频时长，5 或 10 秒
    - shot_type: 镜头类型，single/multi
    - watermark: 是否添加水印
    - seed: 随机种子
    - audio: 是否生成音频
    - r2v_prompt_extend: 提示词改写，默认 True
    """
    project_id: str
    name: str = ""
    
    # 任务类型
    task_type: str = "image_to_video"  # image_to_video 或 reference_to_video
    
    # 图生视频参数
    mode: str = "first_frame"  # first_frame 或 first_last_frame
    first_frame_url: Optional[str] = None  # 首帧图URL
    last_frame_url: Optional[str] = None  # 尾帧图URL（首尾帧模式）
    audio_url: Optional[str] = None  # 自定义音频URL
    
    # 视频生视频参数
    reference_video_urls: List[str] = []  # 参考视频URL列表（最多3个）
    
    # 通用参数
    prompt: str = ""
    negative_prompt: str = ""
    model: str = "wan2.5-i2v-preview"
    duration: int = 5
    watermark: bool = False  # 水印
    seed: Optional[int] = None  # 随机种子
    shot_type: Optional[str] = None  # 镜头类型
    auto_audio: bool = True  # 自动配音
    
    # 图生视频专用
    resolution: str = "1080P"  # 默认1080P
    prompt_extend: bool = True  # 智能改写
    
    # 视频生视频专用
    size: str = "1920*1080"  # 分辨率（宽*高格式）
    r2v_prompt_extend: bool = True  # 视频生视频的提示词改写，默认开启
    
    group_count: int = 1


class VideoStudioTaskUpdateRequest(BaseModel):
    """更新任务请求"""
    name: Optional[str] = None
    selected_video_url: Optional[str] = None
    task_type: Optional[str] = None  # 任务类型: image_to_video / reference_to_video
    # 支持编辑的字段
    prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    model: Optional[str] = None
    resolution: Optional[str] = None
    duration: Optional[int] = None
    prompt_extend: Optional[bool] = None
    watermark: Optional[bool] = None
    seed: Optional[int] = None
    auto_audio: Optional[bool] = None
    shot_type: Optional[str] = None  # 镜头类型
    first_frame_url: Optional[str] = None
    audio_url: Optional[str] = None
    reference_video_urls: Optional[List[str]] = None  # 参考视频URL列表
    size: Optional[str] = None  # 视频生视频分辨率
    r2v_prompt_extend: Optional[bool] = None  # 视频生视频的提示词改写
    group_count: Optional[int] = None  # 生成组数


@router.get("")
async def list_tasks(project_id: str):
    """获取项目所有视频工作室任务"""
    tasks = storage_service.get_video_studio_tasks(project_id)
    return {"tasks": tasks}


@router.get("/{task_id}")
async def get_task(task_id: str):
    """获取单个任务"""
    task = storage_service.get_video_studio_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.post("")
async def create_task(request: VideoStudioTaskCreateRequest):
    """创建并启动视频生成任务
    
    支持两种任务类型：
    1. image_to_video（图生视频）：需要 first_frame_url
    2. reference_to_video（视频生视频）：需要 reference_video_urls
    """
    # 打印详细请求信息
    print(f"\n{'#'*60}")
    print(f"# 视频工作室 - 创建任务")
    print(f"{'#'*60}")
    print(f"[请求参数] task_type: {request.task_type}")
    print(f"[请求参数] project_id: {request.project_id}")
    print(f"[请求参数] name: {request.name}")
    print(f"[请求参数] model: {request.model}")
    print(f"[请求参数] mode: {request.mode}")
    print(f"[请求参数] resolution: {request.resolution}")
    print(f"[请求参数] size: {request.size}")
    print(f"[请求参数] duration: {request.duration}")
    print(f"[请求参数] prompt_extend: {request.prompt_extend}")
    print(f"[请求参数] watermark: {request.watermark}")
    print(f"[请求参数] seed: {request.seed}")
    print(f"[请求参数] auto_audio: {request.auto_audio}")
    print(f"[请求参数] shot_type: {request.shot_type}")
    print(f"[请求参数] r2v_prompt_extend: {request.r2v_prompt_extend}")
    print(f"[请求参数] group_count: {request.group_count}")
    if request.first_frame_url:
        print(f"[请求参数] first_frame_url: {request.first_frame_url[:100]}...")
    if request.reference_video_urls:
        print(f"[请求参数] reference_video_urls: {request.reference_video_urls}")
    print(f"[请求参数] prompt: {request.prompt[:200] if request.prompt else 'None'}...")
    print(f"{'#'*60}\n")
    
    # 根据任务类型验证参数
    if request.task_type == "image_to_video":
        if not request.first_frame_url:
            raise HTTPException(status_code=400, detail="图生视频任务需要选择首帧图")
        if request.mode == "first_last_frame" and not request.last_frame_url:
            raise HTTPException(status_code=400, detail="首尾帧模式需要选择尾帧图")
    elif request.task_type == "reference_to_video":
        if not request.reference_video_urls:
            raise HTTPException(status_code=400, detail="视频生视频任务需要选择参考视频")
        if len(request.reference_video_urls) > 3:
            raise HTTPException(status_code=400, detail="参考视频最多3个")
    else:
        raise HTTPException(status_code=400, detail="不支持的任务类型")
    
    # 创建任务记录
    task = VideoStudioTask(
        project_id=request.project_id,
        name=request.name or f"视频任务 {datetime.now().strftime('%Y%m%d_%H%M%S')}",
        task_type=request.task_type,
        mode=request.mode,
        first_frame_url=request.first_frame_url,
        last_frame_url=request.last_frame_url,
        reference_video_urls=request.reference_video_urls,
        audio_url=request.audio_url,
        prompt=request.prompt,
        negative_prompt=request.negative_prompt,
        model=request.model,
        resolution=request.resolution,
        duration=request.duration,
        prompt_extend=request.prompt_extend,
        watermark=request.watermark,
        seed=request.seed,
        auto_audio=request.auto_audio,
        shot_type=request.shot_type,
        size=request.size,
        r2v_prompt_extend=request.r2v_prompt_extend,
        group_count=request.group_count,
        status="processing"
    )
    
    try:
        # 为每组创建生成任务
        for i in range(request.group_count):
            if request.task_type == "image_to_video":
                # 图生视频任务
                i2v_service = ImageToVideoService()
                
                if request.mode == "first_frame":
                    api_task_id = await i2v_service.create_task(
                        image_url=request.first_frame_url,
                        prompt=request.prompt,
                        model=request.model,
                        resolution=request.resolution,
                        duration=request.duration,
                        prompt_extend=request.prompt_extend,
                        watermark=request.watermark,
                        seed=request.seed + i if request.seed else None,
                        audio_url=request.audio_url,
                        audio=request.auto_audio if not request.audio_url else None,
                        negative_prompt=request.negative_prompt if request.negative_prompt else None,
                        shot_type=request.shot_type
                    )
                    task.task_ids.append(api_task_id)
                else:
                    raise HTTPException(status_code=400, detail="首尾帧模式暂不支持")
            
            elif request.task_type == "reference_to_video":
                # 视频生视频任务
                r2v_service = ReferenceToVideoService()
                
                api_task_id = await r2v_service.create_task(
                    reference_video_urls=request.reference_video_urls,
                    prompt=request.prompt,
                    model=request.model,
                    size=request.size,
                    duration=request.duration,
                    shot_type=request.shot_type,
                    watermark=request.watermark,
                    seed=request.seed + i if request.seed else None,
                    audio=request.auto_audio,
                    negative_prompt=request.negative_prompt if request.negative_prompt else None,
                    prompt_extend=request.r2v_prompt_extend,
                )
                task.task_ids.append(api_task_id)
        
        storage_service.save_video_studio_task(task)
        
        return {"task": task}
        
    except Exception as e:
        task.status = "failed"
        task.error_message = str(e)
        storage_service.save_video_studio_task(task)
        raise HTTPException(status_code=500, detail=f"创建任务失败: {str(e)}")


@router.get("/{task_id}/status")
async def get_task_status(task_id: str):
    """查询任务状态"""
    print(f"\n[视频工作室状态查询] task_id: {task_id}")
    
    task = storage_service.get_video_studio_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    print(f"[视频工作室状态查询] 任务名: {task.name}")
    print(f"[视频工作室状态查询] 任务类型: {getattr(task, 'task_type', 'image_to_video')}")
    print(f"[视频工作室状态查询] 模型: {task.model}")
    print(f"[视频工作室状态查询] 当前状态: {task.status}")
    print(f"[视频工作室状态查询] API任务IDs: {task.task_ids}")
    
    if task.status != "processing":
        print(f"[视频工作室状态查询] 任务已完成，无需轮询")
        return {"task": task}
    
    all_succeeded = True
    all_finished = True
    video_urls = []
    
    # 根据任务类型选择服务
    task_type = getattr(task, 'task_type', 'image_to_video')
    
    for api_task_id in task.task_ids:
        print(f"\n[视频工作室状态查询] 查询子任务: {api_task_id}")
        try:
            if task_type == "reference_to_video" or task.model == "wan2.6-r2v":
                # 视频生视频任务使用 HTTP 查询
                print(f"[视频工作室状态查询] 使用 视频生视频服务 (HTTP)")
                r2v_service = ReferenceToVideoService()
                status, video_url = await r2v_service.get_task_status(api_task_id, task.project_id)
            else:
                # 图生视频任务
                i2v_service = ImageToVideoService()
                # wan2.6-i2v 模型也使用 HTTP 查询
                use_http = 'wan2.6' in task.model
                print(f"[视频工作室状态查询] 使用 图生视频服务 (HTTP={use_http})")
                status, video_url = await i2v_service.get_task_status(api_task_id, task.project_id, use_http=use_http)
            
            print(f"[视频工作室状态查询] 子任务 {api_task_id} 状态: {status}")
            
            if status == "SUCCEEDED" and video_url:
                # 上传视频到 OSS
                if oss_service.is_enabled():
                    print(f"[视频工作室状态查询] 正在上传视频到 OSS...")
                    oss_url = oss_service.upload_video(video_url, task.project_id)
                    if oss_url != video_url:
                        print(f"[视频工作室状态查询] OSS上传成功: {oss_url[:80]}...")
                        video_url = oss_url
                    else:
                        print(f"[视频工作室状态查询] OSS上传失败，使用原始URL")
                
                video_urls.append(video_url)
                print(f"[视频工作室状态查询] 子任务成功，视频URL已获取")
            elif status == "FAILED":
                all_succeeded = False
                print(f"[视频工作室状态查询] 子任务失败")
            elif status in ["PENDING", "RUNNING"]:
                all_finished = False
                print(f"[视频工作室状态查询] 子任务进行中")
                
        except Exception as e:
            all_succeeded = False
            task.error_message = str(e)
            print(f"[视频工作室状态查询] 查询子任务异常: {e}")
    
    # 更新任务状态
    task.video_urls = video_urls
    
    if all_finished:
        if all_succeeded and len(video_urls) == len(task.task_ids):
            task.status = "succeeded"
            print(f"[视频工作室状态查询] 所有任务成功完成！共 {len(video_urls)} 个视频")
        else:
            task.status = "failed"
            if not task.error_message:
                task.error_message = "部分视频生成失败"
            print(f"[视频工作室状态查询] 任务失败: {task.error_message}")
    else:
        print(f"[视频工作室状态查询] 任务进行中，已完成 {len(video_urls)}/{len(task.task_ids)}")
    
    task.updated_at = datetime.now()
    storage_service.save_video_studio_task(task)
    
    return {"task": task}


@router.put("/{task_id}")
async def update_task(task_id: str, request: VideoStudioTaskUpdateRequest):
    """更新任务信息"""
    task = storage_service.get_video_studio_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 更新各字段
    if request.name is not None:
        task.name = request.name
    if request.selected_video_url is not None:
        task.selected_video_url = request.selected_video_url
    if request.prompt is not None:
        task.prompt = request.prompt
    if request.negative_prompt is not None:
        task.negative_prompt = request.negative_prompt
    if request.model is not None:
        task.model = request.model
    if request.resolution is not None:
        task.resolution = request.resolution
    if request.duration is not None:
        task.duration = request.duration
    if request.prompt_extend is not None:
        task.prompt_extend = request.prompt_extend
    if request.watermark is not None:
        task.watermark = request.watermark
    if request.seed is not None:
        task.seed = request.seed
    if request.auto_audio is not None:
        task.auto_audio = request.auto_audio
    if request.shot_type is not None:
        task.shot_type = request.shot_type
    if request.first_frame_url is not None:
        task.first_frame_url = request.first_frame_url
    if request.audio_url is not None:
        task.audio_url = request.audio_url
    if request.reference_video_urls is not None:
        task.reference_video_urls = request.reference_video_urls
    if request.size is not None:
        task.size = request.size
    if request.r2v_prompt_extend is not None:
        task.r2v_prompt_extend = request.r2v_prompt_extend
    if request.task_type is not None:
        task.task_type = request.task_type
    if request.group_count is not None:
        task.group_count = request.group_count
    
    task.updated_at = datetime.now()
    storage_service.save_video_studio_task(task)
    
    return task


@router.post("/{task_id}/regenerate")
async def regenerate_task(task_id: str):
    """重新生成任务视频"""
    task = storage_service.get_video_studio_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 根据任务类型验证
    task_type = getattr(task, 'task_type', 'image_to_video')
    
    if task_type == "image_to_video":
        if not task.first_frame_url:
            raise HTTPException(status_code=400, detail="任务没有首帧图")
    elif task_type == "reference_to_video":
        if not task.reference_video_urls:
            raise HTTPException(status_code=400, detail="任务没有参考视频")
    
    # 重置任务状态
    task.status = "processing"
    task.video_urls = []
    task.error_message = None
    task.task_ids = []
    task.updated_at = datetime.now()
    
    import asyncio
    
    if task_type == "reference_to_video" or task.model == "wan2.6-r2v":
        # 视频生视频任务
        r2v_service = ReferenceToVideoService()
        
        async def generate_one_r2v(idx: int):
            current_seed = task.seed + idx if task.seed is not None else None
            # 获取r2v_prompt_extend，如果没有则默认True
            r2v_prompt_extend = getattr(task, 'r2v_prompt_extend', True)
            return await r2v_service.create_task(
                reference_video_urls=task.reference_video_urls,
                prompt=task.prompt,
                model=task.model,
                size=task.size,
                duration=task.duration,
                shot_type=task.shot_type,
                watermark=task.watermark,
                seed=current_seed,
                audio=task.auto_audio,
                negative_prompt=task.negative_prompt,
                prompt_extend=r2v_prompt_extend,
            )
        
        try:
            task_ids = await asyncio.gather(*[generate_one_r2v(i) for i in range(task.group_count)])
            task.task_ids = list(task_ids)
            storage_service.save_video_studio_task(task)
            return {"task": task, "task_ids": task_ids}
        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            storage_service.save_video_studio_task(task)
            raise HTTPException(status_code=500, detail=str(e))
    else:
        # 图生视频任务
        i2v_service = ImageToVideoService()
        
        async def generate_one_i2v(idx: int):
            current_seed = task.seed + idx if task.seed is not None else None
            return await i2v_service.create_task(
                image_url=task.first_frame_url,
                prompt=task.prompt,
                model=task.model,
                resolution=task.resolution,
                duration=task.duration,
                prompt_extend=task.prompt_extend,
                watermark=task.watermark,
                seed=current_seed,
                audio_url=task.audio_url,
                audio=task.auto_audio if not task.audio_url else None,
                negative_prompt=task.negative_prompt,
                shot_type=task.shot_type,
            )
        
        try:
            task_ids = await asyncio.gather(*[generate_one_i2v(i) for i in range(task.group_count)])
            task.task_ids = list(task_ids)
            storage_service.save_video_studio_task(task)
            return {"task": task, "task_ids": task_ids}
        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            storage_service.save_video_studio_task(task)
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/{task_id}/save-to-library")
async def save_to_library(task_id: str, video_url: str, name: str = ""):
    """保存视频到视频库"""
    from app.models.media import VideoItem
    
    task = storage_service.get_video_studio_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if video_url not in task.video_urls:
        raise HTTPException(status_code=400, detail="视频URL不属于此任务")
    
    # 创建视频库记录
    video = VideoItem(
        project_id=task.project_id,
        name=name or f"工作室视频 {datetime.now().strftime('%Y%m%d_%H%M%S')}",
        url=video_url,
        file_type="mp4",
        duration=task.duration
    )
    
    storage_service.save_video_item(video)
    
    return {"message": "已保存到视频库", "video": video}


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    """删除任务"""
    task = storage_service.get_video_studio_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    storage_service.delete_video_studio_task(task_id)
    return {"message": "任务已删除"}


@router.delete("")
async def delete_all_tasks(project_id: str):
    """删除项目所有任务"""
    tasks = storage_service.get_video_studio_tasks(project_id)
    for task in tasks:
        storage_service.delete_video_studio_task(task.id)
    return {"message": f"已删除 {len(tasks)} 个任务"}

