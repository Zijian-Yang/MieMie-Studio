# 部署指南

> 本文档介绍如何将 MieMie-Studio 部署到生产环境服务器。

---

## 一、环境要求

### 硬件建议

| 规模 | CPU | 内存 | 磁盘 | 说明 |
|------|-----|------|------|------|
| 个人/小团队（1-10 用户） | 2 核 | 4 GB | 50 GB | 轻量使用足够 |
| 中型团队（10-100 用户） | 4 核 | 8 GB | 100 GB | 推荐配置 |
| 大规模（100+ 用户） | 8 核+ | 16 GB+ | 200 GB+ | 建议增加 Redis |

### 软件依赖

| 依赖 | 最低版本 | 说明 |
|------|---------|------|
| Python | 3.9+ | 推荐 3.10 或 3.11 |
| Node.js | 18+ | 推荐 LTS 版本 |
| npm | 9+ | 随 Node.js 安装 |
| Git | 2.0+ | 用于代码获取和自动更新 |
| screen | - | 后台进程管理 |
| Docker / Compose | Docker 24+ / Compose v2+ | Compose 推荐路径需要 |

### 操作系统

- **推荐**：Ubuntu 22.04 LTS / Debian 12 / CentOS Stream 9
- **支持**：macOS 13+
- **未测试**：Windows（建议使用 WSL2）

---

## 二、当前可用路径与推荐路径

### 当前可用路径

当前仓库**已经可用**的生产部署路径是：

- `./run.sh install`
- `./run.sh start --prod`

这条路径适合：

- 不熟悉 Docker 的用户
- 先尽快把平台部署起来的用户
- 单机、小规模或初期验证场景

### 推荐路径（Compose）

当前仓库已经补齐 **Docker Compose** 的第一阶段推荐生产路径，用于统一编排当前的单应用生产形态：

- API 服务（容器内 Gunicorn + UvicornWorker）
- 前端静态资源（镜像构建阶段生成，运行时由 FastAPI 统一服务）
- 宿主机持久化目录（`backend/data/`、`backend/logs/`）
- Redis（session、限流、Celery broker / result backend）
- Celery worker 与独立 `worker-video`
- PostgreSQL 16（数据库升级阶段基础设施，业务依赖默认关闭）

当前阶段仍然保持：

- **脚本模式可继续作为兼容路径**
- **Compose 是生产与 pre 验证的推荐路径**
- **JSON 当前仍是主数据源，PostgreSQL 先作为可观测、可备份、可迁移的基础设施接入**

### 反向代理边界

无论使用脚本模式还是未来的 Compose 模式，平台的边界都保持一致：

- 项目负责启动应用并提供监听端口
- 用户自己用宝塔 / Nginx / Caddy / 云负载均衡反代到该端口
- 仓库不托管某一种特定反向代理配置

### 给不熟悉 Docker 的用户

你现在可以先完全忽略 Docker，继续使用脚本模式。

如果你不熟悉 Docker，可以先把它理解为：

- **镜像（image）**：打包好的运行环境
- **容器（container）**：镜像启动后的实例
- **Compose**：一次性启动多个相关容器的编排文件
- **volume**：持久化数据目录
- **network**：容器之间通信的虚拟网络

可以把它理解成：

- 脚本模式：直接在服务器上安装并运行程序
- Compose 模式：把当前应用先装进标准化“箱子”里统一启动，后续再逐步纳入更多服务

---

## 三、快速部署

### 1. 获取代码

```bash
git clone https://github.com/Zian-Yang/MieMie-Studio.git
cd MieMie-Studio
```

### 2. 一键安装

首次部署建议先给脚本执行权限，再运行只读自检：

```bash
chmod +x run.sh
./run.sh doctor
```

它只检查当前 Mac/服务器是否具备基本部署条件，不安装依赖、不修改配置、不启动服务；报告默认写到 `/tmp/<run_id>/artifacts`。Compose 路径建议先复制 `compose.env` 后再跑一次：

