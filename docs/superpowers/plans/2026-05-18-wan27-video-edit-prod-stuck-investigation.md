# Wan2.7 视频编辑线上卡死排查计划

**时间**：2026-05-18 CST  
**目标**：检查生产服务器上 `qingshui` 账号下多个 `wan2.7-videoedit` 视频编辑任务一直处于运行中，且任务详情未显示 `task_id` / `request_id` 的原因。  
**原则**：先读文档、代码、日志和数据证据；不先改线上数据；不在文档中记录服务器密码、Token、API Key 等敏感信息。

## 背景约束

- 视频工作室 `wan2.7-videoedit` 应支持 1 个待编辑视频 + 最多 3 张参考图。
- 已提交任务详情页应展示 `task ids`、`request ids`、`provider_payload_snapshot`、`provider_result_meta`。
- `/preview-payload` 与真实提交应共用同一套构参逻辑，开发者模式可核对请求体。
- 线上排查需遵循系统化调试：先收集进程、日志、用户数据、任务状态和代码版本证据，再形成根因假设。

## 排查步骤

- [x] 阅读本地文档入口和视频工作室/wan2.7 相关约束。
- [x] 登录生产服务器，确认部署目录、当前 git 版本、运行方式和服务健康状态。
- [x] 定位本地 `qingshui` 用户 ID 与视频工作室任务存储结构。
- [x] 找出线上状态为运行中的 `wan2.7-videoedit` 任务，记录创建/更新时间、平台任务 ID、请求 ID、错误元数据和素材信息。
- [x] 检查线上后端日志中对应任务提交、payload 构建、DashScope 调用、轮询和异常信息。
- [x] 对照当前代码的数据流，判断 `processing` 但无 `task_id/request_id` 的可形成路径。
- [x] 更新本计划的排查日志，并视结果补充 `docs/ISSUES.md`。

## 排查日志

- 2026-05-18：创建计划，准备进行生产服务器只读排查。
- 2026-05-18：尝试使用提供的 root SSH 凭据登录 `47.79.125.140`，服务器返回 `Permission denied (publickey,password)`；为避免触发锁定，停止继续尝试。
- 2026-05-18：生产站 `/api/health` 可访问，当前线上版本为 `3f6874c9b21bf1511d6f5a44440b4ec437412718`，启动时间 `2026-05-08T08:00:56Z`。
- 2026-05-18：本地 `qingshui` 用户 ID 为 `04383daf-2b3c-497d-941f-1deefe31fbf0`，视频工作室任务存于 `backend/data/users/{user_id}/video_studio/*.json`。
- 2026-05-18：代码路径显示任务创建时先保存为 `processing`，随后后台协程才提交 DashScope 并写入 `task_ids/request_ids`。若后台协程卡在模型并发槽、提交前阻塞或进程重启丢失，该任务会保持 `processing` 且没有厂商 `task_id/request_id`。
- 2026-05-18：`wan2.7-videoedit` 被配置为最多 5 个处理中任务；并发槽在提交成功后只会在 `/video-studio/{id}/status` 查询到终态时释放。若前 5 个任务未被轮询到终态、查询过期返回 `UNKNOWN`，或进程里等待队列在重启时丢失，后续任务存在长期无厂商 ID 的风险。
- 2026-05-18：生产 SSH 已连通，部署目录为 `/home/MieMie-Studio`；线上版本 `3f6874c9b21bf1511d6f5a44440b4ec437412718`，`run_mode=prod`，`MIEMIE_WORKERS=1`，当前 gunicorn worker PID `573143`，启动于 `2026-05-13 22:19:48 CST`。
- 2026-05-18：线上 `qingshui` 用户 ID 为 `4af026d5-b51b-430d-8582-fc913379764b`。其视频工作室目录中当前仅有 3 个 `processing && wan2.7-videoedit && task_ids=[] && request_ids=[]` 任务：
  - `779f58a9-6cb8-41cb-ba64-5dd26f27effd` / `case12test`，创建 `2026-05-18T10:52:05.669571`，更新 `2026-05-18T12:18:57.079512`，`group_count=5`
  - `8449b6c5-aebf-4777-b2a5-cd4b23043ee8` / `case13test`，创建 `2026-05-18T11:33:25.197134`，更新 `2026-05-18T12:20:18.486570`，`group_count=5`
  - `e1c59cac-9c03-427e-bb1b-c06fb1df01df` / `case15test`，创建 `2026-05-18T12:23:32.683470`，更新 `2026-05-18T12:27:34.347888`，`group_count=5`
- 2026-05-18：后端日志显示 `779f...` 曾在 `10:55:28` 和 `11:20:04` 成功提交 3 个 API 任务，`8449...` 曾在 `11:42:17` 成功提交 3 个 API 任务；但二者后续 regenerate 后清空了 `task_ids/request_ids`，之后没有新的“已提交”或“提交失败”日志。
- 2026-05-18：`backend.log` 从第 6742 行开始到文件末尾，没有任何视频工作室“已提交/提交失败/Traceback/ERROR”日志；同期三个卡住任务的 `/status` 分别被轮询约 1251、1236、977 次，均返回 200。由于 `/status` 在 `task_ids=[]` 时直接返回，轮询无法触发恢复。
- 2026-05-18：日志显示一个更明确的 lease 泄漏触发链：`bb4f7d53-9816-46de-8a49-51c57a3e7fcd` 在第 6661 行被删除并随即 404；第 6677 行后台协程又记录“已提交 3 个 API 任务”，说明删除没有取消后台提交，后台保存又把任务文件复活；第 6717 行该任务再次被删除。删除接口只删除 JSON 文件，不释放 `_video_studio_inflight_leases`，因此这些已提交任务的模型并发槽会留在单 worker 内存里。
- 2026-05-18：根因结论：不是前端没有展示字段，也不是 DashScope 已返回但字段丢失；而是视频工作室把任务先置为 `processing` 并清空 ID，再等待后台批量提交。删除/重新生成与后台提交并发时，`wan2.7-videoedit` 的 inflight lease 可以泄漏；后续 `group_count=5` 任务在 `_submit_api_tasks` 内等待凑齐 5 个并发槽，`asyncio.gather` 未返回前不会持久化任何部分 `task_id/request_id`，于是 UI 长期显示运行中但没有厂商 ID。
- 2026-05-18：本次没有修改线上任务数据。短期恢复选项：重启后端 worker 清空内存 semaphore/lease，再将这 3 个无 ID 任务标记失败或重新生成；需注意第一个卡住的 regenerate 可能已经提交了少量未持久化的厂商任务，重启不会取消厂商侧任务。长期修复应包括：删除/批量删除释放已知 lease 并取消后台任务、regenerate 前释放旧 lease、提交阶段增加超时并把 `submit_state`/部分提交结果持久化、启动时对 `processing && task_ids=[]` 做超时 reconciliation。
