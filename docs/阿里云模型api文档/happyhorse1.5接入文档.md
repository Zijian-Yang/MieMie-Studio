# HappyHorse 1.5 线上接口文档说明（对外）

## HH1.0 & 1.5

> "需要提前加白使用"：申请统一走百炼申请（加白通过后需要登陆一下百炼控制台，才能继续使用）

> "视频默认都带音频直出，不支持关闭推理音频"

## 调用步骤

- 调用参考：[百炼API控制台](https://bailian.console.aliyun.com/cn-beijing?tab=api#/api/?type=model&url=3025059)
- **任务提交：**

```bash
curl --location \
  'https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis' \
  -H 'X-DashScope-Async: enable' \
  -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
  "model": "happyhorse-1.5-i2v",
  "input": {
    "prompt": "一幅都市奇幻艺术的场景。一个充满动感的涂鸦艺术角色。一个由喷漆所画成的少年，正从一面混凝土墙上活过来。他一边用极快的语速演唱一首英文rap，一边摆着一个经典的、充满活力的说唱歌手姿势。场景设定在夜晚一个充满都市感的铁路桥下。灯光来自一盏孤零零的街灯，营造出电影般的氛围，充满高能量和惊人的细节。视频的音频部分完全由rap构成，没有其他对话或杂音。",
    "media": [
      {
        "type": "first_frame",
        "url": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20250925/wpimhv/rap.png"
      }
    ]
  },
  "parameters": {
    "resolution": "720P",
    "duration": 10,
    "watermark": true
  }
}'
```

- **任务查询：**

```bash
curl -X GET https://dashscope.aliyuncs.com/api/v1/tasks/{task_id} \
  --header "Authorization: Bearer $DASHSCOPE_API_KEY"
```

## 线上接口地址

- **国内：** `https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis`
- **国际：** `https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis`

---

## 一、HH1 Text-to-Video (T2V)

**model name:** `happyhorse-1.5-t2v` / `happyhorse-1.0-t2v`

### 请求结构

```json
{
  "input": {
    "prompt": "string"
  },
  "parameters": {
    "resolution": "1080P",
    "ratio": "16:9",
    "duration": 5,
    "seed": null
  }
}
```

### 字段说明

#### Input

| 字段 | 类型 | 是否必填 | 范围/限制 | 默认值 | 说明 |
|------|------|----------|-----------|--------|------|
| prompt | string | 必填 | 最大 2500，超长自动截断；不能为空或纯空格；不能包含特殊 token (`<`) | - | 文本生成提示词 |

#### Parameters

| 字段 | 类型 | 是否必填 | 范围值 | 默认值 | 说明 |
|------|------|----------|--------|--------|------|
| resolution | string | 可选 | `"1080P"`, `"720P"` | `"1080P"` | 视频分辨率 |
| ratio | string | 可选 | `"16:9"`, `"9:16"`, `"1:1"`, `"4:3"`, `"3:4"`, `"21:9"`, `"9:21"`, `"5:4"`, `"4:5"` | `"16:9"` | 视频宽高比 |
| duration | int | 可选 | 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15 | 5 | 视频时长（秒） |
| seed | int | 可选 | [0, 2147483647] | 随机生成 | 随机种子，用于控制生成结果的确定性 |
| watermark | bool | 可选 | True / False | True | 默认带水印 |

### Request example

`POST https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis`

```json
{
  "model": "happyhorse-1.5-t2v",
  "input": {
    "prompt": "一个小女孩走在路上"
  },
  "parameters": {
    "resolution": "1080P",
    "duration": 5,
    "seed": 42
  }
}
```

### Response example

```json
{
  "output": {
    "video_url": "https://dashscope-b358.oss-accelerate.aliyuncs.com/1d/40/20260410/0470ea79/22373962-metadata_8dcc404d88fac6f8.mp4?Expires=1775896500&OSSAccessKeyId=LTAI5tPxpiCM2hjmWrFXrym1&Signature=YkmvbgARgje%2B2nXcFErxlUCAQhY%3D",
    "origin_prompt": "一个小女孩走在路上"
  },
  "usage": {
    "video_count": 1,
     "duration": 5,
    "SR": 720,
    "output_video_duration": 5,
    "input_video_duration": 0,
    "ratio": "16:9"
  }
}
```

---

## 二、HH1 Image-to-Video (I2V)

**model name:** `happyhorse-1.5-i2v` / `happyhorse-1.0-i2v`

### 请求结构

```json
{
  "input": {
    "media": [
      {
        "url": "string",
        "type": "first_frame"
      }
    ],
    "prompt": "string"
  },
  "parameters": {
    "resolution": "1080P",
    "duration": 5,
    "seed": 42
  }
}
```

### 字段说明

#### Input

| 字段 | 类型 | 是否必填 | 范围/限制 | 默认值 | 说明 |
|------|------|----------|-----------|--------|------|
| media | array | 必填 | 必须包含 1 个 `first_frame` 类型元素；不支持多个 `first_frame`；不支持其他类型（`last_frame`, `driving_audio`, `first_clip`） | - | 输入媒体列表 |
| media[].url | string | 必填 | 不能为空字符串 | - | 图片 URL |
| media[].type | string | 可选 | `"first_frame"` | `"first_frame"` | 媒体类型（HH1 仅支持 `first_frame`） |
| prompt | string | 可选 | 2500，超长自动截断；不能为空或纯空格；不能包含特殊 token | - | 文本生成提示词 |

**输入图片要求：**

- 长宽像素：图片宽高尺寸不小于 300px，无上限限制
- 长宽比：图片宽高比介于 1:2.5 ~ 2.5:1 之间
- 格式：JPEG、JPG、PNG、BMP、WEBP
- 文件大小：不能超过 20MB

#### Parameters

| 字段 | 类型 | 是否必填 | 范围值 | 默认值 | 说明 |
|------|------|----------|--------|--------|------|
| resolution | string | 可选 | `"1080P"`, `"720P"` | `"1080P"` | 视频分辨率 |
| duration | int | 可选 | 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15 | 5 | 视频时长（秒） |
| seed | int | 可选 | [0, 2147483647] | 随机生成 | 随机种子，用于控制生成结果的确定性 |
| watermark | bool | 可选 | True / False | True | 默认带水印 |

### Request example

`POST https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis`

```json
{
  "model": "happyhorse-1.5-i2v",
  "input": {
    "media": [
      {
        "type": "first_frame",
        "url": "https://example.com/image.jpg"
      }
    ],
    "prompt": "让图片中的场景动起来"
  },
  "parameters": {
    "resolution": "1080P",
    "duration": 5,
    "seed": 42
  }
}
```

### Response example

```json
{
  "output": {
    "video_url": "https://dashscope-b358.oss-accelerate.aliyuncs.com/1d/40/20260410/0470ea79/22373962-metadata_8dcc404d88fac6f8.mp4?Expires=1775896500&OSSAccessKeyId=LTAI5tPxpiCM2hjmWrFXrym1&Signature=YkmvbgARgje%2B2nXcFErxlUCAQhY%3D",
    "origin_prompt": "让图片中的场景动起来"
  },
  "usage": {
    "video_count": 1,
    "duration": 5,
    "SR": 720,
    "output_video_duration": 5,
    "input_video_duration": 0
  }
}
```

---

## 三、HH1 Reference-to-Video (R2V)

**model name:** `happyhorse-1.5-r2v` / `happyhorse-1.0-r2v`

### 请求结构

```json
{
  "input": {
    "prompt": "图 1 中的主角在图 2 的场景中奔跑，随后拿起图 3 中的道具。画面保持 3D 卡通风格，动作流畅。",
    "media": [
      {
        "type": "reference_image",
        "url": "https://public-bucket.example.com/image_01.jpg"
      },
      {
        "type": "reference_image",
        "url": "https://public-bucket.example.com/image_02.png"
      },
      {
        "type": "reference_image",
        "url": "https://public-bucket.example.com/image_03.jpeg"
      }
    ]
  },
  "parameters": {
    "resolution": "1080P",
    "ratio": "16:9",
    "duration": 5,
    "seed": null,
    "watermark": false
  }
}
```

### 字段说明

#### Input

| 字段 | 类型 | 是否必填 | 范围/限制 | 默认值 | 说明 |
|------|------|----------|-----------|--------|------|
| media | array | 必填 | 必须包含至少1个 `reference_image` 类型元素 | - | 输入媒体列表 |
| media[].url | string | 必填 | 不能为空字符串 | - | 图片 URL |
| media[].type | string | 必填 | `"reference_image"` | `reference_image` | reference_image，数量：1 ≤ N ≤ 9 |
| prompt | string | 必填 | 2500字符，超长自动截断；不能为空或纯空格 | - | 文本生成提示词 |

#### Parameters

| 字段 | 类型 | 是否必填 | 范围值 | 默认值 | 说明 |
|------|------|----------|--------|--------|------|
| resolution | string | 可选 | `"1080P"`, `"720P"` | `"1080P"` | 视频分辨率 |
| ratio | string | 可选 | `16:9`, `9:16`, `3:4`, `4:3`, `1:1`, `21:9`, `9:21`, `5:4`, `4:5` | `"16:9"` | 视频宽高比 |
| duration | int | 可选 | 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15 | 5 | 视频时长（秒） |
| seed | int | 可选 | [0, 2147483647] | 随机生成 | 随机种子，用于控制生成结果的确定性 |
| watermark | bool | 可选 | true / false | true | 是否添加水印。默认带水印 |

**输入图片要求：**

- 分辨率：短边不低于400px，更推荐720p 以上清晰图；避免极小图、糊图、压缩严重的图
- 图片短边比长边比例，不得小于 0.4
- 宽高比：图片短边比长边比例，不得小于 0.4，但建议多张图比例一致，且和目标视频比例接近
- 格式：JPEG、JPG、PNG、BMP、WEBP
- 文件大小：单张图片不能超过 10MB

### Request example

`POST https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis`

```json
{
  "model": "happyhorse-1.5-r2v",
  "input": {
    "prompt": "图 1 中的主角在图 2 的场景中奔跑，随后拿起图 3 中的道具。画面保持 3D 卡通风格，动作流畅。",
    "media": [
      {
        "type": "reference_image",
        "url": "https://public-bucket.example.com/image_01.jpg"
      },
      {
        "type": "reference_image",
        "url": "https://public-bucket.example.com/image_02.png"
      },
      {
        "type": "reference_image",
        "url": "https://public-bucket.example.com/image_03.jpeg"
      }
    ]
  },
  "parameters": {
    "resolution": "1080P",
    "duration": 5,
    "seed": 42,
    "watermark": false
  }
}
```

### Response example

```json
{
  "output": {
    "video_url": "https://dashscope-b358.oss-accelerate.aliyuncs.com/1d/40/20260410/0470ea79/22373962-metadata_8dcc404d88fac6f8.mp4?Expires=1775896500&OSSAccessKeyId=LTAI5tPxpiCM2hjmWrFXrym1&Signature=YkmvbgARgje%2B2nXcFErxlUCAQhY%3D",
    "origin_prompt": "让图片中的场景动起来"
  },
  "usage": {
    "video_count": 1,
    "duration": 5,
    "SR": 720,
    "output_video_duration": 5,
    "input_video_duration": 0,
    "ratio": "16:9"
  }
}
```

---

## 四、HH-EDIT

> 目前没有1.5版本

**model name:** `happyhorse-1.0-video-edit`

### 请求结构

```json
{
  "input": {
    "media": [
      {
        "url": "string",
        "type": "video"
      },
      {
        "url": "string",
        "type": "reference_image"
      }
    ],
    "prompt": "string"
  },
  "parameters": {
    "resolution": "1080P",
    "audio_setting": "origin",
    "seed": 42
  }
}
```

### 字段说明

#### Input

| 字段 | 类型 | 是否必填 | 范围/限制 | 默认值 | 说明 |
|------|------|----------|-----------|--------|------|
| media | array | 必填 | 必须包含 1 个 `video` 类型元素；不支持多个 `video`；支持 `reference_image` 0-5张 | - | 输入媒体列表 |
| media[].url | string | 必填 | 不能为空字符串 | - | 视频/图片 URL |
| media[].type | string | 必填 | `"video"`, `"reference_image"` | - | video（数量：1，必填）；reference_image（数量：0 ≤ N ≤ 5） |
| prompt | string | 必填 | 2500字符，超长自动截断；不能为空或纯空格；不能包含特殊 token | - | 文本生成提示词 |

**输入视频要求：**

- 时长：3-60 秒（传入超过15s的视频，将从0开始截断到15s）
- 分辨率：最小480p，短边下限360
- 长宽比：宽高比介于 1:8 ~ 8:1 之间
- 格式：MP4，MOV（建议H.264 编码）
- 文件大小：不能超过 100MB
- 帧率：大于8fps

**输入图片要求：**

- 长宽像素：图片宽高尺寸不小于 300px，无上限限制
- 长宽比：图片宽高比介于 1:2.5 ~ 2.5:1 之间
- 格式：JPEG、JPG、PNG、BMP、WEBP
- 文件大小：不能超过 20MB

#### Parameters

| 字段 | 类型 | 是否必填 | 范围值 | 默认值 | 说明 |
|------|------|----------|--------|--------|------|
| resolution | string | 可选 | `"1080P"`, `"720P"` | `"1080P"` | 视频分辨率 |
| seed | int | 可选 | [0, 2147483647] | 随机生成 | 随机种子，用于控制生成结果的确定性 |
| audio_setting | string | 可选 | `"auto"`, `"origin"` | `"auto"` | 声音控制 |
| watermark | bool | 可选 | true / false | true | 默认带水印 |

### Request example

`POST https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis`

```json
{
  "model": "happyhorse-1.0-video-edit",
  "input": {
    "media": [
      {
        "type": "video",
        "url": "https://example.com/image.mp4"
      }
    ],
    "prompt": "让图片中的场景动起来"
  },
  "parameters": {
    "resolution": "1080P",
    "audio_setting": "origin",
    "seed": 42
  }
}
```

### Response example

```json
{
  "output": {
    "video_url": "https://dashscope-b358.oss-accelerate.aliyuncs.com/1d/40/20260410/0470ea79/22373962-metadata_8dcc404d88fac6f8.mp4?Expires=1775896500&OSSAccessKeyId=LTAI5tPxpiCM2hjmWrFXrym1&Signature=YkmvbgARgje%2B2nXcFErxlUCAQhY%3D",
    "origin_prompt": "让图片中的场景动起来"
  },
  "usage": {
    "video_count": 1,
    "duration": 10,
    "SR": 720,
    "output_video_duration": 5,
    "input_video_duration": 5
  }
}
```