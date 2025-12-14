# 模型开发规范指南

本文档指导如何为平台添加新的 AI 模型支持。请严格遵循此规范，确保模型的一致性和可维护性。

## 目录结构

```
models_registry/
├── __init__.py          # 主入口，导入所有模型
├── base.py              # 基础定义（不要修改）
├── MODEL_DEVELOPMENT_GUIDE.md  # 本文档
├── llm/                 # 文本模型
│   ├── __init__.py
│   ├── qwen3_max.py
│   └── qwen_plus.py
├── image/               # 图像模型
│   ├── __init__.py
│   ├── wan25_t2i.py     # 文生图
│   └── wan25_i2i.py     # 图生图
└── video/               # 视频模型
    ├── __init__.py
    ├── wan25_i2v.py     # 图生视频
    └── wanx21_i2v.py    # 图生视频 Turbo
```

## 添加新模型的步骤

### 第一步：确定模型类型

根据模型功能选择正确的目录：
- `llm/` - 大语言模型（对话、文本生成）
- `image/` - 图像模型（文生图、图生图）
- `video/` - 视频模型（图生视频、文生视频）

### 第二步：收集模型信息

在编写代码前，先收集以下信息：

1. **API 文档链接**
2. **模型名称**（API 调用时使用的名称）
3. **支持的参数**（每个参数的类型、约束、默认值）
4. **模型能力**（是否支持流式、批量、异步等）
5. **调用方式**（SDK 方法、参数格式）

### 第三步：创建模型文件

在对应目录下创建 Python 文件，命名规则：`{provider}_{version}_{type}.py`

例如：`wan25_i2v.py`（万相2.5图生视频）

### 第四步：定义 ModelInfo

```python
from ..base import (
    ModelInfo, ModelType, ModelCapability, ModelParameter,
    ParameterType, ParameterConstraint, SelectOption,
    BaseModelService, TaskResult, TaskStatus, registry
)

# 定义模型信息
MY_MODEL_INFO = ModelInfo(
    # === 基本信息（必填）===
    id="my-model-id",              # 唯一标识，用于 API 路由和前端
    name="模型显示名称",            # 前端显示的名称
    type=ModelType.IMAGE_TO_VIDEO, # 模型类型
    provider="dashscope",          # 提供商
    description="模型描述",         # 简短描述
    
    # === API 信息（必填）===
    api_model_name="api-model-name",  # API 调用时使用的模型名
    doc_url="https://...",            # 文档链接
    
    # === 能力声明（根据模型实际能力设置）===
    capabilities=ModelCapability(
        supports_streaming=False,      # 是否支持流式输出
        supports_batch=False,          # 是否支持批量
        supports_async=True,           # 是否支持异步
        max_concurrent=3,              # 最大并发数
        # ... 其他能力
    ),
    
    # === 参数定义（重要！）===
    parameters=[
        ModelParameter(
            name="param_name",           # 参数名（API 中使用）
            label="参数显示名",           # 前端显示
            type=ParameterType.STRING,   # 参数类型
            description="参数描述",       # 提示文字
            required=True,               # 是否必填
            default="默认值",             # 默认值
            group="basic",               # 分组：basic, generation, audio, advanced
            order=1,                     # 显示顺序
            constraint=ParameterConstraint(
                # 约束条件
            ),
        ),
        # ... 更多参数
    ],
)
```

### 第五步：实现 Service 类

```python
class MyModelService(BaseModelService[str]):
    """
    服务类文档
    """
    
    def __init__(self, model_info: ModelInfo = MY_MODEL_INFO):
        super().__init__(model_info)
    
    def configure(self, api_key: str, base_url: str = ""):
        """配置 API 密钥"""
        super().configure(api_key, base_url)
        # 设置 SDK 配置
        import dashscope
        if base_url:
            dashscope.base_http_api_url = base_url
    
    async def generate(self, **params) -> str:
        """
        同步生成方法
        
        参数应与 ModelInfo.parameters 中定义的一致
        """
        # 1. 验证参数
        valid, errors = self.validate_params(params)
        if not valid:
            raise ValueError(f"参数错误: {errors}")
        
        # 2. 调用 API
        # ...
        
        # 3. 返回结果
        return result
    
    async def create_task(self, **params) -> str:
        """
        创建异步任务
        
        Returns:
            任务ID
        """
        # 调用 SDK 的 async_call 方法
        pass
    
    async def get_task_status(self, task_id: str) -> TaskResult:
        """
        获取任务状态
        """
        # 调用 SDK 的 fetch 方法
        pass
```

### 第六步：注册模型

在文件末尾添加注册代码：

```python
def register():
    """注册模型"""
    registry.register(MY_MODEL_INFO, MyModelService)

# 自动注册
register()
```

### 第七步：更新 __init__.py

在对应目录的 `__init__.py` 中导入模型：

```python
from . import my_model
from .my_model import MY_MODEL_INFO, MyModelService

__all__ = [
    "MY_MODEL_INFO",
    "MyModelService",
]
```

在 `models_registry/__init__.py` 中导入：

```python
from .video import my_model  # 添加导入
```

## 参数类型说明