```bash
cp compose.env.example compose.env
DOCTOR_PROFILE=compose ./run.sh doctor
```

```bash
./run.sh install
```

此命令会自动：
- 创建 Python 虚拟环境
- 安装后端依赖（FastAPI、Gunicorn 等）
- 安装前端依赖（React、Ant Design 等）
- 检测内核、CPU、内存和当前 Swap，并在用户确认后写入推荐运行参数

如果是服务器部署，建议在首次启动前主动执行一次：

```bash
./run.sh optimize
```

### 3. 启动生产模式

```bash
./run.sh start --prod
```

生产模式特点：
- **后端**：Gunicorn + 多 Worker，默认会按机器资源自动推荐更稳妥的值
- **前端**：构建为静态文件，由后端统一服务
- **访问地址**：`http://服务器IP:8000`
- **资源保护**：生产启动前会先检测资源并提示推荐配置，小内存 Linux 机器会额外建议创建 Swap

### 4. 验证部署

```bash
./run.sh status
```

或直接在浏览器访问 `http://服务器IP:8000`，应看到登录页面。

### 5. Compose 推荐路径

```bash
cp compose.env.example compose.env
sed -i.bak "s/replace-with-git-commit/$(git rev-parse HEAD)/" compose.env
DOCTOR_PROFILE=compose ./run.sh doctor
docker compose --env-file compose.env up -d --build
docker compose ps
curl http://127.0.0.1:8000/api/health
```

说明：

- Compose 当前只编排应用本身，不接管你的反向代理。
- 默认只把宿主机 `127.0.0.1:8000` 映射到容器内 `8000`，避免应用端口直接暴露公网。
- 如需修改监听地址或宿主机端口，可调整 `compose.env` 中的 `MIEMIE_HOST_BIND` / `MIEMIE_HOST_PORT`。
- 用户数据仍落在宿主机 `backend/data/`，不会因为重建容器而丢失。
- `pre` 扩容路径下 Compose 还会启动 Redis 与 Worker：
  - Redis 用于 session、限流和后台任务 broker。
  - Worker 先承接图片工作室生成任务。
  - API 与 Worker 共享 `backend/data/` 和 `backend/logs/` 挂载，便于保持当前 JSON 存储兼容。
- Compose 也会定义 PostgreSQL：
  - 默认不暴露宿主机端口，只供 Compose 内部服务访问。
  - 默认 `MIEMIE_DATABASE_ENABLED=false`，因此 API / Worker 不依赖 PostgreSQL 启动。
  - 真实 `compose.env` 必须设置 `MIEMIE_POSTGRES_PASSWORD` 强密码，不要使用样例占位值。
  - 小内存服务器可先使用 `MIEMIE_POSTGRES_SHARED_BUFFERS=128MB`、`MIEMIE_POSTGRES_MAX_CONNECTIONS=50` 等保守默认值，再按压测结果调整。
  - 数据库迁移遵循 `JSON 主数据源 → PostgreSQL shadow/backfill/reconcile → dual-write → read-switch → PostgreSQL primary` 的分阶段路线。
  - 视频工作室任务双写的服务器启用顺序必须是：PostgreSQL health 通过、`alembic upgrade head` 通过、backfill/reconcile 干净后，再设置 `MIEMIE_DATABASE_ENABLED=true` 与 `MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=video_studio_tasks`；回滚双写只需清空 `MIEMIE_DATABASE_DUAL_WRITE_DOMAINS` 并保持 `MIEMIE_DATABASE_WRITE_MODE=file`。
  - 视频工作室任务读切换必须在双写和再次对账干净后启用：设置 `MIEMIE_DATABASE_READ_DOMAINS=video_studio_tasks`；回滚读切换只需清空 `MIEMIE_DATABASE_READ_DOMAINS`，保留 `MIEMIE_DATABASE_JSON_FALLBACK_READ=true` 可在 PostgreSQL miss/异常时回退 JSON。
  - 视频工作室任务 PostgreSQL 主写必须在读切换和再次对账干净后启用：设置 `MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=video_studio_tasks`，必要时临时设置 `MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=true` 保留 JSON 归档镜像；回滚主写只需清空 `MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS` 并恢复前一阶段双写/读切换组合。
  - 如果本机 SSH 因 Clash/TUN/fake-IP 路径无法稳定执行远程 wrapper，可登录服务器后在 `/opt/miemie-pre` 运行：`CONFIRM_SERVER_SEQUENCE=run scripts/pre_studio_server_postgres_sequence.sh`。该入口会先做服务器上下文检查和 `git merge --ff-only origin/pre`，确认 sequence 包含 `live-data-gate` 后，再串行执行同一套 staging live-data/canary/rollback sequence。
  - 如果本机 SSH 路径恢复，可在本机运行 `CONFIRM_REMOTE_SEQUENCE=run scripts/pre_studio_remote_postgres_sequence.sh`。该 wrapper 会先跑本机 connectivity preflight，通过后远端 `git merge --ff-only origin/pre`，再调用同一个 server fallback 入口，避免本机远程路径和服务器终端路径门禁分叉。
  - 如果 `scripts/pre_studio_connectivity_preflight.sh` 显示 route 被 `32.0.0.0/3` 或 `utun*` 捕获，可在 Clash 规则前部加入 `IP-CIDR,47.79.99.190/32,DIRECT,no-resolve`，并确保它位于宽泛代理规则和 Rule Providers 之前；只有 `route -n get 47.79.99.190` 显示物理网卡后，才继续本机远程 wrapper。

