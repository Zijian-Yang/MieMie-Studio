"""
配置管理模块
支持从 JSON 文件读写配置，包括 API Key 等敏感信息
"""

import json
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel


# API 地域配置
API_REGIONS = {
    "beijing": {
        "name": "北京",
        "base_url": "https://dashscope.aliyuncs.com/api/v1"
    },
    "singapore": {
        "name": "新加坡",
        "base_url": "https://dashscope-intl.aliyuncs.com/api/v1"
    }
}

# 文本模型配置
# 参考文档：
# - JSON Mode: https://help.aliyun.com/zh/model-studio/json-mode
# - 深度思考: https://help.aliyun.com/zh/model-studio/deep-thinking
# - 联网搜索: https://help.aliyun.com/zh/model-studio/web-search
LLM_MODELS = {
    "qwen3-max": {
        "name": "Qwen3-Max",
        "max_output_tokens": 65536,
        "supports_thinking": False,  # 仅非思考模式
        "supports_search": True,
        "supports_json_mode": True  # 非思考模式下支持
    },
    "qwen-plus-latest": {
        "name": "Qwen-Plus-Latest",
        "max_output_tokens": 32768,
        "supports_thinking": True,  # 支持思考和非思考模式
        "supports_search": True,
        "supports_json_mode": True  # 非思考模式下支持
    }
}

