"""
图片测评与数据集数据模型
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
import uuid

from pydantic import BaseModel, Field, model_validator


ImageBenchmarkTaskKind = Literal["text_to_image", "image_edit", "interactive_edit"]
ImageBenchmarkSuiteStatus = Literal["draft", "running", "completed", "failed"]
ImageBenchmarkRunStatus = Literal["pending", "running", "completed", "failed"]
ImageBenchmarkCellStatus = Literal["pending", "running", "completed", "failed", "skipped", "unsupported"]


class ImageBenchmarkDatasetImage(BaseModel):
    """数据集中的输入图片快照"""

    url: str
    name: str = ""
    mime_type: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    source_label: Optional[str] = None


class ImageBenchmarkImageSlot(BaseModel):
    """带顺序语义的输入图片槽位"""

    position: int
    image: ImageBenchmarkDatasetImage


class ImageBenchmarkDatasetItem(BaseModel):
    """数据集样例行"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    prompt: str = ""
    negative_prompt: str = ""
    sort_order: int = 0
    tags: List[str] = []
    image_slots: List[ImageBenchmarkImageSlot] = []
    bbox_list: List[List[List[int]]] = []

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_input_images(cls, value: Any):
        if not isinstance(value, dict):
            return value
        if value.get("image_slots"):
            return value
        legacy_images = value.get("input_images") or []
        if legacy_images:
            value = dict(value)
            value["image_slots"] = [
                {
                    "position": index + 1,
                    "image": image,
                }
                for index, image in enumerate(legacy_images)
                if image and image.get("url")
            ]
        return value


class ImageBenchmarkDataset(BaseModel):
    """图片测评数据集"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    name: str
    description: str = ""
    task_kind: ImageBenchmarkTaskKind
    schema_version: str = "2.0"
    max_image_slot_index: int = 0
    items: List[ImageBenchmarkDatasetItem] = []
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    @model_validator(mode="after")
    def _sync_max_image_slot_index(self):
        inferred_max = 0
        for item in self.items:
            if item.image_slots:
                inferred_max = max(inferred_max, max(slot.position for slot in item.image_slots))
        if inferred_max > self.max_image_slot_index:
            self.max_image_slot_index = inferred_max
        return self


class ImageBenchmarkOutputImage(BaseModel):
    """单个输出图片"""

    url: Optional[str] = None
    prompt_used: Optional[str] = None


class ImageBenchmarkCellResult(BaseModel):
    """单个 case × model 执行结果"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    case_id: str
    case_name: str = ""
    model_id: str
    model_name: str = ""
    status: ImageBenchmarkCellStatus = "pending"
    output_images: List[ImageBenchmarkOutputImage] = []
    error_message: Optional[str] = None
    request_ids: List[str] = []
    task_ids: List[str] = []
    validation_warnings: List[str] = []
    effective_params: Dict[str, Any] = {}
    canonical_request: Optional[Dict[str, Any]] = None
    provider_payload: Optional[Dict[str, Any]] = None
    provider_result_meta: Dict[str, Any] = {}
    attempt_count: int = 1
    auto_retry_count: int = 0
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class ImageBenchmarkSuite(BaseModel):
    """图片测评任务配置"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    name: str
    description: str = ""
    dataset_id: str
    task_kind: ImageBenchmarkTaskKind
    selected_models: List[str] = []
    baseline_params: Dict[str, Any] = {}
    model_overrides: Dict[str, Dict[str, Any]] = {}
    status: ImageBenchmarkSuiteStatus = "draft"
    latest_run_id: Optional[str] = None
    latest_run_snapshot: Optional[Dict[str, Any]] = None
    share_token: Optional[str] = None
    share_enabled: bool = False
    share_created_at: Optional[datetime] = None
    share_disabled_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class ImageBenchmarkRun(BaseModel):
    """一次实际执行的运行记录"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    suite_id: str
    project_id: str
    dataset_id: str
    task_kind: ImageBenchmarkTaskKind
    status: ImageBenchmarkRunStatus = "pending"
    dataset_snapshot: Dict[str, Any] = {}
    model_snapshots: List[Dict[str, Any]] = []
    baseline_params: Dict[str, Any] = {}
    model_overrides: Dict[str, Dict[str, Any]] = {}
    cell_results: List[ImageBenchmarkCellResult] = []
    retry_source_run_id: Optional[str] = None
    retry_targets: List[Dict[str, str]] = []
    stats: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
