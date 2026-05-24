# 已知问题与待优化项

> 本文档记录已发现的问题、技术债务和优化建议。
> 修复后请更新状态并记录解决方案。

## 🔴 待修复 Bug

### 6. 视频工作室 Worker 迁移 pre 服务器验收未闭环

**状态**: ✅ 已完成 pre 服务器验收与真实 DashScope 视频 smoke (2026-05-24)

**问题**: 视频工作室创建/重新生成链路已迁移到 Celery dispatcher 与独立 `worker-video` 队列，需要证明 pre 服务器上真实供应商视频任务也能完成，而不只是不带 key 的失败路径。

**本地进展**:
- `VideoStudioTask` 新增 `submit_state`、`submit_started_at`、`submit_attempt_id`，并在 `provider_result_meta.worker_attempt` 记录 worker attempt。
- Celery 新增 `video_studio.generate`，Compose 新增 `worker-video`，图片 `worker` 只消费 `studio` 队列，视频 `worker-video` 只消费 `video_studio` 队列。
- submit stale 会转 `failed/SubmitTimeout`，worker stale 有 provider task id 时只恢复状态协调，不重复提交供应商任务。
- 后端回归覆盖创建入队、启动恢复、submit timeout、worker stale recovery、旧 attempt 丢弃、删除后不复活和 provider error 元数据保留。
- pre 已部署 `7f736affd91a503dd007580af335b0254f3cceb4`，`/api/health redis.ok=true`、`GET /` 200，Celery `ping` 2 nodes online，`registered` 包含 `studio.generate` 和 `video_studio.generate`。
- pre 无 key 失败路径通过：视频任务快速返回 `processing`，worker 写回 `failed`，未永久卡住。
- pre `worker-video restart` 基础恢复通过；server override 已补 `worker-video: image: miemie-studio:pre-local`。
- pre 真实 DashScope 视频 smoke 通过：1 个 `wan2.7-t2v` 文生视频任务最终 `succeeded`，供应商 task id / request id / video URL 各 1 个；SSH 外层连接中断后从服务器任务文件恢复核验，测试用户 key 与 `/tmp` 临时 key 文件均已清理。

**后续治理**:
1. worker 容器当前仍以 root 运行，Celery 启动日志保留 `SecurityWarning`，正式生产发布前需要做非 root hardening。
2. 本轮未启用 OSS，真实视频 smoke 只证明供应商提交、worker 状态协调和平台结果落盘，不证明生成视频已转存到长期对象存储。

**调查记录**: [Step 03 Async Job Orchestrator](./specs/2026-04-step-03-async-job-orchestrator.md)

---

### 5. Celery Worker 执行中断后图片工作室任务可能永久停留 `generating`

**状态**: ✅ 已修复并完成 pre 验证与真实 DashScope 图片 smoke (2026-05-24)

**问题**: `pre` 服务器 Redis + Worker 稳定性补强中，图片工作室任务提交后立即重启 `worker`，Celery worker 可恢复 `ping` 且 `registered` 包含 `studio.generate`，但该任务在 150 秒观察窗口后仍停留 `generating`。

**证据**:
- `docker compose restart worker` 返回成功
- 重启后 `celery inspect ping` 返回 `1 node online`
- 重启后 `registered` 包含 `studio.generate`
- 对应图片工作室任务最终状态：`generating`，`timed_out=true`
- 脱敏 artifact：`docs/reports/artifacts/2026-05-24-redis-worker-stability/redis-worker-core-20260524.json`

**影响**: 阻塞视频工作室生成链路迁移到 worker。若不先修复，执行中断、worker 重启或 broker 抖动可能留下用户侧永久生成中任务。

**修复进展**:
- 图片工作室生成请求新增 `provider_result_meta.generation_attempt`，记录 attempt id、dispatcher、Celery task id、dispatch/start/heartbeat/finish 时间和 stale 超时
- `dispatch_studio_generation` 与 Celery task entrypoint 传递 `attempt_id`
- Worker 开始执行和最终写回前校验 attempt id，避免旧执行覆盖新执行
- `GET /api/studio/{task_id}`、任务列表和再次 generate 前识别 stale `generating`，默认 30 分钟后标记 `failed`
- 已补后端回归覆盖 attempt 写入、stale 失败、stale 后重新生成、旧 attempt 不覆盖新 attempt、worker 异常失败写回
- pre 服务器已部署 `977457bb4aa8e1b89d7f9fcb1efac5bf32820006`，临时设置 `MIEMIE_STUDIO_GENERATION_STALE_SECONDS=90`
- pre 验证中，同一任务连续两次 generate 复用同一 attempt；`restart worker` 后任务在约 93 秒由 GET stale 兜底标记为 `failed`，`failure_reason=stale_generating`
- 真实 DashScope 图片队列 smoke 已补跑成功：`wan2.6-t2i` 任务快速返回 `generating`，最终 `completed`，平台记录 1 个图片结果和 1 个 request id
- 测试用户临时 key 已删除，补充检查确认服务器用户配置中没有 DashScope / production / test key

