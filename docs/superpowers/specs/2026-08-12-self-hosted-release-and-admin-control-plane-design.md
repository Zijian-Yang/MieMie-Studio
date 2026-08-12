# MieMie-Studio 自托管发行与管理控制面设计

- **状态**：Approved
- **日期**：2026-08-12
- **目标分支**：`pre`
- **替代方向**：`pre` 完成发行验收后替代当前 `main`

## 背景

`pre` 已完成单机 Compose 中 Redis、PostgreSQL、API、图片 Worker、视频 Worker、Cloudflare 入口、数据库迁移、JSON 主存储退场和第一轮运营门禁。当前升级版可以作为受控预发布服务运行，但 GitHub 新用户仍需手工复制 `compose.env`、生成密码、构建镜像、运行迁移、启动服务和安装数据库巡检任务；README 的一键启动路径也仍偏向源码开发运行。

项目最终定位不是托管边缘网络或完整服务器面板，而是一套容易在单台 Linux 服务器部署和维护的自托管应用服务。项目只提供绑定在本地回环地址的 HTTP 端口；域名、DNS、HTTPS、Cloudflare、Nginx、Caddy、aaPanel 和云防火墙由部署者管理。

## 目标

1. 让陌生用户按照 README 在一台干净服务器上用一个安装入口完成生产部署。
2. 新安装默认运行 PostgreSQL-only + Redis + API + 图片 Worker + 视频 Worker + 运维调度器。
3. 提供幂等安装、升级、回滚、诊断、备份和恢复 CLI。
4. 增加平台管理员角色和独立管理页面，至少完整覆盖平台用户的创建、查询、修改、禁用、启用和软删除。
5. 默认关闭公开注册，由首位管理员创建用户或显式开启公开注册。
6. 在管理员页面配置数据库定时备份、阿里云 OSS 异地备份和通用 Webhook 告警。
7. 保持 Web 进程低权限，不让管理页面直接获得 Docker、Git、宿主机 root 或任意命令执行能力。
8. 用干净服务器从零安装、升级、回滚、备份、恢复、真实生成和容量门禁证明交付路径可复现。

## 非目标

- 不自动配置域名、DNS、HTTPS、Cloudflare、Nginx、Caddy、aaPanel 或防火墙。
- 第一版不发布 GHCR/Docker Hub 应用镜像；应用镜像在目标服务器从固定 Git commit 本地构建。
- 第一版不支持 Kubernetes、多机高可用、托管 PostgreSQL、RabbitMQ 或 SSE。
- 管理页面不直接执行代码更新、容器重建、数据库恢复、永久用户数据清除或卸载。
- 第一版不支持 S3 通用对象存储；异地备份只适配已有的阿里云 OSS 能力。
- 用户软删除不自动删除项目、任务、媒体、OSS 对象或本地资产。

## 角色与权限

### 平台管理员

平台管理员可以：

- 访问 `/admin` 管理区域。
- 查看、搜索、分页和筛选平台用户。
- 创建普通用户或管理员。
- 修改用户名、显示名称、角色和状态。
- 重置用户密码，并要求用户下次登录修改密码。
- 禁用、启用和软删除用户。
- 修改公开注册开关。
- 配置和测试备份、OSS 与通用 Webhook。
- 触发一次立即备份并查看备份/告警历史。
- 查看平台版本与运行状态摘要。
- 查看管理员操作审计日志。

平台管理员不能通过 Web 页面：

- 运行 `git`、Docker、Compose、shell 或宿主机包管理命令。
- 执行数据库恢复或永久删除用户数据。
- 修改 HTTPS、反向代理、防火墙或宿主机 cron。

### 普通用户

普通用户只能访问现有业务能力和自己的设置，不能访问任何 `/api/admin/*` 接口或管理页面。前端隐藏管理入口不是授权边界；所有权限必须在后端再次检查。

## 用户状态模型

`users` 表新增：

