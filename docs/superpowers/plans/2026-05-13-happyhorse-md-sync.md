# HappyHorse Markdown 文档同步执行计划

## 目标

- 对齐本地更新的 4 份 HappyHorse Markdown 镜像文档。
- 同步平台中 HappyHorse 文生、图生、参考生、视频编辑的参数能力与素材限制。
- 保持现有模型映射、默认 `watermark=false`、提示词长度策略和前端 URL 工作流不变。

## 检查清单

- [x] 保存执行计划文件。
- [x] 先补测试，覆盖新增比例、20MB 图片上限和 Base64 data URI。
- [x] 更新后端 capability schema 和 HappyHorse adapter 校验。
- [x] 更新 HappyHorse spec、后端/前端说明和 CHANGELOG。
- [x] 运行后端与前端指定验证命令。

## 实施要点

- `happyhorse-1.0-t2v` 与 `happyhorse-1.0-r2v` 的 `ratio` 增加 `4:5`、`5:4`。
- I2V 首帧图、R2V 参考图、视频编辑参考图支持 URL 或 Base64 data URI。
- HappyHorse 图片大小上限从 `10MB` 调整为 `20MB`。
- 不新增前端 Base64 粘贴入口；API 层继续通过 `input.media[].url` 传 URL 或 data URI。

## 验证

- `venv/bin/pytest backend/tests/test_video_studio_capabilities.py backend/tests/test_remote_media_validation.py -q`
- `cd frontend && npm run test:video-capability-limits`
