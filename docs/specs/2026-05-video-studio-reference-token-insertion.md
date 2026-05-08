# 视频工作室参考素材指代词插入规格

## 背景

参考生视频、视频编辑、局部编辑和重绘任务可能同时携带多张参考图或参考视频。不同模型对 prompt 中的素材指代方式不同：HappyHorse 使用 `[Image 1]`，Wan 2.7 使用 `图1` / `视频1`，Kling 使用 `<<<image_1>>>` / `<<<video_1>>>`。手写这些 token 容易出错，尤其在素材顺序变化时。

## 能力 Schema

后端在任务 profile 的 `ui_hints.reference_token_policy` 中声明 token 规则：

```json
{
  "mode": "media_reference_tokens",
  "index_base": 1,
  "numbering_scope": "by_type",
  "reference_order": ["reference_video", "reference_image"],
  "tokens": {
    "reference_image": { "template": "图{index}" },
    "reference_video": { "template": "视频{index}" }
  }
}
```

- `by_type`：图片和视频分别编号。
- `combined`：按 `reference_order` 合并编号，用于 Wan 2.6 `character{index}`。
- `variants`：同一素材的备用 token，例如 Wan 2.7 英文 `Image 1` / `Video 1`。
- 缺少 policy 时，前端默认参考图 `图{index}`、参考视频 `视频{index}`。

## 前端行为

- 已选参考图/参考视频旁显示 `@` 按钮。
- 点击主按钮将主 token 插入提示词光标位置；若有选区则替换选区。
- 无可用光标时追加到提示词末尾，并自动补一个空格。
- Wan 2.7 显示下拉菜单，主按钮插入中文 token，菜单可选英文 token。
- 不对首帧、尾帧、base video、source video、mask、audio 显示 `@`。
- 不自动改写 prompt，不校验用户是否使用 token。

## 验收

- HappyHorse R2V 第 1 张参考图插入 `[Image 1]`。
- Wan 2.7 R2V 第 1 张图/视频插入 `图1` / `视频1`，菜单可插入 `Image 1` / `Video 1`。
- Kling Omni R2V 插入 `<<<image_1>>>` / `<<<video_1>>>`。
- Wan 2.6 R2V 使用合并编号，参考视频在参考图之前参与 `character{index}`。
- Vidu 和未配置 policy 的新模型回退 `图{index}` / `视频{index}`。
