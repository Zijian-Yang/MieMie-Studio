"""
设置 API 路由
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from app.config import (
    config_manager, AppConfig, LLMConfig, ImageConfig, ImageEditConfig, VideoConfig, TextToVideoConfig, RefVideoConfig, OSSConfig,
    API_REGIONS, LLM_MODELS, IMAGE_MODELS, IMAGE_EDIT_MODELS, VIDEO_MODELS, TEXT_TO_VIDEO_MODELS, REF_VIDEO_MODELS,
    KEYFRAME_TO_VIDEO_MODELS, VIDEO_REPAINTING_MODELS, VIDEO_EDIT_MODELS, normalize_key_profile
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
    watermark: Optional[bool] = None  # 水印（仅 wan2.6-t2i 支持）
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


class TextToVideoConfigRequest(BaseModel):
    """文生视频配置请求（wan2.6-t2v等）"""
    model: Optional[str] = None
    size: Optional[str] = None  # 分辨率（宽*高格式，如 1920*1080）
    duration: Optional[int] = None  # 视频时长（秒）
    prompt_extend: Optional[bool] = None  # 智能改写
    shot_type: Optional[str] = None  # 镜头类型，single/multi（仅wan2.6支持）
    watermark: Optional[bool] = None  # 水印
    seed: Optional[int] = None  # 随机种子
    audio: Optional[bool] = None  # 是否自动配音


class RefVideoConfigRequest(BaseModel):
    """参考生视频配置请求（wan2.6-r2v）"""
    model: Optional[str] = None
    size: Optional[str] = None  # 分辨率（宽*高格式，如 1920*1080），默认1080P 16:9
    duration: Optional[int] = None  # 视频时长（2-10秒整数）
    shot_type: Optional[str] = None  # 镜头类型，single/multi
    watermark: Optional[bool] = None  # 水印
    seed: Optional[int] = None  # 随机种子


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
    test_api_key: Optional[str] = None
    production_api_key: Optional[str] = None
    volcengine_api_key: Optional[str] = None
    wan_key_profile: Optional[str] = None
    happyhorse_key_profile: Optional[str] = None
    kling_key_profile: Optional[str] = None
    vidu_key_profile: Optional[str] = None
    video_task_notifications_enabled: Optional[bool] = None
    image_task_notifications_enabled: Optional[bool] = None
    api_region: Optional[str] = None
    llm: Optional[LLMConfigRequest] = None
    image: Optional[ImageConfigRequest] = None
    image_edit: Optional[ImageEditConfigRequest] = None
    video: Optional[VideoConfigRequest] = None
    text_to_video: Optional[TextToVideoConfigRequest] = None  # 文生视频配置
    ref_video: Optional[RefVideoConfigRequest] = None  # 参考生视频配置
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
    test_api_key_masked: str
    is_test_api_key_set: bool
    production_api_key_masked: str
    is_production_api_key_set: bool
    volcengine_api_key_masked: str
    is_volcengine_api_key_set: bool
    wan_key_profile: str
    happyhorse_key_profile: str
    kling_key_profile: str
    vidu_key_profile: str
    video_task_notifications_enabled: bool
    image_task_notifications_enabled: bool
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
    
    # 文生视频配置
    text_to_video: Dict[str, Any]
    
    # 参考生视频配置
    ref_video: Dict[str, Any]
    
    # OSS 配置
    oss: OSSConfigResponse
    
    # 可用选项
    available_regions: Dict[str, Dict[str, str]]
    available_llm_models: Dict[str, Dict[str, Any]]
    available_image_models: Dict[str, Dict[str, Any]]
    available_image_edit_models: Dict[str, Dict[str, Any]]
    available_video_models: Dict[str, Dict[str, Any]]
    available_text_to_video_models: Dict[str, Dict[str, Any]]  # 文生视频模型
    available_ref_video_models: Dict[str, Dict[str, Any]]  # 参考生视频模型
    available_keyframe_to_video_models: Dict[str, Dict[str, Any]]  # 首尾帧生视频模型
    available_video_repainting_models: Dict[str, Dict[str, Any]]  # 视频重绘模型
    available_video_edit_models: Dict[str, Dict[str, Any]]  # 局部编辑模型


def mask_api_key(api_key: str) -> str:
    """隐藏 API Key 中间部分"""
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "*" * len(api_key)
    return api_key[:4] + "*" * (len(api_key) - 8) + api_key[-4:]


def normalize_secret_update(value: Optional[str]) -> Optional[str]:
    """规范化敏感字段更新：空白表示不修改。"""
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


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
    
    production_api_key = config.production_api_key or config.dashscope_api_key

    return ConfigResponse(
        api_key_masked=mask_api_key(production_api_key),
        is_api_key_set=bool(production_api_key),
        test_api_key_masked=mask_api_key(config.test_api_key),
        is_test_api_key_set=bool(config.test_api_key),
        production_api_key_masked=mask_api_key(production_api_key),
        is_production_api_key_set=bool(production_api_key),
        volcengine_api_key_masked=mask_api_key(config.volcengine_api_key),
        is_volcengine_api_key_set=bool(config.volcengine_api_key),
        wan_key_profile=normalize_key_profile(config.wan_key_profile),
        happyhorse_key_profile=normalize_key_profile(getattr(config, "happyhorse_key_profile", "production")),
        kling_key_profile=normalize_key_profile(config.kling_key_profile),
        vidu_key_profile=normalize_key_profile(config.vidu_key_profile),
        video_task_notifications_enabled=bool(getattr(config, "video_task_notifications_enabled", False)),
        image_task_notifications_enabled=bool(getattr(config, "image_task_notifications_enabled", False)),
        api_region=config.api_region,
        base_url=config.base_url,
        llm=config.llm.model_dump(),
        image=config.image.model_dump(),
        image_edit=config.image_edit.model_dump(),
        video=config.video.model_dump(),
        text_to_video=config.text_to_video.model_dump(),
        ref_video=config.ref_video.model_dump(),
        oss=oss_response,
        available_regions=API_REGIONS,
        available_llm_models=LLM_MODELS,
        available_image_models=IMAGE_MODELS,
        available_image_edit_models=IMAGE_EDIT_MODELS,
        available_video_models=VIDEO_MODELS,
        available_text_to_video_models=TEXT_TO_VIDEO_MODELS,
        available_ref_video_models=REF_VIDEO_MODELS,
        available_keyframe_to_video_models=KEYFRAME_TO_VIDEO_MODELS,
        available_video_repainting_models=VIDEO_REPAINTING_MODELS,
        available_video_edit_models=VIDEO_EDIT_MODELS
    )


@router.put("")
async def update_settings(request: ConfigUpdateRequest):
    """更新设置"""
    update_data = {}

    api_key = normalize_secret_update(request.api_key)
    if api_key is not None:
        update_data["dashscope_api_key"] = api_key
        update_data["production_api_key"] = api_key

    test_api_key = normalize_secret_update(request.test_api_key)
    if test_api_key is not None:
        update_data["test_api_key"] = test_api_key

    production_api_key = normalize_secret_update(request.production_api_key)
    if production_api_key is not None:
        update_data["production_api_key"] = production_api_key
        update_data["dashscope_api_key"] = production_api_key

    volcengine_api_key = normalize_secret_update(request.volcengine_api_key)
    if volcengine_api_key is not None:
        update_data["volcengine_api_key"] = volcengine_api_key

    if request.wan_key_profile is not None:
        update_data["wan_key_profile"] = normalize_key_profile(request.wan_key_profile)

    if request.happyhorse_key_profile is not None:
        update_data["happyhorse_key_profile"] = normalize_key_profile(request.happyhorse_key_profile)

    if request.kling_key_profile is not None:
        update_data["kling_key_profile"] = normalize_key_profile(request.kling_key_profile)

    if request.vidu_key_profile is not None:
        update_data["vidu_key_profile"] = normalize_key_profile(request.vidu_key_profile)

    if request.video_task_notifications_enabled is not None:
        update_data["video_task_notifications_enabled"] = bool(request.video_task_notifications_enabled)
    if request.image_task_notifications_enabled is not None:
        update_data["image_task_notifications_enabled"] = bool(request.image_task_notifications_enabled)
    
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
    
    if request.text_to_video is not None:
        text_to_video_update = {k: v for k, v in request.text_to_video.model_dump().items() if v is not None}
        if text_to_video_update:
            if "model" in text_to_video_update and text_to_video_update["model"] not in TEXT_TO_VIDEO_MODELS:
                raise HTTPException(status_code=400, detail=f"无效的文生视频模型: {text_to_video_update['model']}")
            update_data["text_to_video"] = text_to_video_update
    
    if request.ref_video is not None:
        ref_video_update = {k: v for k, v in request.ref_video.model_dump().items() if v is not None}
        if ref_video_update:
            if "model" in ref_video_update and ref_video_update["model"] not in REF_VIDEO_MODELS:
                raise HTTPException(status_code=400, detail=f"无效的参考生视频模型: {ref_video_update['model']}")
            update_data["ref_video"] = ref_video_update
    
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
    config_manager.update(dashscope_api_key="", production_api_key="")
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


@router.get("/models/text-to-video")
async def get_text_to_video_models():
    """获取可用的文生视频模型列表"""
    return {"models": TEXT_TO_VIDEO_MODELS}


@router.get("/models/ref-video")
async def get_ref_video_models():
    """获取可用的参考生视频模型列表"""
    return {"models": REF_VIDEO_MODELS}


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