| 字段 | 类型 | 默认值 | 语义 |
|---|---|---|---|
| `role` | text | `member` | `admin` 或 `member` |
| `status` | text | `active` | `active` 或 `disabled` |
| `must_change_password` | boolean | `false` | 下次登录后必须修改密码 |
| `updated_at` | timestamp with timezone | 当前时间 | 管理变更时间 |

现有 `deleted_at` 继续表示软删除。登录、token 恢复和所有受保护请求都必须拒绝 `disabled` 或已软删除用户。

硬性规则：

- 完成首位管理员 bootstrap 后，系统必须始终保留至少一个 `active admin`。
- 管理员不能删除、禁用或降级自己。
- 不能删除、禁用或降级最后一个有效管理员。
- 禁用、软删除、重置密码或角色安全变更后撤销目标用户全部 session。
- 用户名唯一性继续忽略软删除记录之外的活动用户。
- 用户删除默认保留业务数据；永久清除只由显式 CLI 维护命令承担，并不进入第一阶段管理页面。

## 首位管理员与注册策略

新安装流程要求安装者提供管理员用户名、显示名称和密码。密码支持交互式输入或仅用于自动化的安全环境变量输入，不接受命令行明文参数。安装器在 migration 后通过一次性容器命令调用幂等 bootstrap 服务：

- 数据库没有管理员时，创建指定管理员。
- 已存在同名管理员且状态正常时，返回成功但不覆盖密码。
- 已存在其他管理员时，不自动提升新用户，要求使用 `miemie admin promote <username>` 显式处理。

旧部署升级时，`miemie admin bootstrap` 列出现有活动用户，并要求操作员显式选择一个用户成为首位管理员。

公开注册默认关闭。`POST /api/auth/register` 在关闭时返回 `403` 和稳定错误码 `registration_disabled`。登录页根据公开 bootstrap 状态决定是否显示注册入口；管理员可在平台设置中开启或再次关闭。

## 管理 API

