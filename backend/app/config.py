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
# 参考: https://help.aliyun.com/zh/model-studio/text-to-image-v2-api-reference
IMAGE_MODELS = {
    "wan2.5-t2i-preview": {
        "name": "万相2.5 Preview",
        "description": "取消单边限制，在总像素面积与宽高比约束内自由选尺寸",
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
        "name": "万相2.5 图像编辑 Preview",
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
        "name": "通义千问 图像编辑 Plus",
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

# 图生视频模型配置
# 参考: https://www.alibabacloud.com/help/zh/model-studio/image-to-video-api-reference
VIDEO_MODELS = {
    "wan2.5-i2v-preview": {
        "name": "万相2.5 图生视频 Preview",
        "description": "最新图生视频模型，支持音频/自动配音，分辨率由输入图像决定",
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
        "image_param": "img_url",  # API 中图片参数名
    },
    "wanx2.1-i2v-turbo": {
        "name": "万相2.1 图生视频 Turbo",
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
    model: str = "wan2.5-t2i-preview"
    width: int = 1024  # 图片宽度
    height: int = 1024  # 图片高度
    prompt_extend: bool = True  # 智能改写
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
    - resolution: 分辨率档位，wan2.5 支持 480P/720P/1080P，默认 1080P
    - duration: 视频时长，wan2.5 支持 5 或 10 秒，wanx2.1 支持 3/4/5 秒
    - prompt_extend: 智能改写，默认 True
    - watermark: 水印标识（右下角"AI生成"），默认 False
    - audio: 自动配音（仅 wan2.5 支持），默认 True
    - seed: 随机种子，范围 [0, 2147483647]
    """
    model: str = "wan2.5-i2v-preview"  # 默认使用最新的 2.5 模型
    resolution: str = "1080P"  # 分辨率（wan2.5默认1080P，wanx2.1用宽*高）
    prompt_extend: bool = True  # 智能改写，默认开启
    watermark: bool = False  # 水印，默认关闭
    seed: Optional[int] = None  # 种子，None表示随机
    duration: int = 5  # 视频时长（秒）
    audio: bool = True  # 是否自动生成音频（仅wan2.5支持，默认开启）


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
    
    # OSS 配置
    oss: OSSConfig = OSSConfig()
    
    @property
    def base_url(self) -> str:
        """根据地域获取 API 基础地址"""
        return API_REGIONS.get(self.api_region, API_REGIONS["beijing"])["base_url"]


class ConfigManager:
    """配置管理器"""
    
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
        self._config: Optional[AppConfig] = None
    
    def _ensure_config_dir(self):
        """确保配置目录存在"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
    
    def load(self) -> AppConfig:
        """加载配置"""
        if self._config is not None:
            return self._config
        
        if self.config_file.exists():
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self._config = AppConfig(**data)
        else:
            self._config = AppConfig()
            self.save(self._config)
        
        return self._config
    
    def save(self, config: AppConfig) -> None:
        """保存配置"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config.model_dump(), f, ensure_ascii=False, indent=2)
        self._config = config
    
    def update(self, **kwargs) -> AppConfig:
        """更新配置"""
        config = self.load()
        updated_data = config.model_dump()
        
        # 处理嵌套更新
        for key, value in kwargs.items():
            if key in ['llm', 'image', 'image_edit', 'video', 'oss'] and isinstance(value, dict):
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
        self._config = None
        return self.load()
    
    def get_api_key(self) -> str:
        """获取 API Key"""
        return self.load().dashscope_api_key
    
    def set_api_key(self, api_key: str) -> None:
        """设置 API Key"""
        self.update(dashscope_api_key=api_key)


# 全局配置管理器实例
config_manager = ConfigManager()


def get_config() -> AppConfig:
    """获取当前配置"""
    return config_manager.load()


def get_api_key() -> str:
    """获取 API Key"""
    return config_manager.get_api_key()


def get_base_url() -> str:
    """获取 API 基础地址"""
    return get_config().base_url
