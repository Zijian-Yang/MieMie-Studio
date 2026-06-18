# HappyHorse 系列视频工作室接入

## 背景

- `docs/阿里云模型api文档/HappyHorse-文生视频API参考.md`
- `docs/阿里云模型api文档/HappyHorse-图生视频-基于首帧API参考.md`
- `docs/阿里云模型api文档/HappyHorse-参考生视频API参考.md`
- `docs/阿里云模型api文档/HappyHorse-视频编辑API参考.md`
- `docs/阿里云模型api文档/happyhorse1.5接入文档.md`

以上文件是厂商镜像文档，只作为原始参考。本 spec 是平台侧唯一实现口径。

视频工作室当前以 `task_kind + capability schema + provider adapter` 为模型接入主轴。HappyHorse 继续作为独立 `provider=happyhorse` 接入，但复用现有 DashScope 异步 `video-synthesis`、轮询、OSS 持久化和开发者模式元数据链路。

## 目标

- 将 `happyhorse-1.0-t2v` 映射到 `text_to_video`。
- 将 `happyhorse-1.0-i2v` 映射到 `image_to_video`。
- 将 `happyhorse-1.0-r2v` 映射到 `reference_to_video`。
- 将 `happyhorse-1.0-video-edit` 映射到 `video_edit_global`。
- 将 `happyhorse-1.5-t2v` 映射到 `text_to_video`。
- 将 `happyhorse-1.5-i2v` 映射到 `image_to_video`。
- 将 `happyhorse-1.5-r2v` 映射到 `reference_to_video`。
- 默认模型保持现状，不替换 Wan/Kling/Vidu 既有默认。
- 设置页保留独立 `happyhorse_key_profile`，并复用测试/生产 DashScope Key 池。
- API 地域新增美国（弗吉尼亚），对应 `https://dashscope-us.aliyuncs.com/api/v1`。

## 非目标

- 不新增路由、任务类型或新的设置页密钥字段。
- 不把 HappyHorse 复制到 legacy 视频模型常量或通用模型注册接口。
- 不接入 `keyframe_to_video`、`video_extension`、`video_edit_local`、`video_repainting`。
- 不新增 `happyhorse-1.5-video-edit`；厂商文档明确 HH-EDIT 当前没有 1.5 版本。
- 不在本轮引入视频结果本地回退策略。

## 能力映射

### `happyhorse-1.0-t2v` / `happyhorse-1.5-t2v`

- `task_kind=text_to_video`
- `prompt` 必填，去首尾空白后不能为空，最大 2500 个中文字符或 5000 个非中文字符；混合文本按中文 2 单位、非中文 1 单位累计，上限 5000 单位
- 参数支持 `resolution`、`ratio`、`duration`、`watermark`、`prompt_extend`、`disable_data_inspection`、`seed`
- `resolution`: `720P` / `1080P`，默认 `1080P`
- `ratio`: `16:9` / `9:16` / `1:1` / `4:3` / `3:4` / `4:5` / `5:4` / `21:9` / `9:21`，默认 `16:9`
- `duration`: 3 到 15 秒整数，默认 5
- 平台默认 `watermark=false`，adapter 必须显式下发
- `prompt_extend` 默认 `true` 且不显式下发；关闭时下发隐藏参数 `parameters.prompt_extend=false`
- `disable_data_inspection` 默认 `false`；开启时提交额外 header `X-DashScope-DataInspection: {"input":"disable","output":"disable"}`
- HappyHorse 视频默认带音频直出，当前厂商接口不支持关闭推理音频；平台不额外暴露关闭音频开关

### `happyhorse-1.0-i2v` / `happyhorse-1.5-i2v`