# 文生图模型配置
# wan2.5-t2i-preview：总像素在[768*768, 1440*1440]之间，宽高比[1:4, 4:1]
# wan2.6-t2i：总像素在[768*768, 1440*1440]之间，宽高比[1:4, 4:1]，仅支持同步HTTP调用
# wan2.6-image：支持参考图生图和图文混合输出，HTTP异步调用
# 参考: https://help.aliyun.com/zh/model-studio/text-to-image-v2-api-reference
IMAGE_MODELS = {
    "wan2.6-image": {
        "name": "图生图 wan2.6-image",
        "description": "最强模型，支持参考图生图、图文混合，HTTP异步调用",
        "min_pixels": 768 * 768,  # 最小总像素 [768*768, 1280*1280]
        "max_pixels": 1280 * 1280,  # 最大总像素
        "min_ratio": 0.25,  # 最小宽高比 1:4
        "max_ratio": 4.0,  # 最大宽高比 4:1
        "use_http": True,  # 使用 HTTP 异步调用
        "is_async": True,  # 异步调用，需要轮询
        "max_n": 4,  # enable_interleave=false 时最多生成 4 张，enable_interleave=true 时固定为 1
        "default_n": 4,  # 默认生成数量（enable_interleave=false 时）
        "supports_prompt_extend": True,  # 仅在 enable_interleave=false 时生效
        "supports_watermark": True,
        "supports_seed": True,
        "supports_negative_prompt": True,
        "supports_reference_images": True,  # 支持参考图
        "supports_interleave": True,  # 支持图文混合输出模式
        "max_reference_images": 3,  # enable_interleave=false 时最多3张参考图
        "max_reference_images_interleave": 1,  # enable_interleave=true 时最多1张参考图
        "min_reference_images": 0,  # 最少参考图数量（纯文生图时可以为0）
        "supports_max_images": True,  # enable_interleave=true 时可设置最大生成图数
        "max_images_range": [1, 5],  # max_images 参数范围
        "default_max_images": 5,  # max_images 默认值
        "common_sizes": [
            {"width": 1280, "height": 1280, "label": "1:1 方形 (默认)"},
            {"width": 1024, "height": 1024, "label": "1:1 方形 (小)"},
            {"width": 1280, "height": 720, "label": "16:9 横屏"},
            {"width": 720, "height": 1280, "label": "9:16 竖屏"},
            {"width": 1280, "height": 960, "label": "4:3 横屏"},
            {"width": 960, "height": 1280, "label": "3:4 竖屏"},
            {"width": 800, "height": 1200, "label": "2:3 竖屏"},
            {"width": 1200, "height": 800, "label": "3:2 横屏"},
            {"width": 1344, "height": 576, "label": "21:9 超宽横屏"},
        ],
        # 图像尺寸限制
        "image_min_dimension": 384,  # 参考图最小边长
        "image_max_dimension": 5000,  # 参考图最大边长
        "image_max_size_mb": 10,  # 参考图最大文件大小
        "supported_formats": ["JPEG", "JPG", "PNG", "BMP", "WEBP"],  # 支持的图片格式（PNG不支持透明通道）
    },
    "wan2.6-t2i": {
        "name": "文生图 wan2.6-t2i",
        "description": "HTTP同步调用，快速生成高质量图像",
        "min_pixels": 768 * 768,  # 最小总像素
        "max_pixels": 1440 * 1440,  # 最大总像素
        "min_ratio": 0.25,  # 最小宽高比 1:4
        "max_ratio": 4.0,  # 最大宽高比 4:1
        "use_http": True,  # 使用 HTTP 同步调用（不是 SDK）
        "max_n": 4,  # 最多生成 4 张图片
        "supports_prompt_extend": True,
        "supports_watermark": True,
        "supports_seed": True,
        "supports_negative_prompt": True,
        "common_sizes": [
            {"width": 1280, "height": 1280, "label": "1:1 方形 (默认)"},
            {"width": 1024, "height": 1024, "label": "1:1 方形 (小)"},
            {"width": 1280, "height": 720, "label": "16:9 横屏"},
            {"width": 720, "height": 1280, "label": "9:16 竖屏"},
            {"width": 1280, "height": 960, "label": "4:3 横屏"},
            {"width": 960, "height": 1280, "label": "3:4 竖屏"},
            {"width": 800, "height": 1200, "label": "2:3 竖屏"},
            {"width": 1200, "height": 800, "label": "3:2 横屏"},
            {"width": 1344, "height": 576, "label": "21:9 超宽横屏"},
        ]
    },
    "wan2.5-t2i-preview": {
        "name": "文生图 wan2.5-t2i-preview",
        "description": "SDK异步调用，在总像素面积与宽高比约束内自由选尺寸",
        "min_pixels": 768 * 768,  # 最小总像素
        "max_pixels": 1440 * 1440,  # 最大总像素
        "min_ratio": 0.25,  # 最小宽高比 1:4
        "max_ratio": 4.0,  # 最大宽高比 4:1
        "use_http": False,  # 使用 SDK 异步调用
        "max_n": 4,
        "supports_prompt_extend": True,
        "supports_watermark": True,  # wan2.5 支持水印参数
        "supports_seed": True,
        "supports_negative_prompt": True,
        "common_sizes": [
            {"width": 1024, "height": 1024, "label": "1:1 方形"},
            {"width": 1280, "height": 720, "label": "16:9 横屏"},
            {"width": 720, "height": 1280, "label": "9:16 竖屏"},
            {"width": 1024, "height": 768, "label": "4:3 横屏"},
            {"width": 768, "height": 1024, "label": "3:4 竖屏"},
            {"width": 1440, "height": 810, "label": "16:9 高清横屏"},
            {"width": 810, "height": 1440, "label": "9:16 高清竖屏"},
        ]
    }
}

