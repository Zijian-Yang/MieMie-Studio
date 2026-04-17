# 2026-04 平台批判性审计报告

## 范围

- 代码：后端认证、存储、工作室主链路、前端布局与关键页面
- 架构：模型真相来源、页面/路由/服务膨胀、可持续演进能力
- UI：主题一致性、导航结构、错误反馈、复杂页面维护成本
- 文档：入口、规范、厂商镜像、AI 可接手性

## 基线

- 后端：审计启动时 `112` 个 pytest 通过；本轮治理收尾后为 `115`
- 前端：`typecheck / lint / build` 通过
- 自动化缺口：前端几乎没有测试
- 结构热点：
  - `frontend/src/pages/VideoStudio/VideoStudioPage.tsx`
  - `frontend/src/pages/Studio/StudioPage.tsx`
  - `frontend/src/pages/Frames/FramesPage.tsx`
  - `frontend/src/services/api.ts`
  - `backend/app/routers/studio.py`
  - `backend/app/routers/video_studio.py`
  - `backend/app/services/video_capabilities.py`

## 执行摘要

平台当前**不是不可用**，而是已经进入“功能持续堆叠后，维护复杂度高于局部缺陷本身”的阶段。

本轮治理确认了三类主问题：

1. **正确性风险已开始集中在并发写入、错误反馈和多份真相漂移**
2. **复杂页面/复杂路由过大，导致 UI 与逻辑耦合过深**
3. **文档入口分散且新旧范式并存，AI 接手成本高**

## 本轮已修复

### 1. `UserService` 并发读改写丢更新

- **Severity**: P1
- **Domain**: 后端 / 认证 / 并发安全
- **Evidence**: `backend/app/services/user_service.py`
- **现象**: 注册、登录、登出、改密都走“读文件 → 改内存 → 写文件”，但原实现没有实例级锁，也没有文件锁。
- **根因**: `users.json` / `sessions.json` 的持久化与 `StorageService` 采用了不同并发模型。
- **影响**: 高并发下可能丢用户记录、丢 session、覆盖最后登录时间。
- **修复**:
  - 增加实例级 `RLock`
  - 增加共享/排他文件锁
  - 增补并发注册 / 并发登录测试
- **验证**: `backend/tests/test_fixes.py`

### 2. 前端页面吞掉服务端错误细节

- **Severity**: P1
- **Domain**: 前端 / 功能逻辑 / UX
- **Evidence**:
  - `frontend/src/pages/Login/LoginPage.tsx`
  - `frontend/src/pages/Gallery/GalleryPage.tsx`
  - `frontend/src/pages/Script/ScriptPage.tsx`
  - `frontend/src/pages/Videos/VideosPage.tsx`
- **现象**: 全局 API 层已经把错误包装成 `Error.message`，但页面仍按 axios 原始 `error.response` 读取，导致真实错误原因被吞掉。
- **根因**: 页面错误处理和 `services/api.ts` 的约定不一致。
- **影响**: 用户只能看到“上传失败 / 解析失败 / 登录失败”等泛化提示。
- **修复**:
  - 新增 `frontend/src/utils/apiError.ts`
  - 统一关键页面错误提取
- **验证**: 前端 `typecheck / lint`

### 3. 主题 token 规范在根布局回潮

- **Severity**: P1
- **Domain**: UI / 可维护性
- **Evidence**:
  - `frontend/src/main.tsx`
  - `frontend/src/components/Layout/MainLayout.tsx`
- **现象**: 根布局和 `body` 级样式仍在写死颜色常量。
- **根因**: 主题规范落到了页面级，但没有把入口和布局层彻底纳入约束。
- **影响**: 主题切换的一致性与后续设计系统治理被削弱。
- **修复**:
  - `main.tsx` 改为从 theme config 取运行时色值
  - `MainLayout.tsx` 改为用 token 派生背景与头像渐变
- **验证**: 前端 `typecheck / lint / build`

### 4. 文生图服务返回契约漂移

- **Severity**: P1
- **Domain**: 后端 / 工作室 / 真实模型链路
- **Evidence**:
  - `backend/app/services/dashscope/text_to_image.py`
  - `backend/app/routers/frames.py`