---

## 四、配置说明

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MIEMIE_WORKERS` | 自动推荐 | Gunicorn Worker 数量，优先兼顾稳定性和机器内存 |
| `NODE_BUILD_MEMORY_MB` | 自动推荐 | 前端生产构建时的 Node 内存上限（MB） |
| `MIEMIE_MODE` | 跟随 `DEFAULT_RUN_MODE` | 临时覆盖当前运行模式：`dev`（开发）/ `prod`（生产） |
| `MIEMIE_DATABASE_ENABLED` | `false` | 是否启用 PostgreSQL health/业务数据库连接 |
| `MIEMIE_DATABASE_URL` | Compose 内部 `postgres` | PostgreSQL 连接串，不能写入真实密码到 Git |
| `MIEMIE_DATABASE_WRITE_MODE` | `file` | 写入模式，数据库迁移初期保持 JSON 主写 |
| `MIEMIE_DATABASE_READ_MODE` | `file` | 读取模式，按域灰度切换前保持 JSON 主读 |
| `MIEMIE_DATABASE_READ_DOMAINS` | 空 | 允许从 PostgreSQL 读取的域，逗号分隔 |
| `MIEMIE_DATABASE_DUAL_WRITE_DOMAINS` | 空 | 允许双写的域，逗号分隔 |
| `MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS` | 空 | 允许 PostgreSQL 主写的域，逗号分隔；当前支持 `video_studio_tasks` |
| `MIEMIE_DATABASE_JSON_FALLBACK_READ` | `true` | PostgreSQL 读缺失时是否回退 JSON |
| `MIEMIE_DATABASE_JSON_ARCHIVE_WRITES` | `false` | PostgreSQL 主写时是否继续维护 JSON 归档镜像，灰度/对账期可临时开启 |
| `MIEMIE_DATABASE_RECONCILE_STRICT` | `false` | 双写 shadow 失败是否抛出；灰度初期保持 `false`，让 JSON 主路径不中断 |
| `MIEMIE_POSTGRES_PASSWORD` | 无安全默认值 | PostgreSQL 密码，生产必须在未跟踪的 `compose.env` 中设置强值 |

设置方式：

```bash
# 临时设置
export MIEMIE_WORKERS=2
export NODE_BUILD_MEMORY_MB=2048
./run.sh start --prod

