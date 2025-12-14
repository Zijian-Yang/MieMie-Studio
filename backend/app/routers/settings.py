"""
设置 API 路由
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from app.config import (
    config_manager, AppConfig, LLMConfig, ImageConfig, ImageEditConfig, VideoConfig, OSSConfig,
    API_REGIONS, LLM_MODELS, IMAGE_MODELS, IMAGE_EDIT_MODELS, VIDEO_MODELS
)
from app.services.oss import oss_service

router = APIRouter()


class ApiKeyRequest(BaseModel):
    """API Key 请求"""
    api_key: str


class ApiKeyResponse(BaseModel):
    """API Key 响应"""
    api_key_masked: str
    is_set: bool


class LLMConfigRequest(BaseModel):
    """LLM 配置请求"""
    model: Optional[str] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    temperature: Optional[float] = None
    enable_thinking: Optional[bool] = None
    thinking_budget: Optional[int] = None
    result_format: Optional[str] = None
    enable_search: Optional[bool] = None


class ImageConfigRequest(BaseModel):
    """文生图配置请求"""
    model: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    prompt_extend: Optional[bool] = None
    seed: Optional[int] = None


class ImageEditConfigRequest(BaseModel):
    """图像编辑配置请求"""
    model: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    prompt_extend: Optional[bool] = None
    watermark: Optional[bool] = None  # 水印（仅 qwen-image-edit-plus 支持）
    seed: Optional[int] = None


class VideoConfigRequest(BaseModel):
    """图生视频配置请求"""
    model: Optional[str] = None
    resolution: Optional[str] = None  # 分辨率（wan2.5用480P/720P/1080P）
    duration: Optional[int] = None  # 视频时长（秒）
    prompt_extend: Optional[bool] = None  # 智能改写
    watermark: Optional[bool] = None  # 水印
    seed: Optional[int] = None  # 随机种子
    audio: Optional[bool] = None  # 自动生成音频（仅wan2.5支持）


class OSSConfigRequest(BaseModel):
    """OSS 配置请求"""
    enabled: Optional[bool] = None
    access_key_id: Optional[str] = None
    access_key_secret: Optional[str] = None
    bucket_name: Optional[str] = None
    endpoint: Optional[str] = None
    prefix: Optional[str] = None


class ConfigUpdateRequest(BaseModel):
    """配置更新请求"""
    api_key: Optional[str] = None
    api_region: Optional[str] = None
    llm: Optional[LLMConfigRequest] = None
    image: Optional[ImageConfigRequest] = None
    image_edit: Optional[ImageEditConfigRequest] = None
    video: Optional[VideoConfigRequest] = None
    oss: Optional[OSSConfigRequest] = None


class OSSConfigResponse(BaseModel):
    """OSS 配置响应（隐藏敏感信息）"""
    enabled: bool
    access_key_id_masked: str
    access_key_secret_masked: str
    is_configured: bool
    bucket_name: str
    endpoint: str
    prefix: str


class ConfigResponse(BaseModel):
    """完整配置响应"""
    api_key_masked: str
    is_api_key_set: bool
    api_region: str
    base_url: str
    
    # LLM 配置
    llm: Dict[str, Any]
    
    # 文生图配置
    image: Dict[str, Any]
    
    # 图像编辑配置
    image_edit: Dict[str, Any]
    
    # 图生视频配置
    video: Dict[str, Any]
    
    # OSS 配置
    oss: OSSConfigResponse
    
    # 可用选项
    available_regions: Dict[str, Dict[str, str]]
    available_llm_models: Dict[str, Dict[str, Any]]
    available_image_models: Dict[str, Dict[str, Any]]
    available_image_edit_models: Dict[str, Dict[str, Any]]
    available_video_models: Dict[str, Dict[str, Any]]


def mask_api_key(api_key: str) -> str:
    """隐藏 API Key 中间部分"""
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "*" * len(api_key)
    return api_key[:4] + "*" * (len(api_key) - 8) + api_key[-4:]


@router.get("", response_model=ConfigResponse)
async def get_settings():
    """获取当前设置"""
    config = config_manager.load()
    
    # 构建 OSS 配置响应
    oss_config = config.oss
    oss_is_configured = bool(
        oss_config.access_key_id and 
        oss_config.access_key_secret and 
        oss_config.bucket_name and 
        oss_config.endpoint
    )
    
    oss_response = OSSConfigResponse(
        enabled=oss_config.enabled,
        access_key_id_masked=mask_api_key(oss_config.access_key_id),
        access_key_secret_masked=mask_api_key(oss_config.access_key_secret),
        is_configured=oss_is_configured,
        bucket_name=oss_config.bucket_name,
        endpoint=oss_config.endpoint,
        prefix=oss_config.prefix
    )
    
    return ConfigResponse(
        api_key_masked=mask_api_key(config.dashscope_api_key),
        is_api_key_set=bool(config.dashscope_api_key),
        api_region=config.api_region,
        base_url=config.base_url,
        llm=config.llm.model_dump(),
        image=config.image.model_dump(),
        image_edit=config.image_edit.model_dump(),
        video=config.video.model_dump(),
        oss=oss_response,
        available_regions=API_REGIONS,
        available_llm_models=LLM_MODELS,
        available_image_models=IMAGE_MODELS,
        available_image_edit_models=IMAGE_EDIT_MODELS,
        available_video_models=VIDEO_MODELS
    )


@router.put("")
async def update_settings(request: ConfigUpdateRequest):
    """更新设置"""
    update_data = {}
    
    if request.api_key is not None:
        update_data["dashscope_api_key"] = request.api_key
    
    if request.api_region is not None:
        if request.api_region not in API_REGIONS:
            raise HTTPException(status_code=400, detail=f"无效的地域: {request.api_region}")
        update_data["api_region"] = request.api_region
    
    if request.llm is not None:
        llm_update = {k: v for k, v in request.llm.model_dump().items() if v is not None}
        if llm_update:
            # 验证模型
            if "model" in llm_update and llm_update["model"] not in LLM_MODELS:
                raise HTTPException(status_code=400, detail=f"无效的 LLM 模型: {llm_update['model']}")
            
            # 验证 thinking 相关参数
            model = llm_update.get("model") or config_manager.load().llm.model
            model_info = LLM_MODELS.get(model, {})
            
            if llm_update.get("enable_thinking") and not model_info.get("supports_thinking"):
                raise HTTPException(status_code=400, detail=f"模型 {model} 不支持深度思考功能")
            
            update_data["llm"] = llm_update
    
    if request.image is not None:
        image_update = {k: v for k, v in request.image.model_dump().items() if v is not None}
        if image_update:
            if "model" in image_update and image_update["model"] not in IMAGE_MODELS:
                raise HTTPException(status_code=400, detail=f"无效的文生图模型: {image_update['model']}")
            update_data["image"] = image_update
    
    if request.image_edit is not None:
        image_edit_update = {k: v for k, v in request.image_edit.model_dump().items() if v is not None}
        if image_edit_update:
            if "model" in image_edit_update and image_edit_update["model"] not in IMAGE_EDIT_MODELS:
                raise HTTPException(status_code=400, detail=f"无效的图像编辑模型: {image_edit_update['model']}")
            update_data["image_edit"] = image_edit_update
    
    if request.video is not None:
        video_update = {k: v for k, v in request.video.model_dump().items() if v is not None}
        if video_update:
            if "model" in video_update and video_update["model"] not in VIDEO_MODELS:
                raise HTTPException(status_code=400, detail=f"无效的视频模型: {video_update['model']}")
            update_data["video"] = video_update
    
    if request.oss is not None:
        oss_update = {k: v for k, v in request.oss.model_dump().items() if v is not None}
        if oss_update:
            # 验证 endpoint 格式
            if "endpoint" in oss_update:
                endpoint = oss_update["endpoint"]
                if endpoint and not endpoint.startswith("https://"):
                    raise HTTPException(status_code=400, detail="OSS Endpoint 必须以 https:// 开头")
            update_data["oss"] = oss_update
    
    if update_data:
        config_manager.update(**update_data)
        # 如果更新了 OSS 配置，重新初始化 OSS 服务
        if "oss" in update_data:
            oss_service.reinitialize()
    
    return {"message": "设置已更新"}


@router.post("/api-key")
async def set_api_key(request: ApiKeyRequest):
    """设置 API Key"""
    if not request.api_key:
        raise HTTPException(status_code=400, detail="API Key 不能为空")
    
    config_manager.set_api_key(request.api_key)
    return {"message": "API Key 已保存"}


@router.get("/api-key", response_model=ApiKeyResponse)
async def get_api_key():
    """获取 API Key 状态"""
    api_key = config_manager.get_api_key()
    return ApiKeyResponse(
        api_key_masked=mask_api_key(api_key),
        is_set=bool(api_key)
    )


@router.delete("/api-key")
async def delete_api_key():
    """删除 API Key"""
    config_manager.set_api_key("")
    return {"message": "API Key 已删除"}


@router.get("/models/llm")
async def get_llm_models():
    """获取可用的 LLM 模型列表"""
    return {"models": LLM_MODELS}


@router.get("/models/image")
async def get_image_models():
    """获取可用的文生图模型列表"""
    return {"models": IMAGE_MODELS}


@router.get("/models/image-edit")
async def get_image_edit_models():
    """获取可用的图像编辑模型列表"""
    return {"models": IMAGE_EDIT_MODELS}


@router.get("/models/video")
async def get_video_models():
    """获取可用的图生视频模型列表"""
    return {"models": VIDEO_MODELS}


@router.get("/regions")
async def get_regions():
    """获取可用的 API 地域列表"""
    return {"regions": API_REGIONS}


@router.post("/oss/test")
async def test_oss_connection():
    """测试 OSS 连接"""
    success, message = oss_service.test_connection()
    return {
        "success": success,
        "message": message
    }