- `task_kind=image_to_video`
- 输入必须且仅能有 1 张 `first_frame`
- `prompt` 可选；若填写，去首尾空白后不能为空，最大 2500 个中文字符或 5000 个非中文字符；混合文本按中文 2 单位、非中文 1 单位累计，上限 5000 单位
- 参数支持 `resolution`、`duration`、`watermark`、`prompt_extend`、`disable_data_inspection`、`seed`
- 图片支持公网 URL 或 Base64 data URI，格式 `JPEG/JPG/PNG/BMP/WEBP`，宽高均不小于 300 像素，宽高比 `1:2.5~2.5:1`，文件不超过 20MB
- 不支持 `ratio`、`audio`、`last_frame`、`first_clip`、`shot_type`
- HappyHorse 视频默认带音频直出，当前厂商接口不支持关闭推理音频；平台不额外暴露关闭音频开关

### `happyhorse-1.0-r2v` / `happyhorse-1.5-r2v`

- `task_kind=reference_to_video`
- `prompt` 必填，最大 2500 个中文字符或 5000 个非中文字符；混合文本按中文 2 单位、非中文 1 单位累计，上限 5000 单位
- 输入仅支持 1 到 9 张 `reference_image`
- `prompt` 中 `[Image 1]`、`[Image 2]` 等引用按 `media` 数组顺序对应参考图；历史 `character1` prompt 不做自动改写或拒绝
- capability schema 暴露 `ui_hints.reference_token_policy`，前端已选参考图 `@` 按钮插入 `[Image {index}]`
- 参数支持 `resolution`、`ratio`、`duration`、`watermark`、`prompt_extend`、`disable_data_inspection`、`seed`
- `ratio`: `16:9` / `9:16` / `1:1` / `4:3` / `3:4` / `4:5` / `5:4` / `21:9` / `9:21`，默认 `16:9`
- 参考图支持公网 URL 或 Base64 data URI，格式 `JPEG/JPG/PNG/BMP/WEBP`，短边不低于 400 像素，文件不超过 20MB
- 不支持参考视频、参考音频、首帧、负面提示词；`prompt_extend` 仅作为隐藏开关透传，不使用旧版自动提示词字段
- HappyHorse 视频默认带音频直出，当前厂商接口不支持关闭推理音频；平台不额外暴露关闭音频开关

### `happyhorse-1.0-video-edit`

- `task_kind=video_edit_global`
- `prompt` 必填，最大 2500 个中文字符或 5000 个非中文字符；混合文本按中文 2 单位、非中文 1 单位累计，上限 5000 单位
- 输入必须有 1 个 `video`，可选 0 到 5 张 `reference_image`
- 参数支持 `resolution`、`watermark`、`prompt_extend`、`disable_data_inspection`、`audio_setting`、`seed`
- 视频格式 `MP4/MOV`，建议 H.264，时长 3 到 60 秒，长边不超过 2160 像素，短边不小于 320 像素，宽高比 `1:2.5~2.5:1`，文件不超过 100MB，帧率大于 8 FPS
- 参考图支持公网 URL 或 Base64 data URI，格式 `JPEG/JPG/PNG/BMP/WEBP`，宽高均不小于 300 像素，宽高比 `1:2.5~2.5:1`，文件不超过 20MB
- `audio_setting`: `auto` / `origin`，默认 `auto`
- 不支持 `duration`、`ratio`、`negative_prompt`、外部 `audio`

## 接口与数据

- `/api/video-studio/capabilities` 暴露 7 个 HappyHorse 模型，`provider` 固定为 `happyhorse`。
- `/api/video-studio/capabilities` 为 7 个 HappyHorse 任务 profile 暴露高级开关 `prompt_extend=true` 与 `disable_data_inspection=false`。
- `/api/video-studio/preview-payload` 返回 `provider_headers`，仅包含非密钥类额外 header；真实提交成功或失败时同样写入 `provider_result_meta`。
- HappyHorse `ui_hints` 暴露 `prompt_length_policy={mode:"cjk_weighted", max_units:5000, cjk_unit:2, non_cjk_unit:1, cjk_equivalent_limit:2500, non_cjk_equivalent_limit:5000}`。
- `happyhorse-1.0-r2v` / `happyhorse-1.5-r2v` 暴露 `reference_token_policy`，参考图 token 模板为 `[Image {index}]`；视频编辑未有厂商专用指代词，沿用默认 `图{index}`。
- `/api/settings.available_regions` 暴露 `us_virginia`，用于全局 DashScope 美国（弗吉尼亚）地域。
- 创建、更新、重跑和 `preview-payload` 继续使用现有视频工作室协议。
- 任务继续保留 `provider`、`model_id`、`task_kind`、`key_profile`、`normalized_params`、`provider_payload_snapshot`、`provider_result_meta`、`request_ids`、`task_ids`。
- 厂商提交阶段失败且未返回 `task_id` 时，`provider_result_meta.submit_error.raw_response` 必须保留原始响应。