# 图像编辑模型配置 (图生图)
# 参考: https://www.alibabacloud.com/help/zh/model-studio/wan2-5-image-edit-api-reference
# 参考: https://www.alibabacloud.com/help/zh/model-studio/qwen-image-edit-api
IMAGE_EDIT_MODELS = {
    "wan2.5-i2i-preview": {
        "name": "图生图 wan2.5-i2i-preview",
        "description": "支持风格迁移、局部编辑等图像编辑功能",
        "min_pixels": 768 * 768,  # 最小总像素
        "max_pixels": 1440 * 1440,  # 最大总像素
        "min_ratio": 0.25,  # 最小宽高比 1:4
        "max_ratio": 4.0,  # 最大宽高比 4:1
        "common_sizes": [
            {"width": 1024, "height": 1024, "label": "1:1 方形"},
            {"width": 1280, "height": 720, "label": "16:9 横屏"},
            {"width": 720, "height": 1280, "label": "9:16 竖屏"},
            {"width": 1024, "height": 768, "label": "4:3 横屏"},
            {"width": 768, "height": 1024, "label": "3:4 竖屏"},
        ],
        "supports_prompt_extend": True,
        "supports_seed": True,
    },
    "qwen-image-edit-plus": {
        "name": "图生图 qwen-image-edit-plus",
        "description": "支持单图编辑和多图融合，可修改文字、增删物体、改变动作、风格迁移等",
        "max_images": 3,  # 最多输入3张图片
        "max_output": 6,  # 最多输出6张图片
        "min_size": 512,  # 最小尺寸
        "max_size": 2048,  # 最大尺寸
        "common_sizes": [
            {"value": "", "label": "默认（保持原图比例）"},
            {"value": "1024*1024", "label": "1024×1024 (1:1)"},
            {"value": "1280*720", "label": "1280×720 (16:9 横屏)"},
            {"value": "720*1280", "label": "720×1280 (9:16 竖屏)"},
            {"value": "1024*768", "label": "1024×768 (4:3 横屏)"},
            {"value": "768*1024", "label": "768×1024 (3:4 竖屏)"},
            {"value": "1920*1080", "label": "1920×1080 (全高清横屏)"},
            {"value": "1080*1920", "label": "1080×1920 (全高清竖屏)"},
            {"value": "2048*2048", "label": "2048×2048 (最大方形)"},
        ],
        "supports_prompt_extend": True,
        "supports_watermark": True,
        "supports_seed": True,
        "size_only_when_n_is_1": True,  # size 参数仅当 n=1 时可用
    }
}

# 视频生视频模型配置（参考视频生成视频）
# 参考: https://help.aliyun.com/zh/model-studio/reference-to-video-api
REF_VIDEO_MODELS = {
    "wan2.6-r2v": {
        "name": "视频生视频 wan2.6-r2v",
        "description": "参考输入视频的角色形象和音色，生成保持角色一致性的新视频，支持多镜头叙事",
        # 720P档位的所有分辨率
        "resolutions_720p": [
            {"value": "1280*720", "label": "1280×720 (16:9 横屏)"},
            {"value": "720*1280", "label": "720×1280 (9:16 竖屏)"},
            {"value": "960*960", "label": "960×960 (1:1 方形)"},
            {"value": "1088*832", "label": "1088×832 (4:3 横屏)"},
            {"value": "832*1088", "label": "832×1088 (3:4 竖屏)"},
        ],
        # 1080P档位的所有分辨率
        "resolutions_1080p": [
            {"value": "1920*1080", "label": "1920×1080 (16:9 横屏)"},
            {"value": "1080*1920", "label": "1080×1920 (9:16 竖屏)"},
            {"value": "1440*1440", "label": "1440×1440 (1:1 方形)"},
            {"value": "1632*1248", "label": "1632×1248 (4:3 横屏)"},
            {"value": "1248*1632", "label": "1248×1632 (3:4 竖屏)"},
        ],
        "default_size": "1920*1080",  # 官方默认值
        "durations": [5, 10],  # 支持的时长
        "default_duration": 5,  # 默认时长
        "supports_shot_type": True,  # 支持镜头类型 (single/multi)
        "default_shot_type": "single",
        "supports_watermark": True,
        "supports_seed": True,
        "supports_negative_prompt": True,
        "supports_audio": True,  # 默认自动配音
        "default_audio": True,
        "max_reference_videos": 3,  # 最多3个参考视频
        "reference_video_duration": "2-30s",  # 参考视频时长要求
        "reference_video_max_size": "100MB",  # 单个视频最大100MB
    }
}