**后续**:
1. 视频工作室 worker 迁移需要单独计划、实施和验收
2. worker 非 root 运行、Redis 无密码、SSH 新连接偶发关闭仍作为正式生产发布前硬化项

**调查记录**: [pre 服务器验证报告](./reports/2026-05-18-pre-server-validation.md)

---

### 4. 线上图片工作室切页慢加载与生成按钮无响应

**状态**: 🟡 本地已修复，pre API 体验 smoke 已通过，仍待浏览器/线上验证 (2026-05-24)

**问题**: 生产站 `https://studio.miemie.co/` 使用 `guest` 测试账号进入图片工作室时，切换页面会出现全页转圈；任务详情中点击“开始生成”后经常没有即时反馈，仍停留在“待生成”状态。

**证据**:
- Edge DevTools Console 显示 `/api/studio/preview-payload` 多次返回 `520/524`
- `/api/studio/{task_id}/generate` 返回过 `520`
- `/api/studio/{task_id}` 返回过 `522`
- 生产站首页与 `/api/health` 正常，问题集中在工作室业务接口

**初步原因**: `/preview-payload` 与 `/generate` 在请求返回前会同步读取并校验 wan2.7 参考图；线上下载/解析远程图片较慢时，Cloudflare 或源站超时导致前端长时间无反馈。

**建议方案**:
1. `/preview-payload` 默认不做完整远程图片下载，改为缓存、短超时或开发者模式手动探测
2. `/generate` 真正做到先写入 `generating` 并立即返回，慢校验与供应商调用进入后台任务
3. 前端 payload 预览请求增加取消/去重，只保留最后一次有效请求
4. 生成按钮增加“提交中”即时反馈与 Cloudflare 错误提示
5. 核对 2026-04-22 03:00 UTC 左右的源站和 Cloudflare 日志

**本地修复进展**:
- 已实现：开发者模式未展开时不再自动请求 `/api/studio/preview-payload`
- 已实现：预览请求增加取消/去重，避免旧请求覆盖新状态
- 已实现：`/api/studio/{task_id}/generate` 不再在返回前同步探测 wan2.7 远程参考图
- 已验证：`backend/tests/test_studio_capabilities.py` 33 项通过，前端 `npm run typecheck` 通过

**pre 体验验证进展**:
- 已验证：`miemie-pre` 项目列表、图片工作室列表、视频工作室列表均快速返回 `200`
- 已验证：图片工作室创建任务后首次生成约 `14.0ms` 返回 `generating`
- 已验证：同一图片任务连续两次 generate 均返回 `200/generating`，且复用同一个 attempt，未重复提交
- 已验证：无 key 图片任务最终进入 `failed`，错误可见，不静默卡住
- 真实浏览器验证发现生产 bundle 白屏，根因为 Vite 手动分包把 React 生态依赖和 AntD 子模块拆出初始化循环；已将 AntD 主包收敛到单一 `antd-vendor` 并新增 `npm run test:vite-chunks` 回归。
- 已验证：`miemie-pre` 运行 `32ff189a57ca13cafcc73f7dd6e956ca1d8ce1e9` 后，真实浏览器登录页不再白屏，登录/注册切换可交互，控制台 error/warn 为 `0`。
- 待补：真实浏览器网络面板验证工作室页面切换无长时间全页转圈、开发者模式未展开时不触发 heavy preview
- 证据：`docs/reports/2026-05-24-next-phase-experience-and-performance.md`

**调查记录**: [线上工作室卡顿与生成无响应调查记录](./reviews/2026-04-22-online-studio-investigation.md)
**修复规格**: [图片工作室生产环境卡顿治理](./specs/2026-04-studio-prod-latency-hardening.md)

---

### 1. ~~OSS 测试连接误报权限错误~~

**状态**: ✅ 已修复 (2024-12-24)

**问题**: 设置页 OSS 配置即使正确，点击测试连接仍显示"访问被拒绝，请检查 AccessKey 权限"，但实际上传功能正常。

**原因**: 测试方法使用了 `bucket.get_bucket_info()`，需要更高的 Bucket 管理权限。

**解决方案**: 改为上传并删除一个测试文件（`.connection_test`），只需要对象读写权限即可。

---

### 2. ~~StorageService 方法不一致~~

**状态**: ✅ 已修复 (2025-12-30)

**问题**: 部分存储方法使用文件锁 `_write_json_with_lock`，部分直接使用 `open()`，并发安全性不一致。

**解决方案**: 统一所有保存方法使用 `_write_json_with_lock` 和 `self._lock`。

---

### 3. ~~批量生成中断后状态残留~~

**状态**: ✅ 已修复 (2025-12-30)