## 验收标准

- capability schema 能暴露 7 个 HappyHorse 模型，并为每个任务面提供结构化 `asset_help`、`prompt_help` 和 `verification_profiles`。
- `happyhorse-1.5-t2v`、`happyhorse-1.5-i2v`、`happyhorse-1.5-r2v` 与 1.0 并列展示，不替换默认模型。
- 平台不暴露 `happyhorse-1.5-video-edit`。
- HappyHorse 提示词中英文长度限制前后端一致：中文按 2 单位、非中文按 1 单位，超过 5000 单位时阻止提交。
- HappyHorse T2V/R2V capability 和后端 adapter 接受 `4:5`、`5:4`、`21:9`、`9:21` 画幅。
- HappyHorse 图片入参可通过 URL 或 Base64 data URI 传入，平台校验上限为 20MB。
- HappyHorse 图片入参支持 `JPEG/JPG/PNG/BMP/WEBP`。
- HappyHorse 任务面高级参数中关闭“提示词改写”后，provider payload 包含 `parameters.prompt_extend=false`；默认开启时保持旧请求体，不显式下发。
- HappyHorse 任务面开启“关闭绿网”后，preview 和真实提交元信息都能看到 `X-DashScope-DataInspection`，且该开关不会进入 provider payload。
- `text_to_video` / `image_to_video` 不能只依赖通用 `default` 验证档位，需分别暴露 HappyHorse 语义化 smoke/full profiles。
- `happyhorse-1.0-r2v` / `happyhorse-1.5-r2v` provider payload 使用 `input.media=[{type:"reference_image"}]`，顺序与前端素材顺序一致。
- 视频工作室 `@` 按钮能按 HappyHorse R2V 顺序插入 `[Image 1]`、`[Image 2]`。
- `happyhorse-1.0-video-edit` provider payload 使用 `input.media=[{type:"video"}, {type:"reference_image"}...]`。
- 不支持的参数不会进入 HappyHorse provider payload。
- HappyHorse 设置为测试 Key 后，刷新设置仍保持 `happyhorse_key_profile=test`，且 Wan/Kling/Vidu 独立 profile 不受影响。
- 非法参数和非法媒体元数据在后端返回明确错误。

## 验证

自动化：

```bash
venv/bin/pytest backend/tests/test_video_studio_capabilities.py backend/tests/test_provider_key_and_manifest.py -q
cd frontend && npm run typecheck
cd frontend && npm run test:video-capability-limits
cd frontend && npm run test:video-prompt-length-policy
cd frontend && npm run test:video-reference-tokens
git diff --check
```

手工 smoke：

1. 重启本地平台。
2. 打开视频工作室，确认 7 个 HappyHorse 模型都可选，且没有 `happyhorse-1.5-video-edit`。
3. 选择 HappyHorse 参考生视频，确认帮助文案使用 `[Image 1]` / `[Image 2]`。
4. 设置页选择美国（弗吉尼亚）地域并确认 base URL 为 `https://dashscope-us.aliyuncs.com/api/v1`。
5. 展开开发者模式，检查 canonical/provider payload。
6. 有可用权限时分别提交 1 条 HappyHorse 1.5 T2V、I2V、R2V；Video Edit 继续只验证 1.0。
7. 核对轮询、OSS URL、`request_id`、`usage`、失败错误展示。