# 图生视频模型配置
# 参考: https://www.alibabacloud.com/help/zh/model-studio/image-to-video-api-reference
VIDEO_MODELS = {
    "wan2.6-i2v": {
        "name": "图生视频 wan2.6-i2v",
        "description": "最新模型，支持多镜头叙事、自动配音，分辨率由输入图像决定",
        "resolutions": [
            {"value": "720P", "label": "720P (高清)"},
            {"value": "1080P", "label": "1080P (全高清)"},
        ],
        "default_resolution": "1080P",  # 官方默认值
        "durations": [5, 10, 15],  # 支持的时长（比2.5多了15秒）
        "default_duration": 5,  # 默认时长
        "supports_prompt_extend": True,
        "supports_watermark": True,
        "supports_seed": True,
        "supports_negative_prompt": True,
        "supports_audio": True,  # 支持音频参数 (audio, audio_url)
        "default_audio": True,  # 默认开启自动配音
        "supports_shot_type": True,  # 支持镜头类型 (single/multi)
        "default_shot_type": "single",
        "image_param": "img_url",  # API 中图片参数名
    },
    "wan2.5-i2v-preview": {
        "name": "图生视频 wan2.5-i2v-preview",
        "description": "图生视频模型，支持音频/自动配音，分辨率由输入图像决定",
        # wan2.5 使用 resolution 参数（分辨率档位），不是具体宽高
        "resolutions": [
            {"value": "480P", "label": "480P (标清)"},
            {"value": "720P", "label": "720P (高清)"},
            {"value": "1080P", "label": "1080P (全高清)"},
        ],
        "default_resolution": "1080P",  # 官方默认值
        "durations": [5, 10],  # 支持的时长
        "default_duration": 5,  # 默认时长
        "supports_prompt_extend": True,
        "supports_watermark": True,
        "supports_seed": True,
        "supports_negative_prompt": True,
        "supports_audio": True,  # 支持音频参数 (audio, audio_url)
        "default_audio": True,  # 默认开启自动配音
        "supports_shot_type": False,
        "image_param": "img_url",  # API 中图片参数名
    },
    "wanx2.1-i2v-turbo": {
        "name": "图生视频 wanx2.1-i2v-turbo",
        "description": "快速生成模型，适合快速预览",
        # wanx2.1 使用 size 参数（具体分辨率）
        "resolutions": [
            {"value": "1280*720", "label": "1280x720 (16:9 横屏)"},
            {"value": "720*1280", "label": "720x1280 (9:16 竖屏)"},
            {"value": "960*960", "label": "960x960 (1:1 方形)"},
        ],
        "default_resolution": "1280*720",
        "durations": [3, 4, 5],  # 支持的时长
        "default_duration": 5,
        "supports_prompt_extend": True,
        "supports_watermark": True,
        "supports_seed": True,
        "supports_negative_prompt": True,
        "supports_audio": False,  # 不支持音频
        "supports_shot_type": False,
        "image_param": "image_url",  # API 中图片参数名
    }
}


class LLMConfig(BaseModel):
    """LLM 模型配置"""
    model: str = "qwen3-max"
    max_tokens: int = 8192
    top_p: float = 0.8
    temperature: float = 0.7
    enable_thinking: bool = False
    thinking_budget: int = 4096
    result_format: str = "message"  # message 或 json_object
    enable_search: bool = False


class ImageConfig(BaseModel):
    """文生图配置"""
    model: str = "wan2.6-t2i"  # 默认使用最新的 wan2.6
    width: int = 1280  # 图片宽度（wan2.6默认1280）
    height: int = 1280  # 图片高度（wan2.6默认1280）
    prompt_extend: bool = True  # 智能改写
    watermark: bool = False  # 水印（仅 wan2.6 支持）
    seed: Optional[int] = None  # 种子，None表示随机
    
    @property
    def size(self) -> str:
        """返回 width*height 格式的尺寸字符串"""
        return f"{self.width}*{self.height}"


class ImageEditConfig(BaseModel):
    """图像编辑配置（图生图）"""
    model: str = "wan2.5-i2i-preview"
    width: int = 1024  # 图片宽度
    height: int = 1024  # 图片高度
    prompt_extend: bool = True  # 智能改写
    watermark: bool = False  # 水印（仅 qwen-image-edit-plus 支持）
    seed: Optional[int] = None  # 种子，None表示随机
    
    @property
    def size(self) -> str:
        """返回 width*height 格式的尺寸字符串"""
        return f"{self.width}*{self.height}"


