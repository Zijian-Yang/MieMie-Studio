"""
视频工作室 API 路由
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.models.media import VideoStudioTask
from app.services.storage import storage_service
from app.services.dashscope.image_to_video import ImageToVideoService

router = APIRouter()


class VideoStudioTaskCreateRequest(BaseModel):
    """创建视频生成任务请求
    
    参数说明（根据官方文档）：
    - resolution: 分辨率档位，wan2.5 支持 480P/720P/1080P（默认1080P）
    - duration: 视频时长，wan2.5 支持 5/10 秒，wanx2.1 支持 3/4/5 秒
    - prompt_extend: 智能改写，默认 True
    - watermark: 水印标识（右下角"AI生成"），默认 False
    - audio: 自动配音（仅 wan2.5 支持），默认 True
    - audio_url: 自定义音频URL（传入时 audio 参数无效）
    - seed: 随机种子，范围 [0, 2147483647]
    """
    project_id: str
    name: str = ""
    mode: str = "first_frame"  # first_frame 或 first_last_frame
    first_frame_url: str  # 首帧图URL
    last_frame_url: Optional[str] = None  # 尾帧图URL（首尾帧模式）
    audio_url: Optional[str] = None  # 自定义音频URL
    prompt: str = ""
    negative_prompt: str = ""
    model: str = "wan2.5-i2v-preview"
    resolution: str = "1080P"  # 默认1080P
    duration: int = 5
    prompt_extend: bool = True  # 智能改写
    watermark: bool = False  # 水印
    seed: Optional[int] = None  # 随机种子
    auto_audio: bool = True  # 自动配音（仅wan2.5，默认开启）
    group_count: int = 1


class VideoStudioTaskUpdateRequest(BaseModel):
    """更新任务请求"""
    name: Optional[str] = None
    selected_video_url: Optional[str] = None


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
    """创建并启动视频生成任务"""
    # 验证首帧图
    if not request.first_frame_url:
        raise HTTPException(status_code=400, detail="请选择首帧图")
    
    # 首尾帧模式验证
    if request.mode == "first_last_frame" and not request.last_frame_url:
        raise HTTPException(status_code=400, detail="首尾帧模式需要选择尾帧图")
    
    # 创建任务记录
    task = VideoStudioTask(
        project_id=request.project_id,
        name=request.name or f"视频任务 {datetime.now().strftime('%Y%m%d_%H%M%S')}",
        mode=request.mode,
        first_frame_url=request.first_frame_url,
        last_frame_url=request.last_frame_url,
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
        group_count=request.group_count,
        status="processing"
    )
    
    i2v_service = ImageToVideoService()
    
    try:
        # 为每组创建生成任务
        for i in range(request.group_count):
            # 首帧生视频模式
            if request.mode == "first_frame":
                api_task_id = await i2v_service.create_task(
                    image_url=request.first_frame_url,
                    prompt=request.prompt,
                    model=request.model,
                    resolution=request.resolution,
                    duration=request.duration,
                    prompt_extend=request.prompt_extend,
                    watermark=request.watermark,
                    seed=request.seed,
                    audio_url=request.audio_url,
                    # audio 参数仅在没有 audio_url 时生效
                    audio=request.auto_audio if not request.audio_url else None,
                    negative_prompt=request.negative_prompt if request.negative_prompt else None
                )
                task.task_ids.append(api_task_id)
            
            # 首尾帧模式（暂不支持）
            else:
                raise HTTPException(status_code=400, detail="首尾帧模式暂不支持")
        
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
    task = storage_service.get_video_studio_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if task.status != "processing":
        return {"task": task}
    
    i2v_service = ImageToVideoService()
    all_succeeded = True
    all_finished = True
    video_urls = []
    
    for api_task_id in task.task_ids:
        try:
            status, video_url = await i2v_service.get_task_status(api_task_id, task.project_id)
            
            if status == "SUCCEEDED" and video_url:
                video_urls.append(video_url)
            elif status == "FAILED":
                all_succeeded = False
            elif status in ["PENDING", "RUNNING"]:
                all_finished = False
                
        except Exception as e:
            all_succeeded = False
            task.error_message = str(e)
    
    # 更新任务状态
    task.video_urls = video_urls
    
    if all_finished:
        if all_succeeded and len(video_urls) == len(task.task_ids):
            task.status = "succeeded"
        else:
            task.status = "failed"
            if not task.error_message:
                task.error_message = "部分视频生成失败"
    
    task.updated_at = datetime.now()
    storage_service.save_video_studio_task(task)
    
    return {"task": task}


@router.put("/{task_id}")
async def update_task(task_id: str, request: VideoStudioTaskUpdateRequest):
    """更新任务信息"""
    task = storage_service.get_video_studio_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if request.name is not None:
        task.name = request.name
    if request.selected_video_url is not None:
        task.selected_video_url = request.selected_video_url
    
    task.updated_at = datetime.now()
    storage_service.save_video_studio_task(task)
    
    return task


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