| 类型 | 说明 | 前端组件 |
|------|------|---------|
| `STRING` | 短字符串 | Input |
| `TEXT` | 长文本 | TextArea |
| `INTEGER` | 整数 | InputNumber |
| `FLOAT` | 浮点数 | InputNumber (小数) |
| `BOOLEAN` | 布尔值 | Switch |
| `SELECT` | 单选 | Select |
| `MULTI_SELECT` | 多选 | Select (多选模式) |
| `IMAGE_URL` | 图片URL | ImagePicker |
| `IMAGE_URLS` | 多图片URL | MultiImagePicker |
| `AUDIO_URL` | 音频URL | AudioPicker |
| `VIDEO_URL` | 视频URL | VideoPicker |
| `FILE` | 文件上传 | Upload |

## 参数分组

| 分组 | 说明 |
|------|------|
| `basic` | 基础参数（提示词、输入等） |
| `generation` | 生成参数（分辨率、时长等） |
| `audio` | 音频参数 |
| `advanced` | 高级参数（默认折叠） |

## 能力声明

```python
ModelCapability(
    # 通用能力
    supports_streaming=False,    # 流式输出（LLM）
    supports_batch=False,        # 批量处理
    supports_async=True,         # 异步调用
    max_concurrent=5,            # 最大并发
    
    # LLM 特有
    supports_thinking=False,     # 深度思考
    supports_search=False,       # 联网搜索
    supports_json_mode=False,    # JSON 输出
    supports_tools=False,        # 工具调用
    max_context_length=None,     # 上下文长度
    
    # 图像/视频特有
    supports_negative_prompt=False,  # 负面提示词
    supports_seed=False,             # 种子
    supports_prompt_extend=False,    # 智能改写
    supports_watermark=False,        # 水印
    supports_audio=False,            # 音频（视频模型）
)
```

## 示例：添加 wanx2.1-i2v-turbo 模型

```python
# backend/app/models_registry/video/wanx21_i2v.py

from ..base import (
    ModelInfo, ModelType, ModelCapability, ModelParameter,
    ParameterType, ParameterConstraint, SelectOption,
    BaseModelService, TaskResult, TaskStatus, registry
)

WANX21_I2V_MODEL_INFO = ModelInfo(
    id="wanx2.1-i2v-turbo",
    name="万相2.1 图生视频 Turbo",
    type=ModelType.IMAGE_TO_VIDEO,
    provider="dashscope",
    description="快速生成模型，适合快速预览",
    api_model_name="wanx2.1-i2v-turbo",
    
    capabilities=ModelCapability(
        supports_async=True,
        supports_negative_prompt=True,
        supports_seed=True,
        supports_prompt_extend=True,
        supports_audio=False,  # 不支持音频
    ),
    
    parameters=[
        ModelParameter(
            name="image_url",  # 注意：wanx2.1 使用 image_url
            label="首帧图片",
            type=ParameterType.IMAGE_URL,
            required=True,
            group="basic",
        ),
        ModelParameter(
            name="size",  # 注意：wanx2.1 使用 size 而不是 resolution
            label="分辨率",
            type=ParameterType.SELECT,
            default="1280*720",
            constraint=ParameterConstraint(
                options=[
                    SelectOption(value="1280*720", label="1280x720 (16:9)"),
                    SelectOption(value="720*1280", label="720x1280 (9:16)"),
                    SelectOption(value="960*960", label="960x960 (1:1)"),
                ]
            ),
            group="generation",
        ),
        # ... 其他参数（duration 固定为 5 秒，不需要暴露）
    ],
)


class Wanx21I2VService(BaseModelService[str]):
    """万相2.1 图生视频服务"""
    
    async def create_task(self, image_url: str, **params) -> str:
        # 注意：wanx2.1 使用 image_url 参数名
        rsp = VideoSynthesis.async_call(
            api_key=self._api_key,
            model=self.model_info.api_model_name,
            image_url=image_url,  # 与 wan2.5 的 img_url 不同
            **params
        )
        return rsp.output.task_id
    
    # ... 其他实现


def register():
    registry.register(WANX21_I2V_MODEL_INFO, Wanx21I2VService)

register()
```

## 注意事项

1. **参数名称一致性**：ModelInfo.parameters 中的 name 必须与 Service 方法的参数名一致

2. **不同模型的 API 差异**：
   - wan2.5 使用 `img_url`，wanx2.1 使用 `image_url`
   - wan2.5 使用 `resolution`，wanx2.1 使用 `size`
   - 在 Service 中处理这些差异

3. **异步支持**：所有 Service 方法应使用 `async def`

4. **错误处理**：合理捕获和抛出异常，提供清晰的错误信息

5. **文档完整**：每个模型文件顶部应包含 API 文档链接和使用说明

## 测试新模型

添加模型后，运行以下测试：

```python
# 测试注册
from app.models_registry import registry, ModelType

# 检查模型是否注册成功
model = registry.get_model_info("my-model-id")
assert model is not None

# 检查参数定义
assert len(model.parameters) > 0

# 测试服务创建
service = registry.create_service("my-model-id", "your-api-key")
assert service is not None

# 测试参数验证
valid, errors = model.validate_params({"param_name": "value"})
assert valid
```

## 更新前端

添加新模型后，前端会自动获取模型配置。但如果需要特殊的 UI 处理，请更新：

1. `frontend/src/services/api.ts` - 添加类型定义
2. `frontend/src/pages/*/` - 更新相关页面

## 提交规范

提交新模型时，commit message 格式：

```
feat(models): add {model-name} support

- Add {model-id} model definition
- Implement {ModelService} service class
- Register model in models_registry

API Doc: {doc-url}
```

