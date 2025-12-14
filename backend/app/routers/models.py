"""
模型配置 API 路由

提供模型信息的查询接口，前端可以动态获取：
- 可用模型列表
- 模型参数定义
- 模型能力声明
"""

from fastapi import APIRouter, HTTPException
from typing import Optional, List
from pydantic import BaseModel

from app.models_registry import registry, ModelType

router = APIRouter()


class ModelListResponse(BaseModel):
    """模型列表响应"""
    models: dict  # model_id -> model_info


@router.get("")
async def list_all_models():
    """
    获取所有可用模型
    
    返回按类型分组的模型配置，前端可直接用于渲染参数表单
    """
    return {
        "models": registry.get_all_model_info_for_frontend()
    }


@router.get("/by-type/{model_type}")
async def list_models_by_type(model_type: str):
    """
    按类型获取模型列表
    
    Args:
        model_type: 模型类型 (llm, text_to_image, image_to_video, etc.)
    """
    try:
        mt = ModelType(model_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"无效的模型类型: {model_type}")
    
    models = registry.list_models(mt)
    return {
        "models": {
            m.id: {
                "id": m.id,
                "name": m.name,
                "description": m.description,
                "capabilities": m.capabilities.model_dump(),
                "parameters": [p.model_dump() for p in m.parameters],
                "default_values": m.get_default_values(),
            }
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
    
    return {
        "id": model.id,
        "name": model.name,
        "type": model.type.value,
        "description": model.description,
        "version": model.version,
        "capabilities": model.capabilities.model_dump(),
        "parameters": [p.model_dump() for p in model.parameters],
        "default_values": model.get_default_values(),
        "doc_url": model.doc_url,
        "deprecated": model.deprecated,
        "deprecated_message": model.deprecated_message,
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
    return {
        "types": [
            {
                "type": mt.value,
                "label": {
                    ModelType.LLM: "文本模型",
                    ModelType.TEXT_TO_IMAGE: "文生图",
                    ModelType.IMAGE_TO_IMAGE: "图生图",
                    ModelType.IMAGE_TO_VIDEO: "图生视频",
                    ModelType.TEXT_TO_VIDEO: "文生视频",
                    ModelType.TEXT_TO_AUDIO: "文生音频",
                    ModelType.AUDIO_TO_TEXT: "语音识别",
                }.get(mt, mt.value),
                "count": len(models),
            }
            for mt, models in models_by_type.items()
        ]
    }

