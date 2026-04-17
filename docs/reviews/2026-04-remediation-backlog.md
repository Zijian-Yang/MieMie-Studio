# 2026-04 整改 Backlog

## Phase 0：已在本轮完成

- 修复 `UserService` 并发读改写风险
- 修复关键页面吞掉后端错误细节的问题
- 修复根布局与入口层主题 token 回潮
- 建立 `spec / adr / checklist / playbook / review` 文档分层

## Phase 1：下一批必须做

### P1

1. **拆分 `frontend/src/services/api.ts`**
   - 目标：transport、shared types、domain types 分离
   - 验收：单文件显著缩小；页面不再从一个巨型文件拉所有类型

2. **拆分 `VideoStudioPage`**
   - 目标：提取数据加载、能力表单、任务详情、媒体预处理
   - 验收：主页面只保留编排逻辑

3. **为前端补 smoke tests**
   - 目标：登录、项目列表、至少一个工作室创建流程
   - 验收：CI/本地可执行

4. **建立真实模型验证脚本或固定流程**
   - 目标：每次模型接入都能稳定抽检成功/失败路径
   - 验收：依照 playbook 可复现

## Phase 2：中期治理

### P2

1. **拆分 `StudioPage` / `FramesPage`**
2. **下沉 router 逻辑到 service / builder / adapter**
3. **把镜像厂商文档与平台规范彻底隔离**
4. **为 `config.py` 做清晰的“兼容层”边界说明**
5. **建立复杂页面复杂度阈值和重构触发条件**

## Phase 3：长期优化

### P3

1. 为项目级资源建立索引或存储抽象
2. 考虑把部分 JSON 扫描型数据迁到更适合查询的存储
3. 建立统一的 UI 组件目录与设计 token 扩展策略

## 优先级原则

- 优先修“多人/多 AI 协作时会反复踩”的问题
- 优先修“一个地方改动会波及多个页面/多个 router”的问题
- 优先让规范落盘，不再依赖口口相传
