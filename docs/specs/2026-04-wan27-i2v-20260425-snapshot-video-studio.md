# Wan2.7 I2V 2026-04-25 快照模型接入

## 背景

- 原始参考文档：`docs/阿里云模型api文档/万相-图生视频2.7.md`
- 平台长期主用模型仍为 `wan2.7-i2v`。
- `wan2.7-i2v-2026-04-25` 是独立快照模型，用于阶段性测试效果；它不是 `wan2.7-i2v` 的别名，也不替换现有默认模型。

## 目标

- 在视频工作室并排新增 `wan2.7-i2v-2026-04-25`。
- 快照模型支持 `image_to_video`、`keyframe_to_video`、`video_extension`。
- 快照模型与 `wan2.7-i2v` 共享当前 wan2.7 i2v 新版 `video-synthesis` 协议的素材位、参数 schema、校验与 payload builder。
- 新建任务选择快照模型时，任务记录和厂商 payload 均保留 `wan2.7-i2v-2026-04-25`。

## 非目标

- 不把 `wan2.7-i2v-2026-04-25` 作为 `wan2.7-i2v` 的兼容别名。
- 不迁移历史任务。
- 不调整 `video_extension` 默认模型；默认仍为 `wan2.7-i2v`。
- 不修改 `wan2.7-t2v`、`wan2.7-r2v`、`wan2.7-videoedit`。

## 检查结论

- 当前更新的 `万相-图生视频2.7.md` 请求示例和模型参数均以 `wan2.7-i2v-2026-04-25` 为模型名。
- 文档没有明确要求把长期主用 `wan2.7-i2v` 改成快照模型，也没有说明二者是别名关系。
- 因此本次只新增快照模型入口；`wan2.7-i2v` 的默认地位、任务记录和 provider payload 均保持不变。

## 能力与接口

- `/api/video-studio/capabilities` 同时暴露：
  - `models["wan2.7-i2v"]`
  - `models["wan2.7-i2v-2026-04-25"]`
- 两个模型均支持：
  - 图生视频：`first_frame`，可选 `audio`，下发为 `driving_audio`
  - 首尾帧生视频：`first_frame + last_frame`，可选 `audio`
  - 视频续写：`first_clip`，可选 `last_frame`，不支持 `audio`
- 参数保持一致：
  - `resolution`: `720P` / `1080P`
  - `duration`: 2 到 15 秒整数
  - `prompt_extend`
  - `watermark`
  - `seed`
- `WanVideoAdapter` 识别两个独立模型 ID，但 `provider_payload.model` 必须使用用户选择的 `request.model_id`，不做 canonical rewrite。

## 验收标准

- capabilities 同时包含主线模型和快照模型。
- `video_extension` 默认模型仍为 `wan2.7-i2v`。
- 快照模型在开发者模式和真实提交 payload 中下发 `model=wan2.7-i2v-2026-04-25`。
- 主线模型仍下发 `model=wan2.7-i2v`。
- 快照模型后续删除时，只需移除 capabilities 条目、adapter ID 判断、测试和本 spec/文档记录。

## 验证

```bash
venv/bin/pytest backend/tests/test_video_studio_capabilities.py -q
cd frontend && npm run typecheck
git diff --check
```
