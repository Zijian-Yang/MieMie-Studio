# 运行模式矩阵

## 目的

统一说明开发环境、脚本生产模式和 Compose 生产模式的边界，避免把三种运行形态混为一谈。

## 矩阵

| 维度 | 开发环境 | 脚本生产模式 | Compose 生产模式 |
|------|----------|--------------|------------------|
| 启动命令 | `./run.sh start` | `./run.sh start --prod` | `docker compose --env-file compose.env up -d --build` |
| 前端来源 | Vite dev server | 先构建 `frontend/dist`，再由 FastAPI 统一服务 | 镜像构建阶段生成 `frontend/dist`，运行时由 FastAPI 统一服务 |
| 后端进程 | `uvicorn --reload` | `gunicorn + UvicornWorker` | 容器内 `gunicorn + UvicornWorker` |
| 对外端口 | 前端 `3000`，后端 `8000` | 单一应用端口（默认 `8000`） | 单一容器端口 `8000`，宿主机端口由 Compose 映射 |
| 反向代理 | 不要求 | 用户自管 | 用户自管 |
| 数据持久化 | 本地工作目录 | `backend/data/` | 挂载宿主机 `backend/data/` |
| 日志 | 控制台 + 本地日志文件 | `logs/` 与 `backend/logs/` | `docker logs` + 挂载的 `backend/logs/` |
| 目标场景 | 功能开发与调试 | 低门槛 Linux 单机部署 | 推荐生产参考路径 / Step 01 起点 |

## 默认约束

- 三种模式都只提供应用端口，不托管反向代理配置。
- `GET /api/health` 是当前阶段统一健康检查入口。
- 生产模式下都应暴露：
  - `X-Request-ID`
  - `X-Deployment-Version`

## 什么时候选哪种

- **开发环境**：本地功能开发、页面调试、接口联调。
- **脚本生产模式**：先快速把单机 Linux 服务器跑起来，或作为 Step 00 的 S0 基线。
- **Compose 生产模式**：从 Step 01 开始的推荐路径，用于后续纳入 Redis / PostgreSQL / Worker。