class VideoConfig(BaseModel):
    """图生视频配置
    
    参数说明（根据官方文档）：
    - resolution: 分辨率档位，wan2.5/2.6 支持 480P/720P/1080P，默认 1080P
    - duration: 视频时长，wan2.6 支持 5/10/15 秒，wan2.5 支持 5/10 秒，wanx2.1 支持 3/4/5 秒
    - prompt_extend: 智能改写，默认 True
    - watermark: 水印标识（右下角"AI生成"），默认 False
    - audio: 自动配音（仅 wan2.5/2.6 支持），默认 True
    - seed: 随机种子，范围 [0, 2147483647]
    - shot_type: 镜头类型（仅 wan2.6 支持），single/multi，默认 single
    """
    model: str = "wan2.5-i2v-preview"  # 默认使用 2.5 模型
    resolution: str = "1080P"  # 分辨率（wan2.5/2.6默认1080P，wanx2.1用宽*高）
    prompt_extend: bool = True  # 智能改写，默认开启
    watermark: bool = False  # 水印，默认关闭
    seed: Optional[int] = None  # 种子，None表示随机
    duration: int = 5  # 视频时长（秒）
    audio: bool = True  # 是否自动生成音频（仅wan2.5/2.6支持，默认开启）
    shot_type: str = "single"  # 镜头类型（仅wan2.6支持），single单镜头/multi多镜头叙事


class RefVideoConfig(BaseModel):
    """视频生视频配置（参考视频生成视频）
    
    参数说明（根据官方文档 wan2.6-r2v）：
    - model: 模型名称，目前仅支持 wan2.6-r2v
    - size: 分辨率，格式为"宽*高"（如 1920*1080）
    - duration: 视频时长，5 或 10 秒
    - shot_type: 镜头类型，single 单镜头 / multi 多镜头叙事
    - watermark: 水印标识（右下角"AI生成"），默认 False
    - seed: 随机种子，范围 [0, 2147483647]
    - audio: 是否生成音频，默认 True
    """
    model: str = "wan2.6-r2v"  # 目前仅支持此模型
    size: str = "1920*1080"  # 分辨率（宽*高格式）
    duration: int = 5  # 视频时长（秒）
    shot_type: str = "single"  # 镜头类型：single单镜头/multi多镜头叙事
    watermark: bool = False  # 水印，默认关闭
    seed: Optional[int] = None  # 种子，None表示随机
    audio: bool = True  # 是否生成音频，默认开启


class OSSConfig(BaseModel):
    """阿里云 OSS 配置"""
    enabled: bool = False  # 是否启用 OSS 持久化
    access_key_id: str = ""
    access_key_secret: str = ""
    bucket_name: str = ""
    endpoint: str = "https://oss-cn-beijing.aliyuncs.com"  # 包含 https:// 前缀
    prefix: str = "aistudio/"  # OSS 存储目录前缀
    
    @property
    def endpoint_url(self) -> str:
        """返回完整的 endpoint URL（确保有 https://）"""
        if self.endpoint.startswith("https://") or self.endpoint.startswith("http://"):
            return self.endpoint
        return f"https://{self.endpoint}"
    
    @property
    def endpoint_host(self) -> str:
        """返回不含协议的 endpoint 主机名"""
        return self.endpoint.replace("https://", "").replace("http://", "")


class AppConfig(BaseModel):
    """应用配置模型"""
    dashscope_api_key: str = ""
    api_region: str = "beijing"  # beijing 或 singapore
    
    # LLM 配置
    llm: LLMConfig = LLMConfig()
    
    # 文生图配置
    image: ImageConfig = ImageConfig()
    
    # 图像编辑配置
    image_edit: ImageEditConfig = ImageEditConfig()
    
    # 图生视频配置
    video: VideoConfig = VideoConfig()
    
    # 视频生视频配置
    ref_video: RefVideoConfig = RefVideoConfig()
    
    # OSS 配置
    oss: OSSConfig = OSSConfig()
    
    @property
    def base_url(self) -> str:
        """根据地域获取 API 基础地址"""
        return API_REGIONS.get(self.api_region, API_REGIONS["beijing"])["base_url"]


import threading
import fcntl
from contextvars import ContextVar

# 当前用户配置的上下文变量
_current_user_config_dir: ContextVar[Optional[str]] = ContextVar('current_user_config_dir', default=None)


def set_user_config_dir(config_dir: Optional[str]):
    """设置当前请求的用户配置目录"""
    _current_user_config_dir.set(config_dir)


def get_user_config_dir() -> Optional[str]:
    """获取当前请求的用户配置目录"""
    return _current_user_config_dir.get()