# 或者用脚本自动检测后持久化到 .miemie.conf
./run.sh optimize
```

说明：

- `DEFAULT_RUN_MODE` 会持久化到 `.miemie.conf`，服务器推荐长期保持为 `prod`
- TUI 中选择过一次“生产模式”后，后续 TUI 更新/重启会默认沿用该模式
- `MIEMIE_MODE` 只覆盖当前命令，不会替代持久化默认值

### 推荐策略

- `./run.sh install`、`./run.sh start --prod` 和 `./run.sh optimize` 都会触发资源检测
- 脚本会根据 CPU 核数、总内存和当前 Swap 推荐 `MIEMIE_WORKERS` 与 `NODE_BUILD_MEMORY_MB`
- Linux 小内存机器会额外建议创建 Swap；只有在用户确认后才会执行
- 应用后脚本会立即检查配置是否生效，并在 `./run.sh status` 中显示当前值
- Compose 路径下建议同时维护一个 `compose.env`（未纳入 Git），用于记录宿主机端口、worker 数和运行 commit

---

## 五、反向代理与入口端口

本项目的边界是：

- **项目负责启动应用并提供监听端口**（默认可为 `8000`）
- **反向代理由用户自行选择和管理**

你可以使用：

- 宝塔面板里的 Nginx
- 自己安装的 Nginx / Caddy
- 云厂商负载均衡 / CDN

仓库文档只说明“反向代理需要满足什么条件”，不把某一种代理配置作为平台交付的一部分。

### 需要满足的最小条件

- 能把外部流量反代到项目监听端口，例如 `127.0.0.1:8000`
- 能透传 `Host`、`X-Forwarded-For`、`X-Forwarded-Proto`
- 能配置较大的上传体积限制，覆盖图片/视频上传
- 能配置较长的读取超时，覆盖 AI 任务提交、查询以及后续 SSE
- 当平台后续启用 SSE 时，不能对事件流做缓冲或过早断开

### 推荐链路

```text
用户自管反向代理（宝塔 / Nginx / Caddy / ALB）
                ↓
        本项目提供的监听端口（如 8000）
                ↓
         Gunicorn / UvicornWorker
