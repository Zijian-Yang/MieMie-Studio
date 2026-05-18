# 已知问题与待优化项

> 本文档记录已发现的问题、技术债务和优化建议。
> 修复后请更新状态并记录解决方案。

## 🔴 待修复 Bug

### 4. 线上图片工作室切页慢加载与生成按钮无响应

**状态**: 🟡 本地已修复，待线上验证 (2026-04-22)

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

**调查记录**: [线上工作室卡顿与生成无响应调查记录](./reviews/2026-04-22-online-studio-investigation.md)
**修复规格**: [图片工作室生产环境卡顿治理](./specs/2026-04-studio-prod-latency-hardening.md)

---

### 5. 线上 `wan2.7-videoedit` 视频编辑任务卡在运行中且无厂商 ID

**状态**: 🟡 本地已修复，待线上部署验证 (2026-05-18)

**问题**: 生产站 `qingshui` 账号下多个视频工作室 `wan2.7-videoedit` 任务长期显示运行中，但任务详情没有 `task_id` / `request_id`，因此状态轮询无法展示厂商侧进度。

**证据**:
- 线上 3 个卡住任务均为 `status=processing`、`task_kind=video_edit_global`、`model_id=wan2.7-videoedit`、`group_count=5`、`task_ids=[]`、`request_ids=[]`
- 后端日志中，相关任务的 `/regenerate` 或创建接口返回 200 后，没有后续“已提交”或“提交失败”日志
- `/status` 接口在 `task_ids=[]` 时直接返回任务对象，无法自愈，也不会释放模型并发槽
- 日志出现已删除任务随后又由后台协程写出“已提交 3 个 API 任务”的现象，说明删除没有取消后台提交，也没有释放内存中的 inflight lease

**根因**: 视频工作室创建/重新生成任务时先保存 `processing` 并清空 `task_ids/request_ids`，随后用 `asyncio.create_task` 后台批量提交。`wan2.7-videoedit` 的模型并发上限为 5，提交协程会先为每个 group 获取 inflight lease，只有全部 group 提交完成后才持久化 `task_ids/request_ids`。当任务在后台提交期间被删除或重新生成时，旧 lease 可能滞留在单 worker 内存中；后续 `group_count=5` 任务等待剩余并发槽，无法完成 `asyncio.gather`，于是长期保持无厂商 ID 的 `processing` 状态。

**建议方案**:
1. 删除和批量删除任务时，释放该任务已知 `task_ids` 的 inflight lease，并标记/取消仍在提交中的后台任务
2. 重新生成前释放旧任务 lease，并避免在新提交成功前彻底丢弃旧的厂商元数据
3. 提交阶段增加超时，超时后将 `processing && task_ids=[]` 标记为失败并写入可见错误
4. 将部分已提交的 `task_id/request_id` 及时落盘，避免等待全部 group 完成后才可观测
5. worker 启动时对 `processing && task_ids=[]` 的陈旧任务做 reconciliation，提示用户重新生成或自动失败

**本地修复进展**:
- 已实现：`VideoStudioTask` 增加 `submit_state`、`submit_started_at`、`submit_attempt_id`，用于识别当前提交尝试
- 已实现：删除、批量删除、重新生成会取消本地后台提交并释放已知 inflight lease
- 已实现：后台提交保存前校验任务仍存在且 `submit_attempt_id` 未变化，避免删除后的迟到提交复活任务
- 已实现：`processing && task_ids=[]` 的陈旧提交会失败化，并写入 `SubmitTimeout` 元信息
- 已验证：`backend/tests/test_video_studio_capabilities.py` 63 项通过，`./run.sh test` 后端全量 225 项通过

**调查记录**: [Wan2.7 视频编辑线上卡死排查计划](./superpowers/plans/2026-05-18-wan27-video-edit-prod-stuck-investigation.md)
**修复计划**: [视频工作室 inflight lease 修复计划](./superpowers/plans/2026-05-18-video-studio-inflight-lease-fix.md)

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
| 2026-05-18 | 新增线上 `wan2.7-videoedit` 视频编辑任务卡住且无厂商 ID 问题 |
| 2026-04-22 | 新增线上图片工作室切页慢加载与生成按钮无响应问题 |
| 2026-03-28 | 标记 print→logger 和单元测试为已修复 |
| 2026-02-05 | 新增 CSS 变量统一问题（已修复） |
| 2025-12-30 | 创建文档，记录初始问题 |

---

*如发现新问题，请在此文档中添加并标注状态。*
