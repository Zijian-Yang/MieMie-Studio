# HappyHorse API 更新与提示词计数修复计划

## Summary

- 以现有 `/Users/zane/Project/Miemie-studio/docs/specs/2026-04-happyhorse-video-studio-integration.md` 为平台侧唯一口径，吸收新版 HappyHorse 文档差异。
- 本轮同步三类行为：HappyHorse 参考图指代文案改为 `[Image 1]`，新增美国（弗吉尼亚）API 地域，修复 HappyHorse 提示词中英文长度检测。
- 实施时先把本计划保存到 `/Users/zane/Project/Miemie-studio/docs/superpowers/plans/2026-05-08-happyhorse-api-and-prompt-count.md`，再改代码和日志。

## Key Changes

- 后端 HappyHorse prompt 校验：
  - 在 `/Users/zane/Project/Miemie-studio/backend/app/services/video_adapters.py` 新增通用计数 helper。
  - HappyHorse 使用加权规则：汉字按 2 单位，非中文字符按 1 单位，总上限 5000 单位，等价于 2500 个中文字符或 5000 个非中文字符。
  - 英文按“非中文字符”计，不按英文单词数计；混合文本按同一加权规则处理。
- Capability schema 与前端：
  - 在 `/api/video-studio/capabilities` 的 HappyHorse profiles 增加 `ui_hints.prompt_length_policy`。
  - 在 `/Users/zane/Project/Miemie-studio/frontend/src/services/api.ts` 补类型。
  - 在视频工作室新建/编辑弹窗显示同一计数口径，并在提交前拦截超限 prompt。
- HappyHorse 文档差异同步：
  - `/Users/zane/Project/Miemie-studio/backend/app/services/video_capabilities.py` 中 HappyHorse R2V 的说明、帮助、测试示例从 `character1/character2` 改为 `[Image 1]/[Image 2]`。
  - 不自动改写用户 prompt，也不拒绝历史 `character1` prompt，只更新新任务引导和测试期望。
- API 地域：
  - `/Users/zane/Project/Miemie-studio/backend/app/config.py` 的 `API_REGIONS` 新增 `us_virginia`，base URL 为 `https://dashscope-us.aliyuncs.com/api/v1`。
  - 设置页已有 `available_regions` 动态渲染，前端无需硬编码新增选项。

## Public API / Types

- `GET /api/settings` 的 `available_regions` 新增：
  - key: `us_virginia`
  - name: `美国（弗吉尼亚）`
  - base_url: `https://dashscope-us.aliyuncs.com/api/v1`
- `GET /api/video-studio/capabilities` 的 HappyHorse `ui_hints` 新增：
  - `prompt_length_policy: { mode: "cjk_weighted", max_units: 5000, cjk_unit: 2, non_cjk_unit: 1, cjk_equivalent_limit: 2500, non_cjk_equivalent_limit: 5000 }`

## Test Plan

- 后端：
  - 更新 `/Users/zane/Project/Miemie-studio/backend/tests/test_video_studio_capabilities.py`，覆盖 HappyHorse 2500 中文、5000 非中文、混合文本边界、R2V `[Image 1]` 文案。
  - 增加 settings 区域测试，确认 `us_virginia` 从 `/api/settings` 暴露。
  - 运行 `venv/bin/pytest backend/tests/test_video_studio_capabilities.py backend/tests/test_provider_key_and_manifest.py -q`。
- 前端：
  - 新增 prompt length helper 与脚本测试，覆盖中文、英文、混合文本、emoji/标点边界。
  - 运行 `cd frontend && npm run typecheck`。
  - 运行现有 `cd frontend && npm run test:video-capability-limits` 和新增 prompt length 测试脚本。
- 收尾：
  - 运行 `git diff --check`。
  - 更新 `/Users/zane/Project/Miemie-studio/docs/CHANGELOG.md`、HappyHorse spec、`/Users/zane/Project/Miemie-studio/docs/BACKEND.md`、`/Users/zane/Project/Miemie-studio/docs/FRONTEND.md`。
  - 手工 smoke：设置页可选美国（弗吉尼亚）；视频工作室 HappyHorse R2V 帮助显示 `[Image 1]`；超限 prompt 前后端错误一致。

## Assumptions

- “英文中文检测方式不一样”按新版 HappyHorse 文档解释为：中文汉字上限 2500，非中文字符上限 5000；不是按英文单词数。
- 新增美国地域作为全局 DashScope 地域能力开放，不做 HappyHorse 专用地域分支。
- 现有未提交的任务卡片布局改动属于用户已有改动，实施时只在必要位置顺手兼容，不回退。
