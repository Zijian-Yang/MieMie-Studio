万相-参考生视频模型支持**多模态输入**，可将人或物体作为主角，生成单角色表演或多角色互动视频。模型还支持智能分镜，生成多镜头视频。

**相关文档**：[使用指南](https://help.aliyun.com/zh/model-studio/video-to-video-guide)

## 适用范围

为确保调用成功，请务必保证模型、Endpoint URL 和 API Key 均属于**同一地域**。跨地域调用将会失败。

-   [**选择模型**](https://help.aliyun.com/zh/model-studio/video-to-video-guide#06f39eafa2dwt)：确认模型所属的地域。
    
-   **选择 URL**：选择对应的地域 Endpoint URL，支持HTTP URL。
    
-   **配置 API Key**：选择地域并[获取API Key](https://help.aliyun.com/zh/model-studio/get-api-key)，再[配置API Key到环境变量](https://help.aliyun.com/zh/model-studio/configure-api-key-through-environment-variables)。
    

**说明**

本文的示例代码适用于**北京地域**。

## HTTP调用（wan2.7模型）

**重要**

此接口为**新版协议**，支持**wan2.7模型**。

由于文生视频任务耗时较长（通常为1-5分钟），API采用异步调用。整个流程包含 **“创建任务 -> 轮询获取”** 两个核心步骤，具体如下：

#### **步骤1：创建任务获取任务ID**

## **北京**

`POST https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis`

## **新加坡**

`POST https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis`

**说明**

-   创建成功后，使用接口返回的 `task_id` 查询结果，task\_id 有效期为 24 小时。**请勿重复创建任务**，轮询获取即可。
    
-   新手指引请参见[Postman](https://help.aliyun.com/zh/model-studio/first-call-to-image-and-video-api)。
    

| #### 请求参数 | ## 多主体参考 传入多张参考素材（图像/视频）生成视频。 ``` curl --location 'https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis' \\ -H 'X-DashScope-Async: enable' \\ -H "Authorization: Bearer $DASHSCOPE_API_KEY" \\ -H 'Content-Type: application/json' \\ -d '{ "model": "wan2.7-r2v", "input": { "prompt": "视频2抱着图片3在咖啡厅里弹奏一支舒缓的美式乡村民谣，视频1笑着看着视频2", "media": [ { "type": "reference_video", "url": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20260129/hfugmr/wan-r2v-role1.mp4" }, { "type": "reference_video", "url": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20260129/qigswt/wan-r2v-role2.mp4" }, { "type": "reference_image", "url": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20260129/qpzxps/wan-r2v-object4.png" } ] }, "parameters": { "resolution": "720P", "duration": 10, "prompt_extend": false, "watermark": true } }' ``` |
| --- | --- |
| ##### 请求头（Headers） |
| **Content-Type** `*string*` **（必选）** 请求内容类型。此参数必须设置为`application/json`。 |
| **Authorization** `*string*`**（必选）** 请求身份认证。接口使用阿里云百炼API-Key进行身份认证。示例值：Bearer sk-xxxx。 |
| **X-DashScope-Async** `*string*` **（必选）** 异步处理配置参数。HTTP请求只支持异步，**必须设置为**`**enable**`。 **重要** 缺少此请求头将报错：“current user api does not support synchronous calls”。 |
| ##### 请求体（Request Body） |
| **model** `*string*` **（必选）** 模型名称。模型列表与价格详见[模型价格](https://help.aliyun.com/zh/model-studio/model-pricing#5c3d28ad8a4x8)。 示例值：wan2.7-r2v。 |
| **input** `*object*` **（必选）** 输入的基本信息，如提示词等。 **属性** **prompt** `*string*` **（必选）** 文本提示词。用来描述生成视频中期望包含的元素和视觉特点。 支持中英文，每个汉字、字母、标点占一个字符，超过部分会自动截断。 - wan2.7-r2v：不超过5000个字符。 角色引用说明：通过“**图片1、图片2**”这类标识引用参考图像中的角色，通过“**视频1、视频2**”这类标识引用参考视频中的角色。每个参考素材（视频或图像）仅包含单一角色。模型仅通过此方式识别参考中的角色。 示例值：图片1在吃饭，视频1和图片2在旁边唱歌。 提示词的使用技巧请参见[文生视频/图生视频Prompt指南](https://help.aliyun.com/zh/model-studio/text-to-video-prompt)。 **negative\\_prompt** `*string*` （可选） 反向提示词，用来描述不希望在视频画面中出现的内容，可以对视频画面进行限制。 支持中英文，长度不超过500个字符，超过部分会自动截断。 示例值：低分辨率、错误、最差质量、低质量、残缺、多余的手指、比例不良等。 **media** `*array*` **（必选）** 媒体素材数组，素材包括图像、视频和音频。 - 数组中每个元素为一个媒体对象，包含 `type` 与 `url` 字段。 - 按照数组顺序定义`prompt`中角色引用的顺序。 - 数组中的第 1 个`reference_video` 对应 **视频1**，第 2 个对应 **视频2**，以此类推。 - 数组中的第 1 个`reference_image`对应 **图片1**，第 2 个对应 **图片2**，以此类推。 - 每个图像/视频最多包含一个主体角色。例如 **视频1** 为小女孩，**图片1** 为闹钟。 **属性** **type** `*string*` **（必选）** 媒体素材类型。可选值为： - `reference_image`：参考图像。提供主体角色（人物/动物/物体）和场景参考。 - `reference_video`：参考视频。提供主体角色（人物/动物/物体）和音色参考，不推荐传入空镜视频。 - `first_frame`：首帧图像。基于首帧生成视频，通常包含主体角色（人物/动物/物体）。 素材限制： - 首帧图像，最多传入1张。 - 参考图像和参考视频至少传入1个，**图像 + 视频 ≤ 5**。 - 参考素材为主体角色时，仅包含单一角色。 **url** `*string*` **（必选）** 媒体素材URL。每个 URL 可指向**一张图像或一段视频**。 传入参考图像（type=reference\\_image） 参考图像URL。参考图可以是主体（人物/动物/物体）或者背景。当包含主体时，仅包含一个角色。 图像限制： - 格式：JPEG、JPG、PNG（不支持透明通道）、BMP、WEBP。 - 分辨率：宽度和高度范围为\\[240, 8000\\]像素。 - 宽高比：1:8～8:1。 - 文件大小：不超过20MB。 支持输入的格式： 1. 公网URL: - 支持 HTTP 或 HTTPS 协议。 - 示例值：https://xxx/xxx.png。 2. 临时URL： - 支持OSS协议，必须通过[上传文件获取临时 URL](https://help.aliyun.com/zh/model-studio/get-temporary-file-url)。 - 示例值：oss://dashscope-instant/xxx/xxx.png。 传入参考视频（type=reference\\_video） 参考视频URL。视频内容建议包含主体（人物/动物/物体），不建议使用背景或空镜视频。当包含主体时，仅包含一个角色。若视频有声音，也可以参考音色。 视频限制： - 格式：mp4、mov。 - 时长：1～30s。 - 分辨率：宽度和高度范围为\\[240,4096\\]像素。 - 宽高比：1:8～8:1。 - 文件大小：不超过100MB。 支持输入的格式： 1. 公网URL： - 支持 HTTP 和 HTTPS 协议。 - 示例值：https://xxx/xxx.mp4。 2. 临时URL： - 支持OSS协议，必须通过[上传文件获取临时 URL](https://help.aliyun.com/zh/model-studio/get-temporary-file-url)。 - 示例值：oss://dashscope-instant/xxx/xxx.mp4。 **reference\\_voice** `*string*` **（可选）** 音频 URL。用于指定参考素材（图像/视频）中主体角色的音色。与`reference_image`或`reference_video`搭配使用。 音频逻辑： - 默认行为：若 `reference_video` 本身包含音频，但未指定 `reference_voice`，默认使用视频原声。 - 优先级：若同时传入 `reference_video`（含音频）和 `reference_voice`，则优先使用 `reference_voice` 的音色，覆盖视频原声。 音频限制： - 格式：wav、mp3。 - 时长：1～10s。 - 文件大小：不超过15MB。 支持输入的格式： 1. 公网URL： - 支持 HTTP 和 HTTPS 协议。 - 示例值：https://xxx/xxx.mp3。 2. 临时URL： - 支持OSS协议，必须通过[上传文件获取临时 URL](https://help.aliyun.com/zh/model-studio/get-temporary-file-url)。 - 示例值：oss://dashscope-instant/xxx/xxx.mp3。 |
| **parameters** `*object*` （可选） 视频处理参数，如设置视频分辨率。 **属性** **resolution** `*string*` （可选） **重要** `resolution`直接影响费用，同一模型：1080P > 720P，请在调用前确认[模型价格](https://help.aliyun.com/zh/model-studio/models#577af209dc0rc)。 生成视频的分辨率档位，用于控制视频的清晰度（总像素）。 - wan2.7-r2v：可选值：720P、1080P。默认值为`1080P`。 **ratio** `*string*` （可选） 生成视频的宽高比。 生效逻辑： - 未传入首帧图像：按指定的 `ratio` 参数生成视频。 - 已传入首帧图像：自动忽略 `ratio` 参数，以首帧图像的宽高比生成近似比例的视频。 可选值为： - `16:9`（默认值） - `9:16` - `1:1` - `4:3` - `3:4` 不同宽高比对应的输出视频分辨率（宽高像素值）见下方表格。 \\| 分辨率档位 \\| 宽高比 \\| 输出视频分辨率（宽\\\\*高） \\| \\| --- \\| --- \\| --- \\| \\| 720P \\| 16:9 \\| 1280\\\\*720 \\| \\| 9:16 \\| 720\\\\*1280 \\| \\| 1:1 \\| 960\\\\*960 \\| \\| 4:3 \\| 1104\\\\*832 \\| \\| 3:4 \\| 832\\\\*1104 \\| \\| 1080P \\| 16:9 \\| 1920\\\\*1080 \\| \\| 9:16 \\| 1080\\\\*1920 \\| \\| 1:1 \\| 1440\\\\*1440 \\| \\| 4:3 \\| 1648\\\\*1248 \\| \\| 3:4 \\| 1248\\\\*1648 \\| **duration** `*integer*` （可选） **重要** duration直接影响费用。费用 = 单价（基于分辨率）× 时长（秒），请在调用前确认[模型价格](https://help.aliyun.com/zh/model-studio/model-pricing#5c3d28ad8a4x8)。 生成视频的时长，单位为秒。 - wan2.7-r2v：取值为\\[2, 10\\]之间的整数。默认值为5。 **prompt\\_extend** `*boolean*` （可选） 是否开启prompt智能改写。开启后使用大模型对输入prompt进行智能改写。对于较短的prompt生成效果提升明显，但会增加耗时。 - true：默认值，开启智能改写。 - false：不开启智能改写。 **watermark** `*boolean*` （可选） 是否添加水印标识，水印位于视频右下角，文案固定为“AI生成”。 - `false`：默认值，不添加水印。 - `true`：添加水印。 **seed** `*integer*` （可选） 随机数种子，取值范围为`[0, 2147483647]`。 未指定时，系统自动生成随机种子。若需提升生成结果的可复现性，建议固定seed值。 请注意，由于模型生成具有概率性，即使使用相同 seed，也不能保证每次生成结果完全一致。 |

| #### 响应参数 | ### 成功响应 请保存 task\\_id，用于查询任务状态与结果。 ``` { "output": { "task_status": "PENDING", "task_id": "0385dc79-5ff8-4d82-bcb6-xxxxxx" }, "request_id": "4909100c-7b5a-9f92-bfe5-xxxxxx" } ``` ### 异常响应 创建任务失败，请参见[错误信息](https://help.aliyun.com/zh/model-studio/error-code)进行解决。 ``` { "code": "InvalidApiKey", "message": "No API-key provided.", "request_id": "7438d53d-6eb8-4596-8835-xxxxxx" } ``` |
| --- | --- |
| **output** `*object*` 任务输出信息。 **属性** **task\\_id** `*string*` 任务ID。查询有效期24小时。 **task\\_status** `*string*` 任务状态。 **枚举值** - PENDING：任务排队中 - RUNNING：任务处理中 - SUCCEEDED：任务执行成功 - FAILED：任务执行失败 - CANCELED：任务已取消 - UNKNOWN：任务不存在或状态未知 |
| **request\\_id** `*string*` 请求唯一标识。可用于请求明细溯源和问题排查。 |
| **code** `*string*` 请求失败的错误码。请求成功时不会返回此参数，详情请参见[错误信息](https://help.aliyun.com/zh/model-studio/error-code)。 |
| **message** `*string*` 请求失败的详细信息。请求成功时不会返回此参数，详情请参见[错误信息](https://help.aliyun.com/zh/model-studio/error-code)。 |

#### **步骤2：根据任务ID查询结果**

## **北京**

`GET https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}`

## **新加坡**

`GET https://dashscope-intl.aliyuncs.com/api/v1/tasks/{task_id}`

## **弗吉尼亚**

`GET https://dashscope-us.aliyuncs.com/api/v1/tasks/{task_id}`

**说明**

-   **轮询建议**：视频生成过程约需数分钟，建议采用**轮询**机制，并设置合理的查询间隔（如 15 秒）来获取结果。
    
-   **任务状态流转**：PENDING（排队中）→ RUNNING（处理中）→ SUCCEEDED（成功）/ FAILED（失败）。
    
-   **结果链接**：任务成功后返回视频链接，有效期为 **24 小时**。建议在获取链接后立即下载并转存至永久存储（如[阿里云 OSS](https://help.aliyun.com/zh/oss/user-guide/what-is-oss)）。
    
-   **task\_id 有效期**：**24小时**，超时后将无法查询结果，接口将返回任务状态为`UNKNOWN`。
    
-   **RPS 限制**：查询接口默认RPS为20。如需更高频查询或事件通知，建议[配置异步任务回调](https://help.aliyun.com/zh/model-studio/async-task-api)。
    
-   **更多操作**：如需批量查询、取消任务等操作，请参见[管理异步任务](https://help.aliyun.com/zh/model-studio/manage-asynchronous-tasks#f26499d72adsl)。
    

| #### 请求参数 | ## 查询任务结果 将`{task_id}`完整替换为上一步接口返回的`task_id`的值。`task_id`查询有效期为24小时。 ``` curl -X GET https://dashscope.aliyuncs.com/api/v1/tasks/{task_id} \\ --header "Authorization: Bearer $DASHSCOPE_API_KEY" ``` |
| --- | --- |
| ##### **请求头（Headers）** |
| **Authorization** `*string*`**（必选）** 请求身份认证。接口使用阿里云百炼API-Key进行身份认证。示例值：Bearer sk-xxxx。 |
| ##### **URL路径参数（Path parameters）** |
| **task\\_id** `*string*`**（必选）** 任务ID。 |

| #### **响应参数** | #### **任务执行成功** 视频URL仅保留24小时，超时后会被自动清除，请及时保存生成的视频。 ``` { "request_id": "52cade0d-905e-9b7d-a01e-xxxxxx", "output": { "task_id": "18814247-f944-4102-aa4a-xxxxxx", "task_status": "SUCCEEDED", "submit_time": "2026-04-02 22:53:19.537", "scheduled_time": "2026-04-02 22:53:30.427", "end_time": "2026-04-02 23:00:39.287", "orig_prompt": "视频2抱着图片3在咖啡厅里弹奏一支舒缓的美式乡村民谣，视频1笑着看着视频2，并缓缓向他走去", "video_url": "https://dashscope-a717.oss-accelerate.aliyuncs.com/xxx.mp4?xxxx" }, "usage": { "duration": 15, "input_video_duration": 5, "output_video_duration": 10, "video_count": 1, "SR": 720, "ratio": "16:9" } } ``` ## 任务执行失败 若任务执行失败，task\\_status将置为 FAILED，并提供错误码和信息。请参见[错误信息](https://help.aliyun.com/zh/model-studio/error-code)进行解决。 ``` { "request_id": "e5d70b02-ebd3-98ce-9fe8-759d7d7b107d", "output": { "task_id": "86ecf553-d340-4e21-af6e-a0c6a421c010", "task_status": "FAILED", "code": "InvalidParameter", "message": "The size is not match xxxxxx" } } ``` ## 任务查询过期 task\\_id查询有效期为 24 小时，超时后将无法查询，返回以下报错信息。 ``` { "request_id": "a4de7c32-7057-9f82-8581-xxxxxx", "output": { "task_id": "502a00b1-19d9-4839-a82f-xxxxxx", "task_status": "UNKNOWN" } } ``` |
| --- | --- |
| **output** `*object*` 任务输出信息。 **属性** **task\\_id** `*string*`**（必选）** 任务ID。 **task\\_status** `*string*` 任务状态。 **枚举值** - PENDING：任务排队中 - RUNNING：任务处理中 - SUCCEEDED：任务执行成功 - FAILED：任务执行失败 - CANCELED：任务已取消 - UNKNOWN：任务不存在或状态未知 **submit\\_time** `*string*` 任务提交时间。格式为 YYYY-MM-DD HH:mm:ss.SSS。 **scheduled\\_time** `*string*` 任务执行时间。格式为 YYYY-MM-DD HH:mm:ss.SSS。 **end\\_time** `*string*` 任务完成时间。格式为 YYYY-MM-DD HH:mm:ss.SSS。 **video\\_url** `*string*` 视频URL。仅在 task\\_status 为 SUCCEEDED 时返回。 链接有效期24小时，可通过此URL下载视频。视频格式为MP4（H.264 编码）。 **orig\\_prompt** `*string*` 原始输入的prompt，对应请求参数`prompt`。 **code** `*string*` 请求失败的错误码。请求成功时不会返回此参数，详情请参见[错误信息](https://help.aliyun.com/zh/model-studio/error-code)。 **message** `*string*` 请求失败的详细信息。请求成功时不会返回此参数，详情请参见[错误信息](https://help.aliyun.com/zh/model-studio/error-code)。 |
| **usage** `*object*` 输出信息统计。只对成功的结果计数。 **属性** **input\\_video\\_duration** `*integer*` 输入视频的时长，单位秒。 **output\\_video\\_duration** `*integer*` 输出视频的时长，单位秒。 **duration** `*float*` 总视频时长。计费按duration时长计算。 计算公式：`duration = input_video_duration + output_video_duration`。 **SR** `*integer*` 生成视频的分辨率档位。示例值：720。 **ratio** `*string*` 生成视频的宽高比。示例值：16:9。 **video\\_count** `*integer*` 生成视频的数量。固定为1。 |
| **request\\_id** `*string*` 请求唯一标识。可用于请求明细溯源和问题排查。 |

## HTTP调用（wan2.6模型）

**重要**

此接口为**旧版协议**，支持**wan2.6模型**。

由于文生视频任务耗时较长（通常为1-5分钟），API采用异步调用。整个流程包含 **“创建任务 -> 轮询获取”** 两个核心步骤，具体如下：

#### **步骤1：创建任务获取任务ID**

## **北京**

`POST https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis`

## **新加坡**

`POST https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis`

## **弗吉尼亚**

`POST https://dashscope-us.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis`

**说明**

-   创建成功后，使用接口返回的 `task_id` 查询结果，task\_id 有效期为 24 小时。**请勿重复创建任务**，轮询获取即可。
    
-   新手指引请参见[Postman](https://help.aliyun.com/zh/model-studio/first-call-to-image-and-video-api)。
    

| #### 请求参数 | ## 多角色互动（参考图像和视频） 通过`reference_urls`传入图像和视频URL。同时设置`shot_type`为`multi`，生成多镜头视频。 ``` curl --location 'https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis' \\ -H 'X-DashScope-Async: enable' \\ -H "Authorization: Bearer $DASHSCOPE_API_KEY" \\ -H 'Content-Type: application/json' \\ -d '{ "model": "wan2.6-r2v-flash", "input": { "prompt": "Character2 坐在靠窗的椅子上，手持 character3，在 character4 旁演奏一首舒缓的美国乡村民谣。Character1 对Character2开口说道：“听起来不错”", "reference_urls": [ "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20260129/hfugmr/wan-r2v-role1.mp4", "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20260129/qigswt/wan-r2v-role2.mp4", "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20260129/qpzxps/wan-r2v-object4.png", "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20260129/wfjikw/wan-r2v-backgroud5.png" ] }, "parameters": { "size": "1280*720", "duration": 10, "audio": true, "shot_type": "multi", "watermark": true } }' ``` ## 多角色互动（参考视频） 通过`reference_urls`传入多个视频URL。同时设置`shot_type`为`multi`，生成多镜头视频。 ``` curl --location 'https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis' \\ -H 'X-DashScope-Async: enable' \\ -H "Authorization: Bearer $DASHSCOPE_API_KEY" \\ -H 'Content-Type: application/json' \\ -d '{ "model": "wan2.6-r2v", "input": { "prompt": "character1对character2说: “I’ll rely on you tomorrow morning!” character2 回答: “You can count on me!”", "reference_urls": [ "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20251217/dlrrly/%E5%B0%8F%E5%A5%B3%E5%AD%A91%E8%8B%B1%E6%96%872.mp4", "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20251217/fkxknn/%E9%93%83%E9%93%83.mp4" ] }, "parameters": { "size": "1280*720", "duration": 10, "shot_type": "multi" } }' ``` ## 单角色扮演 通过`reference_urls`传入单个视频URL。同时设置`shot_type`为`multi`，生成多镜头视频。 ``` curl --location 'https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis' \\ -H 'X-DashScope-Async: enable' \\ -H "Authorization: Bearer $DASHSCOPE_API_KEY" \\ -H 'Content-Type: application/json' \\ -d '{ "model": "wan2.6-r2v", "input": { "prompt": "character1一边喝奶茶，一边随着音乐即兴跳舞。", "reference_urls":["https://cdn.wanx.aliyuncs.com/static/demo-wan26/vace.mp4"] }, "parameters": { "size": "1280*720", "duration": 5, "shot_type":"multi" } }' ``` ## 生成无声视频 仅支持`wan2.6-r2v-flash`生成无声视频。 当生成无声视频时，**必须显式设置** `parameters.audio = false`。 ``` curl --location 'https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis' \\ -H 'X-DashScope-Async: enable' \\ -H "Authorization: Bearer $DASHSCOPE_API_KEY" \\ -H 'Content-Type: application/json' \\ -d '{ "model": "wan2.6-r2v-flash", "input": { "prompt": "character1一边喝奶茶，一边随着音乐即兴跳舞。", "reference_urls":["https://cdn.wanx.aliyuncs.com/static/demo-wan26/vace.mp4"] }, "parameters": { "size": "1280*720", "duration": 5, "audio": false, "shot_type":"multi" } }' ``` |
| --- | --- |
| ##### 请求头（Headers） |
| **Content-Type** `*string*` **（必选）** 请求内容类型。此参数必须设置为`application/json`。 |
| **Authorization** `*string*`**（必选）** 请求身份认证。接口使用阿里云百炼API-Key进行身份认证。示例值：Bearer sk-xxxx。 |
| **X-DashScope-Async** `*string*` **（必选）** 异步处理配置参数。HTTP请求只支持异步，**必须设置为**`**enable**`。 **重要** 缺少此请求头将报错：“current user api does not support synchronous calls”。 |
| ##### 请求体（Request Body） |
| **model** `*string*` **（必选）** 模型名称。模型列表与价格详见[模型价格](https://help.aliyun.com/zh/model-studio/model-pricing#5c3d28ad8a4x8)。 示例值：wan2.6-r2v-flash。 |
| **input** `*object*` **（必选）** 输入的基本信息，如提示词等。 **属性** **prompt** `*string*` **（必选）** 文本提示词。用来描述生成视频中期望包含的元素和视觉特点。 支持中英文，每个汉字、字母、标点占一个字符，超过部分会自动截断。 - wan2.6-r2v-flash：长度不超过1500个字符。 - wan2.6-r2v：长度不超过1500个字符。 角色引用说明：通过“**character1、character2**”这类标识引用参考角色，每个参考（视频或图像）仅包含单一角色。模型仅通过此方式识别参考中的角色。 示例值：character1在沙发上开心地看电影。 提示词的使用技巧请参见[文生视频/图生视频Prompt指南](https://help.aliyun.com/zh/model-studio/text-to-video-prompt)。 **negative\\_prompt** `*string*` （可选） 反向提示词，用来描述不希望在视频画面中出现的内容，可以对视频画面进行限制。 支持中英文，长度不超过500个字符，超过部分会自动截断。 示例值：低分辨率、错误、最差质量、低质量、残缺、多余的手指、比例不良等。 **reference\\_urls** `*array[string]*` **（必选）** **重要** reference\\_urls直接影响费用，计费规则请参见[计费与限流](https://help.aliyun.com/zh/model-studio/video-to-video-guide#6f5774ce5fqie)。 上传的参考文件 URL 数组，支持传入视频和图像。用于提取角色形象与音色（如有），以生成符合参考特征的视频。 - 每个 URL 可指向 **一张图像** 或 **一段视频**： - 图像数量：0～5。 - 视频数量：0～3。 - 总数限制：图像 + 视频 ≤ 5。 - 传入多个参考文件时，按照数组顺序定义角色的顺序。即第 1 个 URL 对应 character1，第 2 个对应 character2，以此类推。 - 每个参考文件仅包含一个主体角色。例如 character1 为小女孩，character2 为闹钟。 支持输入的格式： 1. 公网URL: - 支持 HTTP 或 HTTPS 协议。 - 示例值：https://cdn.translate.alibaba.com/xxx.png。 2. 临时URL： - 支持OSS协议，必须通过[上传文件获取临时 URL](https://help.aliyun.com/zh/model-studio/get-temporary-file-url)。 - 示例值：oss://dashscope-instant/xxx/xxx.png。 参考视频要求： - 格式：MP4、MOV。 - 时长：1s～30s。 - 视频大小：不超过100MB。 参考图像要求： - 格式：JPEG、JPG、PNG（不支持透明通道）、BMP、WEBP。 - 分辨率：宽高均需在\\[240,8000\\]像素之间。 - 图像大小：不超过10MB。 示例值：\\["https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/xxx.mp4", "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/xxx.jpg"\\]。 **已废弃字段** **reference\\_video\\_urls** `*array[string]*` **重要** 推荐使用`reference_urls`替代`reference_video_urls`。 上传的参考视频文件 URL 数组。用于提取角色形象与音色（如有），以生成符合参考特征的视频。 - 最多支持 **3 个视频**。 - 传入多个视频时，按照数组顺序定义视频角色的顺序。即第 1 个 URL 对应 character1，第 2 个对应 character2，以此类推。 - 每个参考视频仅包含一个角色（如 character1 为小女孩，character2 为闹钟）。 - URL支持 HTTP 或 HTTPS 协议。本地文件可通过[上传文件获取临时URL](https://help.aliyun.com/zh/model-studio/get-temporary-file-url)。 单个视频要求： - 格式：MP4、MOV。 - 时长：2～30s。 - 文件大小：视频不超过100MB。 示例值：\\["https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/xxx.mp4"\\]。 |
| **parameters** `*object*` （可选） 图像处理参数。如设置视频分辨率、开启prompt智能改写、添加水印等。 **属性** **size** `*string*` （可选） **重要** - size直接影响费用，费用 = 单价（基于分辨率）× 时长（秒）。同一模型：1080P > 720P ，请在调用前确认[模型价格](https://help.aliyun.com/zh/model-studio/model-pricing#5c3d28ad8a4x8)。 - size必须设置为具体数值（如 `1280*720`），而不是 1:1或720P。 指定生成的视频分辨率，格式为`**宽*高**`。该参数的默认值和可用枚举值依赖于 model 参数，规则如下： - wan2.6-r2v-flash：默认值为 `1920*1080`（1080P）。可选分辨率：720P、1080P对应的所有分辨率。 - wan2.6-r2v：默认值为 `1920*1080`（1080P）。可选分辨率：720P、1080P对应的所有分辨率。 720P档位：可选的视频分辨率及其对应的视频宽高比为： - `1280*720`：16:9。 - `720*1280`：9:16。 - `960*960`：1:1。 - `1088*832`：4:3。 - `832*1088`：3:4。 1080P档位：可选的视频分辨率及其对应的视频宽高比为： - `1920*1080`： 16:9。 - `1080*1920`： 9:16。 - `1440*1440`： 1:1。 - `1632*1248`： 4:3。 - `1248*1632`： 3:4。 **duration** `*integer*` （可选） **重要** duration直接影响费用。费用 = 单价（基于分辨率）× 时长（秒），请在调用前确认[模型价格](https://help.aliyun.com/zh/model-studio/model-pricing#5c3d28ad8a4x8)。 生成视频的时长，单位为秒。 - wan2.6-r2v-flash：取值为\\[2, 10\\]之间的整数。默认值为5。 - wan2.6-r2v：取值为\\[2, 10\\]之间的整数。默认值为5。 示例值：5。 **shot\\_type** `*string*` （可选） 指定生成视频的镜头类型，即视频是由一个连续镜头还是多个切换镜头组成。 参数优先级：`shot_type > prompt`。例如，若 shot\\_type设置为"single"，即使 prompt 中包含“生成多镜头视频”，模型仍会输出单镜头视频。 可选值： - single：默认值，输出单镜头视频 - multi：输出多镜头视频。 示例值：single。 **说明** 当希望严格控制视频的叙事结构（如产品展示用单镜头、故事短片用多镜头），可通过此参数指定。 **audio** `*boolean*` （可选） **重要** audio直接影响费用，有声视频与无声视频价格不同，请在调用前确认[模型价格](https://help.aliyun.com/zh/model-studio/model-pricing#5c3d28ad8a4x8)。 **支持模型：wan2.6-r2v-flash。** 是否生成有声视频。 可选值： - true：默认值，输出有声视频。 - false：输出无声视频。 示例值：true。 **watermark** `*boolean*` （可选） 是否添加水印标识，水印位于视频右下角，文案固定为“AI生成”。 - false：默认值，不添加水印。 - true：添加水印。 示例值：false。 **seed** `*integer*` （可选） 随机数种子，取值范围为`[0, 2147483647]`。 未指定时，系统自动生成随机种子。若需提升生成结果的可复现性，建议固定seed值。 请注意，由于模型生成具有概率性，即使使用相同 seed，也不能保证每次生成结果完全一致。 |

| #### 响应参数 | ### 成功响应 请保存 task\\_id，用于查询任务状态与结果。 ``` { "output": { "task_status": "PENDING", "task_id": "0385dc79-5ff8-4d82-bcb6-xxxxxx" }, "request_id": "4909100c-7b5a-9f92-bfe5-xxxxxx" } ``` ### 异常响应 创建任务失败，请参见[错误信息](https://help.aliyun.com/zh/model-studio/error-code)进行解决。 ``` { "code": "InvalidApiKey", "message": "No API-key provided.", "request_id": "7438d53d-6eb8-4596-8835-xxxxxx" } ``` |
| --- | --- |
| **output** `*object*` 任务输出信息。 **属性** **task\\_id** `*string*` 任务ID。查询有效期24小时。 **task\\_status** `*string*` 任务状态。 **枚举值** - PENDING：任务排队中 - RUNNING：任务处理中 - SUCCEEDED：任务执行成功 - FAILED：任务执行失败 - CANCELED：任务已取消 - UNKNOWN：任务不存在或状态未知 |
| **request\\_id** `*string*` 请求唯一标识。可用于请求明细溯源和问题排查。 |
| **code** `*string*` 请求失败的错误码。请求成功时不会返回此参数，详情请参见[错误信息](https://help.aliyun.com/zh/model-studio/error-code)。 |
| **message** `*string*` 请求失败的详细信息。请求成功时不会返回此参数，详情请参见[错误信息](https://help.aliyun.com/zh/model-studio/error-code)。 |

#### **步骤2：根据任务ID查询结果**

## **北京**

`GET https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}`

## **新加坡**

`GET https://dashscope-intl.aliyuncs.com/api/v1/tasks/{task_id}`

## **弗吉尼亚**

`GET https://dashscope-us.aliyuncs.com/api/v1/tasks/{task_id}`

**说明**

-   **轮询建议**：视频生成过程约需数分钟，建议采用**轮询**机制，并设置合理的查询间隔（如 15 秒）来获取结果。
    
-   **任务状态流转**：PENDING（排队中）→ RUNNING（处理中）→ SUCCEEDED（成功）/ FAILED（失败）。
    
-   **结果链接**：任务成功后返回视频链接，有效期为 **24 小时**。建议在获取链接后立即下载并转存至永久存储（如[阿里云 OSS](https://help.aliyun.com/zh/oss/user-guide/what-is-oss)）。
    
-   **task\_id 有效期**：**24小时**，超时后将无法查询结果，接口将返回任务状态为`UNKNOWN`。
    
-   **RPS 限制**：查询接口默认RPS为20。如需更高频查询或事件通知，建议[配置异步任务回调](https://help.aliyun.com/zh/model-studio/async-task-api)。
    
-   **更多操作**：如需批量查询、取消任务等操作，请参见[管理异步任务](https://help.aliyun.com/zh/model-studio/manage-asynchronous-tasks#f26499d72adsl)。
    

| #### 请求参数 | ## 查询任务结果 将`{task_id}`完整替换为上一步接口返回的`task_id`的值。`task_id`查询有效期为24小时。 ``` curl -X GET https://dashscope.aliyuncs.com/api/v1/tasks/{task_id} \\ --header "Authorization: Bearer $DASHSCOPE_API_KEY" ``` |
| --- | --- |
| ##### **请求头（Headers）** |
| **Authorization** `*string*`**（必选）** 请求身份认证。接口使用阿里云百炼API-Key进行身份认证。示例值：Bearer sk-xxxx。 |
| ##### **URL路径参数（Path parameters）** |
| **task\\_id** `*string*`**（必选）** 任务ID。 |

| #### **响应参数** | #### **任务执行成功** 视频URL仅保留24小时，超时后会被自动清除，请及时保存生成的视频。 ``` { "request_id": "caa62a12-8841-41a6-8af2-xxxxxx", "output": { "task_id": "eff1443c-ccab-4676-aad3-xxxxxx", "task_status": "SUCCEEDED", "submit_time": "2025-12-16 00:25:59.869", "scheduled_time": "2025-12-16 00:25:59.900", "end_time": "2025-12-16 00:30:35.396", "orig_prompt": "character1在沙发上开心的看电影", "video_url": "https://dashscope-result-sh.oss-accelerate.aliyuncs.com/xxx.mp4?Expires=xxx" }, "usage": { "duration": 10.0, "size": "1280*720", "input_video_duration": 5, "output_video_duration": 5, "video_count": 1, "SR": 720 } } ``` ## 任务执行失败 若任务执行失败，task\\_status将置为 FAILED，并提供错误码和信息。请参见[错误信息](https://help.aliyun.com/zh/model-studio/error-code)进行解决。 ``` { "request_id": "e5d70b02-ebd3-98ce-9fe8-759d7d7b107d", "output": { "task_id": "86ecf553-d340-4e21-af6e-a0c6a421c010", "task_status": "FAILED", "code": "InvalidParameter", "message": "The size is not match xxxxxx" } } ``` ## 任务查询过期 task\\_id查询有效期为 24 小时，超时后将无法查询，返回以下报错信息。 ``` { "request_id": "a4de7c32-7057-9f82-8581-xxxxxx", "output": { "task_id": "502a00b1-19d9-4839-a82f-xxxxxx", "task_status": "UNKNOWN" } } ``` |
| --- | --- |
| **output** `*object*` 任务输出信息。 **属性** **task\\_id** `*string*`**（必选）** 任务ID。 **task\\_status** `*string*` 任务状态。 **枚举值** - PENDING：任务排队中 - RUNNING：任务处理中 - SUCCEEDED：任务执行成功 - FAILED：任务执行失败 - CANCELED：任务已取消 - UNKNOWN：任务不存在或状态未知 **submit\\_time** `*string*` 任务提交时间。格式为 YYYY-MM-DD HH:mm:ss.SSS。 **scheduled\\_time** `*string*` 任务执行时间。格式为 YYYY-MM-DD HH:mm:ss.SSS。 **end\\_time** `*string*` 任务完成时间。格式为 YYYY-MM-DD HH:mm:ss.SSS。 **video\\_url** `*string*` 视频URL。仅在 task\\_status 为 SUCCEEDED 时返回。 链接有效期24小时，可通过此URL下载视频。视频格式为MP4（H.264 编码）。 **orig\\_prompt** `*string*` 原始输入的prompt，对应请求参数`prompt`。 **code** `*string*` 请求失败的错误码。请求成功时不会返回此参数，详情请参见[错误信息](https://help.aliyun.com/zh/model-studio/error-code)。 **message** `*string*` 请求失败的详细信息。请求成功时不会返回此参数，详情请参见[错误信息](https://help.aliyun.com/zh/model-studio/error-code)。 |
| **usage** `*object*` 输出信息统计。只对成功的结果计数。 **属性** **input\\_video\\_duration** `*integer*` 输入的参考视频的时长，单位秒。 **output\\_video\\_duration** `*integer*` 输出视频的时长，单位秒。 **duration** `*float*` 总视频时长。计费按duration时长计算。 计算公式：`duration = input_video_duration + output_video_duration`。 **SR** `*integer*` 生成视频的分辨率档位。示例值：720。 **size**`*string*` 生成视频的分辨率。格式为“宽\\*高*”*，示例值：1280\\*720。 **video\\_count** `*integer*` 生成视频的数量。固定为1。 |
| **request\\_id** `*string*` 请求唯一标识。可用于请求明细溯源和问题排查。 |

## **错误码**

如果模型调用失败并返回报错信息，请参见[错误信息](https://help.aliyun.com/zh/model-studio/error-code)进行解决。

.table-wrapper { overflow: visible !important; } /\* 调整 table 宽度 \*/ .aliyun-docs-content table.medium-width { max-width: 1018px; width: 100%; } .aliyun-docs-content table.table-no-border tr td:first-child { padding-left: 0; } .aliyun-docs-content table.table-no-border tr td:last-child { padding-right: 0; } /\* 支持吸顶 \*/ div:has(.aliyun-docs-content), .aliyun-docs-content .markdown-body { overflow: visible; } .stick-top { position: sticky; top: 46px; } /\*\*代码块字体\*\*/ /\* 减少表格中的代码块 margin，让表格信息显示更紧凑 \*/ .unionContainer .markdown-body table .help-code-block { margin: 0 !important; } /\* 减少表格中的代码块字号，让表格信息显示更紧凑 \*/ .unionContainer .markdown-body .help-code-block pre { font-size: 12px !important; } /\* 减少表格中的代码块字号，让表格信息显示更紧凑 \*/ .unionContainer .markdown-body .help-code-block pre code { font-size: 12px !important; } /\*\* API Reference 表格 \*\*/ .aliyun-docs-content table.api-reference tr td:first-child { margin: 0px; border-bottom: 1px solid #d8d8d8; } .aliyun-docs-content table.api-reference tr:last-child td:first-child { border-bottom: none; } .aliyun-docs-content table.api-reference p { color: #6e6e80; } .aliyun-docs-content table.api-reference b, i { color: #181818; } .aliyun-docs-content table.api-reference .collapse { border: none; margin-top: 4px; margin-bottom: 4px; } .aliyun-docs-content table.api-reference .collapse .expandable-title-bold { padding: 0; } .aliyun-docs-content table.api-reference .collapse .expandable-title { padding: 0; } .aliyun-docs-content table.api-reference .collapse .expandable-title-bold .title { margin-left: 16px; } .aliyun-docs-content table.api-reference .collapse .expandable-title .title { margin-left: 16px; } .aliyun-docs-content table.api-reference .collapse .expandable-title-bold i.icon { position: absolute; color: #777; font-weight: 100; } .aliyun-docs-content table.api-reference .collapse .expandable-title i.icon { position: absolute; color: #777; font-weight: 100; } .aliyun-docs-content table.api-reference .collapse.expanded .expandable-content { padding: 10px 14px 10px 14px !important; margin: 0; border: 1px solid #e9e9e9; } .aliyun-docs-content table.api-reference .collapse .expandable-title-bold b { font-size: 13px; font-weight: normal; color: #6e6e80; } .aliyun-docs-content table.api-reference .collapse .expandable-title b { font-size: 13px; font-weight: normal; color: #6e6e80; } .aliyun-docs-content table.api-reference .tabbed-content-box { border: none; } .aliyun-docs-content table.api-reference .tabbed-content-box section { padding: 8px 0 !important; } .aliyun-docs-content table.api-reference .tabbed-content-box.mini .tab-box { /\* position: absolute; left: 40px; right: 0; \*/ } .aliyun-docs-content .margin-top-33 { margin-top: 33px !important; } .aliyun-docs-content .two-codeblocks pre { max-height: calc(50vh - 136px) !important; height: auto; } .expandable-content section { border-bottom: 1px solid #e9e9e9; padding-top: 6px; padding-bottom: 4px; } .expandable-content section:last-child { border-bottom: none; } .expandable-content section:first-child { padding-top: 0; }

/\* 让表格显示成类似钉钉文档的分栏卡片 \*/ table.help-table-card td { border: 10px solid #FFF !important; background: #F4F6F9; padding: 16px !important; vertical-align: top; } /\* 减少表格中的代码块 margin，让表格信息显示更紧凑 \*/ .unionContainer .markdown-body table .help-code-block { margin: 0 !important; } /\* 减少表格中的代码块字号，让表格信息显示更紧凑 \*/ .unionContainer .markdown-body .help-code-block pre { font-size: 12px !important; } /\* 减少表格中的代码块字号，让表格信息显示更紧凑 \*/ .unionContainer .markdown-body .help-code-block pre code { font-size: 12px !important; } /\* 表格中的引用上下间距调小，避免内容显示过于稀疏 \*/ .unionContainer .markdown-body table blockquote { margin: 4px 0 0 0; }

/\* ========================================= \*/ /\* 新增样式：带边框的表格 (api-table-border) \*/ /\* ========================================= \*/ /\* 1. 表格容器核心设置 \*/ .aliyun-docs-content table.api-table-border { border: 1px solid #d8d8d8 !important; /\* 表格外边框 \*/ border-collapse: collapse !important; /\* 合并边框，防止双线 \*/ width: 100% !important; /\* 宽度占满 \*/ margin: 10px 0 !important; /\* 上下间距 \*/ background-color: #fff !important; /\* 背景色 \*/ box-sizing: border-box !important; } /\* 2. 表头、表体、行设置 \*/ /\* 确保行本身没有干扰边框 \*/ .aliyun-docs-content table.api-table-border thead, .aliyun-docs-content table.api-table-border tbody, .aliyun-docs-content table.api-table-border tr { border: none !important; background-color: transparent !important; } /\* 3. 单元格设置 (th 和 td) \*/ /\* 这是边框显示的关键位置 \*/ .aliyun-docs-content table.api-table-border th, .aliyun-docs-content table.api-table-border td { border: 1px solid #d8d8d8 !important; /\* 单元格四周边框 \*/ padding: 8px 12px !important; /\* 内边距 \*/ text-align: left !important; /\* 文字左对齐 \*/ vertical-align: middle !important; /\* 垂直居中 \*/ color: #6e6e80 !important; /\* 文字颜色 \*/ font-size: 14px !important; /\* 字体大小 \*/ line-height: 1.5 !important; } /\* 4. 表头特殊样式 \*/ .aliyun-docs-content table.api-table-border th { background-color: #f9fafb !important; /\* 表头背景色 \*/ color: #181818 !important; /\* 表头文字颜色 \*/ font-weight: 600 !important; /\* 表头加粗 \*/ } /\* 5. 鼠标悬停效果 (可选) \*/ .aliyun-docs-content table.api-table-border tbody tr:hover td { background-color: #fcfcfc !important; /\* 悬停时背景微变 \*/ } /\* 6. 兼容原有 api-reference 可能存在的冲突 \*/ /\* 如果原有样式针对 td:first-child 等特殊选择器有干扰，这里强制覆盖 \*/ .aliyun-docs-content table.api-table-border tr td:first-child { border-bottom: 1px solid #d8d8d8 !important; margin: 0 !important; } .aliyun-docs-content table.api-table-border tr:last-child td:first-child { border-bottom: 1px solid #d8d8d8 !important; /\* 保持底部边框 \*/ }