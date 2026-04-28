"""
视频测评数据模型
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
import uuid

from pydantic import BaseModel, Field


VideoBenchmarkTaskKind = Literal["image_to_video"]
VideoBenchmarkSuiteStatus = Literal["draft", "running", "completed", "failed"]
VideoBenchmarkRunStatus = Literal["pending", "running", "completed", "failed"]
VideoBenchmarkCellStatus = Literal["pending", "running", "completed", "failed", "skipped", "unsupported"]


class VideoBenchmarkMediaAsset(BaseModel):
    """视频测评输入素材快照"""

    url: str
    name: str = ""
    mime_type: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[float] = None
    source_label: Optional[str] = None


class VideoBenchmarkDatasetItem(BaseModel):
    """首帧生视频测评样例行"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    prompt: str = ""
    negative_prompt: str = ""
    sort_order: int = 0
    tags: List[str] = []
    first_frame: Optional[VideoBenchmarkMediaAsset] = None
    audio: Optional[VideoBenchmarkMediaAsset] = None
    duration: Optional[int] = None


class VideoBenchmarkDataset(BaseModel):
    """视频测评数据集"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    name: str
    description: str = ""
    task_kind: VideoBenchmarkTaskKind = "image_to_video"
    schema_version: str = "1.0"
    items: List[VideoBenchmarkDatasetItem] = []
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class VideoBenchmarkOutputVideo(BaseModel):
    """单个输出视频"""

    url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    prompt_used: Optional[str] = None


class VideoBenchmarkCellResult(BaseModel):
    """单个 case × model 视频测评结果"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    case_id: str
    case_name: str = ""
    model_id: str
    model_name: str = ""
    status: VideoBenchmarkCellStatus = "pending"
    output_videos: List[VideoBenchmarkOutputVideo] = []
    error_message: Optional[str] = None
    request_ids: List[str] = []
    task_ids: List[str] = []
    validation_warnings: List[str] = []
    effective_params: Dict[str, Any] = {}
    canonical_request: Optional[Dict[str, Any]] = None
    provider_payload: Optional[Dict[str, Any]] = None
    provider_result_meta: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class VideoBenchmarkSuite(BaseModel):
    """视频测评任务配置"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    name: str
    description: str = ""
    dataset_id: str
    task_kind: VideoBenchmarkTaskKind = "image_to_video"
    selected_models: List[str] = []
    baseline_params: Dict[str, Any] = {}
    model_overrides: Dict[str, Dict[str, Any]] = {}
    status: VideoBenchmarkSuiteStatus = "draft"
    latest_run_id: Optional[str] = None
    latest_run_snapshot: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class VideoBenchmarkRun(BaseModel):
    """一次视频测评运行记录"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    suite_id: str
    project_id: str
    dataset_id: str
    task_kind: VideoBenchmarkTaskKind = "image_to_video"
    status: VideoBenchmarkRunStatus = "pending"
    dataset_snapshot: Dict[str, Any] = {}
    model_snapshots: List[Dict[str, Any]] = []
    baseline_params: Dict[str, Any] = {}
    model_overrides: Dict[str, Dict[str, Any]] = {}
    cell_results: List[VideoBenchmarkCellResult] = []
    retry_source_run_id: Optional[str] = None
    retry_targets: List[Dict[str, str]] = []
    stats: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
