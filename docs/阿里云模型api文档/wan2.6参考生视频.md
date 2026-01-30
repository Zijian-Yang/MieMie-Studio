# 通义万相-参考生视频-API参考

参与者：米昵、闻奕 等 **4** 人

更新时间：2026-01-26 23:13:48

**复制为 MD 格式**[产品详情](https://www.aliyun.com/product/bailian)

[我的收藏](https://help.aliyun.com/my_favorites.html)

通义万相参考生视频模型，参考输入视频或图像中的角色形象（视频还可参考音色），搭配提示词生成保持角色一致性的视频。支持的能力包括：

* **基础能力** ：支持整数秒级视频时长（2～10秒）、指定视频分辨率（720P/1080P）、添加水印。
* **音频能力** ：支持通过提示词生成声音，可参考输入视频的音色。
* **多镜头叙事** ：支持生成包含多个镜头的视频，并且在镜头切换时保持主体一致性。

 **快速入口：** [通义万相官网](https://tongyi.aliyun.com/wan/generate/video/text-to-video)

**说明**

通义万相官网的功能与API支持的能力可能存在差异。本文档以API的实际能力为准，并会随功能更新及时同步。

## 模型概览

|          |  |  |
| -------- | - | - |
| -------- |  |  |

| **模型名称（model）** | **模型简介**                                                                                                                  | **输出视频规格**                                                             |
| --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| wan2.6-r2v `<b>推荐</b>`  | 万相2.6**（有声视频）**基于参考视频或图像的角色形象（视频还可参考音色），默认生成有声视频，支持多镜头叙事（自动分镜），支持自动配音 | 分辨率档位：720P、1080P视频时长：2秒～10秒（整数）固定规格：30fps、MP4 (H.264编码) |

## 前提条件

您需要已[获取API Key](https://help.aliyun.com/zh/model-studio/get-api-key)并[配置API Key到环境变量](https://help.aliyun.com/zh/model-studio/configure-api-key-through-environment-variables)。

**重要**

北京和新加坡地域拥有独立的 **API Key **与 **请求地址** ，不可混用，跨地域调用将导致鉴权失败或服务报错。

## HTTP调用

由于文生视频任务耗时较长（通常为1-5分钟），API采用异步调用。整个流程包含 **“创建任务 -> 轮询获取”** 两个核心步骤，具体如下：

> 具体耗时受限于排队任务数和服务执行情况，请在获取结果时耐心等待。

### 步骤1：创建任务获取任务ID

 **北京地域** ：`POST https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis`

 **新加坡地域** ：`POST https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis`

 **弗吉尼亚地域** ：`POST https://dashscope-us.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis`

**说明**

* 创建成功后，使用接口返回的 `task_id` 查询结果，task_id 有效期为 24 小时。 **请勿重复创建任务** ，轮询获取即可。
* 新手指引请参见[Postman](https://help.aliyun.com/zh/model-studio/first-call-to-image-and-video-api)。

| #### 请求参数 |
| ------------- |


| ##### 请求头（Headers）                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Content-Type **`<i>string</i>` **（必选）**请求内容类型。此参数必须设置为 `application/json`。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| **Authorization**`<i>string</i>`**（必选）**请求身份认证。接口使用阿里云百炼API-Key进行身份认证。示例值：Bearer sk-xxxx。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| **X-DashScope-Async **`<i>string</i>` **（必选）**异步处理配置参数。HTTP请求只支持异步，**必须设置为** `<b>enable</b>`。**重要**缺少此请求头将报错：“current user api does not support synchronous calls”。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| ##### 请求体（Request Body）                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| **model** `<i>string</i>` **（必选）**模型名称。模型列表与价格详见[模型价格](https://help.aliyun.com/zh/model-studio/model-pricing#5c3d28ad8a4x8)。示例值：wan2.6-r2v。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| **input** `<i>object</i>` **（必选）**输入的基本信息，如提示词等。**属性****prompt** `<i>string</i>` **（必选）**文本提示词。用来描述生成视频中期望包含的元素和视觉特点。支持中英文，每个汉字、字母、标点占一个字符，超过部分会自动截断。* wan2.6-r2v：长度不超过1500个字符。角色引用说明：通过" **character1、character2** "这类标识引用参考角色，每个参考（视频或图像）仅包含单一角色。模型仅通过此方式识别参考中的角色。示例值：character1在沙发上开心地看电影。提示词的使用技巧请参见[文生视频/图生视频Prompt指南](https://help.aliyun.com/zh/model-studio/text-to-video-prompt)。**negative_prompt** `<i>string</i>` （可选）反向提示词，用来描述不希望在视频画面中看到的内容，可以对视频画面进行限制。支持中英文，长度不超过500个字符，超过部分会自动截断。示例值：低分辨率、错误、最差质量、低质量、残缺、多余的手指、比例不良等。**reference_urls** `<i>array[string]</i>` **（必选）****重要**reference_urls直接影响费用，计费规则请参见[计费与限流](https://help.aliyun.com/zh/model-studio/wan-video-to-video-api-reference?spm=a2c4g.11186623.help-menu-2400256.d_2_3_3.94276968rmPIlU#f79461ca408qn)。上传的参考文件 URL 数组，支持传入视频和图像。用于提取角色形象与音色（如有），以生成符合参考特征的视频。* 每个 URL 可指向 **一张图像** 或  **一段视频** ：* 图像数量：0～5* 视频数量：0～3* 总数限制：图像 + 视频 ≤ 5* 传入多个参考文件时，按照数组顺序定义角色的顺序。即第 1 个 URL 对应 character1，第 2 个对应 character2，以此类推。* 每个参考文件仅包含一个主体角色。例如 character1 为小女孩，character2 为闹钟。* URL支持 HTTP 或 HTTPS 协议。**本地文件可通过**[上传文件获取临时URL](https://help.aliyun.com/zh/model-studio/get-temporary-file-url)。参考视频要求：* 格式：MP4、MOV。* 时长：1s～30s。* 视频大小：不超过100MB。参考图像要求：* 格式：JPEG、JPG、PNG（不支持透明通道）、BMP、WEBP。* 分辨率：宽高均需在 [240, 5000]像素之间。* 图像大小：不超过10MB。示例值：["https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/xxx.mp4", "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/xxx.jpg"]。**已废弃字段** |
| **parameters** `<i>object</i>` （可选）图像处理参数。如设置视频分辨率、开启prompt智能改写、添加水印等。**属性****size** `<i>string</i>` （可选）**重要*** size直接影响费用，费用 = 单价（基于分辨率）× 时长（秒）。同一模型：1080P > 720P ，请在调用前确认[模型价格](https://help.aliyun.com/zh/model-studio/model-pricing#5c3d28ad8a4x8)。* size必须设置为具体数值（如 `1280*720`），而不是 1:1或720P。指定生成的视频分辨率，格式为 `<b>宽*高</b>`。该参数的默认值和可用枚举值依赖于 model 参数，规则如下：* wan2.6-r2v：默认值为 `1920*1080`（1080P）。可选分辨率：720P、1080P对应的所有分辨率。720P档位：可选的视频分辨率及其对应的视频宽高比为：* `1280*720`：16:9。* `720*1280`：9:16。* `960*960`：1:1。* `1088*832`：4:3。* `832*1088`：3:4。1080P档位：可选的视频分辨率及其对应的视频宽高比为：* `1920*1080`： 16:9。* `1080*1920`： 9:16。* `1440*1440`： 1:1。* `1632*1248`： 4:3。* `1248*1632`： 3:4。**duration** `<i>integer</i>` （可选）**重要**duration直接影响费用。费用 = 单价（基于分辨率）× 时长（秒）。生成视频的时长，单位为秒。* wan2.6-r2v：取值为[2, 10]之间的整数。默认值为5。示例值：5。**shot_type** `<i>string</i>` （可选）指定生成视频的镜头类型，即视频是由一个连续镜头还是多个切换镜头组成。参数优先级：`shot_type > prompt`。例如，若 shot_type设置为"single"，即使 prompt 中包含“生成多镜头视频”，模型仍会输出单镜头视频。可选值：* single：默认值，输出单镜头视频* multi：输出多镜头视频。示例值：single。**说明**当希望严格控制视频的叙事结构（如产品展示用单镜头、故事短片用多镜头），可通过此参数指定。**watermark** `<i>boolean</i>` （可选）是否添加水印标识，水印位于视频右下角，文案固定为“AI生成”。* false：默认值，不添加水印。* true：添加水印。示例值：false。**seed **`<i>integer</i>` （可选）随机数种子，取值范围为 `[0, 2147483647]`。未指定时，系统自动生成随机种子。若需提升生成结果的可复现性，建议固定seed值。请注意，由于模型生成具有概率性，即使使用相同 seed，也不能保证每次生成结果完全一致。示例值：12345。                                                                                 |

单角色参考


参考视频或图像中角色的形象（视频还可参考音色），设置shot_type为multi，生成多镜头视频。

```curl
curl --location 'https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis' \
    -H 'X-DashScope-Async: enable' \
    -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
    -H 'Content-Type: application/json' \
    -d '{
    "model": "wan2.6-r2v",
    "input": {
        "prompt": "character1一边喝奶茶，一边随着音乐即兴跳舞。",
        "reference_urls":["https://cdn.wanx.aliyuncs.com/static/demo-wan26/vace.mp4"]
    },
    "parameters": {
        "size": "1280*720",
        "duration": 5,
        "shot_type":"multi"
    }
}'
```

多角色参考


基于人物与道具的参考视频或图像，通过提示词定义两者间的联系，设置shot_type为multi，生成多镜头视频。您可以在提示词中多次引用同一角色。

```curl
curl --location 'https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis' \
    -H 'X-DashScope-Async: enable' \
    -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
    -H 'Content-Type: application/json' \
    -d '{
    "model": "wan2.6-r2v",
    "input": {
        "prompt": "character1对character2说: “I’ll rely on you tomorrow morning!” character2 回答: “You can count on me!”",
        "reference_urls": [
            "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20251217/dlrrly/%E5%B0%8F%E5%A5%B3%E5%AD%A91%E8%8B%B1%E6%96%872.mp4",
            "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20251217/fkxknn/%E9%93%83%E9%93%83.mp4"
        ]
    },
    "parameters": {
        "size": "1280*720",
        "duration": 10,
        "shot_type": "multi"
    }
}'
```


#### 响应参数


| **output** `<i>object</i>`任务输出信息。**属性****task_id** `<i>string</i>`任务ID。查询有效期24小时。**task_status** `<i>string</i>`任务状态。**枚举值*** PENDING：任务排队中* RUNNING：任务处理中* SUCCEEDED：任务执行成功* FAILED：任务执行失败* CANCELED：任务已取消* UNKNOWN：任务不存在或状态未知 |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **request_id **`<i>string</i>`请求唯一标识。可用于请求明细溯源和问题排查。                                                                                                                                                                                                                                                         |
| **code **`<i>string</i>`请求失败的错误码。请求成功时不会返回此参数，详情请参见[错误信息](https://help.aliyun.com/zh/model-studio/error-code)。                                                                                                                                                                                        |
| **message **`<i>string</i>`请求失败的详细信息。请求成功时不会返回此参数，详情请参见[错误信息](https://help.aliyun.com/zh/model-studio/error-code)。                                                                                                                                                                                   |

成功响应


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

异常响应


创建任务失败，请参见[错误信息](https://help.aliyun.com/zh/model-studio/error-code)进行解决。

```json
{
    "code": "InvalidApiKey",
    "message": "No API-key provided.",
    "request_id": "7438d53d-6eb8-4596-8835-xxxxxx"
}
```


### 步骤2：根据任务ID查询结果

 **北京地域** ：`GET https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}`

 **新加坡地域** ：`GET https://dashscope-intl.aliyuncs.com/api/v1/tasks/{task_id}`

 **弗吉尼亚地域：** `GET https://dashscope-us.aliyuncs.com/api/v1/tasks/{task_id}`

**说明**

* **轮询建议** ：视频生成过程约需数分钟，建议采用**轮询**机制，并设置合理的查询间隔（如 15 秒）来获取结果。
* **任务状态流转** ：PENDING（排队中）→ RUNNING（处理中）→ SUCCEEDED（成功）/ FAILED（失败）。
* **结果链接** ：任务成功后返回视频链接，有效期为  **24 小时** 。建议在获取链接后立即下载并转存至永久存储（如[阿里云 OSS](https://help.aliyun.com/zh/oss/user-guide/what-is-oss)）。
* **task_id 有效期** ： **24小时** ，超时后将无法查询结果，接口将返回任务状态为 `UNKNOWN`。
* **QPS 限制** ：查询接口默认QPS为20。如需更高频查询或事件通知，建议[配置异步任务回调](https://help.aliyun.com/zh/model-studio/async-task-api)。
* **更多操作** ：如需批量查询、取消任务等操作，请参见[管理异步任务](https://help.aliyun.com/zh/model-studio/manage-asynchronous-tasks#f26499d72adsl)。

| #### 请求参数                                                                                                                   | 查询任务结果请将 `86ecf553-d340-4e21-xxxxxxxxx`替换为真实的task_id。> 若使用新加坡地域的模型，需将base_url替换为https://dashscope-intl.aliyuncs.com/api/v1/tasks/86ecf553-d340-4e21-xxxxxxxxx

```curl
curl -X GET https://dashscope.aliyuncs.com/api/v1/tasks/86ecf553-d340-4e21-xxxxxxxxx \
--header "Authorization: Bearer $DASHSCOPE_API_KEY"
```

|                                                                                                                                   |  |
| --------------------------------------------------------------------------------------------------------------------------------- | - |
| #####**请求头（Headers）**                                                                                                  |  |
| **Authorization**`<i>string</i>`**（必选）**请求身份认证。接口使用阿里云百炼API-Key进行身份认证。示例值：Bearer sk-xxxx。 |  |
| #####**URL路径参数（Path parameters）**                                                                                     |  |
| **task_id** `<i>string</i>`**（必选）**任务ID。                                                                           |  |

| #### **响应参数**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   | 任务执行成功 视频URL仅保留24小时，超时后会被自动清除，请及时保存生成的视频。

```json
{
    "request_id": "caa62a12-8841-41a6-8af2-xxxxxx",
    "output": {
        "task_id": "eff1443c-ccab-4676-aad3-xxxxxx",
        "task_status": "SUCCEEDED",
        "submit_time": "2025-12-16 00:25:59.869",
        "scheduled_time": "2025-12-16 00:25:59.900",
        "end_time": "2025-12-16 00:30:35.396",
        "orig_prompt": "character1在沙发上开心的看电影",
        "video_url": "https://dashscope-result-sh.oss-accelerate.aliyuncs.com/xxx.mp4?Expires=xxx"
    },
     "usage": {
        "duration": 10.0,
        "size": "1280*720",
        "input_video_duration": 5,
        "output_video_duration": 5,
        "video_count": 1,
        "SR": 720
    }
}
```
任务执行失败
若任务执行失败，task_status将置为 FAILED，并提供错误码和信息。请参见错误信息进行解决。

 
{
    "request_id": "e5d70b02-ebd3-98ce-9fe8-759d7d7b107d",
    "output": {
        "task_id": "86ecf553-d340-4e21-af6e-a0c6a421c010",
        "task_status": "FAILED",
        "code": "InvalidParameter",
        "message": "The size is not match xxxxxx"
    }
}
任务查询过期
task_id查询有效期为 24 小时，超时后将无法查询，返回以下报错信息。

 
{
    "request_id": "a4de7c32-7057-9f82-8581-xxxxxx",
    "output": {
        "task_id": "502a00b1-19d9-4839-a82f-xxxxxx",
        "task_status": "UNKNOWN"
    }
}



|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |  |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | - |
| **output **`<i>object</i>`任务输出信息。**属性****task_id** `<i>string</i>`**（必选）**任务ID。**task_status** `<i>string</i>`任务状态。**枚举值*** PENDING：任务排队中* RUNNING：任务处理中* SUCCEEDED：任务执行成功* FAILED：任务执行失败* CANCELED：任务已取消* UNKNOWN：任务不存在或状态未知**submit_time** `<i>string</i>`任务提交时间。格式为 YYYY-MM-DD HH:mm:ss.SSS。**scheduled_time** `<i>string</i>`任务执行时间。格式为 YYYY-MM-DD HH:mm:ss.SSS。**end_time** `<i>string</i>`任务完成时间。格式为 YYYY-MM-DD HH:mm:ss.SSS。**video_url **`<i>string</i>`视频URL。仅在 task_status 为 SUCCEEDED 时返回。链接有效期24小时，可通过此URL下载视频。视频格式为MP4（H.264 编码）。**orig_prompt** `<i>string</i>`原始输入的prompt，对应请求参数 `prompt`。**actual_prompt** `<i>string</i>`当 `prompt_extend=true` 时，系统会对输入 prompt 进行智能改写，此字段返回实际用于生成的优化后 prompt。若 `prompt_extend=false`，该字段不会返回。注意：wan2.6 模型无论 `prompt_extend` 取值如何，均不返回此字段。**code **`<i>string</i>`请求失败的错误码。请求成功时不会返回此参数，详情请参见[错误信息](https://help.aliyun.com/zh/model-studio/error-code)。**message **`<i>string</i>`请求失败的详细信息。请求成功时不会返回此参数，详情请参见[错误信息](https://help.aliyun.com/zh/model-studio/error-code)。 |  |
| **usage** `<i>object</i>`输出信息统计。只对成功的结果计数。**属性****input_video_duration** `<i>integer</i>`输入的参考视频的时长，单位秒。**output_video_duration** `<i>integer</i>`输出视频的时长，单位秒。**duration** `<i>float</i>`总视频时长。计费按duration时长计算。计算公式：`duration = input_video_duration + output_video_duration`。**SR** `<i>integer</i>`生成视频的分辨率档位。示例值：720。**size** `<i>string</i>`生成视频的分辨率。格式为“宽*高 *”* ，示例值：1280*720。**video_count** `<i>integer</i>`生成视频的数量。固定为1。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |  |
| **request_id **`<i>string</i>`请求唯一标识。可用于请求明细溯源和问题排查。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |  |

## **使用限制**

* **数据时效** ：任务task_id和 视频url均只保留 24 小时，过期后将无法查询或下载。
* **内容审核** ：输入的 prompt 和输出的视频均会经过内容安全审核，包含违规内容的请求将报错“IPInfringementSuspect”或“DataInspectionFailed”，具体参见[错误信息](https://help.aliyun.com/zh/model-studio/error-code)。
* **网络访问配置** ：视频链接存储于阿里云 OSS，如果业务系统因安全策略无法访问外部OSS链接，请将以下 OSS 域名加入网络访问白名单。

```plaintext
  # OSS域名列表
  dashscope-result-bj.oss-cn-beijing.aliyuncs.com
  dashscope-result-hz.oss-cn-hangzhou.aliyuncs.com
  dashscope-result-sh.oss-cn-shanghai.aliyuncs.com
  dashscope-result-wlcb.oss-cn-wulanchabu.aliyuncs.com
  dashscope-result-zjk.oss-cn-zhangjiakou.aliyuncs.com
  dashscope-result-sz.oss-cn-shenzhen.aliyuncs.com
  dashscope-result-hy.oss-cn-heyuan.aliyuncs.com
  dashscope-result-cd.oss-cn-chengdu.aliyuncs.com
  dashscope-result-gz.oss-cn-guangzhou.aliyuncs.com
  dashscope-result-wlcb-acdr-1.oss-cn-wulanchabu-acdr-1.aliyuncs.com
```

## **计费与限流**

* 模型免费额度和计费单价请参见[模型列表与价格](https://help.aliyun.com/zh/model-studio/models#577af209dc0rc)。
* 模型限流请参见[通义万相系列](https://help.aliyun.com/zh/model-studio/rate-limit#a729d7b6bar7y)。
* 计费说明：

  * 输入图像不计费，输入视频计费。
  * 采用 **输入视频时长 + 输出视频时长** 联合计费，按 **视频秒数** 计费。仅当查询结果接口返回 `task_status`为 `SUCCEEDED` 并成功生成视频后，才会计费。
  * 模型调用失败或处理错误不产生任何费用，也不消耗[新人免费额度](https://help.aliyun.com/zh/model-studio/new-free-quota)。

  **计费时长的计算规则**

  **总视频计费时长 = 输入视频计费时长 + 输出视频计费时长。**

  **输入视频计费时长** ：总输入计费时长不超过  **5 秒** 。参考素材总数（含图像+视频）均摊 5 秒总配额，作为单视频的截断上限值。各参考视频分别截断后，累加计算。

  * **输入1个参考文件** ：单视频截断上限为5s。
  * 若为视频：`输入计费时长=min(视频时长，5s)`。
  * 若为图像：免费。
  * **输入2个参考文件** ：单视频截断上限为2.5s。
  * 若1个视频+1张图像：`输入计费时长=min(视频<span class="help-letter-space"></span>1<span class="help-letter-space"></span>时长，2.5s)`。
  * 若2个视频：`输入计费时长=min(视频<span class="help-letter-space"></span>1<span class="help-letter-space"></span>时长，2.5s)+ min(视频<span class="help-letter-space"></span>2<span class="help-letter-space"></span>时长，2.5s)`。
  * **输入3个参考文件** ：单视频截断上限为1.65s。
  * 若1个视频+2张图像：`输入计费时长=min(视频<span class="help-letter-space"></span>1<span class="help-letter-space"></span>长度，1.65s)`。
  * 若3个视频：`输入计费时长=min(视频<span class="help-letter-space"></span>1<span class="help-letter-space"></span>长度，1.65s)+ min(视频<span class="help-letter-space"></span>2<span class="help-letter-space"></span>长度，1.65s)+min(视频<span class="help-letter-space"></span>3<span class="help-letter-space"></span>长度，1.65s)`。
  * **输入4个参考文件** ：单视频截断上限为1.25s。
  * 若2个视频+2张图像：`输入计费时长=min(视频<span class="help-letter-space"></span>1<span class="help-letter-space"></span>长度，1.25s)+ min(视频<span class="help-letter-space"></span>2<span class="help-letter-space"></span>长度，1.25s)`。
  * 若3个视频+1张图像：`输入计费时长=min(视频<span class="help-letter-space"></span>1<span class="help-letter-space"></span>长度，1.25s)+ min(视频<span class="help-letter-space"></span>2<span class="help-letter-space"></span>长度，1.25s)+min(视频<span class="help-letter-space"></span>3<span class="help-letter-space"></span>长度，1.25s)`。
  * **输入5个参考文件** ：单视频截断上限为1s。
  * 若1个视频+4张图像：`输入计费时长=min(视频<span class="help-letter-space"></span>1<span class="help-letter-space"></span>长度，1s)`。
  * 若3个视频+2张图像：`输入计费时长=min(视频<span class="help-letter-space"></span>1<span class="help-letter-space"></span>长度，1s)+ min(视频<span class="help-letter-space"></span>2<span class="help-letter-space"></span>长度，1s)+min(视频<span class="help-letter-space"></span>3<span class="help-letter-space"></span>长度，1s)`。

  **输出视频计费时长** ：模型 **成功生成的视频秒数** 。

## **错误码**

如果模型调用失败并返回报错信息，请参见[错误信息](https://help.aliyun.com/zh/model-studio/error-code)进行解决。

## **常见问题**

**Q: 如何将临时的视频链接转为永久链接？**

A: 不能直接转换该链接。正确的做法是：后端服务获取到url后，通过代码下载该视频文件，然后将其上传到永久对象存储服务（如阿里云 OSS），生成一个新的、永久访问链接。

**示例代码：下载视频到本地**

**Q: 返回的视频链接可以在浏览器中直接播放吗？**

A: 不建议这样做，因为链接会在 24 小时后失效。最佳实践是后端下载转存后，使用永久链接进行视频播放。
