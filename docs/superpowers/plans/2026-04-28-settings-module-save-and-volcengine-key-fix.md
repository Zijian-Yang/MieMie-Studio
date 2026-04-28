# 设置页模块化保存与火山 Key 修复执行计划

## 目标

- 修复火山引擎 Ark API Key 保存后仍可能被空白更新覆盖，导致 Seedream 提示未配置的问题。
- 移除设置页底部“保存所有设置”，改为每个模块单独保存。
- 开关类配置在切换后自动保存。

## 执行清单

- [x] 追踪设置页保存、后端 `PUT /api/settings` 与运行时取 Key 链路
- [x] 增加后端回归测试：空白 `volcengine_api_key` 更新不能清空已有 Key
- [x] 后端 Key 字段写入前统一 trim，空白表示不修改
- [x] 设置页移除全局保存按钮
- [x] 设置页补齐 API 地域、文本模型、OSS 模块保存按钮
- [x] 通知、文本模型开关、OSS 启用开关切换后自动保存
- [x] 更新 `docs/CHANGELOG.md` 与 `docs/API.md`
- [x] 运行后端目标测试、前端 typecheck/lint、`git diff --check`

## 验证记录

- 已执行红灯验证：`venv/bin/pytest backend/tests/test_provider_key_and_manifest.py::test_blank_volcengine_key_update_keeps_existing_key -q`
- 红灯结果：空白火山 Key 更新后 masked 值变为 `***`，证明已有 Key 被覆盖。
- 已执行绿灯验证：`venv/bin/pytest backend/tests/test_provider_key_and_manifest.py::test_blank_volcengine_key_update_keeps_existing_key -q`
- 绿灯结果：`1 passed`
- 已执行前端类型检查：`cd frontend && npm run typecheck`
- 当前结果：退出码 0
- 已执行后端目标测试：`venv/bin/pytest backend/tests/test_studio_capabilities.py backend/tests/test_provider_key_and_manifest.py backend/tests/test_image_benchmark.py -q`
- 当前结果：`78 passed`
- 已执行前端 lint：`cd frontend && npm run lint`
- 当前结果：退出码 0
- 已执行空白检查：`git diff --check`
- 当前结果：退出码 0