```

### 为什么这样划分

- 用户环境差异很大，有人用宝塔，有人用云负载均衡，有人直接自建 Nginx。
- 如果仓库把某一种代理配置当成官方唯一方案，后续文档和支持成本会很高。
- 平台更应该稳定应用端口、健康检查、静态资源路径和转发头语义，而不是接管外层代理实现。

### Cloudflare / CDN 提速建议

推荐链路：

```text
Cloudflare/CDN -> 用户自管反向代理 -> 127.0.0.1:8000 -> Gunicorn/UvicornWorker
```

建议项：

- 源站长期运行 `./run.sh start --prod`，不要把 Vite 开发服务直接暴露到公网
- Cloudflare 开启 `HTTP/2`、`HTTP/3`、`Brotli`
- 对 `/_static/*` 启用缓存；对 `/api/*` 保持绕过缓存
- 反向代理仅回源到 `127.0.0.1:8000`
- 小内存实例先执行 `./run.sh optimize`，降低构建和重启时卡死概率

### 宝塔 / 域名 / Nginx 边界

从开源项目视角，本仓库不内置也不托管宝塔站点、域名解析、SSL 证书或某一份 Nginx 配置。平台只保证在服务器上提供一个稳定应用端口，使用者可在宝塔或自己的反向代理里把域名回源到该端口。

推荐生产做法：

- Compose 模式保持 `MIEMIE_HOST_BIND=127.0.0.1`，反向代理回源到 `127.0.0.1:${MIEMIE_HOST_PORT}`。
- 防火墙只开放 `80/443` 和必要的 SSH 端口，不直接开放应用端口。
- `main` 与 `pre` 并行部署时使用不同目录、不同 `MIEMIE_HOST_PORT`、不同数据目录，避免共用 `backend/data/`。

---

## 六、安全加固

### 1. 防火墙

```bash
# Ubuntu/Debian (ufw)
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 80/tcp      # HTTP
sudo ufw allow 443/tcp     # HTTPS
sudo ufw enable

# 建议不要直接暴露 8000 端口，通过你自己的反向代理转发
```

### 2. API Key 安全

- 用户的阿里云 API Key 存储在各用户的独立配置目录中
- 每个用户只能看到自己的 API Key（已脱敏显示）
- 建议在阿里云控制台为每个用户创建独立的子账号和 API Key

### 3. 会话安全

- Token 有效期默认 7 天，过期自动失效
- 登出时 Token 立即失效
- 密码存储在服务器本地文件中，不暴露在 API 响应中

### 4. 定期备份

```bash
# 手动备份用户数据
cp -r backend/data /path/to/backup/$(date +%Y%m%d)

# 或使用内置的自动更新功能（更新前自动备份）
./run.sh auto-update enable
```

---

## 七、监控与日志

### 日志文件

| 日志 | 路径 | 内容 |
|------|------|------|
| 后端日志 | `logs/backend.log` | Gunicorn 访问日志和错误日志 |
| 前端构建日志 | `logs/frontend.log` | Vite 构建输出 |
| API 详细日志 | `backend/logs/api_YYYYMMDD.log` | 应用级别日志（按天滚动） |
| 自动更新日志 | `logs/update.log` | 自动更新执行记录 |

### 查看日志

```bash
# 通过控制面板
./run.sh logs backend

# 或直接查看
tail -f logs/backend.log
tail -f backend/logs/api_$(date +%Y%m%d).log
```

### 健康检查

```bash
curl http://localhost:8000/api/health
# 返回 status=ok 表示服务正常；redis 字段会显示 Redis 是否已配置和可达
```

可以配合监控工具（如 UptimeRobot、Prometheus）定期检查。

---

## 八、常见问题

### 端口被占用

```bash
# 查看端口占用
lsof -i :8000

# 或使用控制面板自动处理
./run.sh start --prod
# 会提示是否终止占用进程
```

### 构建失败

```bash
# 清理缓存后重试
./run.sh clean
./run.sh start --prod
```

### 内存不足

```bash
./run.sh optimize
./run.sh restart --prod
```

如果机器内存很小，接受脚本的 Swap 建议通常比单纯增加 workers 更稳妥。

### 服务异常重启

```bash
./run.sh restart --prod
```

### 更新后确认最新代码已生效

```bash
./run.sh update --apply
curl http://127.0.0.1:8000/api/health
./run.sh status
```

校验要点：

- `GET /api/health` 中的 `git_commit` 应与当前 `git rev-parse HEAD` 一致
- `run_mode` 在服务器上应为 `prod`
- `./run.sh status` 中“前端方式”应显示“静态构建（后端统一服务）”

### 需要回滚到旧版本

```bash
./run.sh rollback
```

---

## 八、架构说明

### 开发模式 vs 生产模式

```
开发模式 (dev，建议仅本地开发):
  浏览器 -> Vite(3000) --proxy--> FastAPI(8000)
                                      ↓
                                   Uvicorn (单 worker, 热重载)

生产模式 (prod，服务器推荐):
  浏览器 -> [Nginx(443)] -> FastAPI(8000)
                                ↓
                           Gunicorn (多 worker)
                                ↓
                           UvicornWorker × N
                                ↓
                        ┌───────┴────────┐
                        │   API 路由     │
                        │   静态文件     │
                        │  (前端构建产物) │
                        └────────────────┘
```

### 数据隔离

```
backend/data/
├── users.json          # 用户账号信息
├── sessions.json       # 会话 Token（含过期时间）
└── users/
    ├── user-001/       # 用户 A 的所有数据
    │   ├── projects/
    │   ├── characters/
    │   ├── gallery/
    │   └── ...
    └── user-002/       # 用户 B 的所有数据
        └── ...
```

每个用户的数据完全隔离，互不可见。
