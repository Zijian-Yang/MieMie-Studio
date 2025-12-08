"""
视频数据模型
"""

from typing import Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
import uuid


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class VideoTask(BaseModel):
    """视频生成任务"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""  # 阿里云任务ID
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0  # 进度百分比
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class Video(BaseModel):
    """视频"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str  # 所属项目ID
    shot_id: str  # 关联的分镜ID
    shot_number: int = 0  # 镜头序号
    
    # 输入
    first_frame_url: Optional[str] = None  # 首帧图 URL
    prompt: str = ""  # 视频生成提示词
    duration: float = 2.0  # 目标时长（秒）
    
    # 任务
    task: Optional[VideoTask] = None
    
    # 输出
    video_url: Optional[str] = None  # 生成的视频 URL
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