- **现象**: 真实文生图任务提交与轮询成功后，平台内部仍因把 `GenerationResult` 当作 `List[str]` 使用而崩溃。
- **根因**: `generate_batch()` 已升级为结构化返回，但 `generate()` 和旧调用方没有同步更新。
- **影响**: 真实环境下会出现“厂商成功、平台失败”。
- **修复**:
  - `generate()` 改为读取 `result.urls`
  - `frames.py` 增加对结构化结果的兼容
  - 新增服务返回契约测试
- **验证**: 真实 `wan2.6-t2i` 调用成功返回 OSS URL；后端全量测试通过

## 主要未完成问题

### 1. 超大页面 / 超大路由仍是主债务源

- **Severity**: P2
- **Evidence**:
  - `frontend/src/pages/VideoStudio/VideoStudioPage.tsx`
  - `frontend/src/pages/Studio/StudioPage.tsx`
  - `backend/app/routers/studio.py`
  - `backend/app/routers/video_studio.py`
- **影响**:
  - 逻辑难以局部验证
  - UI 状态与数据契约耦合
  - 新模型接入容易继续复制逻辑
- **建议**:
  - 页面拆为：数据 hook / canonical form / preview panel / task detail
  - router 下沉为 schema builder + adapter + orchestration service

### 2. `config.py ↔ registry ↔ frontend types ↔ docs` 多份真相仍存在

- **Severity**: P2
- **Domain**: 架构
- **Evidence**:
  - `backend/app/config.py`
  - `backend/app/models_registry/`
  - `frontend/src/services/api.ts`
  - `docs/BACKEND.md`
- **影响**: 新功能落地时容易出现“代码能跑、文档和页面含义不同步”。
- **建议**:
  - 新工作室能力以 schema/capabilities 为真相
  - `api.ts` 收敛成 transport + type adapter，而非继续堆领域定义

### 3. 前端自动化测试仍不足

- **Severity**: P2
- **Domain**: 工程质量
- **Evidence**: `frontend/` 下缺少 test/spec 文件
- **影响**: 复杂页面回归主要依赖人工观察和构建通过
- **建议**:
  - 先为登录、项目、工作室创建最小 smoke test
  - 再补 schema 驱动表单和错误提示测试

### 4. 厂商镜像文档污染规范空间

- **Severity**: P2
- **Domain**: 文档治理
- **Evidence**: `docs/阿里云模型api文档/`
- **现象**: 原始镜像中混有样式片段、控制字符、重复段落。
- **影响**: AI 容易把厂商原始碎片误当平台规范。
- **建议**:
  - 原始镜像只作为参考
  - 平台侧结论必须沉淀到 spec / ADR / playbook

## UI 结论

- 导航层级总体清晰，但“工具域 + 工作流域”在侧栏里密集混排，新人理解成本偏高
- 深色主题基调稳定，但局部硬编码/叠加层颜色仍影响一致性
- 复杂表单的主要风险不是视觉，而是**状态过多、反馈分散、错误链路不可预测**
- 登录页视觉独立性强，但与主应用设计系统仍存在一定割裂

## 文档结论

- 现有文档最主要问题不是数量不足，而是**入口和优先级不明确**
- 本轮新增的 `spec / adr / checklist / playbook / review` 分层，已经可以作为未来 AI 接手的主入口
- `docs/BACKEND.md`、`docs/FRONTEND.md` 仍保留大量历史内容，应逐步做增量收敛，而不是继续并行扩写

## 真实模型验证结果

### 成功路径

- **图片**：`wan2.6-t2i` 成功提交、轮询完成并转存 OSS
- **视频**：`wan2.6-t2v` 成功提交、轮询完成并转存 OSS，同时记录 `request_id` 与 `usage`
- **音频**：`cosyvoice-v3-flash` + `longwan_v3` 成功合成并转存 OSS

### 失败路径

- **音频失败用例**：无效音色 ID 能稳定抛出 `RuntimeError`，并带回供应商的 `InvalidParameter`/引擎错误信息

### 结论

- 当前默认配置链路、外网访问、DashScope 调用与 OSS 持久化均可用
- 真实验证暴露并推动修复了 1 个仅会在“厂商成功后”才显现的返回契约问题

## 下一步

1. 先拆 `VideoStudioPage` / `StudioPage` / `api.ts`
2. 补前端 smoke tests
3. 把真实模型验证流程固化到 playbook
4. 逐步把旧文档里的“已失效范式”迁出或标记为 legacy
