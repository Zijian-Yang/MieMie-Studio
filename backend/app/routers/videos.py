"""
视频生成 API 路由
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from app.models.video import Video, VideoTask, TaskStatus
from app.services.storage import storage_service
from app.services.dashscope.image_to_video import ImageToVideoService

router = APIRouter()


class VideoGenerateRequest(BaseModel):
    """视频生成请求"""
    project_id: str
    shot_id: str
    shot_number: int = 0
    first_frame_url: Optional[str] = None  # 首帧图 URL（可从分镜中自动获取）
    prompt: Optional[str] = None  # 视频生成提示词（可自动生成）
    duration: float = 5.0  # 目标时长（秒），不超过10秒


def generate_video_prompt(shot) -> str:
    """根据分镜信息生成视频提示词"""
    prompt_parts = []
    
    # 动作描述（最重要）
    if shot.character_action:
        prompt_parts.append(f"动作: {shot.character_action}")
    
    # 镜头设计
    if shot.shot_design:
        prompt_parts.append(f"镜头: {shot.shot_design}")
    
    # 情绪基调
    if shot.mood:
        prompt_parts.append(f"氛围: {shot.mood}")
    
    # 角色表现
    if shot.characters:
        char_desc = ", ".join(shot.characters)
        if shot.character_appearance:
            char_desc += f" ({shot.character_appearance})"
        prompt_parts.append(f"角色: {char_desc}")
    
    # 场景和光线
    if shot.lighting:
        prompt_parts.append(f"光线: {shot.lighting}")
    
    if prompt_parts:
        return ", ".join(prompt_parts) + ", 流畅自然的动作, 电影级画质"
    else:
        return "流畅的摄像机运动, 自然的场景变化, 电影级画质"


class VideoBatchGenerateRequest(BaseModel):
    """批量视频生成请求"""
    project_id: str


@router.post("/generate")
async def generate_video(request: VideoGenerateRequest):
    """生成单个视频
    
    如果未提供 first_frame_url 和 prompt，会从分镜信息中自动获取/生成
    """
    project = storage_service.get_project(request.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 获取分镜信息
    shot = None
    if project.script and project.script.shots:
        for s in project.script.shots:
            if s.id == request.shot_id:
                shot = s
                break
    
    # 获取首帧图URL
    first_frame_url = request.first_frame_url
    if not first_frame_url and shot:
        first_frame_url = shot.first_frame_url
    
    if not first_frame_url:
        # 尝试从 Frame 中获取
        frame = storage_service.get_frame_by_shot(request.project_id, request.shot_id)
        if frame and frame.image_groups and frame.selected_group_index < len(frame.image_groups):
            first_frame_url = frame.image_groups[frame.selected_group_index].url
    
    if not first_frame_url:
        raise HTTPException(status_code=400, detail="首帧图未生成，请先生成首帧图")
    
    # 获取或生成提示词
    prompt = request.prompt
    if not prompt and shot:
        prompt = generate_video_prompt(shot)
    if not prompt:
        prompt = "流畅的摄像机运动, 自然的场景变化"
    
    # 确保时长不超过10秒
    duration = min(request.duration, 10.0)
    
    i2v_service = ImageToVideoService()
    
    try:
        # 创建视频记录
        video = Video(
            project_id=request.project_id,
            shot_id=request.shot_id,
            shot_number=request.shot_number,
            first_frame_url=first_frame_url,
            prompt=prompt,
            duration=duration
        )
        
        # 提交生成任务
        task_id = await i2v_service.create_task(
            image_url=first_frame_url,
            prompt=prompt
        )
        
        video.task = VideoTask(
            task_id=task_id,
            status=TaskStatus.PROCESSING
        )
        
        storage_service.save_video(video)
        
        return {"video": video, "task_id": task_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"视频生成失败: {str(e)}")


@router.post("/generate-batch")
async def generate_videos_batch(request: VideoBatchGenerateRequest):
    """批量生成所有分镜视频"""
    project = storage_service.get_project(request.project_id)
    if not project or not project.script:
        raise HTTPException(status_code=404, detail="项目或剧本不存在")
    
    if not project.script.shots:
        raise HTTPException(status_code=400, detail="分镜列表为空")
    
    i2v_service = ImageToVideoService()
    videos = []
    errors = []
    
    for shot in project.script.shots:
        # 获取首帧图URL
        first_frame_url = shot.first_frame_url
        if not first_frame_url:
            # 尝试从 Frame 中获取
            frame = storage_service.get_frame_by_shot(request.project_id, shot.id)
            if frame and frame.image_groups and frame.selected_group_index < len(frame.image_groups):
                first_frame_url = frame.image_groups[frame.selected_group_index].url
        
        if not first_frame_url:
            errors.append({
                "shot_id": shot.id,
                "shot_number": shot.shot_number,
                "error": "首帧图未生成"
            })
            continue
        
        try:
            # 根据分镜信息生成详细提示词
            prompt = generate_video_prompt(shot)
            
            # 确保时长不超过10秒
            duration = min(shot.duration, 10.0)
            
            video = Video(
                project_id=request.project_id,
                shot_id=shot.id,
                shot_number=shot.shot_number,
                first_frame_url=first_frame_url,
                prompt=prompt,
                duration=duration
            )
            
            task_id = await i2v_service.create_task(
                image_url=first_frame_url,
                prompt=prompt
            )
            
            video.task = VideoTask(
                task_id=task_id,
                status=TaskStatus.PROCESSING
            )
            
            storage_service.save_video(video)
            videos.append(video)
            
        except Exception as e:
            errors.append({
                "shot_id": shot.id,
                "shot_number": shot.shot_number,
                "error": str(e)
            })
    
    return {
        "videos": videos,
        "errors": errors,
        "success_count": len(videos),
        "error_count": len(errors)
    }


@router.get("/status/{task_id}")
async def get_video_status(task_id: str):
    """查询视频生成状态"""
    i2v_service = ImageToVideoService()
    
    try:
        status, video_url = await i2v_service.get_task_status(task_id)
        
        # 更新数据库中的视频记录
        video = storage_service.get_video_by_task(task_id)
        if video and video.task:
            if status == "SUCCEEDED":
                video.task.status = TaskStatus.SUCCEEDED
                video.video_url = video_url
                
                # 更新分镜的视频URL
                project = storage_service.get_project(video.project_id)
                if project and project.script:
                    for shot in project.script.shots:
                        if shot.id == video.shot_id:
                            shot.video_url = video_url
                            break
                    storage_service.save_project(project)
                    
            elif status == "FAILED":
                video.task.status = TaskStatus.FAILED
            elif status == "PROCESSING":
                video.task.status = TaskStatus.PROCESSING
            
            storage_service.save_video(video)
        
        return {
            "task_id": task_id,
            "status": status,
            "video_url": video_url
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询状态失败: {str(e)}")


@router.get("")
async def list_videos(project_id: str):
    """获取项目所有视频"""
    videos = storage_service.get_videos_by_project(project_id)
    return {"videos": videos}


@router.get("/{video_id}")
async def get_video(video_id: str):
    """获取视频详情"""
    video = storage_service.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    return video


@router.delete("/{video_id}")
async def delete_video(video_id: str):
    """删除视频"""
    video = storage_service.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    
    storage_service.delete_video(video_id)
    return {"message": "视频已删除"}
