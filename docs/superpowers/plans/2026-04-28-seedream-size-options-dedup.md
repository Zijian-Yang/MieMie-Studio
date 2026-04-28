# Seedream 尺寸选项去重执行计划

## 目标

- 修复 Seedream 尺寸下拉中“清晰度档位”和“固定尺寸”语义重复的问题。
- 后端 schema 只保留一处清晰度档位来源，固定像素尺寸继续通过 `common_sizes` 暴露。
- 前端参考 Wan2.7 的尺寸设计，使用“清晰度档位 / 固定尺寸”互斥方案，避免所有选项平铺造成重复感。
- 清晰度模式只展示清晰度档位，不展示不同比例；固定尺寸模式才展示带比例的像素尺寸。
- 在尺寸方案 popover 中说明清晰度档位与固定尺寸的区别。

## 执行清单

- [x] 追踪 Seedream `size` 参数 options 与 `common_sizes` 的来源
- [x] 增加后端回归测试：`size.constraint.options` 只包含清晰度档位，且不与 `common_sizes` 重叠
- [x] 后端调整 `_seedream_size_options`，移除固定像素尺寸
- [x] 前端 Seedream 输出尺寸改为“清晰度档位 / 固定尺寸”二选一方案
- [x] 清晰度模式只展示 `2K/3K/4K` 档位，固定尺寸模式才展示比例和像素尺寸
- [x] Seedream 尺寸方案 popover 说明两种方案区别和互斥关系
- [x] 更新 `docs/CHANGELOG.md` 与 `docs/API.md`
- [x] 运行后端目标测试、前端 typecheck/lint、`git diff --check`

## 验证记录

- 已执行红灯验证：`venv/bin/pytest backend/tests/test_studio_capabilities.py::test_get_available_image_models_includes_seedream_models -q`
- 红灯结果：`size.constraint.options` 包含固定像素值，与 `common_sizes` 重叠。
- 已执行绿灯验证：`venv/bin/pytest backend/tests/test_studio_capabilities.py::test_get_available_image_models_includes_seedream_models -q`
- 当前结果：`1 passed`
- 已执行前端红灯验证：`cd frontend && npm run typecheck`
- 红灯结果：旧的 `seedreamSizeOptions` 已被拆分但渲染层仍引用旧变量，同时新变量未使用，TypeScript 失败。
- 已执行后端目标测试：`venv/bin/pytest backend/tests/test_studio_capabilities.py backend/tests/test_provider_key_and_manifest.py backend/tests/test_image_benchmark.py -q`
- 当前结果：`78 passed`
- 已执行前端类型检查：`cd frontend && npm run typecheck`
- 当前结果：退出码 0
- 已执行前端 lint：`cd frontend && npm run lint`
- 当前结果：退出码 0
- 已执行空白检查：`git diff --check`
- 当前结果：退出码 0
