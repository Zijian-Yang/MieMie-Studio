# **千问-图像编辑API参考**

更新时间：2026-03-03 20:05:13

复制为 MD 格式

[产品详情](https://www.aliyun.com/product/bailian)

[我的收藏](https://help.aliyun.com/my_favorites.html)

千问-图像编辑模型支持多图输入和多图输出，可精确修改图内文字、增删或移动物体、改变主体动作、迁移图片风格及增强画面细节。


|                                                                                                                                                                                                                                                                                                                                        |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **快速入口：**[使用指南](https://help.aliyun.com/zh/model-studio/qwen-image-edit-guide) **|** [技术博客](https://qwen.ai/blog?id=1675c295dc29dd31073e5b3f72876e9d684e41c6&from=research.research-list) | [在线体验](https://bailian.console.aliyun.com/?tab=model#/efm/model_experience_center/vision?currentTab=imageGenerate&modelId=qwen-image-edit) |


## **模型概览**


|          |          |          |              |
| -------- | -------- | -------- | ------------ |
| **输入图1** | **输入图2** | **输入图3** | **输出图像（多图）** |



|          |          |          |              |     |
| -------- | -------- | -------- | ------------ | --- |
| **输入图1** | **输入图2** | **输入图3** | **输出图像（多图）** |     |
|          |          |          |              |     |


> 输入提示词：图1中的女生穿着图2中的黑色裙子按图3的姿势坐下。


|                                                              |                                                                                                               |                                                                                                                  |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| **模型名称**                                                     | **模型简介**                                                                                                      | **输出图像规格**                                                                                                       |
| qwen-image-2.0-pro `推荐`当前与qwen-image-2.0-pro-2026-03-03能力相同 | 千问图像生成与编辑模型Pro系列。文字渲染、真实质感、语义遵循能力更强。图像生成请参考[千问-文生图](https://help.aliyun.com/zh/model-studio/qwen-image-api)。 | 图像分辨率：- **可指定**：图像总像素需在512*512至2048*2048之间。- **默认**：与输入图（多图输入时为最后一张）一致。图像格式：png图像张数：1-6张                      |
| qwen-image-2.0-pro-2026-03-03 `推荐`                           |                                                                                                               |                                                                                                                  |
| qwen-image-2.0 `推荐`当前与qwen-image-2.0-2026-03-03能力相同         | 千问图像生成与编辑模型加速版，兼顾效果与响应速度。图像生成请参考[千问-文生图](https://help.aliyun.com/zh/model-studio/qwen-image-api)。            |                                                                                                                  |
| qwen-image-2.0-2026-03-03 `推荐`                               |                                                                                                               |                                                                                                                  |
| qwen-image-edit-max当前与qwen-image-edit-max-2026-01-16能力相同    | 千问图像编辑Max系列。工业设计、几何推理、角色一致性更强。                                                                                | 图像分辨率：- **可指定**：宽和高的取值范围均为`[512, 2048]`像素。- **默认**：总像素数接近 `1024*1024`，宽高比与输入图（多图输入时为最后一张）相近。图像格式：png图像张数：1-6张 |
| qwen-image-edit-max-2026-01-16                               |                                                                                                               |                                                                                                                  |
| qwen-image-edit-plus当前与qwen-image-edit-plus-2025-10-30能力相同  | 千问图像编辑Plus系列，支持多图输出与自定义分辨率。                                                                                   |                                                                                                                  |
| qwen-image-edit-plus-2025-12-15                              |                                                                                                               |                                                                                                                  |
| qwen-image-edit-plus-2025-10-30                              |                                                                                                               |                                                                                                                  |
| qwen-image-edit                                              | 支持单图编辑和多图融合。                                                                                                  | 图像分辨率：**不可指定**。生成规则同上方的**默认**规则。图像格式：png图像张数：固定1张                                                              |


**说明**

调用前，请查阅各地域支持的[模型列表](https://help.aliyun.com/zh/model-studio/models#bfe15d8aa2lxh)。

## **前提条件**

在调用前，您需要[获取API Key](https://help.aliyun.com/zh/model-studio/get-api-key)，再[配置API Key到环境变量](https://help.aliyun.com/zh/model-studio/configure-api-key-through-environment-variables)。

如需通过SDK进行调用，请[安装DashScope SDK](https://help.aliyun.com/zh/model-studio/install-sdk)。目前，该SDK已支持Python和Java。

**重要**

北京和新加坡地域拥有独立的 **API Key** 与**请求地址**，不可混用，跨地域调用将导致鉴权失败或服务报错。

## **HTTP调用**

**北京地域**：`POST https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation`

**新加坡地域**：`POST https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation`


|               |
| ------------- |
| #### **请求参数** |



|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ##### **请求头（Headers）**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| **Content-Type** `string` ****（必选）**请求内容类型。此参数必须设置为`application/json`。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| **Authorization** `string`**（必选）**请求身份认证。接口使用阿里云百炼API-Key进行身份认证。示例值：Bearer sk-xxxx。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| ##### **请求体（Request Body）**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| **model** `string` **（必选）**模型名称，示例值qwen-image-2.0-pro。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| **input** `object` **（必选）**输入参数对象，包含以下字段：**属性****messages** `array` **（必选）**请求内容数组。**当前仅支持单轮对话**，因此数组内**有且只有一个对象**，该对象包含`role`和`content`两个属性。**属性****role** `string` **（必选）**消息发送者角色，必须设置为`user`。**content** `array` **（必选）**消息内容，包含1-3张图像，格式为 `{"image": "..."}`；以及单个编辑指令，格式为 `{"text": "..."}`。**属性****image** `string` **（必选）**输入图像的 URL 或 Base64 编码数据。支持传入1-3张图像。多图输入时，按照数组顺序定义图像顺序，输出图像的比例以最后一张为准。**图像要求：**- 图像格式：JPG、JPEG、PNG、BMP、TIFF、WEBP和GIF。 > 输出图像为PNG格式，对于GIF动图，仅处理其第一帧。- 图像分辨率：为获得最佳效果，建议图像的宽和高均在384像素至3072像素之间。分辨率过低可能导致生成效果模糊，过高则会增加处理时长。- 图像大小：不超过10MB。**支持的输入格式**- 公网URL： - 支持 HTTP 和 HTTPS 协议。 - 示例值：`https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20250925/fpakfo/image36.webp`。- 临时URL： - 支持OSS协议，必须通过[上传文件获取临时 URL](https://help.aliyun.com/zh/model-studio/get-temporary-file-url)。 - 示例值：`oss://dashscope-instant/xxx/2024-07-18/xxx/cat.png`。- 传入 Base64 编码图像后的字符串 - 示例值：`data:image/jpeg;base64,GDU7MtCZz...`（示例已截断，仅做演示） - Base64 编码规范请参见[通过Base64编码传入图片](https://help.aliyun.com/zh/model-studio/qwen-image-edit-api?spm=a2c4g.11186623.help-menu-2400256.d_2_2_1.59de23169QUPCw&scm=20140722.H_2976416._.OR_help-T_cn~zh-V_1#907c84c1a6wrm)。**text** `string` **（必选）**正向提示词，用于描述期望生成的图像内容、风格和构图。支持中英文，长度不超过800个字符，每个汉字、字母、数字或符号计为一个字符，超过部分会自动截断。示例值：图1中的女生穿着图2中的黑色裙子按图3的姿势坐下，保持其服装、发型和表情不变，动作自然流畅。**注意**：仅支持传入一个text，不传或传入多个将报错。 |
| **parameters** `object` （可选）控制图像生成的附加参数。**属性****n** `integer` （可选）输出图像的数量，默认值为1。对于qwen-image-2.0系列、qwen-image-edit-max、qwen-image-edit-plus系列模型，可选择输出1-6张图片。对于`qwen-image-edit`，仅支持输出1张图片。**negative_prompt** `string` （可选）反向提示词，用来描述不希望在画面中看到的内容，可以对画面进行限制。支持中英文，长度上限500个字符，每个汉字、字母、数字或符号计为一个字符，超过部分会自动截断。示例值：低分辨率、错误、最差质量、低质量、残缺、多余的手指、比例不良等。**size** `string` （可选）设置输出图像的分辨率，格式为`宽*高`，例如`"1024*1536"`。**qwen-image-2.0系列模型**：- 图像总像素需在512*512至2048*2048之间。- 默认分辨率与输入图（多图输入时为最后一张）一致。**qwen-image-edit-max、qwen-image-edit-plus系列模型**：- 宽和高的取值范围均为[512, 2048]像素。- 默认总像素数接近 `1024*1024`，宽高比与输入图（多图输入时为最后一张）相近。指定 `size` 参数，系统会以 `size`指定的宽高为目标，将实际输出图像的宽高调整为最接近的16的倍数。例如，设置`1033*1032`，输出图像尺寸为`1040*1024`。**常见比例推荐分辨率**- 1:1: 1024*1024、1536*1536- 2:3: 768*1152、1024*1536- 3:2: 1152*768、1536*1024- 3:4: 960*1280、1080*1440- 4:3: 1280*960、1440*1080- 9:16: 720*1280、1080*1920- 16:9: 1280*720、1920*1080- 21:9: 1344*576、2048*872**支持模型**：除`qwen-image-edit`以外的模型。**prompt_extend** `bool` （可选）是否开启提示词智能改写，默认值为 `true`。开启后，模型会优化正向提示词（`text`），对描述较简单的提示词效果提升明显。**支持模型**：除`qwen-image-edit`以外的模型。**watermark** `bool` （可选）是否在图像右下角添加 "Qwen-Image" 水印。默认值为 `false`。水印样式如下：**seed** `integer` （可选）随机数种子，取值范围`[0,2147483647]`。使用相同的`seed`参数值可使生成内容保持相对稳定。若不提供，算法将自动使用随机数种子。**注意**：模型生成过程具有概率性，即使使用相同的`seed`，也不能保证每次生成结果完全一致。                                                  |



|          |
| -------- |
| **单图编辑** |


此处以使用`qwen-image-2.0-pro`模型输出2张图片为例。

```curl
curl --location 'https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation' \
--header 'Content-Type: application/json' \
--header "Authorization: Bearer $DASHSCOPE_API_KEY" \
--data '{
    "model": "qwen-image-2.0-pro",
    "input": {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "image": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20250925/fpakfo/image36.webp"
                    },
                    {
                        "text": "生成一张符合深度图的图像，遵循以下描述：一辆红色的破旧的自行车停在一条泥泞的小路上，背景是茂密的原始森林"
                    }
                ]
            }
        ]
    },
    "parameters": {
        "n": 2,
        "negative_prompt": " ",
        "prompt_extend": true,
        "watermark": false,
        "size": "1536*1024"
    }
}'
```

**多图融合**

此处以使用`qwen-image-2.0-pro`模型输出2张图片为例。

```curl
curl --location 'https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation' \
--header 'Content-Type: application/json' \
--header "Authorization: Bearer $DASHSCOPE_API_KEY" \
--data '{
    "model": "qwen-image-2.0-pro",
    "input": {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "image": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20250925/thtclx/input1.png"
                    },
                    {
                        "image": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20250925/iclsnx/input2.png"
                    },
                    {
                        "image": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20250925/gborgw/input3.png"
                    },
                    {
                        "text": "图1中的女生穿着图2中的黑色裙子按图3的姿势坐下"
                    }
                ]
            }
        ]
    },
    "parameters": {
        "n": 2,
        "negative_prompt": " ",
        "prompt_extend": true,
        "watermark": false,
        "size": "1024*1536"
    }
}'
```

#### **响应参数**


|                                                                                                                                                                                                                                                                                                                |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **output** `object`包含模型生成结果。**属性****choices** `array`结果选项列表。**属性****finish_reason** `string`任务停止原因，自然停止时为`stop`。**message** `object`模型返回的消息。**属性****role** `string`消息的角色，固定为`assistant`。**content** `array`消息内容，包含生成的图像信息。**属性****image** `string`生成图像的 URL，格式为PNG。**链接有效期为24小时**，请及时下载并保存图像。 |
| **usage** `object`本次调用的资源使用情况，仅调用成功时返回。**属性****image_count** `integer`生成图像的张数。**width** `integer`生成图像的宽度（像素）。**height** `integer`生成图像的高度（像素）。                                                                                                                                                          |
| **request_id** `string`请求唯一标识。可用于请求明细溯源和问题排查。                                                                                                                                                                                                                                                                 |
| **code** `string`请求失败的错误码。请求成功时不会返回此参数，详情请参见[错误信息](https://help.aliyun.com/zh/model-studio/error-code)。                                                                                                                                                                                                       |
| **message** `string`请求失败的详细信息。请求成功时不会返回此参数，详情请参见[错误信息](https://help.aliyun.com/zh/model-studio/error-code)。                                                                                                                                                                                                   |


**任务执行成功**

任务数据（如任务状态、图像URL等）仅保留24小时，超时后会被自动清除。请您务必及时保存生成的图像。

```json
{
    "output": {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "image": "https://dashscope-result-sz.oss-cn-shenzhen.aliyuncs.com/xxx.png?Expires=xxx"
                        },
                        {
                            "image": "https://dashscope-result-sz.oss-cn-shenzhen.aliyuncs.com/xxx.png?Expires=xxx"
                        }
                    ]
                }
            }
        ]
    },
    "usage": {
        "width": 1536,
        "image_count": 2,
        "height": 1024
    },
    "request_id": "bf37ca26-0abe-98e4-8065-xxxxxx"
}
```

**任务执行异常**

如果因为某种原因导致任务执行失败，将返回相关信息，可以通过code和message字段明确指示错误原因。请参见[错误信息](https://help.aliyun.com/zh/model-studio/error-code)进行解决。

```json
{
    "request_id": "31f808fd-8eef-9004-xxxxx",
    "code": "InvalidApiKey",
    "message": "Invalid API-key provided."
}
```

