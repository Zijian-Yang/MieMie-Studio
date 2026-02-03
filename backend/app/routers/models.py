"""
模型配置 API 路由

统一的模型信息查询接口，前端可以动态获取：
- 可用模型列表（全部/按类型）
- 模型参数定义和默认值
- 模型能力声明
- 尺寸约束和预设尺寸

这是模型配置的唯一数据源，前端不应硬编码任何模型信息。
"""

from fastapi import APIRouter, HTTPException
from typing import Optional, List
from pydantic import BaseModel

from app.models_registry import registry, ModelType

router = APIRouter()


class ModelListResponse(BaseModel):
    """模型列表响应"""
    models: dict  # model_id -> model_info


def _format_model_for_frontend(model) -> dict:
    """格式化模型信息用于前端"""
    return {
        "id": model.id,
        "name": model.name,
        "type": model.type.value,
        "description": model.description,
        "version": model.version,
        "capabilities": model.capabilities.model_dump(),
        "parameters": [p.model_dump() for p in model.parameters],
        "default_values": model.get_default_values(),
        "size_constraints": model.size_constraints.model_dump() if model.size_constraints else None,
        "common_sizes": model.get_common_sizes_for_frontend(),
        "doc_url": model.doc_url,
        "deprecated": model.deprecated,
        "deprecated_message": model.deprecated_message,
        "recommended": model.recommended,
    }


@router.get("")
async def list_all_models():
    """
    获取所有可用模型
    
    返回所有模型的完整配置，前端可直接用于渲染参数表单
    """
    return {
        "models": registry.get_all_model_info_for_frontend()
    }


@router.get("/image")
async def list_image_models():
    """
    获取所有图像生成模型（文生图 + 图生图）
    
    用于图片工作室、角色生成、场景生成等场景
    """
    models = registry.get_image_models()
    return {
        "models": {
            m.id: _format_model_for_frontend(m)
            for m in models
        }
    }


@router.get("/video")
async def list_video_models():
    """
    获取所有视频生成模型（文生视频、图生视频、参考生视频）
    
    用于视频工作室、分镜视频生成等场景
    """
    models = registry.get_video_models()
    return {
        "models": {
            m.id: _format_model_for_frontend(m)
            for m in models
        }
    }


@router.get("/by-type/{model_type}")
async def list_models_by_type(model_type: str):
    """
    按类型获取模型列表
    
    Args:
        model_type: 模型类型 (llm, text_to_image, image_to_image, image_to_video, 
                    text_to_video, reference_to_video, etc.)
    """
    try:
        mt = ModelType(model_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"无效的模型类型: {model_type}")
    
    models = registry.list_models(mt)
    return {
        "models": {
            m.id: _format_model_for_frontend(m)
            for m in models
        }
    }


@router.get("/{model_id}")
async def get_model_info(model_id: str):
    """
    获取单个模型的详细信息
    """
    model = registry.get_model_info(model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"模型不存在: {model_id}")
    
    return _format_model_for_frontend(model)


@router.get("/{model_id}/sizes")
async def get_model_sizes(model_id: str):
    """
    获取模型支持的尺寸选项
    
    返回预设尺寸列表和尺寸约束，用于前端尺寸选择器
    """
    model = registry.get_model_info(model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"模型不存在: {model_id}")
    
    return {
        "model_id": model_id,
        "common_sizes": model.get_common_sizes_for_frontend(),
        "size_constraints": model.size_constraints.model_dump() if model.size_constraints else None,
    }


@router.post("/{model_id}/validate-size")
async def validate_model_size(model_id: str, width: int, height: int):
    """
    验证尺寸是否符合模型约束
    """
    model = registry.get_model_info(model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"模型不存在: {model_id}")
    
    valid, message = model.validate_size(width, height)
    return {
        "valid": valid,
        "message": message,
        "width": width,
        "height": height,
        "total_pixels": width * height,
    }


@router.get("/{model_id}/parameters")
async def get_model_parameters(model_id: str, group: Optional[str] = None):
    """
    获取模型参数定义
    
    Args:
        model_id: 模型ID
        group: 可选的参数分组过滤 (basic, generation, audio, advanced)
    """
    model = registry.get_model_info(model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"模型不存在: {model_id}")
    
    if group:
        params = model.get_parameters_by_group(group)
    else:
        params = model.parameters
    
    return {
        "model_id": model_id,
        "parameters": [p.model_dump() for p in params]
    }


@router.post("/{model_id}/validate")
async def validate_parameters(model_id: str, params: dict):
    """
    验证参数是否合法
    """
    model = registry.get_model_info(model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"模型不存在: {model_id}")
    
    valid, errors = model.validate_params(params)
    return {
        "valid": valid,
        "errors": errors
    }


@router.get("/types/available")
async def list_model_types():
    """
    获取所有可用的模型类型
    """
    models_by_type = registry.list_models_by_type()
    
    type_labels = {
        ModelType.LLM: "文本模型",
        ModelType.TEXT_TO_IMAGE: "文生图",
        ModelType.IMAGE_TO_IMAGE: "图生图",
        ModelType.IMAGE_TO_VIDEO: "图生视频",
        ModelType.TEXT_TO_VIDEO: "文生视频",
        ModelType.REFERENCE_TO_VIDEO: "参考生视频",
        ModelType.KEYFRAME_TO_VIDEO: "关键帧生视频",
        ModelType.TEXT_TO_AUDIO: "文生音频",
        ModelType.AUDIO_TO_TEXT: "语音识别",
    }
    
    return {
        "types": [
            {
                "type": mt.value,
                "label": type_labels.get(mt, mt.value),
                "count": len(models),
            }
            for mt, models in models_by_type.items()
        ]
    }

