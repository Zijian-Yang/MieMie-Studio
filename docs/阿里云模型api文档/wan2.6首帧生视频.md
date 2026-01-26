# 通义万相-图生视频API参考

参与者：米昵、闻奕 等 **7** 人

更新时间：2026-01-18 21:33:24

**复制为 MD 格式**[产品详情](https://www.aliyun.com/product/bailian)

[我的收藏](https://help.aliyun.com/my_favorites.html)

通义万相-图生视频模型根据**首帧图像**和 **文本提示词** ，生成一段流畅的视频。支持的能力包括：

* **基础能力** ：支持选择视频时长（ 2秒~15秒）、指定视频分辨率（480P/720P/1080P）、智能改写prompt、添加水印。
* **音频能力** ：支持自动配音，或传入自定义音频文件，实现音画同步。**（wan2.5、wan2.6支持）**
* **多镜头叙事** ：支持生成包含多个镜头的视频，在镜头切换时保持主体一致性。**（仅wan2.6支持）**
* **视频特效** ：部分模型内置“魔法悬浮”、“气球膨胀”等特效模板，可直接调用。

 **快速入口：** 在线体验（[北京](https://bailian.console.aliyun.com/cn-beijing?tab=model#/efm/model_experience_center/vision?currentTab=videoGenerate)｜[新加坡](https://modelstudio.console.aliyun.com/ap-southeast-1?tab=dashboard#/efm/model_experience_center/vision?currentTab=videoGenerate)｜[弗吉尼亚](https://modelstudio.console.aliyun.com/us-east-1?tab=dashboard#/efm/model_experience_center/vision?currentTab=videoGenerate)）**｜ **[通义万相官网](https://tongyi.aliyun.com/wan/generate/video/image-to-video)** ｜** [视频特效列表](https://help.aliyun.com/zh/model-studio/wanx-video-effects)

**说明**

通义万相官网的功能与API支持的能力可能存在差异。本文档以API的实际能力为准，并会随功能更新及时同步。

## 模型概览

|        |  |
| ------ | - |
| ------ |  |

| **输入首帧图像和音频**                                                                                                 | **输出视频（wan2.6，多镜头视频）** |
| ---------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| ![rap-转换自-png](https://help-static-aliyun-doc.aliyuncs.com/assets/img/zh-CN/5568778571/p1011609.webp) **输入音频** ： |                                          |

<audio id="ef687a652ds55" name="rap.mp3" size="233892" data-tag="audio" src="https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20250925/ozwpvi/rap.mp3" controlslist="nodownload noplaybackrate" controls="" class="audio"></audio>
 | 
<video id="77209bcb8b09i" name="wan2.6.mp4" data-tag="video" src="https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20251215/kgvqga/wan2.6.mp4" controls="" class="video" title="通义万相-图生视频-基于首帧" alt="通义万相-图生视频-基于首帧" controlslist="nodownload"></video>
 |
|  **输入提示词** ：一幅都市奇幻艺术的场景。一个充满动感的涂鸦艺术角色。一个由喷漆所画成的少年，正从一面混凝土墙上活过来。他一边用极快的语速演唱一首英文rap，一边摆着一个经典的、充满活力的说唱歌手姿势。场景设定在夜晚一个充满都市感的铁路桥下。灯光来自一盏孤零零的街灯，营造出电影般的氛围，充满高能量和惊人的细节。视频的音频部分完全由他的rap构成，没有其他对话或杂音。  |

|          |  |  |
| -------- | - | - |
| -------- |  |  |

| **模型名称（model）**      | **模型简介**                                                                                               | **输出视频规格**                                                           |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| wan2.6-i2v-flash `<b>推荐</b>` | 万相2.6**（有声视频&无声视频）****新增多镜头叙事能力**支持**音频**能力：支持自动配音，或传入自定义音频文件 | 分辨率档位：720P、1080P视频时长：2秒~15秒固定规格：30fps、MP4 (H.264编码)        |
| wan2.6-i2v `<b>推荐</b>`       | 万相2.6**（有声视频）****新增多镜头叙事能力**支持**音频**能力：支持自动配音，或传入自定义音频文件          | 分辨率档位：720P、1080P视频时长：5秒、10秒、15秒固定规格：30fps、MP4 (H.264编码) |
| wan2.5-i2v-preview               | 万相2.5 preview**（有声视频）**新增**音频**能力：支持自动配音，或传入自定义音频文件                        | 分辨率档位：480P、720P、1080P视频时长：5秒，10秒固定规格：30fps、MP4 (H.264编码) |
| wan2.2-i2v-flash                 | 万相2.2极速版（无声视频）较2.1模型速度提升50%                                                                    | 分辨率档位：480P、720P、1080P视频时长：5秒固定规格：30fps、MP4 (H.264编码)       |
| wan2.2-i2v-plus                  | 万相2.2专业版（无声视频）较2.1模型稳定性与成功率全面提升                                                         | 分辨率档位：480P、1080P视频时长：5秒固定规格：30fps、MP4 (H.264编码)             |
| wanx2.1-i2v-plus                 | 万相2.1专业版（无声视频）                                                                                        | 分辨率档位：720P视频时长：5秒固定规格：30fps、MP4 (H.264编码)                    |
| wanx2.1-i2v-turbo                | 万相2.1极速版（无声视频）                                                                                        | 分辨率档位：480P、720P视频时长：3、4、5秒固定规格：30fps、MP4 (H.264编码)        |

**说明**

调用前，请查阅各地域支持的[模型列表与价格](https://help.aliyun.com/zh/model-studio/models#af6bc5a9c3cp9)。

## 前提条件

在调用前，先[获取API Key](https://help.aliyun.com/zh/model-studio/get-api-key)，再[配置API Key到环境变量](https://help.aliyun.com/zh/model-studio/configure-api-key-through-environment-variables)。如需通过SDK进行调用，请[安装DashScope SDK](https://help.aliyun.com/zh/model-studio/install-sdk)。

**重要**

北京、新加坡和弗吉尼亚地域拥有独立的 **API Key **与 **请求地址** ，不可混用，跨地域调用将导致鉴权失败或服务报错，详情请参见[选择地域和部署模式](https://help.aliyun.com/zh/model-studio/regions/)。

## HTTP调用

由于图生视频任务耗时较长（通常为1-5分钟），API采用异步调用。整个流程包含 **“创建任务 -> 轮询获取”** 两个核心步骤，具体如下：

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


| ##### 请求头（Headers）                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Content-Type **`<i>string</i>` **（必选）**请求内容类型。此参数必须设置为 `application/json`。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| **Authorization** `<i>string</i>`**（必选）**请求身份认证。接口使用阿里云百炼API-Key进行身份认证。示例值：Bearer sk-xxxx。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| **X-DashScope-Async **`<i>string</i>` **（必选）**异步处理配置参数。HTTP请求只支持异步，**必须设置为** `<b>enable</b>`。**重要**缺少此请求头将报错：“current user api does not support synchronous calls”。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| ##### 请求体（Request Body）                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| **model** `<i>string</i>` **（必选）**模型名称。示例值：wan2.6-i2v-flash。模型列表与价格详见[模型价格](https://help.aliyun.com/zh/model-studio/models#af6bc5a9c3cp9)。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| **input** `<i>object</i>` **（必选）**输入的基本信息，如提示词等。**属性****prompt** `<i>string</i>` （可选）文本提示词。用来描述生成图像中期望包含的元素和视觉特点。支持中英文，每个汉字/字母占一个字符，超过部分会自动截断。长度限制因模型版本而异：* wan2.6-i2v-flash：长度不超过1500个字符。* wan2.6-i2v：长度不超过1500个字符。* wan2.5-i2v-preview：长度不超过1500个字符。* wan2.2及以下版本模型：长度不超过800个字符。当使用视频特效参数（即 `template`不为空）时，prompt参数无效，无需填写。示例值：一只小猫在草地上奔跑。提示词使用技巧详见[文生视频/图生视频Prompt指南](https://help.aliyun.com/zh/model-studio/text-to-video-prompt)。**negative_prompt** `<i>string</i>` （可选）反向提示词，用来描述不希望在视频画面中看到的内容，可以对视频画面进行限制。支持中英文，长度不超过500个字符，超过部分会自动截断。示例值：低分辨率、错误、最差质量、低质量、残缺、多余的手指、比例不良等。**img_url** `<i>string</i>` **（必选）**首帧图像的URL或 Base64 编码数据。图像限制：* 图像格式：JPEG、JPG、PNG（不支持透明通道）、BMP、WEBP。* 图像分辨率：图像的宽度和高度范围为[360, 2000]，单位为像素。* 文件大小：不超过10MB。输入图像说明：1. 使用公网可访问URL* 支持 HTTP 或 HTTPS 协议。**本地文件可通过**[上传文件获取临时URL](https://help.aliyun.com/zh/model-studio/get-temporary-file-url)。* 示例值：`https://cdn.translate.alibaba.com/r/wanx-demo-1.png`。1. 传入 Base64 编码图像后的字符串* 数据格式：`data:{MIME_type};base64,{base64_data}`。* 示例值：`data:image/png;base64,GDU7MtCZzEbTbmRZ......`。（编码字符串过长，仅展示片段）* 更多内容请参见[输入图像](https://help.aliyun.com/zh/model-studio/image-to-video-api-reference?spm=a2c4g.11186623.help-menu-2400256.d_2_3_0.609041357pKsnp&scm=20140722.H_2867393._.OR_help-T_cn~zh-V_1#16b7ccc98dvhb)。**audio_url** `<i>string</i>` （可选）**支持模型：wan2.6-i2v-flash、 wan2.6-i2v、wan2.5-i2v-preview。**音频文件的 URL，模型将使用该音频生成视频。使用方式参见[音频设置](https://help.aliyun.com/zh/model-studio/image-to-video-api-reference?spm=a2c4g.11186623.help-menu-2400256.d_2_3_0.609041357pKsnp&scm=20140722.H_2867393._.OR_help-T_cn~zh-V_1#a106fc89b40m9)。支持 HTTP 或 HTTPS 协议。**本地文件可通过**[上传文件获取临时URL](https://help.aliyun.com/zh/model-studio/get-temporary-file-url)。音频限制：* 格式：wav、mp3。* 时长：3～30s。* 文件大小：不超过15MB。* 超限处理：若音频长度超过 `duration` 值（5秒或10秒），自动截取前5秒或10秒，其余部分丢弃。若音频长度不足视频时长，超出音频长度部分为无声视频。例如，音频为3秒，视频时长为5秒，输出视频前3秒有声，后2秒无声。示例值：https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20250925/ozwpvi/rap.mp3。**template** `<i>string</i>` （可选）视频特效模板的名称。若未填写，表示不使用任何视频特效。不同模型支持不同的特效模板。调用前请查阅[视频特效列表](https://help.aliyun.com/zh/model-studio/wanx-video-effects)，以免调用失败。示例值：flying，表示使用“魔法悬浮”特效。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| **parameters** `<i>object</i>` （可选）视频处理参数，如设置视频分辨率、设置视频时长、开启prompt智能改写、添加水印等。**属性****resolution** `<i>string</i>` （可选）**重要****resolution**直接影响费用，同一模型：1080P > 720P > 480P，请在调用前确认[模型价格](https://help.aliyun.com/zh/model-studio/models#af6bc5a9c3cp9)。指定生成的视频分辨率档位，用于调整视频的清晰度（总像素）。模型根据选择的分辨率档位，自动缩放至相近总像素， **视频宽高比将尽量与输入图像 img_url 的宽高比保持一致** ，更多说明详见[常见问题](https://help.aliyun.com/zh/model-studio/image-to-video-api-reference?spm=a2c4g.11186623.help-menu-2400256.d_2_3_0.609041357pKsnp&scm=20140722.H_2867393._.OR_help-T_cn~zh-V_1#2b6ac4aea9h5n)。此参数的默认值和可用枚举值依赖于 model 参数，规则如下：* wan2.6-i2v-flash：可选值：720P、1080P。默认值为 `1080P`。* wan2.6-i2v ：可选值：720P、1080P。默认值为 `1080P`。* wan2.5-i2v-preview ：可选值：480P、720P、1080P。默认值为 `1080P`。* wan2.2-i2v-flash：可选值：480P、720P**、1080P**。默认值为 `720P`。* wan2.2-i2v-plus：可选值：480P、1080P。默认值为 `1080P`。* **wanx2.1-i2v-turbo**：可选值：480P、720P。默认值为 `720P`。* **wanx2.1-i2v-plus**：可选值：720P。默认值为 `720P`。示例值：1080P。**duration** `<i>integer</i>` （可选）**重要**duration直接影响费用，按秒计费，时间越长费用越高，请在调用前确认[模型价格](https://help.aliyun.com/zh/model-studio/models#577af209dc0rc)。生成视频的时长，单位为秒。该参数的取值依赖于 model参数：* wan2.6-i2v-flash：可选值为[2, 15]。默认值为5。* wan2.6-i2v：可选值为5、10、15。默认值为5。* wan2.5-i2v-preview：可选值为5、10。默认值为5。* wan2.2-i2v-plus：固定为5秒，且不支持修改。* wan2.2-i2v-flash：固定为5秒，且不支持修改。* **wanx2.1-i2v-plus**：固定为5秒，且不支持修改。* **wanx2.1-i2v-turbo**：可选值为3、4或5。默认值为5。示例值：5。**prompt_extend **`<i>boolean</i>` （可选）是否开启prompt智能改写。开启后使用大模型对输入prompt进行智能改写。对于较短的prompt生成效果提升明显，但会增加耗时。* true：默认值，开启智能改写。* false：不开启智能改写。示例值：true。**shot_type** `<i>string</i>` （可选）**支持模型：wan2.6-i2v-flash、 wan2.6-i2v。**指定生成视频的镜头类型，即视频是由一个连续镜头还是多个切换镜头组成。生效条件：仅当 `"prompt_extend": true` 时生效。参数优先级：`shot_type > prompt`。例如，若 shot_type设置为"single"，即使 prompt 中包含“生成多镜头视频”，模型仍会输出单镜头视频。可选值：* single：默认值，输出单镜头视频* multi：输出多镜头视频。示例值：single。**说明**当希望严格控制视频的叙事结构（如产品展示用单镜头、故事短片用多镜头），可通过此参数指定。**audio** `<i>boolean</i>` （可选）**重要**audio直接影响费用，有声视频与无声视频价格不同，请在调用前确认[模型价格](https://help.aliyun.com/zh/model-studio/models#577af209dc0rc)。**支持模型：wan2.6-i2v-flash。**是否生成有声视频。参数优先级：`audio > audio_url`。当 `audio=false`时，即使传入 `audio_url`，输出仍为无声视频，且计费按无声视频计算。可选值：* true：默认值，输出有声视频。* false：输出无声视频。示例值：true。**watermark** `<i>boolean</i>` （可选）是否添加水印标识，水印位于视频右下角，文案固定为“AI生成”。* false：默认值，不添加水印。* true：添加水印。示例值：false。**seed **`<i>integer</i>` （可选）随机数种子，取值范围为 `[0, 2147483647]`。未指定时，系统自动生成随机种子。若需提升生成结果的可复现性，建议固定seed值。请注<br />意，由于模型生成具有概率性，即使使用相同 seed，也不能保证每次生成结果完全一致。示例值：12345。 |

多镜头叙事


wan2.6模型支持生成多镜头视频。

可通过设置 `"prompt_extend": true`和 `"shot_type":"multi"`启用。

```curl
curl --location 'https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis' \
    -H 'X-DashScope-Async: enable' \
    -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
    -H 'Content-Type: application/json' \
    -d '{
    "model": "wan2.6-i2v-flash",
    "input": {
        "prompt": "一幅都市奇幻艺术的场景。一个充满动感的涂鸦艺术角色。一个由喷漆所画成的少年，正从一面混凝土墙上活过来。他一边用极快的语速演唱一首英文rap，一边摆着一个经典的、充满活力的说唱歌手姿势。场景设定在夜晚一个充满都市感的铁路桥下。灯光来自一盏孤零零的街灯，营造出电影般的氛围，充满高能量和惊人的细节。视频的音频部分完全由他的rap构成，没有其他对话或杂音。",
        "img_url": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20250925/wpimhv/rap.png",
        "audio_url": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20250925/ozwpvi/rap.mp3"
    },
    "parameters": {
        "resolution": "720P",
        "prompt_extend": true,
        "duration": 10,
        "shot_type":"multi"
    }
}'
```

自动配音


**仅 wan2.5 及以上版本模型支持此功能。**

若不提供 `input.audio_url` ，模型将根据视频内容自动生成匹配的背景音乐或音效。

```curl
curl --location 'https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis' \
    -H 'X-DashScope-Async: enable' \
    -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
    -H 'Content-Type: application/json' \
    -d '{
    "model": "wan2.5-i2v-preview",
    "input": {
        "prompt": "一幅都市奇幻艺术的场景。一个充满动感的涂鸦艺术角色。一个由喷漆所画成的少年，正从一面混凝土墙上活过来。他一边用极快的语速演唱一首英文rap，一边摆着一个经典的、充满活力的说唱歌手姿势。场景设定在夜晚一个充满都市感的铁路桥下。灯光来自一盏孤零零的街灯，营造出电影般的氛围，充满高能量和惊人的细节。视频的音频部分完全由他的rap构成，没有其他对话或杂音。",
        "img_url": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20250925/wpimhv/rap.png"
    },
    "parameters": {
        "resolution": "480P",
        "prompt_extend": true,
        "duration": 10
    }
}'
```

传入音频文件


**仅 wan2.5 及以上版本模型支持此功能。**

如需为视频指定背景音乐或配音，可通过 `input.audio_url` 参数传入自定义音频的 URL。

```curl
curl --location 'https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis' \
    -H 'X-DashScope-Async: enable' \
    -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
    -H 'Content-Type: application/json' \
    -d '{
    "model": "wan2.5-i2v-preview",
    "input": {
        "prompt": "一幅都市奇幻艺术的场景。一个充满动感的涂鸦艺术角色。一个由喷漆所画成的少年，正从一面混凝土墙上活过来。他一边用极快的语速演唱一首英文rap，一边摆着一个经典的、充满活力的说唱歌手姿势。场景设定在夜晚一个充满都市感的铁路桥下。灯光来自一盏孤零零的街灯，营造出电影般的氛围，充满高能量和惊人的细节。视频的音频部分完全由他的rap构成，没有其他对话或杂音。",
        "img_url": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20250925/wpimhv/rap.png",
        "audio_url": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20250925/ozwpvi/rap.mp3"
    },
    "parameters": {
        "resolution": "480P",
        "prompt_extend": true,
        "duration": 10
    }
}'
```

生成无声视频


仅以下模型支持生成无声视频：

* wan2.6-i2v-flash：若需生成无声视频，**必须显式设置** `parameters.audio = false`。
* wan2.2 及以下版本模型：默认生成无声视频，无需额外参数配置。

```curl
curl --location 'https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis' \
    -H 'X-DashScope-Async: enable' \
    -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
    -H 'Content-Type: application/json' \
    -d '{
    "model": "wan2.2-i2v-plus",
    "input": {
        "prompt": "一只猫在草地上奔跑",
        "img_url": "https://cdn.translate.alibaba.com/r/wanx-demo-1.png"
    },
    "parameters": {
        "resolution": "480P",
        "prompt_extend": true
    }
}'
```


仅以下模型支持生成无声视频：

* wan2.6-i2v-flash：若需生成无声视频，**必须显式设置** `parameters.audio = false`。
* wan2.2 及以下版本模型：默认生成无声视频，无需额外参数配置。

```curl
curl --location 'https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis' \
    -H 'X-DashScope-Async: enable' \
    -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
    -H 'Content-Type: application/json' \
    -d '{
    "model": "wan2.2-i2v-plus",
    "input": {
        "prompt": "一只猫在草地上奔跑",
        "img_url": "https://cdn.translate.alibaba.com/r/wanx-demo-1.png"
    },
    "parameters": {
        "resolution": "480P",
        "prompt_extend": true
    }
}'
```


使用Base64


您可以通过 `img_url` 参数传入图像的 Base64 编码字符串，以代替公开可访问的 URL。关于 Base64 字符串的格式要求，请参见[输入图像](https://help.aliyun.com/zh/model-studio/image-to-video-api-reference?spm=a2c4g.11186623.help-menu-2400256.d_2_3_0.609041357pKsnp&scm=20140722.H_2867393._.OR_help-T_cn~zh-V_1#16b7ccc98dvhb)。

示例：下载[img_base64](https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20250722/pmcjis/img_base64.txt)文件，并将完整内容粘贴至 `img_url`参数中。

```curl
curl --location 'https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis' \
    -H 'X-DashScope-Async: enable' \
    -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
    -H 'Content-Type: application/json' \
    -d '{
    "model": "wan2.2-i2v-plus",
    "input": {
        "prompt": "一只猫在草地上奔跑",
        "img_url": "data:image/png;base64,GDU7MtCZzEbTbmRZ......"
    },
    "parameters": {
        "resolution": "480P",
        "prompt_extend": true
    }
}'
```

使用视频特效


* prompt 字段将被忽略，建议留空。
* 特效的可用性与模型相关。调用前请查阅[视频特效列表](https://help.aliyun.com/zh/model-studio/wanx-video-effects)，以免调用失败。

```curl
curl --location 'https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis' \
    -H 'X-DashScope-Async: enable' \
    -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
    -H 'Content-Type: application/json' \
    -d '{
    "model": "wanx2.1-i2v-turbo",
    "input": {
        "img_url": "https://cdn.translate.alibaba.com/r/wanx-demo-1.png",
        "template": "flying"
    },
    "parameters": {
        "resolution": "720P"
    }
}'
```

使用反向提示词


通过 negative_prompt 指定生成的视频避免出现“花朵”元素。

```curl
curl --location 'https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis' \
    -H 'X-DashScope-Async: enable' \
    -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
    -H 'Content-Type: application/json' \
    -d '{
    "model": "wan2.2-i2v-plus",
    "input": {
        "prompt": "一只猫在草地上奔跑",
        "negative_prompt": "花朵",
        "img_url": "https://cdn.translate.alibaba.com/r/wanx-demo-1.png"
    },
    "parameters": {
        "resolution": "480P",
        "prompt_extend": true
    }
}'
```


#### 响应参数



| **output** `<i data-spm-anchor-id="a2c4g.11186623.0.i33.62284135MOMcUr">object</i>`任务输出信息。属性**task_id** `<i>string</i>`任务ID。查询有效期24小时。**task_status** `<i>string</i>`任务状态。**枚举值*** PENDING：任务排队中* RUNNING：任务处理中* SUCCEEDED：任务执行成功* FAILED：任务执行失败* CANCELED：任务已取消* UNKNOWN：任务不存在或状态未知 |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **request_id **`<i>string</i>`请求唯一标识。可用于请求明细溯源和问题排查。                                                                                                                                                                                                                                                                                                              |
| **code **`<i>string</i>`请求失败的错误码。请求成功时不会返回此参数，详情请参见[错误信息](https://help.aliyun.com/zh/model-studio/error-code)。                                                                                                                                                                                                                                             |
| **message **`<i>string</i>`请求失败的详细信息。请求成功时不会返回此参数，详情请参见[错误信息](https://help.aliyun.com/zh/model-studio/error-code)。                                                                                                                                                                                                                                        |

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

| #### 请求参数                                                                                                                   | 查询任务结果将 `{task_id}`完整替换为上一步接口返回的 `task_id`的值。

```curl
curl -X GET https://dashscope.aliyuncs.com/api/v1/tasks/{task_id} \
--header "Authorization: Bearer $DASHSCOPE_API_KEY"
```

|                                                                                                                                   |  |
| --------------------------------------------------------------------------------------------------------------------------------- | - |
| #####**请求头（Headers）**                                                                                                  |  |
| **Authorization**`<i>string</i>`**（必选）**请求身份认证。接口使用阿里云百炼API-Key进行身份认证。示例值：Bearer sk-xxxx。 |  |
| #####**URL路径参数（Path parameters）**                                                                                     |  |
| **task_id** `<i>string</i>`**（必选）**任务ID。                                                                           |  |

| ####**响应参数** |
| ---------------------- |


| **output **`<i>object</i>`任务输出信息。**属性****task_id** `<i>string</i>`任务ID。查询有效期24小时。**task_status** `<i>string</i>`任务状态。**枚举值*** PENDING：任务排队中* RUNNING：任务处理中* SUCCEEDED：任务执行成功* FAILED：任务执行失败* CANCELED：任务已取消* UNKNOWN：任务不存在或状态未知**轮询过程中的状态流转：*** PENDING（排队中） → RUNNING（处理中）→ SUCCEEDED（成功）/ FAILED（失败）。* 初次查询状态通常为 PENDING（排队中）或 RUNNING（处理中）。* 当状态变为 SUCCEEDED 时，响应中将包含生成的视频url。* 若状态为 FAILED，请检查错误信息并重试。**submit_time** `<i>string</i>`任务提交时间。格式为 YYYY-MM-DD HH:mm:ss.SSS。**scheduled_time** `<i>string</i>`任务执行时间。格式为 YYYY-MM-DD HH:mm:ss.SSS。**end_time** `<i>string</i>`任务完成时间。格式为 YYYY-MM-DD HH:mm:ss.SSS。**video_url **`<i>string</i>`视频URL。仅在 task_status 为 SUCCEEDED 时返回。链接有效期24小时，可通过此URL下载视频。视频格式为MP4（H.264 编码）。**orig_prompt** `<i>string</i>`原始输入的prompt，对应请求参数 `prompt`。**actual_prompt** `<i>string</i>`当 `prompt_extend=true` 时，系统会对输入 prompt 进行智能改写，此字段返回实际用于生成的优化后 prompt。* 若 `prompt_extend=false`，该字段不会返回。* 注意：wan2.6 模型无论 `prompt_extend` 取值如何，均不返回此字段。**code **`<i>string</i>`请求失败的错误码。请求成功时不会返回此参数，详情请参见[错误信息](https://help.aliyun.com/zh/model-studio/error-code)。**message **`<i>string</i>`请求失败的详细信息。请求成功时不会返回此参数，详情请参见[错误信息](https://help.aliyun.com/zh/model-studio/error-code)。 |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **usage** `<i>object</i>`输出信息统计，只对成功的结果计数。**属性****wan2.6模型返回参数****input_video_duration** `<i>integer</i>`输入的视频的时长，单位秒。当前不支持传入视频，因此固定为0。**output_video_duration** `<i>integer</i>`仅在使用 wan2.6 模型时返回。输出视频的时长，单位秒。其值等同于 `input.duration`的值。**duration** `<i>integer</i>`总的视频时长，用于计费。计费公式：`duration=input_video_duration+output_video_duration`。**SR** `<i>integer</i>`仅在使用 wan2.6 模型时返回。生成视频的分辨率档位。示例值：720。**video_count** `<i>integer</i>`生成视频的数量。固定为1。**audio** `<i>boolean</i>`仅在使用wan2.6-i2v-flash模型时返回。表示输出视频是否为有声视频。**wan2.2和wan2.5模型返回参数****duration** `<i>integer</i>`生成视频的时长，单位为秒。枚举值为5、10。计费公式：费用 = 视频秒数 × 单价。**SR** `<i>integer</i>`生成视频的分辨率。枚举值为480、720、1080。**video_count** `<i>integer</i>`生成视频的数量。固定为1。**wan2.1模型返回参数****video_duration** `<i>integer</i>`生成视频的时长，单位为秒。枚举值为3、4、5。计费公式：费用 = 视频秒数 × 单价。**video_ratio** `<i>string</i>`生成视频的比例。固定为standard。**video_count** `<i>integer</i>`生成视频的数量。固定为1。                                                                                                                                                                                                                                                                                                                                     |
| **request_id **`<i>string</i>`请求唯一标识。可用于请求明细溯源和问题排查。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |

任务执行成功


视频URL仅保留24小时，超时后会被自动清除，请及时保存生成的视频。

```json
{
    "request_id": "2ca1c497-f9e0-449d-9a3f-xxxxxx",
    "output": {
        "task_id": "af6efbc0-4bef-4194-8246-xxxxxx",
        "task_status": "SUCCEEDED",
        "submit_time": "2025-09-25 11:07:28.590",
        "scheduled_time": "2025-09-25 11:07:35.349",
        "end_time": "2025-09-25 11:17:11.650",
        "orig_prompt": "一幅都市奇幻艺术的场景。一个充满动感的涂鸦艺术角色。一个由喷漆所画成的少年，正从一面混凝土墙上活过来。他一边用极快的语速演唱一首英文rap，一边摆着一个经典的、充满活力的说唱歌手姿势。场景设定在夜晚一个充满都市感的铁路桥下。灯光来自一盏孤零零的街灯，营造出电影般的氛围，充满高能量和惊人的细节。视频的音频部分完全由他的rap构成，没有其他对话或杂音。",
        "video_url": "https://dashscope-result-sh.oss-cn-shanghai.aliyuncs.com/xxx.mp4?Expires=xxx"
    },
    "usage": {
        "duration": 10,
        "input_video_duration": 0,
        "output_video_duration": 10,
        "video_count": 1,
        "SR": 720
    }
}
```


任务执行失败


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

任务查询过期


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


## **关键参数说明**

### **输入图像**

输入图像 `img_url` 参数支持以下三种方式传入：

方式一：公网URL

方式二：Base 64编码

方式三：本地文件路径（仅限 SDK）

* 一个公网可直接访问的地址，支持 HTTP/HTTPS。**本地文件可通过**[上传文件获取临时URL](https://help.aliyun.com/zh/model-studio/get-temporary-file-url)。
* 示例值：`https://example.com/images/cat.png`。

### **音频设置**

 **支持的模型** ：wan2.6-i2v、wan2.5-i2v-preview。

 **音频设置** ：wan2.5及以上版本默认生成有声视频，音频行为由是否传入 `input.audio_url` 决定，支持以下两种模式：

1. **自动配音** ：当不传入 `audio_url` 时，模型将根据提示词和画面内容，自动生成匹配的背景音频或音乐。
2. **使用自定义音频** ：当传入 `audio_url` 时，模型将使用您提供的音频文件生成视频，视频画面会与音频内容对齐（如口型、节奏等）。

## **计费与限流**

* 模型免费额度和计费单价请参见[模型列表与价格](https://help.aliyun.com/zh/model-studio/models#af6bc5a9c3cp9)。
* 模型限流请参见[通义万相系列](https://help.aliyun.com/zh/model-studio/rate-limit#a729d7b6bar7y)。
* 计费说明：
  * 按成功生成的 **视频秒数** 计费。仅当查询结果接口返回 `task_status`为 `SUCCEEDED` 并成功生成视频后，才会计费。
  * 模型调用失败或处理错误不产生任何费用，也不消耗[新人免费额度](https://help.aliyun.com/zh/model-studio/new-free-quota)。
  * 图生视频还支持[节省计划](https://help.aliyun.com/zh/model-studio/billing-for-model-studio#b0a1f8c35b9wo)，抵扣顺序为  **免费额度 > 节省计划 > 按量付费** 。

## **错误码**

如果模型调用失败并返回报错信息，请参见[错误信息](https://help.aliyun.com/zh/model-studio/error-code)进行解决。

## **常见问题**

 **视频FAQ快速入口** ：[常见问题](https://help.aliyun.com/zh/model-studio/text-to-video-api-reference#c928ee689aw6l)。

#### **Q：如何生成特定宽高比（如3:4）的视频？**

**A：** 输出视频的宽高比由 **输入首帧图像（img_url）** 决定，但 **无法保证精确比例** （如严格3:4）。

 **工作原理** ：模型以输入图像的宽高比为基准，然后根据 resolution 参数（如 480P / 720P / 1080P）将其适配到模型支持的合法分辨率。由于输出分辨率需满足技术要求（长和宽必须能被 16 整除），最终输出的宽高比可能存在微小偏差（例如从 0.75 调整为 0.739），属于正常现象。

* 示例：输入图像750×1000（宽高比 3:4 = 0.75），并设置 resolution = "720P"（目标总像素约 92 万），实际输出816×1104（宽高比 ≈ 0.739，总像素约90万）。
* 请注意，resolution 参数主要用于控制视频清晰度（总像素量），最终视频宽高比仍以输入图像为基础，仅做必要微调。

 **最佳实践** ：若需严格符合目标宽高比，请使用与目标比例一致的输入图像，并对输出视频进行后处理裁剪或填充。例如，使用视频编辑工具将输出视频裁剪至目标比例，或添加黑边、模糊背景进行填充适配。

## **附录**

#### **图生视频基础功能示例**

|            |  |  |  |
| ---------- | - | - | - |
| ---------- |  |  |  |

| **模型功能** | **输入首帧图像**                                                                      | **输入提示词** | **输出视频** |
| ------------------ | ------------------------------------------------------------------------------------------- | -------------------- | ------------------ |
| 无声视频           | ![image](https://help-static-aliyun-doc.aliyuncs.com/assets/img/zh-CN/8524116571/p906901.png) | 一只猫在草地上奔跑   |                    |

<video id="4efe232d399xt" name="29a2e615-6443-4647-bbe2-e26f345a3b26.mp4" data-tag="video" src="https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20250225/glrqyl/29a2e615-6443-4647-bbe2-e26f345a3b26.mp4" controls="" class="video" title="通义万相-图生视频-基于首帧" alt="通义万相-图生视频-基于首帧" controlslist="nodownload"></video>
 |
| 视频特效      | ![image](https://help-static-aliyun-doc.aliyuncs.com/assets/img/zh-CN/6805468571/p1007038.png) **输入特效参数** ：“template: flying” | 无                 | 
<video id="7fd7dea73798t" name="demo_flying.mp4" data-tag="video" src="https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20250924/xfvykl/demo_flying.mp4" controls="" class="video" title="通义万相-图生视频-基于首帧" alt="通义万相-图生视频-基于首帧" controlslist="nodownload"></video>

> “魔法悬浮”特效                        |
>
