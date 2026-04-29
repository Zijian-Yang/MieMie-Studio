# 阿里生图/生视频限流校准

## 背景

阿里云模型限流文档同时给出两种约束：任务下发接口调用频率，以及同时处理中任务数量。平台此前主要把 `max_concurrent` 当成保守并发数使用，容易混淆同步/异步接口口径，也会让 Qwen 图片同步接口误受异步并发限制。

本次按 `docs/阿里云模型api文档/阿里模型限流.md` 校准平台中已接入的阿里生图、生视频模型。限流选择以平台实际调用方式为准：Qwen 图片模型走同步 HTTP，Wan/HappyHorse/Kling/Vidu 视频及 Wan 异步图片模型走异步任务接口。

## 范围

- 新增统一限流定义 `backend/app/services/model_rate_limits.py`。
- 能力 schema 暴露：
  - `api_mode`
  - `submit_rate_limit`
  - `max_concurrent`
  - `concurrency_scope`
  - `concurrency_pool_id`
  - `rate_limit_note`
- 图片工作室、图片测评、视频工作室、视频测评都按统一 helper 执行提交频率与处理中任务并发。
- 状态查询/轮询不使用任务下发接口频率限制。
- Seedream 不受阿里限流文档调整。

## 规则

- `submit_rate_limit` 限制发出同步生成请求或异步任务提交请求的节奏。
- `max_concurrent` 限制异步任务从提交成功到终态期间占用的处理中任务数量。
- `max_concurrent=null` 表示平台当前调用接口的处理中任务数量无限制，但仍需执行 `submit_rate_limit`。
- `shared_pool` 表示多个模型共享同一个账号级处理中任务池。

## 模型映射

- Qwen 图片同步接口：
  - `qwen-image-2.0-pro`、`qwen-image-max`、`qwen-image-edit-max`：`2/min`，处理中任务无限制。
  - `qwen-image-2.0`、`qwen-image-plus`、`qwen-image-edit-plus`：`2/sec`，处理中任务无限制。
  - `qwen-image-plus` 不套用文档中的异步接口并发 2，因为平台实际走同步 HTTP。
- Wan 图片异步任务接口：
  - `wan2.7-image-pro`、`wan2.7-image`、`wan2.6-image`、`wan2.5-t2i-preview`、`wan2.5-i2i-preview`：`5/sec`，`max_concurrent=5`。
  - `wan2.6-t2i` 中国内地：`1/sec`，`max_concurrent=5`。
- Wan 视频异步任务接口：
  - Wan 2.7/2.6/2.5 主线生视频：`5/sec`，`max_concurrent=5`。
  - `wan2.2-t2v-plus`、`wanx2.1-t2v-turbo`、`wanx2.1-t2v-plus`、`wanx2.1-i2v-turbo`：`2/sec`，`max_concurrent=2`。
  - `wan2.2-s2v`：`1/sec`，`max_concurrent=1`。
- HappyHorse 视频：`5/sec`，`max_concurrent=5`。
- Kling 视频：`5/sec`，可灵图像/视频共享 `max_concurrent=10`。
- Vidu 视频：`5/sec`，13 个 Vidu 视频模型共享 `max_concurrent=5`。

## 调度行为

- 工作室创建/更新/生成时，有限 `max_concurrent` 模型的 `group_count` 不可超过并发上限。
- 同步无限并发模型不设置 `group_count` 并发上限，但提交请求按 `submit_rate_limit` 排队。
- 图片测评不再使用固定全局 4 并发；真实厂商任务在底层提交路径取得限流令牌。
- 视频测评每条输出视频单独提交任务，单条任务完成或失败后释放对应 lease；部分提交失败时保留已提交任务的追踪信息并释放未继续追踪的 lease。
- 共享池模型按 `shared_pool_id` 复用同一个 semaphore。

## 非目标

- 不实现跨进程/多实例分布式限流。
- 不推断文档缺失明确数字的旧模型。
- 不调整非阿里模型和 Seedream 模型。
