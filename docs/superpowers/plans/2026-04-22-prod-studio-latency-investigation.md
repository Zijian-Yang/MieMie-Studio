# 线上工作室卡顿与无响应排查计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在生产站 `https://studio.miemie.co/` 上稳定复现页面切换慢加载与工作室“生成/重新生成”无响应问题，并输出可定位的浏览器与接口证据。

**Architecture:** 本次排查先按系统化调试流程建立复现基线，再从浏览器 UI、网络请求、接口响应三个边界收集证据，最后对比本地/线上差异并把结论沉淀到仓库文档。整个过程优先记录证据，不先入为主地下修复结论。

**Tech Stack:** Microsoft Edge、线上站点 `studio.miemie.co`、FastAPI `/api/*`、React + Vite 前端、仓库文档体系

---

### Task 1: 建立复现基线

**Files:**
- Create: `docs/reviews/2026-04-22-online-studio-investigation.md`
- Modify: `docs/ISSUES.md`

- [x] **Step 1: 记录访问与环境基线**

Run: `date '+%F %T %Z'`
Expected: 输出排查开始时间，后续证据统一引用该时间窗口。

- [x] **Step 2: 使用 Edge 登录生产站**

Action: 打开 `https://studio.miemie.co/`，使用账号 `guest` 登录，确认进入主界面。
Expected: 登录成功，具备页面跳转与工作室任务操作能力。

- [x] **Step 3: 记录慢加载与卡住的精确操作路径**

Action: 按“页面切换慢加载 → 工作室点击生成/重新生成无效 → 等待后才恢复”的顺序做最短可复现路径。
Expected: 得到可重复的页面、按钮、项目/任务入口与大致发生频率。

### Task 2: 收集浏览器侧证据

**Files:**
- Modify: `docs/reviews/2026-04-22-online-studio-investigation.md`

- [x] **Step 1: 记录页面切换时的可见症状**

Action: 记录持续转圈、空白、按钮禁用、点击无反馈、等待多久才恢复等现象。
Expected: 明确症状是前端路由阻塞、数据请求阻塞还是任务提交后无状态反馈。

- [x] **Step 2: 采集关键网络请求**

Action: 打开 DevTools Network，复现一次慢跳转和一次工作室生成无效，记录慢请求、失败请求、重复请求与 pending 请求。
Expected: 得到至少 1 组页面切换证据和 1 组工作室任务证据。

- [x] **Step 3: 记录控制台报错或告警**

Action: 查看 Console 中与接口、状态管理、资源加载有关的报错。
Expected: 确认是否存在前端异常、跨域/鉴权、轮询或资源超时问题。

### Task 3: 补充接口层交叉验证

**Files:**
- Modify: `docs/reviews/2026-04-22-online-studio-investigation.md`
- Modify: `docs/ISSUES.md`

- [x] **Step 1: 对关键接口做直连抽查**

Run: `curl -I -L -s https://studio.miemie.co/`
Expected: 确认站点入口可达，并记录服务端基础响应头。

- [x] **Step 2: 对浏览器里最慢的接口做最小复测**

Run: 使用 `curl` 或浏览器重放最慢的一个 `GET` / `POST` 请求，记录响应时间与状态码。
Expected: 判断问题更偏浏览器交互层还是接口响应层。

- [x] **Step 3: 对比本地已知较好的表现**

Action: 把线上异常点与用户反馈中的“本地好很多”并排记录，形成差异假设。
Expected: 产出后续修复优先级：前端交互、接口性能、轮询/任务状态机、部署环境。

### Task 4: 沉淀结论与下一步

**Files:**
- Modify: `docs/reviews/2026-04-22-online-studio-investigation.md`
- Modify: `docs/ISSUES.md`
- Modify: `docs/README.md`

- [x] **Step 1: 汇总复现路径与证据**

Action: 把时间、页面、操作路径、网络证据、接口证据整理到调查文档。
Expected: 其他开发者可按文档快速复现。

- [x] **Step 2: 更新问题台账**

Action: 在 `docs/ISSUES.md` 追加这次线上卡顿问题、状态、证据摘要与建议方向。
Expected: 问题进入仓库长期追踪面板。

- [x] **Step 3: 更新文档入口**

Action: 在 `docs/README.md` 补充 `docs/superpowers/plans/` 与本次调查报告入口。
Expected: 后续可从文档入口找到计划与调查结论。

## 完成记录

- 2026-04-22：使用本机 Microsoft Edge 登录生产站并复现图片工作室任务 `4` 的生成按钮无即时反馈。
- 2026-04-22：DevTools Console 采集到 `/api/studio/preview-payload`、`/api/studio/{task_id}/generate`、`/api/studio/{task_id}` 的 `520/522/524`。
- 2026-04-22：用 `curl` 确认生产站首页和 `/api/health` 正常，问题集中在工作室业务接口。
- 2026-04-22：调查报告已保存到 `docs/reviews/2026-04-22-online-studio-investigation.md`，问题已进入 `docs/ISSUES.md`。
