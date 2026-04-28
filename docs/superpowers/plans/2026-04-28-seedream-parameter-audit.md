# Seedream 参数能力复核执行计划

## 目标

- 按 `docs/火山api文档/seedream文档.md` 重新核对 `doubao-seedream-5.0-lite` 与 `doubao-seedream-4.5` 的能力、参数、请求体格式和限制。
- 确认图片工作室 UI 与后端 payload 均符合火山引擎请求体口径。
- 明确 `guidance_scale` 不属于这两个模型，避免误加控件或下发无效参数。

## 复核结论

- 两个模型均支持文生图、图像编辑和组图生成；组图通过 `task_kind=sequential_generation` 映射为 `sequential_image_generation=auto`。
- 非组图必须下发 `sequential_image_generation=disabled`，且一次只生成 1 张；需要多个结果用平台 `group_count`。
- `size` 支持两种互斥格式：
  - 清晰度档位：5.0 lite 支持 `2K`、`3K`、`4K`；4.5 支持 `2K`、`4K`。
  - 固定像素：格式为 `宽x高`，总像素范围 `2560x1440` 到 `4096x4096`，宽高比范围 `[1/16, 16]`。
- `guidance_scale` 仅 Seedream 3.0 t2i 支持，5.0 lite / 4.5 / 4.0 不支持。
- 5.0 lite 专属参数为 `output_format=jpeg/png` 与 `tools=[{"type":"web_search"}]`；4.5 不支持。
- 平台固定使用 `response_format=url`、`stream=false`，继续走后台生成、轮询和 OSS 持久化。

## 执行清单

- [x] 重新阅读 Seedream 本地文档，逐项核对能力和参数
- [x] 增加后端回归测试覆盖尺寸档位 label、固定尺寸格式、4.5 参数差异和 `guidance_scale` 不暴露
- [x] 调整 Seedream 模型 schema，使清晰度档位 label 只显示 `2K/3K/4K`
- [x] 图片工作室 Seedream 面板新增显式“组图功能”开关
- [x] 更新 Seedream spec、API、模型字段文档、变更日志
- [x] 运行后端目标测试、前端 typecheck/lint、`git diff --check`

## 验证记录

- 已执行红灯验证：`venv/bin/pytest backend/tests/test_studio_capabilities.py::test_get_available_image_models_includes_seedream_models backend/tests/test_studio_capabilities.py::test_preview_payload_builds_seedream_image_edit_payload_with_fixed_size -q`
- 红灯结果：Seedream 清晰度档位 label 仍包含“模型自动判断比例”；新增固定尺寸 payload 测试已通过。
- 已执行绿灯验证：`venv/bin/pytest backend/tests/test_studio_capabilities.py::test_get_available_image_models_includes_seedream_models backend/tests/test_studio_capabilities.py::test_preview_payload_builds_seedream_image_edit_payload_with_fixed_size -q`
- 当前结果：`2 passed`
- 已执行后端目标测试：`venv/bin/pytest backend/tests/test_studio_capabilities.py backend/tests/test_provider_key_and_manifest.py backend/tests/test_image_benchmark.py -q`
- 当前结果：`79 passed`
- 已执行前端类型检查：`cd frontend && npm run typecheck`
- 当前结果：退出码 0
- 已执行前端 lint：`cd frontend && npm run lint`
- 当前结果：退出码 0
- 已执行空白检查：`git diff --check`
- 当前结果：退出码 0
