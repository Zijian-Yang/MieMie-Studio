# 视频测评首帧生视频模块

## 背景

图片测评已经提供数据集、测评配置、运行矩阵、详情排障和报告导出闭环。视频工作室也已经具备多厂商首帧生视频 capability 与 adapter。视频测评 v1 在图片测评下方新增独立入口，先覆盖首帧生视频横向对比。

## 范围

- 新增 `视频数据集` 与 `视频测评` 两个页面。
- 新增 `/api/video-benchmark/*` API，与图片测评独立存储。
- v1 固定 `task_kind=image_to_video`。
- 模型从视频工作室 capability 自动筛选所有支持 `image_to_video` 的模型。
- 数据集 item 包含首帧图、prompt、负向提示词、标签、可选驱动音频和可选样例级 `duration`。
- 视频数据集对标图片数据集的编辑体验，支持行多选、批量导入 Prompt、批量首帧建样例、批量填充首帧、批量编辑字段、选中行排序和删除。
- 缺首帧样例允许暂存、导入、保存和导出；数据集响应通过 `warnings` / `blocking_issues` 提示，启动测评和 payload preview 前必须补齐首帧。
- 样例级 `duration` 只覆盖当前 case × model 单元的有效参数，不回写 suite 配置。
- 视频测评在模型参数中提供测评层 `group_count`（生成数量），范围 1-5；它控制每个 case × model 单元提交多少个厂商任务，并保存为同一单元的多条 `output_videos`。
- 报告导出保留视频 URL；HTML 报告使用 `<video controls preload="metadata">`，不内嵌视频字节。

## 数据与运行

- 存储目录：
  - `video_benchmark_datasets`
  - `video_benchmark_suites`
  - `video_benchmark_runs`
- 单元参数合并顺序：模型默认值 → suite `baseline_params` → suite `model_overrides[model_id]` → case `duration`。
- `group_count` 参与 `effective_params` 和 `canonical_request` 快照，但属于测评层调度参数；构造 provider payload、validate、submit、fetch 时会从 adapter request 中移除，避免透传给厂商。
- case `duration` 若对某模型非法，该单元标记 `unsupported`，其他模型继续运行。
- 后端运行复用视频工作室 `NormalizedVideoTaskRequest` 与 provider adapter，保存：
  - `effective_params`
  - `canonical_request`
  - `provider_payload`
  - `provider_result_meta`
  - `task_ids`
  - `request_ids`
  - `output_videos`
- 并发按模型 capability 的 `capabilities.max_concurrent` 执行；未声明时默认 1。同一单元从提交到终态都占用该模型 semaphore。

## 非目标

- v1 不做公开分享页。
- v1 不复用图片测评数据集，不修改图片测评现有行为。
