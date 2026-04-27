# 图片工作室生产环境卡顿修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 减少图片工作室线上无效预览请求，并让生成接口真正立即返回，修复“切页慢/点击生成没反应”的核心链路。

**Architecture:** 前端通过开发者模式按需请求 payload 预览，并对预览请求做取消/去重；后端把远程参考图探测从 `/generate` 同步返回路径移到后台任务中，接口先快速落库返回 `generating`。这样可以同时降低线上请求风暴和用户点击等待时间。

**Tech Stack:** React 18 + TypeScript + Ant Design、FastAPI、pytest

---

### Task 1: 后端回归测试

**Files:**
- Modify: `backend/tests/test_studio_capabilities.py`
- Test: `backend/tests/test_studio_capabilities.py`

- [ ] **Step 1: 写失败测试，证明 `/generate` 不应同步探测远程图**

- [ ] **Step 2: 运行目标 pytest，确认现状失败**

- [ ] **Step 3: 写回归测试，证明 `/generate` 立即返回 `generating`**

- [ ] **Step 4: 再跑目标 pytest，确认测试语义正确**

### Task 2: 后端异步化修复

**Files:**
- Modify: `backend/app/routers/studio.py`
- Test: `backend/tests/test_studio_capabilities.py`

- [ ] **Step 1: 抽出同步轻量校验与后台重建 payload 的边界**

- [ ] **Step 2: 让 `/generate` 先落 `generating` 并立即返回**

- [ ] **Step 3: 让 `_background_generate` 自行执行远程探测、bbox 归一化与最终 payload 构建**

- [ ] **Step 4: 运行后端目标 pytest，确认通过**

### Task 3: 前端预览降噪

**Files:**
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/pages/Studio/StudioPage.tsx`

- [ ] **Step 1: 让开发者模式预览只在展开时触发**

- [ ] **Step 2: 为预览请求增加取消/去重**

- [ ] **Step 3: 为生成按钮增加提交中即时反馈**

- [ ] **Step 4: 运行前端 `typecheck`，确认通过**

### Task 4: 文档与台账

**Files:**
- Modify: `docs/ISSUES.md`
- Modify: `docs/README.md`
- Modify: `docs/reviews/2026-04-22-online-studio-investigation.md`

- [ ] **Step 1: 更新问题状态与修复方向**

- [ ] **Step 2: 更新文档入口与修复说明**

- [ ] **Step 3: 记录验证结果**