新增独立 `admin` router 和权限依赖。所有列表响应采用固定分页契约：

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 0
}
```

第一阶段接口：

| 方法 | 路径 | 用途 |
|---|---|---|
| `GET` | `/api/bootstrap/status` | 未登录可读，只返回是否允许注册和是否已存在管理员 |
| `GET` | `/api/admin/users` | 用户分页、搜索、角色/状态筛选 |
| `POST` | `/api/admin/users` | 创建用户 |
| `GET` | `/api/admin/users/{user_id}` | 用户详情 |
| `PATCH` | `/api/admin/users/{user_id}` | 修改基本资料、角色和状态 |
| `POST` | `/api/admin/users/{user_id}/reset-password` | 重置密码并撤销 session |
| `DELETE` | `/api/admin/users/{user_id}` | 软删除并撤销 session |
| `GET` | `/api/admin/platform-settings` | 平台设置脱敏视图 |
| `PATCH` | `/api/admin/platform-settings` | 修改注册、备份和告警设置 |
| `POST` | `/api/admin/backups` | 投递一次立即备份 |
| `GET` | `/api/admin/backups` | 查看备份执行历史 |
| `POST` | `/api/admin/backups/test-oss` | 测试备份 OSS 配置 |
| `POST` | `/api/admin/alerts/test` | 发送通用 Webhook 测试事件 |
| `GET` | `/api/admin/audit-logs` | 查看管理员审计日志 |
| `GET` | `/api/admin/runtime` | 只读版本与组件状态摘要 |

错误响应统一包含稳定 `code` 和中文 `detail`。管理员写接口使用现有请求 ID，并对用户管理和测试告警增加独立限流。

## 平台级数据模型

新增 PostgreSQL 表：

### `platform_settings`

单行配置或按稳定 key 分区保存以下内容：

- `registration_enabled`
- `backup_enabled`
- `backup_schedule`，使用受限的每日 `HH:MM`，不直接接受任意 cron 表达式
- `backup_retention_days`
- `backup_min_keep`
- `backup_local_subdirectory`，只能是 Compose 已挂载备份根目录下的安全相对路径
- `backup_oss_enabled`
- `backup_oss_endpoint`
- `backup_oss_bucket_name`
- `backup_oss_prefix`
- 加密后的 OSS access key id/secret
- `webhook_enabled`
- 加密后的 webhook URL
- `webhook_timeout_seconds`
- `webhook_retry_count`
- `webhook_alert_on_warning`
- `updated_by` / `updated_at`

### `admin_audit_logs`

保存 actor、action、target type/id、request ID、安全差异摘要、结果和时间。审计日志不能包含密码、token、API key、Webhook URL、OSS secret、prompt、provider payload 或私有资产 URL。

### `operation_runs`

记录备份、OSS 上传、恢复演练和告警测试的状态：`queued/running/succeeded/failed`、触发来源、开始/结束时间、安全摘要、错误分类和 artifact 相对路径。数据库恢复只由 CLI 写入记录，Web API 不提供恢复动作。

## 密钥保护

安装器生成 `MIEMIE_PLATFORM_ENCRYPTION_KEY`，仅保存在权限为 `600` 的 `compose.env`。平台设置中的 OSS 凭证和 Webhook URL使用认证加密后写入 PostgreSQL，API 只返回 `is_configured` 和脱敏值。

密钥丢失不会影响普通业务数据读取，但会导致运维凭证无法解密。CLI 的备份范围必须包含 `compose.env` 的受保护离机副本说明；仓库、日志、artifact 和 API 响应不得保存明文密钥。

## 备份与告警执行架构

新增 `ops` Celery 队列和两个 Compose 服务：

- `worker-ops`：执行 PostgreSQL dump、校验、OSS 上传、Webhook 测试和运行历史更新。
- `scheduler`：低权限周期进程，每分钟读取受限的每日计划配置，为到期且尚未执行的备份投递幂等任务。

调度器以 `schedule_date + operation_type` 幂等键防止重启后重复执行。API 仅写配置或投递任务，不运行 `pg_dump`，不访问 Docker socket。

备份流程：

1. 创建 `operation_runs` queued 记录。
2. `worker-ops` 使用 PostgreSQL 网络连接执行一致性 dump。
3. 写入临时文件、fsync、原子改名。
4. 计算 SHA-256，验证 dump 可读。
5. 按保留策略处理本地历史。
6. 可选上传阿里云 OSS，并记录对象 key、ETag 和结果。
7. 更新运行记录；失败时调用通用 Webhook 告警。

恢复仍通过 `miemie restore <backup-id-or-path>`：先确认目标、创建恢复前备份、在隔离数据库验证，再要求二次显式确认才覆盖当前数据库。

Webhook 使用固定 JSON 事件契约，包含 instance id、severity、event type、state、reason、release commit、request/run id 和时间。发送采用有限超时与有限重试，不在 payload 中包含密钥或用户内容。

## 管理前端

新增顶层 `/admin` 路由和管理侧导航，只对管理员显示。使用现有 Ant Design 主题 token，不新增硬编码主题色。

页面划分：

- **概览**：版本、数据库/Redis/Worker 状态、最近备份和最近告警。
- **用户**：密集表格、搜索、角色/状态筛选、创建/编辑抽屉、重置密码和删除确认。
- **备份**：计划、保留策略、本地/OSS 配置、连接测试、立即备份、运行历史。
- **告警**：通用 Webhook 配置、测试发送和最近结果。
- **审计日志**：按 actor/action/target/result 查询。

管理页面不做营销式卡片布局，不把页面区块嵌套成卡片。危险动作必须显示具体用户名或备份 ID，并要求明确确认。版本检查只读取 GitHub `pre` 分支公开元数据并显示当前/可用 commit 与对应 CLI 命令；页面不执行 `git` 或更新动作，GitHub 不可达时只显示当前版本。

## 一键安装与管理 CLI

### 支持平台

第一版支持：

- Ubuntu 22.04 LTS
- Ubuntu 24.04 LTS
- Debian 12
- `x86_64` 和 `arm64`，前提是基础镜像和 Python/Node 依赖支持目标架构

推荐最低资源为 2 CPU、4 GB RAM、20 GB 可用磁盘。较小机器可安装，但 doctor 必须给出 warning。

### `install.sh`

安装入口：

```bash
git clone -b pre https://github.com/Zijian-Yang/MieMie-Studio.git
cd MieMie-Studio
sudo ./install.sh
```

安装器按阶段执行并记录 `/var/log/miemie/install.log`：

1. 检查系统、root、网络、端口、磁盘和时间。
2. 检测或安装 Docker Engine、Compose plugin、Git 和 curl。
3. 选择安装目录，默认 `/opt/miemie-studio`。
4. 生成不可提交的 `compose.env` 和 instance id，文件权限 `600`。
5. 设置 PostgreSQL-only 默认值和回环监听端口，默认 `127.0.0.1:8000`。
6. 本地构建以 Git commit 标识的应用镜像。
7. 启动 PostgreSQL 和 Redis，等待 health。
8. 在一次性容器中执行 `alembic upgrade head`。
9. 创建或确认首位管理员。
10. 启动 API、全部 Worker 和 scheduler。
11. 执行本机 health、数据库、队列和版本检查。
12. 安装 `/usr/local/bin/miemie` 管理命令并输出反代目标。

任何阶段失败都停止后续动作、保留日志并输出精确恢复命令。幂等重跑不得覆盖既有密钥、管理员、数据库卷或备份。

### `miemie` CLI

正式支持：

```text
miemie status
miemie logs [service]
miemie doctor
miemie restart [service]
miemie update [--check|--apply]
miemie rollback [release]
miemie backup [--wait]
miemie backups
miemie restore <backup-id-or-path>
miemie admin bootstrap
miemie admin promote <username>
miemie admin reset-password <username>
miemie uninstall
```

`update --apply` 必须：工作树干净检查、升级前备份、fetch `pre`、只允许 fast-forward、构建新 commit 镜像、migration、滚动服务、健康检查和失败时应用镜像回滚。数据库 migration 采用向前兼容策略；自动镜像回滚不承诺自动降级 schema。

`uninstall` 默认只停止服务并保留数据卷、备份和配置；永久删除必须额外提供完整确认短语。

## Compose 发行默认值

新安装使用 PostgreSQL-only 默认配置：

- `MIEMIE_DATABASE_ENABLED=true`
- `MIEMIE_DATABASE_WRITE_MODE=postgres`
- `MIEMIE_DATABASE_READ_MODE=postgres`
- `MIEMIE_DATABASE_JSON_FALLBACK_READ=false`
- `MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=false`
- API 仅绑定 `127.0.0.1`
- Redis 与 PostgreSQL 不发布宿主机端口
- API 和 Worker 使用非 root 用户
- 所有服务有 restart policy、healthcheck、日志轮转和停止宽限期
- 备份根目录由 Compose 固定挂载；管理员只能选择其下经过路径穿越校验的相对子目录

开发者的源码 `run.sh` 可以继续保留，但 README 必须清楚区分“本地开发”和“服务器生产安装”，生产路径只推荐 `install.sh` + Compose。

## 错误处理与可观测性

- 所有安装/更新步骤输出阶段名、状态、原因和下一步命令。
- CLI 日志默认脱敏，不打印环境文件、数据库 URL、Webhook 或 OSS 密钥。
- 管理 API 响应包含 request ID，后台运行包含 operation run ID。
- Worker 失败写入稳定错误分类，并在配置启用时发送 Webhook。
- 管理概览只显示安全运行摘要，不暴露容器环境和宿主机敏感信息。
- 备份历史同时显示本地与 OSS 状态，避免“本地成功”被误认为“异地成功”。

## 兼容与升级

- 现有 PostgreSQL-only `pre` 部署不做数据重迁移，只追加 schema。
- 旧用户默认迁移为 `member/active`。
- 首位管理员必须由 CLI 显式选择或创建，不能按注册顺序自动猜测。
- 现有按用户 API Key/业务 OSS 设置保持不变；平台备份 OSS 是独立平台级配置，不复用任意普通用户凭证。
- 原有 cron 脚本在新 ops scheduler 验收前保留；切换时先证明等价备份/告警，再禁用宿主机 cron，避免重复备份。

## 分阶段交付

### 7A：管理员与用户治理

- 用户角色、状态和 migration。
- bootstrap/admin 权限依赖。
- 默认关闭注册。
- 用户 CRUD、session 撤销、最后管理员保护。
- 审计日志。
- 管理员用户页面。

### 7B：备份与通用 Webhook

- 平台设置和加密凭证。
- operation runs。
- `worker-ops` 与 scheduler。
- 本地/阿里云 OSS 备份和保留策略。
- 通用 Webhook 与测试发送。
- 管理概览、备份、告警和审计页面。
- 从宿主机 cron 平滑切换。

### 7C：一键部署与升级

- PostgreSQL-only Compose 发行默认值。
- 非 root 容器 hardening。
- 幂等 `install.sh`。
- `miemie` CLI 的状态、更新、回滚、备份、恢复和卸载。
- README 生产部署路径。

### 7D：发布验收

- 干净 Ubuntu 22.04、Ubuntu 24.04 和 Debian 12 安装演练。
- 至少一组 arm64 静态/构建兼容验证；没有可用 arm64 服务器时明确标记为发布限制。
- 首位管理员、关闭/开启注册和用户全生命周期验收。
- 本地备份、OSS 上传、隔离恢复、Webhook 真实接收验收。
- 当前 release 的真实图片、真实视频与 OSS 持久化验收。
- Cloudflare 入口下当前 release 的 S4/W2 平台侧门禁。
- 更新、失败回滚和保留数据卸载演练。

## 测试策略

- 后端：repository/service/router 权限、最后管理员不变量、注册策略、session 撤销、审计脱敏、加密配置、备份幂等、Webhook 重试。
- 前端：类型、lint、build、chunk；管理员路由保护、用户表 CRUD、设置脱敏、危险确认和错误态。
- 脚本：shell 语法、静态 verifier、临时目录幂等演练、Compose config、安装失败恢复。
- 集成：临时 PostgreSQL + Redis + Celery，真实 dump 和隔离 restore。
- E2E：管理员和普通用户权限隔离、注册开关、用户禁用后会话立即失效。
- 发布：干净服务器从 clone 到 health 的全流程 artifact，不复用预装项目目录或数据库卷。

## 验收标准

- 新用户只需 README 中一个生产安装入口即可得到 PostgreSQL-only 完整平台。
- 安装后应用仅监听配置的回环端口，Redis/PostgreSQL 不对外发布。
- 只有管理员能访问管理 API/页面。
- 用户 CRUD、禁用、重置密码、软删除和最后管理员保护全部通过。
- 默认公开注册关闭，开启/关闭立即生效。
- 定时与手动备份可追踪，本地和 OSS 状态分别明确。
- OSS 或 Webhook 密钥不出现在 API、日志、artifact 或仓库。
- 更新前自动备份，更新失败恢复旧应用镜像并输出数据库兼容状态。
- 从异地 OSS 副本完成一次隔离恢复演练。
- 当前 release 的完整回归、真实供应商 smoke 和容量门禁通过。

## 文档要求

- 更新根 `README.md`，把生产安装置于快速开始首选路径，开发运行单独说明。
- 更新 `README.pre.md` 为正式自托管发行说明。
- 新增安装、升级、备份恢复、管理员和反向代理 playbook。
- 更新 `docs/README.md`、`docs/CHANGELOG.md`、`docs/ISSUES.md` 和阶段计划状态。
- 每个阶段保存脱敏验证 artifact，禁止提交真实 token、密码、Webhook 或 OSS 凭证。
