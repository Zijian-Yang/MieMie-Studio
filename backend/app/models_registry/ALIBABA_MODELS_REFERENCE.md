# 阿里云百炼模型参考手册

本文档包含阿里云百炼平台常用模型的预置信息，AI 添加新模型时可直接参考。

> **注意**：API 可能会更新，建议对照最新官方文档确认参数。

---

## 1. 大语言模型 (LLM)

### 通用文档
- 调用方式: https://help.aliyun.com/zh/model-studio/developer-reference/use-qwen-by-calling-api
- JSON Mode: https://help.aliyun.com/zh/model-studio/json-mode
- 深度思考: https://help.aliyun.com/zh/model-studio/deep-thinking
- 联网搜索: https://help.aliyun.com/zh/model-studio/web-search

### qwen-max / qwen3-max

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model | string | 是 | 模型名称 |
| messages | array | 是 | 消息列表 |
| max_tokens | int | 否 | 最大输出 token，qwen3-max 最大 65536 |
| temperature | float | 否 | 温度 0-2，默认 0.7 |
| top_p | float | 否 | 0-1，默认 0.8 |
| result_format | string | 否 | message / json_object |
| enable_search | bool | 否 | 是否联网搜索 |

**能力**: 流式、JSON Mode、联网搜索

### qwen-plus / qwen-plus-latest

与 qwen-max 相同，额外支持：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| enable_thinking | bool | 否 | 深度思考模式 |
| thinking_budget | int | 否 | 思考 token 预算 |

**注意**: 深度思考模式下不支持 JSON Mode

---

## 2. 文生图模型

### 通用文档
- https://help.aliyun.com/zh/model-studio/text-to-image-v2-api-reference

### wanx2.5-t2i-preview (万相2.5 文生图)

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model | string | 是 | wanx2.5-t2i-preview |
| prompt | string | 是 | 提示词 |
| negative_prompt | string | 否 | 负面提示词 |
| size | string | 否 | 尺寸，如 "1024*1024" |
| n | int | 否 | 生成数量 1-4 |
| prompt_extend | bool | 否 | 智能改写，默认 true |
| seed | int | 否 | 随机种子 |

**尺寸约束**:
- 总像素: 768*768 ~ 1440*1440
- 宽高比: 1:4 ~ 4:1

**调用方式**: `ImageSynthesis.async_call()` / `ImageSynthesis.call()`

---

## 3. 图生图/图像编辑模型

### 通用文档
- 万相图生图: https://www.alibabacloud.com/help/zh/model-studio/wan2-5-image-edit-api-reference
- 千问图像编辑: https://www.alibabacloud.com/help/zh/model-studio/qwen-image-edit-api

### qwen-image-edit-plus (通义千问图像编辑)

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model | string | 是 | qwen-image-edit-plus |
| messages | array | 是 | 消息数组（单轮对话） |
| n | int | 否 | 输出图片数量 1-6，默认 1 |
| negative_prompt | string | 否 | 负面提示词，最长500字符 |
| size | string | 否 | 输出尺寸 "宽*高"，范围[512,2048]，**仅当n=1时可用** |
| prompt_extend | bool | 否 | 智能改写，默认 true |
| watermark | bool | 否 | 添加水印，默认 false |
| seed | int | 否 | 随机种子，范围[0,2147483647] |

**消息格式**:
```json
{
  "messages": [{
    "role": "user",
    "content": [
      {"image": "url1"},
      {"image": "url2"},  // 可选，多图融合时使用
      {"text": "编辑提示词"}
    ]
  }]
}
```

**SDK 调用示例**:
```python
response = MultiModalConversation.call(
    api_key=api_key,
    model="qwen-image-edit-plus",
    messages=messages,
    stream=False,
    n=2,
    watermark=False,
    negative_prompt=" ",
    prompt_extend=True,
    # size="1024*2048",  # 仅当 n=1 时可用
)
```

**两种模式**:
- 单图编辑：content 中1张图片
- 多图融合：content 中2-3张图片，用"图1"、"图2"、"图3"指代

**重要**:
- **不支持异步接口**，只有同步调用
- 输出比例以最后一张输入图片为准
- 使用 `MultiModalConversation.call()` 调用
- 图片URL有效期24小时
- **size参数仅当n=1时可用**，否则会报错

