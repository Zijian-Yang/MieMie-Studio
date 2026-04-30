# Nano Banana 图片工作室与图片测评接入执行计划

日期：2026-04-30

## 目标

接入 `nano-banana-2` 与 `nano-banana-pro` 到图片工作室和图片测评，provider 固定为 `google`，新增独立 Google Gemini API Key 设置，并支持 inline 图片字节持久化。

## 步骤

1. 准备隔离环境
   - 使用独立 worktree `/tmp/Miemie-studio-nano-banana`
   - 分支：`codex/nano-banana-image-studio`
   - 避免触碰主工作区未提交的视频工作室相关改动

2. 后端红测
   - 扩展图片工作室 capabilities、payload preview、参数校验、adapter 归一化、inline bytes 持久化测试
   - 补充 Google image search grounding 样本夹具，验证 `groundingChunks` 到 `grounding_source_links[]` 的归一化
   - 扩展设置 Key 和 provider key 路由测试
   - 扩展图片测评 capabilities 与执行元信息测试

3. 后端实现
   - 新增 `backend/app/models_registry/image/nano_banana.py`
   - 注册两个模型及参数 schema
   - 扩展 `AppConfig`、`/api/settings`、`get_provider_api_key("google")`
   - 扩展 `StudioTask` 与 studio router 的 canonical request / provider payload / 生成分支
   - 新增 inline 图片字节持久化 fallback 路径
   - 扩展图片测评运行时复用 Nano adapter

4. 前端实现
   - 设置页新增 Google Gemini API Key 模块
   - `frontend/src/services/api.ts` 补配置与 StudioTask 类型
   - 图片工作室按 schema 渲染 Nano Banana 的比例、清晰度、Google Search、thinking 控件
   - 开发者模式展示 grounding 来源链接

5. 文档更新
   - 新增 spec：`docs/specs/2026-04-nano-banana-image-studio-integration.md`
   - 更新 `docs/CHANGELOG.md`
   - 更新 `docs/API.md`
   - 更新 `docs/MODELS.md`
   - 更新 `docs/README.md`

6. 验证
   - 后端：`venv/bin/pytest backend/tests/test_studio_capabilities.py backend/tests/test_provider_key_and_manifest.py backend/tests/test_image_benchmark.py -q`
   - 后端样本回归：`venv/bin/pytest backend/tests/test_studio_capabilities.py -q -k "nano_banana_service_extracts_grounding_source_links_from_sample or generate_with_nano_banana_persists_inline_bytes"`
   - 前端：`cd frontend && npm run typecheck`
   - 前端：`cd frontend && npm run lint`
   - 收尾：`git diff --check`

## 当前完成状态

- [x] 隔离 worktree
- [x] 后端红测
- [x] 后端实现
- [x] 前端实现
- [x] 文档更新
- [x] 最终验证
- [ ] 真实 Google Key smoke

## 备注

真实 Google Key smoke 依赖用户本地有效 Key。无 Key 时以单测、payload preview、类型检查和 lint 作为本轮验收证据。
