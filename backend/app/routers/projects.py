"""
项目管理 API 路由
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime

from app.models.project import Project, Script, ProjectLLMConfig
from app.services.storage import storage_service

router = APIRouter()


class ProjectCreateRequest(BaseModel):
    """创建项目请求"""
    name: str
    description: str = ""


class ProjectUpdateRequest(BaseModel):
    """更新项目请求"""
    name: Optional[str] = None
    description: Optional[str] = None


class ProjectListResponse(BaseModel):
    """项目列表响应"""
    projects: List[Project]
    total: int


@router.post("", response_model=Project)
async def create_project(request: ProjectCreateRequest):
    """创建新项目"""
    project = Project(
        name=request.name,
        description=request.description
    )
    storage_service.save_project(project)
    return project


@router.get("", response_model=ProjectListResponse)
async def list_projects():
    """获取所有项目"""
    projects = storage_service.list_projects()
    return ProjectListResponse(projects=projects, total=len(projects))


@router.get("/{project_id}", response_model=Project)
async def get_project(project_id: str):
    """获取项目详情"""
    project = storage_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


@router.put("/{project_id}", response_model=Project)
async def update_project(project_id: str, request: ProjectUpdateRequest):
    """更新项目信息"""
    project = storage_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    if request.name is not None:
        project.name = request.name
    if request.description is not None:
        project.description = request.description
    
    storage_service.save_project(project)
    return project


@router.delete("/{project_id}")
async def delete_project(project_id: str):
    """删除项目"""
    project = storage_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 删除项目相关的所有数据
    for char_id in project.character_ids:
        storage_service.delete_character(char_id)
    
    for scene_id in project.scene_ids:
        storage_service.delete_scene(scene_id)
    
    for prop_id in project.prop_ids:
        storage_service.delete_prop(prop_id)
    
    # 删除首帧和视频
    frames = storage_service.get_frames_by_project(project_id)
    for frame in frames:
        storage_service.delete_frame(frame.id)
    
    videos = storage_service.get_videos_by_project(project_id)
    for video in videos:
        storage_service.delete_video(video.id)
    
    # 最后删除项目
    storage_service.delete_project(project_id)
    
    return {"message": "项目已删除"}


@router.get("/{project_id}/summary")
async def get_project_summary(project_id: str):
    """获取项目摘要信息"""
    project = storage_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 统计各项数据
    shots_count = len(project.script.shots) if project.script else 0
    characters_count = len(project.character_ids)
    scenes_count = len(project.scene_ids)
    props_count = len(project.prop_ids)
    
    frames = storage_service.get_frames_by_project(project_id)
    frames_count = sum(1 for f in frames if f.selected_url)
    
    videos = storage_service.get_videos_by_project(project_id)
    videos_count = sum(1 for v in videos if v.video_url)
    
    return {
        "project_id": project_id,
        "name": project.name,
        "shots_count": shots_count,
        "characters_count": characters_count,
        "scenes_count": scenes_count,
        "props_count": props_count,
        "frames_generated": frames_count,
        "videos_generated": videos_count,
        "created_at": project.created_at,
        "updated_at": project.updated_at
    }


# ============ 项目级 LLM 配置 API ============

class ProjectLLMConfigUpdateRequest(BaseModel):
    """项目 LLM 配置更新请求"""
    model: str  # 要配置的模型名称
    config: ProjectLLMConfig


@router.get("/{project_id}/llm-configs")
async def get_project_llm_configs(project_id: str):
    """获取项目的所有 LLM 配置"""
    project = storage_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    return {"llm_configs": project.llm_configs}


@router.get("/{project_id}/llm-configs/{model}")
async def get_project_llm_config(project_id: str, model: str):
    """获取项目针对特定模型的 LLM 配置"""
    project = storage_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    config = project.llm_configs.get(model)
    if not config:
        # 返回空配置，表示使用全局默认
        config = ProjectLLMConfig()
    
    return {"model": model, "config": config}


@router.put("/{project_id}/llm-configs/{model}")
async def update_project_llm_config(project_id: str, model: str, config: ProjectLLMConfig):
    """更新项目针对特定模型的 LLM 配置"""
    project = storage_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 更新配置
    project.llm_configs[model] = config
    project.updated_at = datetime.now()
    storage_service.save_project(project)
    
    return {"model": model, "config": config}


@router.delete("/{project_id}/llm-configs/{model}")
async def delete_project_llm_config(project_id: str, model: str):
    """删除项目针对特定模型的 LLM 配置（恢复使用全局默认）"""
    project = storage_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    if model in project.llm_configs:
        del project.llm_configs[model]
        project.updated_at = datetime.now()
        storage_service.save_project(project)
    
    return {"message": f"已删除模型 {model} 的项目配置"}