### wanx2.5-i2i-preview (万相2.5 图生图)

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model | string | 是 | wanx2.5-i2i-preview |
| prompt | string | 是 | 提示词 |
| images | array | 是 | 参考图 URL 列表，最多 5 张 |
| negative_prompt | string | 否 | 负面提示词 |
| size | string | 否 | 输出尺寸 |
| n | int | 否 | 生成数量 |
| prompt_extend | bool | 否 | 智能改写 |
| seed | int | 否 | 随机种子 |

**重要**: `images` 参数是数组，图片顺序影响生成结果

---

## 4. 图生视频模型

### 通用文档
- https://www.alibabacloud.com/help/zh/model-studio/image-to-video-api-reference

### wan2.5-i2v-preview (万相2.5 图生视频)

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model | string | 是 | wan2.5-i2v-preview |
| **img_url** | string | 是 | 首帧图片 URL |
| prompt | string | 否 | 提示词，最长 1000 字符 |
| negative_prompt | string | 否 | 负面提示词 |
| **resolution** | string | 否 | 分辨率：480P / 720P / 1080P |
| duration | int | 否 | 时长：5-10 秒 |
| prompt_extend | bool | 否 | 智能改写 |
| seed | int | 否 | 随机种子 |
| watermark | bool | 否 | 水印 |
| audio_url | string | 否 | 自定义音频 URL |
| audio | bool | 否 | 自动生成音频 |

**重要差异**:
- 使用 `img_url` (不是 image_url)
- 使用 `resolution` (480P/720P/1080P)
- 支持音频: `audio_url` > `audio`

**调用方式**: `VideoSynthesis.async_call()`

### wanx2.1-i2v-turbo (万相2.1 图生视频 Turbo)

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model | string | 是 | wanx2.1-i2v-turbo |
| **image_url** | string | 是 | 首帧图片 URL |
| prompt | string | 否 | 提示词 |
| negative_prompt | string | 否 | 负面提示词 |
| **size** | string | 否 | 尺寸：1280*720 / 720*1280 / 960*960 |
| prompt_extend | bool | 否 | 智能改写 |
| seed | int | 否 | 随机种子 |
| watermark | bool | 否 | 水印 |

**重要差异**:
- 使用 `image_url` (不是 img_url)
- 使用 `size` 指定分辨率 (像素格式)
- 固定 5 秒时长
- **不支持音频**

---

## 5. API 调用模式

### 异步调用 (推荐)

```python
# 创建任务
rsp = VideoSynthesis.async_call(**params)
task_id = rsp.output.task_id

# 轮询状态
status_rsp = VideoSynthesis.fetch(api_key=api_key, task=task_id)
# task_status: PENDING / RUNNING / SUCCEEDED / FAILED
```

### 同步调用

```python
rsp = VideoSynthesis.call(**params)
# 会阻塞直到完成
```

---

## 6. 常见错误

| 错误 | 原因 | 解决 |
|------|------|------|
| `img_url must provided` | wan2.5 使用了 image_url | 改用 `img_url` |
| `image_url must provided` | wanx2.1 使用了 img_url | 改用 `image_url` |
| `InvalidParameter` | 参数名或值不正确 | 检查参数名和约束 |
| `403 Forbidden` | URL 过期 | 使用 OSS 永久链接 |

---

## 7. 添加新模型 Checklist

当阿里云发布新模型时，按以下步骤添加：

1. **确认 API 参数**
   - [ ] 图片参数名是 `img_url` 还是 `image_url`？
   - [ ] 分辨率参数名是 `resolution` 还是 `size`？
   - [ ] 时长范围是多少？
   - [ ] 是否支持音频？

2. **创建模型文件**
   - [ ] 在对应目录创建 .py 文件
   - [ ] 定义 ModelInfo
   - [ ] 实现 Service 类
   - [ ] 注册模型

3. **测试**
   - [ ] 运行 test_registry.py
   - [ ] 测试 API 调用

---

## 8. SDK 版本要求

```bash
pip install dashscope>=1.14.0
```

最新 SDK 文档: https://help.aliyun.com/zh/model-studio/getting-started/sdk-installation

