# 通义万相-首尾帧生视频API参考

参与者：米昵、桐江 等 **5** 人

更新时间：2025-11-26 13:55:50

[产品详情](https://www.aliyun.com/product/bailian)

[我的收藏](https://help.aliyun.com/my_favorites.html)

通义万相首尾帧生视频模型基于 **首帧图像** 、 **尾帧图像和文本提示词** ，生成一段平滑过渡的视频。支持的能力包括：

* **基础能力** ：视频时长固定（5秒）、指定视频分辨率（480P/720P/1080P）、智能改写prompt、添加水印。
* **特效模板** ：仅输入首帧图片，并选择一个特效模板，即可生成具有特定动态效果的视频。

 **快速入口：** [通义万相官网在线体验](https://tongyi.aliyun.com/wanxiang/generate/video/first-and-last-frame)** ｜** [视频特效列表](https://help.aliyun.com/zh/model-studio/wanx-video-effects)

**说明**

通义万相官网的功能与API支持的能力可能存在差异。本文档以API的实际能力为准，并会随功能更新及时同步。

## 模型概览

|          |  |  |
| -------- | - | - |
|          |  |  |
| -------- |  |  |

| **模型功能** | **输入示例**                                                                                | **输出视频**                                                                               |
| ------------------ | ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| **首帧图片** | **尾帧图片**                                                                                | **提示词**                                                                                 |
| 首尾帧生视频       | ![first_frame](https://help-static-aliyun-doc.aliyuncs.com/assets/img/zh-CN/8239161571/p944793.png) | ![last_frame](https://help-static-aliyun-doc.aliyuncs.com/assets/img/zh-CN/9239161571/p944794.png) |

<video id="fce4e060d34r7" name="24376238c6b4bc59486eeb7bb4012bfe3b329502da56ad7fc64e0b7a6746fd56.mp4" data-tag="video" src="https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20250704/mqqldq/24376238c6b4bc59486eeb7bb4012bfe3b329502da56ad7fc64e0b7a6746fd56.mp4" controls="" class="video" title="通义万相-图生视频-基于首尾帧" alt="通义万相-图生视频-基于首尾帧" controlslist="nodownload"></video>
 |
| 视频特效      | ![首尾帧生视频-视频特效-demo](https://help-static-aliyun-doc.aliyuncs.com/assets/img/zh-CN/8150385571/p1000087.png) | 无                                                                                               | 无 | 
<video id="71c2663436eu3" name="首尾帧-视频特效-结果.mp4" data-tag="video" src="https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20250821/qaodio/%E9%A6%96%E5%B0%BE%E5%B8%A7-%E8%A7%86%E9%A2%91%E7%89%B9%E6%95%88-%E7%BB%93%E6%9E%9C.mp4" controls="" class="video" title="通义万相-图生视频-基于首尾帧" alt="通义万相-图生视频-基于首尾帧" controlslist="nodownload"></video>

> 使用“唐韵翩然”特效，template设置为“hanfu-1” |

|          |  |  |
| -------- | - | - |
| -------- |  |  |

| **模型名称（model）**       | **模型简介**                                                    | **输出视频规格**                                                      |
| --------------------------------- | --------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| wan2.2-kf2v-flash `<b>推荐</b>` | 万相2.2极速版（无声视频）较2.1模型速度提升50%，稳定性与成功率全面提升 | 分辨率档位：480P、720P、1080P视频时长：5秒固定规格：30fps、MP4（H.264编码） |
| wanx2.1-kf2v-plus                 | 万相2.1专业版（无声视频）复杂运动，物理规律还原，画面细腻             | 分辨率档位：720P视频时长：5秒固定规格：30fps、MP4（H.264编码）              |

**说明**

调用前，请查阅各地域支持的[模型列表与价格](https://help.aliyun.com/zh/model-studio/models#6a59ecfcads1g)。

## 前提条件

在调用前，需要[获取API Key](https://help.aliyun.com/zh/model-studio/get-api-key)，再[配置API Key到环境变量](https://help.aliyun.com/zh/model-studio/configure-api-key-through-environment-variables)。如果通过SDK进行调用，请[安装DashScope SDK](https://help.aliyun.com/zh/model-studio/install-sdk)。目前，该SDK已支持Python和Java。

**重要**

北京和新加坡地域拥有独立的 **API Key **与 **请求地址** ，不可混用，跨地域调用将导致鉴权失败或服务报错。

## HTTP调用

由于图生视频任务耗时较长（通常为1-5分钟），API采用异步调用。整个流程包含 **“创建任务 -> 轮询获取”** 两个核心步骤，具体如下：

> 具体耗时受限于排队任务数和服务执行情况，请在获取结果时耐心等待。

### 步骤1：创建任务获取任务ID

 **北京地域** ：`POST https://dashscope.aliyuncs.com/api/v1/services/aigc/image2video/video-synthesis`

 **新加坡地域** ：`POST https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/image2video/video-synthesis`

**说明**

* 创建成功后，使用接口返回的 `task_id` 查询结果，task_id 有效期为 24 小时。 **请勿重复创建任务** ，轮询获取即可。
* 新手指引请参见[Postman](https://help.aliyun.com/zh/model-studio/first-call-to-image-and-video-api)。

| #### 请求参数 |
| ------------- |

首尾帧生视频:

根据首帧、尾帧和prompt生成视频。

```curl
curl --location 'https://dashscope.aliyuncs.com/api/v1/services/aigc/image2video/video-synthesis' \
    -H 'X-DashScope-Async: enable' \
    -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
    -H 'Content-Type: application/json' \
    -d '{
    "model": "wan2.2-kf2v-flash",
    "input": {
        "first_frame_url": "https://wanx.alicdn.com/material/20250318/first_frame.png",
        "last_frame_url": "https://wanx.alicdn.com/material/20250318/last_frame.png",
        "prompt": "写实风格，一只黑色小猫好奇地看向天空，镜头从平视逐渐上升，最后俯拍它的好奇的眼神。"
    },
    "parameters": {
        "resolution": "480P",
        "prompt_extend": true
    }
}'
```

使用Base64:

首帧first_frame_url和尾帧last_frame_url参数支持传入图像的 Base64 编码字符串。先下载[first_frame_base64](https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20250722/vzjwiv/first_frame_base64.txt)和[last_frame_base64](https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20250722/qbtevh/last_frame_base64.txt)文件，并将完整内容粘贴至对应参数中。

格式参见[输入图像](https://help.aliyun.com/zh/model-studio/image-to-video-by-first-and-last-frame-api-reference?spm=a2c4g.11186623.help-menu-2400256.d_2_3_1.6bdd7841n3fH58&scm=20140722.H_2880649._.OR_help-T_cn~zh-V_1#16b7ccc98dvhb)。

```curl
curl --location 'https://dashscope.aliyuncs.com/api/v1/services/aigc/image2video/video-synthesis' \
    -H 'X-DashScope-Async: enable' \
    -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
    -H 'Content-Type: application/json' \
    -d '{
    "model": "wanx2.1-kf2v-plus",
    "input": {
        "first_frame_url": "data:image/png;base64,GDU7MtCZzEbTbmRZ......",
        "last_frame_url": "data:image/png;base64,VBORw0KGgoAAAANSUh......",
        "prompt": "写实风格，一只黑色小猫好奇地看向天空，镜头从平视逐渐上升，最后俯拍它的好奇的眼神。"
    },
    "parameters": {
        "resolution": "720P",
        "prompt_extend": true
    }
}'
```

使用视频特效:

必须传入 `first_frame_url`和 `template`，无需传入prompt和last_frame_url。

不同模型支持不同的特效模板。调用前请查阅[视频特效列表](https://help.aliyun.com/zh/model-studio/wanx-video-effects)，以免调用失败。

```curl
curl --location 'https://dashscope.aliyuncs.com/api/v1/services/aigc/image2video/video-synthesis' \
    -H 'X-DashScope-Async: enable' \
    -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
    -H 'Content-Type: application/json' \
    -d '{
    "model": "wanx2.1-kf2v-plus",
    "input": {
        "first_frame_url": "https://ty-yuanfang.oss-cn-hangzhou.aliyuncs.com/lizhengjia.lzj/tmp/11.png",
        "template": "hanfu-1"
    },
    "parameters": {
        "resolution": "720P",
        "prompt_extend": true
    }
}'
```

使用反向提示词:

通过 negative_prompt 指定生成的视频避免出现“人物”元素。

```curl
curl --location 'https://dashscope.aliyuncs.com/api/v1/services/aigc/image2video/video-synthesis' \
    -H 'X-DashScope-Async: enable' \
    -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
    -H 'Content-Type: application/json' \
    -d '{
    "model": "wanx2.1-kf2v-plus",
    "input": {
        "first_frame_url": "https://wanx.alicdn.com/material/20250318/first_frame.png",
        "last_frame_url": "https://wanx.alicdn.com/material/20250318/last_frame.png",
        "prompt": "写实风格，一只黑色小猫好奇地看向天空，镜头从平视逐渐上升，最后俯拍它的好奇的眼神。",
        "negative_prompt": "人物"
    },
    "parameters": {
        "resolution": "720P",
        "prompt_extend": true
    }
}'
```


| ##### 请求头（Headers）                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Content-Type **`<i>string</i>` **（必选）**请求内容类型。此参数必须设置为 `application/json`。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| **Authorization**`<i>string</i>`**（必选）**请求身份认证。接口使用阿里云百炼API-Key进行身份认证。示例值：Bearer sk-xxxx。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| **X-DashScope-Async **`<i>string</i>` **（必选）**异步处理配置参数。HTTP请求只支持异步，**必须设置为** `<b>enable</b>`。**重要**缺少此请求头将报错：“current user api does not support synchronous calls”。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| ##### 请求体（Request Body）                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| **model** `<i>string</i>` **（必选）**模型名称。示例值：**wan2.2-kf2v-flash**。详情参见[模型列表与价格](https://help.aliyun.com/zh/model-studio/models#3511187847vep)。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| **input** `<i>object</i>` **（必选）**输入的基本信息，如提示词等。**属性****prompt** `<i>string</i>` （可选）文本提示词。支持中英文，长度不超过800个字符，每个汉字/字母占一个字符，超过部分会自动截断。如果首尾帧的主体和场景变化较大，建议描写变化过程，例如运镜过程（镜头向左移动）、或者主体运动过程（人向前奔跑）。示例值：一只黑色小猫好奇地看向天空， **镜头从平视逐渐上升** ，最后**俯拍**它的好奇的眼神。提示词的使用技巧请参见[文生视频/图生视频Prompt指南](https://help.aliyun.com/zh/model-studio/text-to-video-prompt)。**negative_prompt** `<i>string</i>` （可选）反向提示词，用来描述不希望在视频画面中看到的内容，可以对视频画面进行限制。支持中英文，长度不超过500个字符，超过部分会自动截断。示例值：低分辨率、错误、最差质量、低质量、残缺、多余的手指、比例不良等。**first_frame_url** `<i>string</i>` **（必选）**首帧图像的URL或 Base64 编码数据。**输出视频的宽高比将以此图像为基准。**图像限制：* 图像格式：JPEG、JPG、PNG（不支持透明通道）、BMP、WEBP。* 图像分辨率：图像的宽度和高度范围为[360, 2000]，单位为像素。* 文件大小：不超过10MB。输入图像说明：1. 使用公网可访问URL* 支持 HTTP 或 HTTPS 协议。**本地文件可通过**[上传文件获取临时URL](https://help.aliyun.com/zh/model-studio/get-temporary-file-url)。* 示例值：`https://wanx.alicdn.com/material/20250318/first_frame.png`。1. 传入 Base64 编码图像后的字符串* 数据格式：`data:{MIME_type};base64,{base64_data}`。* 示例值：`data:image/png;base64,GDU7MtCZzEbTbmRZ......`。* 具体参见[输入图像](https://help.aliyun.com/zh/model-studio/image-to-video-by-first-and-last-frame-api-reference?spm=a2c4g.11186623.help-menu-2400256.d_2_3_1.6bdd7841n3fH58&scm=20140722.H_2880649._.OR_help-T_cn~zh-V_1#16b7ccc98dvhb)。**last_frame_url** `<i>string</i>` （可选）尾帧图像的URL或 Base64 编码数据。图像限制：* 图像格式：JPEG、JPG、PNG（不支持透明通道）、BMP、WEBP。* 图像分辨率：图像的宽度和高度范围为[360, 2000]，单位为像素。尾帧图像分辨率可与首帧不同，无需强制对齐。* 文件大小：不超过10MB。输入图像说明：1. 使用公网可访问URL* 支持 HTTP 或 HTTPS 协议。**本地文件可通过**[上传文件获取临时URL](https://help.aliyun.com/zh/model-studio/get-temporary-file-url)。* 示例值：`https://wanx.alicdn.com/material/20250318/last_frame.png`。1. 使用 Base64 编码图像文件* 数据格式：`data:{MIME_type};base64,{base64_data}`。* 示例值：`data:image/png;base64,VBORw0KGgoAAAANSUh......`。（编码字符串过长，仅展示片段）* 具体参见[输入图像](https://help.aliyun.com/zh/model-studio/image-to-video-by-first-and-last-frame-api-reference?spm=a2c4g.11186623.help-menu-2400256.d_2_3_1.6bdd7841n3fH58&scm=20140722.H_2880649._.OR_help-T_cn~zh-V_1#16b7ccc98dvhb)。**template** `<i>string</i>` （可选）视频特效模板的名称。使用此参数时，仅需传入 `first_frame_url`。不同模型支持不同的特效模板。调用前请查阅[视频特效列表](https://help.aliyun.com/zh/model-studio/wanx-video-effects)，以免调用失败。示例值：hufu-1，表示使用“唐韵翩然”特效。 |
| **parameters** `<i>object</i>` （可选）视频处理参数。**属性****resolution** `<i>string</i>` （可选）**重要****resolution**直接影响费用，同一模型：1080P > 720P > 480P，调用前请确认[模型价格](https://help.aliyun.com/zh/model-studio/models#3511187847vep)。生成的视频分辨率档位。仅用于调整视频的清晰度（总像素），不改变视频的宽高比， **视频宽高比将与首帧图像 first_frame_url 的宽高比保持一致** 。此参数的默认值和可用枚举值依赖于 model 参数，规则如下：* wan2.2-kf2v-flash：可选值：480P、720P、1080P。默认值为 `720P`。* **wanx2.1-kf2v-plus**：可选值：720P。默认值为 `720P`。示例值：720P。**duration** `<i>integer</i>` （可选）**重要**duration直接影响费用，按秒计费，调用前请确认[模型价格](https://help.aliyun.com/zh/model-studio/models#3511187847vep)。视频生成时长，单位为秒。当前参数值固定为5，且不支持修改。模型将始终生成5秒时长的视频。**prompt_extend **`<i>bool</i>` （可选）是否开启prompt智能改写。开启后使用大模型对输入prompt进行智能改写。对于较短的prompt生成效果提升明显，但会增加耗时。* true：默认值，开启智能改写。* false：不开启智能改写。示例值：true。**watermark** `<i>bool</i>` （可选）是否添加水印标识，水印位于图片右下角，文案为“AI生成”。* false：默认值，不添加水印。* true：添加水印。示例值：false。**seed **`<i>integer</i>` （可选）随机数种子。取值范围是 `[0, 2147483647]`。未指定时，系统自动生成随机种子。若需提升生成结果的可复现性，建议固定seed值。请注意，由于模型生成具有概率性，即使使用相同 seed，也不能保证每次生成结果完全一致。示例值：12345。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |

| #### 响应参数 |
| ------------- |

成功响应:

请保存 task_id，用于查询任务状态与结果。

```json
{
    "output": {
        "task_status": "PENDING",
        "task_id": "0385dc79-5ff8-4d82-bcb6-xxxxxx"
    },
    "request_id": "4909100c-7b5a-9f92-bfe5-xxxxxx"
}
```

异常响应:

创建任务失败，请参见[错误信息](https://help.aliyun.com/zh/model-studio/error-code)进行解决。

```json
{
    "code":"InvalidApiKey",
    "message":"Invalid API-key provided.",
    "request_id":"fb53c4ec-1c12-4fc4-a580-xxxxxx"
}
```


| **output** `<i>object</i>`任务输出信息。属性**task_id** `<i>string</i>`任务ID。查询有效期24小时。**task_status** `<i>string</i>`任务状态。**枚举值*** PENDING：任务排队中* RUNNING：任务处理中* SUCCEEDED：任务执行成功* FAILED：任务执行失败* CANCELED：任务已取消* UNKNOWN：任务不存在或状态未知 |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **request_id **`<i>string</i>`请求唯一标识。可用于请求明细溯源和问题排查。                                                                                                                                                                                                                                                     |
| **code **`<i>string</i>`请求失败的错误码。请求成功时不会返回此参数，详情请参见[错误信息](https://help.aliyun.com/zh/model-studio/error-code)。                                                                                                                                                                                    |
| **message **`<i>string</i>`请求失败的详细信息。请求成功时不会返回此参数，详情请参见[错误信息](https://help.aliyun.com/zh/model-studio/error-code)。                                                                                                                                                                               |

### 步骤2：根据任务ID查询结果

 **北京地域** ：`GET https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}`

 **新加坡地域** ：`GET https://dashscope-intl.aliyuncs.com/api/v1/tasks/{task_id}`

**说明**

* **轮询建议** ：视频生成过程约需数分钟，建议采用**轮询**机制，并设置合理的查询间隔（如 15 秒）来获取结果。
* **任务状态流转** ：PENDING（排队中）→ RUNNING（处理中）→ SUCCEEDED（成功）/ FAILED（失败）。
* **结果链接** ：任务成功后返回视频链接，有效期为  **24 小时** 。建议在获取链接后立即下载并转存至永久存储（如[阿里云 OSS](https://help.aliyun.com/zh/oss/user-guide/what-is-oss)）。
* **task_id 有效期** ： **24小时** ，超时后将无法查询结果，接口将返回任务状态为 `UNKNOWN`。
* **QPS 限制** ：查询接口默认QPS为20。如需更高频查询或事件通知，建议[配置异步任务回调](https://help.aliyun.com/zh/model-studio/async-task-api)。
* **更多操作** ：如需批量查询、取消任务等操作，请参见[管理异步任务](https://help.aliyun.com/zh/model-studio/manage-asynchronous-tasks#f26499d72adsl)。

| #### 请求参数 |
| ------------- |


查询任务结果:

请将 `86ecf553-d340-4e21-xxxxxxxxx`替换为真实的task_id。

```curl
curl -X GET https://dashscope.aliyuncs.com/api/v1/tasks/86ecf553-d340-4e21-xxxxxxxxx \
--header "Authorization: Bearer $DASHSCOPE_API_KEY"
```


| #####**请求头（Headers）**                                                                                                  |
| --------------------------------------------------------------------------------------------------------------------------------- |
| **Authorization**`<i>string</i>`**（必选）**请求身份认证。接口使用阿里云百炼API-Key进行身份认证。示例值：Bearer sk-xxxx。 |
| #####**URL路径参数（Path parameters）**                                                                                     |
| **task_id** `<i>string</i>`**（必选）**任务ID。                                                                           |


#### **响应参数**


| **output **`<i data-spm-anchor-id="a2c4g.11186623.0.i40.247676d74Gqo6M">object</i>`任务输出信息。**属性****task_id** `<i>string</i>`任务ID。查询有效期24小时。**task_status** `<i>string</i>`任务状态。**枚举值*** PENDING：任务排队中* RUNNING：任务处理中* SUCCEEDED：任务执行成功* FAILED：任务执行失败* CANCELED：任务已取消* UNKNOWN：任务不存在或状态未知**轮询过程中的状态流转：*** PENDING（排队中） → RUNNING（处理中）→ SUCCEEDED（成功）/ FAILED（失败）。* 初次查询状态通常为 PENDING（排队中）或 RUNNING（处理中）。* 当状态变为 SUCCEEDED 时，响应中将包含生成的视频url。* 若状态为 FAILED，请检查错误信息并重试。**submit_time** `<i>string</i>`任务提交时间。格式为 YYYY-MM-DD HH:mm:ss.SSS。**scheduled_time** `<i>string</i>`任务执行时间。格式为 YYYY-MM-DD HH:mm:ss.SSS。**end_time** `<i>string</i>`任务完成时间。格式为 YYYY-MM-DD HH:mm:ss.SSS。**video_url **`<i>string</i>`视频URL。仅在 task_status 为 SUCCEEDED 时返回。链接有效期24小时，可通过此URL下载视频。视频格式为MP4（H.264 编码）。**orig_prompt** `<i>string</i>`原始输入的prompt，对应请求参数 `prompt`。**actual_prompt** `<i>string</i>`开启 prompt 智能改写后，返回实际使用的优化后 prompt。若未开启该功能，则不返回此字段。**code **`<i>string</i>`请求失败的错误码。请求成功时不会返回此参数，详情请参见[错误信息](https://help.aliyun.com/zh/model-studio/error-code)。**message **`<i>string</i>`请求失败的详细信息。请求成功时不会返回此参数，详情请参见[错误信息](https://help.aliyun.com/zh/model-studio/error-code)。 |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **usage** `<i>object</i>`输出信息统计。只对成功的结果计数。**属性****video_duration** `<i>integer</i>`生成视频的时长，单位秒。枚举值为5。计费公式：费用 = 视频秒数 × 单价。**video_count** `<i>integer</i>`生成视频的数量。固定为1。**video_ratio** `<i>string</i>`当前仅当2.1模型返回该值。生成视频的比例，固定为standard。**SR** `<i>integer</i>`当前仅当2.2模型返回该值。生成视频的分辨率档位，枚举值为480、720、1080。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| **request_id **`<i>string</i>`请求唯一标识。可用于请求明细溯源和问题排查。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |

任务执行成功:


视频URL仅保留24小时，超时后会被自动清除，请及时保存生成的视频。

```json
{
    "request_id": "ec016349-6b14-9ad6-8009-xxxxxx",
    "output": {
        "task_id": "3f21a745-9f4b-4588-b643-xxxxxx",
        "task_status": "SUCCEEDED",
        "submit_time": "2025-04-18 10:36:58.394",
        "scheduled_time": "2025-04-18 10:37:13.802",
        "end_time": "2025-04-18 10:45:23.004",
        "video_url": "https://dashscope-result-wlcb.oss-cn-wulanchabu.aliyuncs.com/xxx.mp4?xxxxx",
        "orig_prompt": "写实风格，一只黑色小猫好奇地看向天空，镜头从平视逐渐上升，最后俯拍它的好奇的眼神。",
        "actual_prompt": "写实风格，一只黑色小猫好奇地看向天空，镜头从平视逐渐上升，最后俯拍它的好奇的眼神。小猫的黄色眼睛明亮有神，毛发光滑，胡须清晰可见。背景是简单的浅色墙面，突显小猫的黑色身影。近景特写，强调小猫的表情变化和眼神细节。"
    },
    "usage": {
        "video_duration": 5,
        "video_count": 1,
        "SR": 480
    }
}
```

任务执行失败:


若任务执行失败，task_status将置为 FAILED，并提供错误码和信息。请参见[错误信息](https://help.aliyun.com/zh/model-studio/error-code)进行解决。

```json
{
    "request_id": "e5d70b02-ebd3-98ce-9fe8-759d7d7b107d",
    "output": {
        "task_id": "86ecf553-d340-4e21-af6e-a0c6a421c010",
        "task_status": "FAILED",
        "code": "InvalidParameter",
        "message": "The size is not match xxxxxx"
    }
}
```

任务查询过期:


task_id查询有效期为 24 小时，超时后将无法查询，返回以下报错信息。

```json
{
    "request_id": "a4de7c32-7057-9f82-8581-xxxxxx",
    "output": {
        "task_id": "502a00b1-19d9-4839-a82f-xxxxxx",
        "task_status": "UNKNOWN"
    }
}
```



## **使用限制**

* **数据时效** ：任务task_id和视频url均只保留 24 小时，过期后将无法查询或下载。
* **音频支持** ：当前仅支持生成无声视频，不支持音频输出。如有需要，可通过[语音合成](https://help.aliyun.com/zh/model-studio/speech-recognition-api-reference/)生成音频。
* **内容审核** ：输入prompt 和图像、输出视频均会经过内容安全审核，含违规内容将返回 “IPInfringementSuspect”或“DataInspectionFailed”错误，详情请参见[错误信息](https://help.aliyun.com/zh/model-studio/error-code)。

## **键参数说明**

### **输入图像**

输入图像 `first_frame_url`和 `last_frame_url`参数均支持以下方式传入：

方式一：公网URL

方式二：Base 64编码

方式三：本地文件路径（仅限 SDK）

* 一个公网可直接访问的地址，支持 HTTP/HTTPS。**本地文件可通过**[上传文件获取临时URL](https://help.aliyun.com/zh/model-studio/get-temporary-file-url)。
* 示例值：`https://example.com/images/cat.png`。