class ConfigManager:
    """配置管理器 - 支持多用户独立配置"""
    
    def __init__(self, config_dir: Optional[str] = None):
        """
        初始化配置管理器
        
        Args:
            config_dir: 配置文件目录，默认为 backend/data
        """
        if config_dir is None:
            self.config_dir = Path(__file__).parent.parent / "data"
        else:
            self.config_dir = Path(config_dir)
        
        self.config_file = self.config_dir / "config.json"
        self._ensure_config_dir()
        self._lock = threading.RLock()  # 可重入锁，支持并发访问
    
    def _ensure_config_dir(self):
        """确保配置目录存在"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
    
    def _read_with_lock(self) -> dict:
        """带文件锁的读取操作"""
        if not self.config_file.exists():
            return {}
        with open(self.config_file, 'r', encoding='utf-8') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)  # 共享锁
            try:
                return json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    
    def _write_with_lock(self, data: dict):
        """带文件锁的写入操作"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # 排他锁
            try:
                json.dump(data, f, ensure_ascii=False, indent=2)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    
    def load(self) -> AppConfig:
        """加载配置（每次都从文件读取，确保最新）"""
        with self._lock:
            data = self._read_with_lock()
            # 如果文件为空或内容为空字典，则使用默认配置
            if data and len(data) > 0:
                try:
                    return AppConfig(**data)
                except Exception:
                    # 如果数据格式错误，使用默认配置
                    pass
            # 创建并保存默认配置
            config = AppConfig()
            self.save(config)
            return config
    
    def save(self, config: AppConfig) -> None:
        """保存配置"""
        with self._lock:
            self._write_with_lock(config.model_dump())
    
    def update(self, **kwargs) -> AppConfig:
        """更新配置"""
        with self._lock:
            config = self.load()
            updated_data = config.model_dump()
            
            # 处理嵌套更新
            for key, value in kwargs.items():
                if key in ['llm', 'image', 'image_edit', 'video', 'ref_video', 'oss'] and isinstance(value, dict):
                    # 合并嵌套配置
                    if key in updated_data:
                        updated_data[key].update(value)
                    else:
                        updated_data[key] = value
                else:
                    updated_data[key] = value
            
            new_config = AppConfig(**updated_data)
            self.save(new_config)
            return new_config
    
    def reload(self) -> AppConfig:
        """强制重新加载配置"""
        return self.load()
    
    def get_api_key(self) -> str:
        """获取 API Key"""
        return self.load().dashscope_api_key
    
    def set_api_key(self, api_key: str) -> None:
        """设置 API Key"""
        self.update(dashscope_api_key=api_key)


# 用户配置管理器缓存
_user_config_managers: dict = {}
_config_managers_lock = threading.Lock()

# 全局默认配置管理器（向后兼容，不推荐使用）
_default_config_manager: Optional[ConfigManager] = None


def get_user_config_manager(user_config_dir: str) -> ConfigManager:
    """获取用户专属的配置管理器"""
    with _config_managers_lock:
        if user_config_dir not in _user_config_managers:
            _user_config_managers[user_config_dir] = ConfigManager(user_config_dir)
        return _user_config_managers[user_config_dir]


def get_default_config_manager() -> ConfigManager:
    """获取默认配置管理器（向后兼容）"""
    global _default_config_manager
    if _default_config_manager is None:
        _default_config_manager = ConfigManager()
    return _default_config_manager


class ConfigManagerProxy:
    """
    配置管理器代理
    
    自动根据当前用户上下文选择正确的配置管理器
    """
    
    def _get_manager(self) -> ConfigManager:
        """获取当前应使用的配置管理器"""
        user_config_dir = get_user_config_dir()
        if user_config_dir:
            return get_user_config_manager(user_config_dir)
        return get_default_config_manager()
    
    def __getattr__(self, name):
        """代理所有属性访问到实际的配置管理器"""
        return getattr(self._get_manager(), name)


# 全局配置管理器代理（自动路由到正确的用户配置）
config_manager = ConfigManagerProxy()


def get_config() -> AppConfig:
    """获取当前用户的配置"""
    return config_manager.load()


def get_api_key() -> str:
    """获取当前用户的 API Key"""
    return config_manager.get_api_key()


def get_base_url() -> str:
    """获取 API 基础地址"""
    return get_config().base_url
