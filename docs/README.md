# MieMie-Studio 文档入口

这份文件是**人类开发者与 AI 代理的共同入口**。如果你只读一份文档，请先读这里。

## 先看什么

### 规则优先级
1. 仓库根 `AGENTS.md`
2. 本文件
3. 当前要改的 spec：`docs/specs/`
4. 相关 ADR：`docs/adr/`
5. 相关 checklist / playbook：`docs/checklists/`、`docs/playbooks/`
6. 背景性资料：`docs/BACKEND.md`、`docs/FRONTEND.md`、`docs/DASHSCOPE.md`

### 推荐阅读顺序

- **第一次接手仓库**：`AGENTS.md` → `docs/README.md` → `docs/ARCHITECTURE.md` → `docs/reviews/2026-04-platform-audit.md`
- **做功能或修 bug**：对应 spec / ADR → 代码 → checklist
- **接入新模型**：`docs/STUDIO_MODEL_INTEGRATION_GUIDE.md` → `docs/checklists/MODEL_INTEGRATION.md` → 相关 playbook
- **做发布或大改**：`docs/checklists/CHANGE_GATE.md` → `docs/checklists/RELEASE_READINESS.md`

## 文档分层

| 目录/文件 | 用途 | 是否当前有效 |
|---|---|---|
| `docs/specs/` | 功能规格与验收标准 | 是 |
| `docs/adr/` | 架构决策、权衡、迁移策略 | 是 |
| `docs/checklists/` | 评审、模型接入、发布前、文档更新门禁 | 是 |
| `docs/playbooks/` | 真实模型验证、供应商文档治理等操作手册 | 是 |
| `docs/reviews/` | 审计报告、整改 backlog、阶段性结论 | 是 |
| `docs/superpowers/plans/` | 代理执行计划、阶段性 TODO 与完成追踪 | 是 |
| `docs/阿里云模型api文档/` | 厂商原始镜像/摘录 | 否，原始参考，不是平台规范 |

## 当前结论

- 平台已具备基本自动化验证链：后端 pytest、前端 `typecheck/lint/build`
- 当前主风险不在“代码完全不可用”，而在：
  - 复杂页面/路由/服务文件过大
  - 前端自动化测试缺口明显
  - 主题 token 与文档约束存在回潮
  - `config.py ↔ models_registry ↔ frontend types ↔ docs` 多份真相并存
  - 供应商文档镜像包含样式碎片/控制字符，容易误导 AI

详见：`docs/reviews/2026-04-platform-audit.md`

## 开发门禁

任何非微小改动都应同时交付：

- 代码
- 验证证据
- 文档更新

以下情况还必须补齐 spec / ADR：

- 新功能或新任务能力
- 新模型接入
- 接口语义变化
- 重要状态流/数据流调整
- 影响多个页面/多个 router 的重构

## 常用文档

| 文档 | 说明 |
|------|------|
| [架构概览](./ARCHITECTURE.md) | 系统整体结构、请求流、多用户隔离 |
| [后端开发规范](./BACKEND.md) | FastAPI、服务层、schema/capabilities、适配器边界 |
| [前端开发规范](./FRONTEND.md) | React 页面、状态管理、错误处理、动态表单 |
| [UI 设计规范](./UI_GUIDELINES.md) | 主题 token、组件视觉约束 |
| [开发经验指南](./DEVELOPMENT_GUIDE.md) | 现有经验沉淀与补丁历史 |
| [工作室模型接入范式指南](./STUDIO_MODEL_INTEGRATION_GUIDE.md) | 模型接入总方法论 |
| [HappyHorse 视频工作室接入 Spec](./specs/2026-04-happyhorse-video-studio-integration.md) | HappyHorse 文生/图生/参考生/视频编辑接入约束与验收标准 |
| [审计报告](./reviews/2026-04-platform-audit.md) | 全平台批判性审计 |
| [整改 Backlog](./reviews/2026-04-remediation-backlog.md) | 分阶段治理路线 |
| [线上工作室卡顿调查](./reviews/2026-04-22-online-studio-investigation.md) | 2026-04-22 生产站 Edge 复现与接口超时证据 |
| [图片工作室卡顿治理 Spec](./specs/2026-04-studio-prod-latency-hardening.md) | 图片工作室预览降噪与生成接口异步化 |
| [Seedream 图片工作室接入 Spec](./specs/2026-04-seedream-image-studio-integration.md) | 火山引擎 Seedream 5.0 lite / 4.5 接入约束与验收标准 |
| [代理执行计划](./superpowers/plans/) | 排查/实现计划落盘目录 |

## 运行与验证

### 环境要求

- Python 3.10+
- Node.js 18+
- `screen`

### 常用命令

```bash
./run.sh start
./run.sh stop
./run.sh status
./run.sh test
cd frontend && npm run typecheck
cd frontend && npm run lint
cd frontend && npm run build
```

## 文档维护规则

- 供应商 API 变化，先更新 spec / ADR / checklist，再决定是否更新镜像文档
- 如果旧文档与新 spec 冲突，以 spec / ADR 为准，并尽快修正文档入口
- 不要把聊天上下文当规范；规范必须落盘

*最后更新：2026-04-28*
