# Seedream 图片工作室接入执行计划

## 目标

- 将 `doubao-seedream-5.0-lite` 与 `doubao-seedream-4.5` 接入图片工作室。
- 使用独立 `provider=volcengine` 与独立火山引擎 Ark API Key。
- 保持现有后台生成、轮询、OSS 持久化和开发者模式链路。

## 执行清单

- [x] 阅读 Seedream 本地文档与图片工作室模型接入指南
- [x] 新增平台 spec 与执行计划文件
- [x] 先补后端失败测试：模型列表、payload preview、参数校验、火山 Key、图片测评能力、结果归一化
- [x] 新增 Volcengine/Seedream 模型注册与服务适配器
- [x] 扩展设置 API 与设置页火山引擎 Ark API Key 模块
- [x] 扩展图片工作室 `text_to_image` / `image_edit` / `sequential_generation` 映射
- [x] 扩展前端图片工作室 Seedream 参数、默认值、校验和 preview 字段
- [x] 更新 API、模型字段、文档入口和变更日志
- [x] 跑后端目标 pytest、前端 typecheck/lint、`git diff --check`
- [ ] 有真实火山 Key 时做 5.0 lite 文生图、4.5 图像编辑、5.0 lite 组图 smoke

## 验证记录

- 已执行后端绿灯验证：`venv/bin/pytest backend/tests/test_studio_capabilities.py backend/tests/test_provider_key_and_manifest.py backend/tests/test_image_benchmark.py -q`
- 当前结果：`77 passed`
- 已执行前端类型检查：`cd frontend && npm run typecheck`
- 当前结果：退出码 0
- 已执行前端 lint：`cd frontend && npm run lint`
- 当前结果：退出码 0
- 已执行空白检查：`git diff --check`
- 当前结果：退出码 0

## 手工收尾

- 无真实火山 Key 时，手工 smoke 只检查设置页 masked 状态、模型可选性和开发者模式 payload。
- 有可用 Key 时，分别提交 5.0 lite 文生图、4.5 图像编辑、5.0 lite 组图，并核对 OSS URL、`request_id`、`usage`、`tools`、单图错误展示。
