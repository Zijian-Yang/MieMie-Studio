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
    duration: int = 5  # 目标时长（秒），wan2.6支持5-15秒，wan2.5支持5-10秒
    # 视频生成参数（覆盖系统设置）
    model: Optional[str] = None
    resolution: Optional[str] = None  # 分辨率（wan2.5/2.6用480P/720P/1080P，wanx2.1用宽*高）
    prompt_extend: Optional[bool] = None
    watermark: Optional[bool] = None
    seed: Optional[int] = None
    # 音频参数（仅wan2.5/2.6支持）
    audio_url: Optional[str] = None  # 自定义音频URL
    audio: Optional[bool] = None  # 是否自动生成音频
    # 镜头类型（仅wan2.6支持）
    shot_type: Optional[str] = None  # single/multi


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
    # 视频生成参数（覆盖系统设置）
    model: Optional[str] = None
    resolution: Optional[str] = None  # 分辨率
    prompt_extend: Optional[bool] = None
    watermark: Optional[bool] = None
    seed: Optional[int] = None
    # 音频参数（仅wan2.5支持）
    audio: Optional[bool] = None


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
    
    # 确保时长在合理范围内（wan2.5支持5-10秒）
    duration = max(5, min(request.duration, 10))
    
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
        
        # 打印调试信息
        print(f"[视频生成] 首帧URL: {first_frame_url[:100] if first_frame_url else 'None'}...")
        print(f"[视频生成] 提示词: {prompt[:100] if prompt else 'None'}...")
        print(f"[视频生成] 模型: {request.model}, 分辨率: {request.resolution}, 时长: {duration}")
        
        # 提交生成任务（传递可选参数）
        task_id = await i2v_service.create_task(
            image_url=first_frame_url,
            prompt=prompt,
            model=request.model,
            resolution=request.resolution,
            duration=duration,
            prompt_extend=request.prompt_extend,
            watermark=request.watermark,
            seed=request.seed,
            audio_url=request.audio_url,
            audio=request.audio,
            shot_type=request.shot_type
        )
        
        video.task = VideoTask(
            task_id=task_id,
            status=TaskStatus.PROCESSING
        )
        
        storage_service.save_video(video)
        
        return {"video": video, "task_id": task_id}
    except Exception as e:
        import traceback
        error_msg = str(e)
        print(f"[视频生成错误] {error_msg}")
        print(f"[视频生成错误] 堆栈: {traceback.format_exc()}")
        
        # 提供更友好的错误信息
        if "DataInspectionFailed" in error_msg or "inappropriate content" in error_msg:
            detail = "内容审核未通过：提示词或图片可能包含敏感内容，请修改提示词后重试"
        elif "url error" in error_msg.lower():
            detail = "首帧图URL无效，请检查图片是否可访问"
        elif "image_url must provided" in error_msg.lower() or "img_url must provided" in error_msg.lower():
            detail = "首帧图URL缺失，请确保已生成首帧图"
        else:
            detail = f"视频生成失败: {error_msg}"
        
        raise HTTPException(status_code=500, detail=detail)


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
            
            # 确保时长在合理范围内（wan2.5支持5-10秒）
            duration = max(5, min(shot.duration, 10))
            
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
                prompt=prompt,
                model=request.model,
                resolution=request.resolution,
                duration=duration,
                prompt_extend=request.prompt_extend,
                watermark=request.watermark,
                seed=request.seed,
                audio=request.audio
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


class SelectVideoRequest(BaseModel):
    """选择视频请求"""
    project_id: str
    shot_id: str
    video_id: str


@router.post("/select")
async def select_video(request: SelectVideoRequest):
    """保存选中的候选视频作为该分镜的最终视频"""
    project = storage_service.get_project(request.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    if not project.script or not project.script.shots:
        raise HTTPException(status_code=404, detail="分镜脚本不存在")
    
    # 获取选中的视频
    video = storage_service.get_video(request.video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    
    if not video.video_url:
        raise HTTPException(status_code=400, detail="视频尚未生成完成")
    
    # 找到对应的分镜并更新
    shot_found = False
    for shot in project.script.shots:
        if shot.id == request.shot_id:
            shot.video_url = video.video_url
            shot.selected_video_id = request.video_id
            shot_found = True
            break
    
    if not shot_found:
        raise HTTPException(status_code=404, detail="分镜不存在")
    
    # 保存项目
    storage_service.save_project(project)
    
    return {
        "message": "视频已保存",
        "shot_id": request.shot_id,
        "video_url": video.video_url
    }


@router.delete("/{video_id}")
async def delete_video(video_id: str):
    """删除视频"""
    video = storage_service.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    
    storage_service.delete_video(video_id)
    return {"message": "视频已删除"}
