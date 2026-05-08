# 视频工作室参考素材 @ 指代词插入计划

## Summary
- 以 `/api/video-studio/capabilities` 的 `ui_hints` 作为唯一配置来源，为多参考图/参考视频模型声明指代词规则。
- 在视频工作室新建/编辑弹窗中，为已选参考图、参考视频增加 `@` 插入按钮，将对应 token 插入提示词光标位置。
- 不自动改写历史 prompt，不校验用户是否使用 token；只降低手写成本。

## Public API / Types
- 在 `VideoTaskProfile.ui_hints` 新增可选字段：

```ts
reference_token_policy: {
  mode: 'media_reference_tokens'
  index_base: 1
  numbering_scope: 'by_type' | 'combined'
  reference_order?: Array<'reference_video' | 'reference_image'>
  tokens: {
    reference_image?: { template: string; variants?: Array<{ key: string; label: string; template: string }> }
    reference_video?: { template: string; variants?: Array<{ key: string; label: string; template: string }> }
  }
}
```

- 默认规则：缺失 policy 时，参考图插入 `图{index}`，参考视频插入 `视频{index}`；编号默认按媒体类型分别计数。
- 已确认默认参考视频 token 使用 `视频1`，不是 `图1`。

## Key Changes
- 后端能力 schema：
  - HappyHorse R2V：参考图 `"[Image {index}]"`。
  - Wan 2.7 R2V：参考图 `"图{index}"`、参考视频 `"视频{index}"`，并提供英文变体 `"Image {index}"` / `"Video {index}"`。
  - Kling Omni R2V/视频编辑：参考图 `"<<<image_{index}>>>"`，参考视频 `"<<<video_{index}>>>"`。
  - Wan 2.6 R2V：沿用现有 `character{index}` 口径，按 provider payload 顺序组合编号，`reference_video` 在 `reference_image` 前。
  - Vidu 与无明确文档的视频编辑参考图：使用默认 `图{index}` / `视频{index}`。
- 前端：
  - 新增 `referenceTokenPolicy.ts`，负责解析 policy、计算媒体编号、格式化 token、处理插入文本。
  - `CapabilityCreateModal.tsx` 给已选参考素材行增加 icon-only `@` 按钮；Wan 2.7 使用按钮菜单，主按钮插入中文 token，菜单可插入英文 token。
  - 插入逻辑替换当前选区；无可用光标时追加到提示词末尾并保持合理空格；插入后恢复焦点和光标位置。
  - 仅对 `reference_image` / `reference_video` 显示按钮，不对首帧、尾帧、base video、source video、mask、audio 显示。
- 文档与计划：
  - 实施前保存计划到 `docs/superpowers/plans/2026-05-08-video-studio-reference-token-insertion.md`。
  - 更新视频工作室相关 spec、`docs/BACKEND.md`、`docs/FRONTEND.md`、`docs/CHANGELOG.md`；HappyHorse spec 补充 R2V token 插入入口。

## Test Plan
- 后端：
  - 更新 `backend/tests/test_video_studio_capabilities.py`，覆盖 HappyHorse、Wan 2.7、Wan 2.6、Kling、Vidu 的 `reference_token_policy`。
  - 运行 `venv/bin/pytest backend/tests/test_video_studio_capabilities.py -q`。
- 前端：
  - 新增脚本测试 reference token helper，覆盖默认图/视频、HappyHorse、Wan 2.7 中英文菜单、Kling、Wan 2.6 combined 编号、光标插入/选区替换。
  - 运行 `cd frontend && npm run typecheck`。
  - 运行 `cd frontend && npm run test:video-capability-limits` 和新增 `npm run test:video-reference-tokens`。
- 收尾：
  - 运行 `git diff --check`。
  - 手工 smoke：HappyHorse R2V 插入 `[Image 1]`；Wan 2.7 R2V 主按钮插入 `图1`/`视频1`，菜单可选 `Image 1`/`Video 1`；Kling 插入 `<<<image_1>>>`；编辑已有任务时同样可插入。

## Assumptions
- `@` 按钮只负责插入文本，不触发上传、不修改素材顺序、不自动补全 prompt。
- Wan 2.7 英文 token 通过按钮菜单提供，不做语言自动判断。
- 新模型若未配置 `reference_token_policy`，前端自动回退到 `图{index}` / `视频{index}`，后端可后续按文档补充精确模板。
