# MieMie-Studio 开发文档

> 本文档由 AI 辅助生成，记录平台的架构设计、开发规范和已知问题。
> 后续开发时请先阅读本文档，并在开发完成后及时更新。

## 📚 文档索引

| 文档 | 说明 |
|------|------|
| [架构概览](./ARCHITECTURE.md) | 系统整体架构、技术栈、目录结构 |
| [后端开发规范](./BACKEND.md) | FastAPI 后端开发规范、服务层设计、数据存储 |
| [前端开发规范](./FRONTEND.md) | React 前端开发规范、状态管理、组件设计 |
| [API 设计规范](./API.md) | RESTful API 设计、请求/响应格式、错误处理 |
| [数据模型](./MODELS.md) | Pydantic 模型定义、数据库 Schema |
| [DashScope 集成](./DASHSCOPE.md) | 阿里云模型服务集成、参数配置 |
| [已知问题](./ISSUES.md) | 待修复的 Bug、待优化项、技术债务 |
| [变更日志](./CHANGELOG.md) | 版本变更记录 |

## 🚀 快速开始

### 环境要求

- Python 3.12+
- Node.js 18+
- pnpm / npm

### 启动开发环境

```bash
# 1. 启动后端
cd backend
source ../venv/bin/activate  # 激活虚拟环境
uvicorn app.main:app --reload --port 8000

# 2. 启动前端（另一个终端）
cd frontend
npm run dev
```

### 默认端口

- 后端 API: http://localhost:8000
- 前端开发服务器: http://localhost:5173
- API 文档: http://localhost:8000/docs

## 🎯 开发原则

### 1. 保持简单
- 不要过度设计，只实现必要功能
- 避免添加"未来可能需要"的代码
- 优先使用已有抽象，遵循 DRY 原则

### 2. 用户数据隔离
- 所有数据按用户隔离存储
- 使用 `ContextVar` 传递用户上下文
- 每个请求结束后清除上下文

### 3. 配置优先
- 模型参数集中在 `config.py` 管理
- 前端配置从后端动态获取
- 敏感信息（API Key）存储在用户配置中

### 4. 日志完整
- 所有 API 调用记录请求和响应
- 错误信息包含足够的调试上下文
- 日志包含用户标识便于追踪

## 📁 核心目录

```
万相/
├── backend/              # FastAPI 后端
│   ├── app/
│   │   ├── config.py     # 🔧 模型配置中心
│   │   ├── main.py       # 应用入口
│   │   ├── dependencies.py # 依赖注入
│   │   ├── middleware/   # 中间件
│   │   ├── models/       # Pydantic 数据模型
│   │   ├── routers/      # API 路由
│   │   ├── services/     # 业务逻辑
│   │   └── prompts/      # 提示词模板
│   ├── data/             # 数据存储（JSON 文件）
│   └── logs/             # 日志文件
├── frontend/             # React 前端
│   └── src/
│       ├── pages/        # 页面组件
│       ├── components/   # 通用组件
│       ├── stores/       # Zustand 状态
│       └── services/     # API 调用
└── docs/                 # 📖 开发文档（本目录）
```

## ⚠️ 重要提醒

### 添加新模型时
1. 在 `backend/app/config.py` 添加模型配置
2. 更新相应的服务层（`services/dashscope/`）
3. 更新设置页和相关 UI
4. 更新前端 API 类型定义（`services/api.ts`）
5. 更新本文档

### 添加新 API 时
1. 在 `routers/` 创建路由
2. 在 `main.py` 注册路由
3. 确保使用 `Depends(get_storage)` 获取用户存储
4. 更新前端 `api.ts`

### 修改数据模型时
1. 更新 `models/` 中的 Pydantic 模型
2. 考虑向后兼容（旧数据能否正常加载）
3. 更新前端对应的 TypeScript 接口

---

*最后更新: 2025-12-30*