**问题**: 批量生成被中断后，`generatingItems` Set 中的项目 ID 可能未被清除，导致无法重新生成。

**解决方案**: 在 `resetGeneration` 时同时清空 `generatingItems`。

---

## 🟡 性能优化

### 1. 文件遍历效率

**问题**: `get_xxx_by_project()` 方法遍历目录下所有 JSON 文件，项目多时效率低。

**当前代码**:
```python
for file_path in self.dir.glob("*.json"):
    with open(file_path) as f:
        data = json.load(f)
        if data.get("project_id") == project_id:
            items.append(...)
```

**建议**:
1. 建立索引文件（如 `index.json`）按 project_id 索引
2. 或改用 SQLite 数据库
3. 或使用目录结构 `projects/{project_id}/items/`

---

### 2. 图片 Base64 转换内存占用

**问题**: `wan2.6-image` 参考图处理时，将图片转为 Base64 会占用较多内存。

**位置**: `services/dashscope/text_to_image.py` - `validate_and_resize_reference_image`

**建议**: 考虑使用临时文件或流式处理大图片。

---

### 3. 前端状态持久化

**问题**: 部分 Zustand store 持久化了不必要的运行时状态。

**建议**: 检查各 store 的 `partialize` 配置，确保只持久化用户设置。

---

## 🟢 功能改进建议

### 1. 添加任务队列

**现状**: 多个生成任务同时发起，可能导致 API 限流或资源竞争。

**建议**: 实现任务队列，限制并发数量，支持任务优先级。

---

### 2. 添加生成历史

**现状**: 生成的图片/视频只保存最新结果，历史版本丢失。

**建议**: 为每个资源保存生成历史，支持回滚。

---

### 3. 错误重试机制

**现状**: API 调用失败后需要手动重试。

**建议**: 实现自动重试，支持配置重试次数和间隔。

---

### 4. 批量导入/导出

**现状**: 项目数据无法批量导入导出。

**建议**: 支持项目 ZIP 打包导出和导入。

---

## 🔧 代码质量

### 1. 日志 print 语句

**状态**: ✅ 已修复 (2026-03-28)

**问题**: 服务层大量使用 `print()` 输出日志，虽然会重定向到日志文件，但不够规范。

**解决方案**: `oss.py` 和 `studio.py` 中约 25 处 `print()` 替换为 `logging.getLogger(__name__)` 的 `logger.info/warning/error`。

---

### 2. 前端类型不完整

**问题**: `api.ts` 中部分接口使用 `any` 类型。

**建议**: 补充完整的 TypeScript 类型定义。

---

### 3. 配置重复定义

**状态**: 🔄 重构中

**问题**: 模型配置在 `config.py` 和前端 `api.ts` 中都有定义，需要同步维护。

**解决方案**: 实施统一模型配置中心重构，详见 [REFACTORING.md](./REFACTORING.md)

---

### 4. ~~CSS 变量系统不统一~~

**状态**: ⚠️ 部分回归 (2026-04-16)

**问题**: 主题系统主干已统一到 Ant Design token，但仍存在布局层和部分超大页面中的硬编码颜色/渐变，导致主题规范回潮。

**解决方案**: 
- 移除 `--studio-*` 和 `--color-*` CSS 变量，改由 Ant Design ConfigProvider theme token 统一驱动
- 继续清理布局层和超大页面中的硬编码颜色
- 优先处理 `main.tsx`、`MainLayout.tsx` 与核心工作流页面
- 实现日间/夜间双主题系统
- 详见 [UI_GUIDELINES.md](./UI_GUIDELINES.md)

---

### 5. ~~缺少单元测试~~

**状态**: ⚠️ 后端基本覆盖，前端仍明显不足 (2026-04-16)

**问题**: 后端已有较完整 pytest 覆盖，但前端几乎没有自动化测试，复杂页面主要依赖人工回归和构建检查。

**解决方案**: 后端当前已有完整 pytest 套件（2026-04-16 审计时基线为 112 项，治理后继续增长），但前端需尽快补：
- 关键流程组件测试
- 表单/状态迁移测试
- 能力 schema 驱动页面的 smoke test
- 关键导出/创建/删除流程的回归测试

运行方式: `./run.sh test` 或 `cd backend && python -m pytest tests/ -v`。

---

## 📝 文档待补充

- [ ] 部署文档
- [ ] 用户使用手册
- [ ] API 变更日志
- [ ] 贡献指南

---

## 更新记录

| 日期 | 更新内容 |
|------|----------|
| 2026-04-22 | 新增线上图片工作室切页慢加载与生成按钮无响应问题 |
| 2026-03-28 | 标记 print→logger 和单元测试为已修复 |
| 2026-02-05 | 新增 CSS 变量统一问题（已修复） |
| 2025-12-30 | 创建文档，记录初始问题 |

---

*如发现新问题，请在此文档中添加并标注状态。*
