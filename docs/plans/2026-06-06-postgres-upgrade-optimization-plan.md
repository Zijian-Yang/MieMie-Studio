# Compose PostgreSQL Upgrade Optimization Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `pre` 分支现有单机 Compose + Redis + Worker 稳定基线上，引入 Compose 内 PostgreSQL，并用 JSON 过渡、双写、回填、对账和分阶段读切换，最终把核心业务状态迁到数据库。

**Architecture:** PostgreSQL 先作为可回滚的影子索引/对账库接入，不在第一刀替换 JSON 主数据。每个数据域按“schema → 回填 → 双写 → 对账 → 读切换 → JSON 只读归档 → DB 成为主数据源”的顺序推进，避免一次性全量迁移。Redis 继续承担 session/cache/rate limit/Celery broker/result backend，不被 PostgreSQL 替代。

**Tech Stack:** Docker Compose PostgreSQL 16、FastAPI、Pydantic、SQLAlchemy Core/ORM 2.x、Alembic、psycopg 3、pytest、现有 k6/Playwright 门禁。

---

## 先解释第 5 个问题

之前的“问题 5：迁移目标是当前 W2/W3 平台承载，还是未来多 API 节点共享核心状态？”意思是：

- 如果目标只是当前单机 W2/W3，数据库可以先做索引和查询优化，JSON 主数据保留更久，风险最低。
- 如果目标包含未来多个 API 容器或多台服务器同时读写同一份数据，就必须把 PostgreSQL 设计成最终核心状态源，不能长期依赖本地 JSON 目录。

你现在的选择等价于：

- **部署形态**：Compose 内 PostgreSQL。
- **过渡策略**：允许 JSON 作为主数据保留一段时间。
- **最终目标**：核心业务状态最终全部上数据库。
- **迁移安全**：保留一段时间双写、回填和对账。

因此，本计划按“最终支持多 API 节点共享核心状态”的方向设计，但第一阶段仍以单机 Compose 安全落地为主。

## 决策摘要

- 选择 PostgreSQL，不走 SQLite 中转。
- PostgreSQL 首轮进入 Compose，但不立刻成为所有读写的唯一来源。
- JSON 文件短期仍是主数据源和回滚来源。
- PostgreSQL 从最有收益、最容易对账的数据域开始：任务索引与任务状态。
- 每个域必须有 schema、迁移脚本、回填脚本、对账脚本、读切换开关和回滚步骤。
- 不把 PostgreSQL 与 SSE 绑成一次大改；任务状态稳定后再考虑 SSE。

## 目标架构

```text
Browser / Cloudflare / Nginx
          |
          v
FastAPI api containers
          |
          +--> Redis: session / rate limit / cache / Celery broker / result backend
          |
          +--> PostgreSQL: core business state, indexes, audit, queryable metadata
          |
          +--> JSON data directory: transitional source of truth, backfill source, rollback archive
          |
          v
Celery worker / worker-video
          |
          +--> PostgreSQL: task status and metadata updates after domain read/write cutover
          +--> JSON: dual-write during transition only
```

最终状态：

- PostgreSQL 是核心业务状态主数据源。
- JSON 只作为迁移归档、离线恢复材料或可删除历史快照。
- Redis 继续做瞬态状态，不作为长期业务状态库。
- OSS/本地文件继续承载大文件本体，PostgreSQL 只存 URL、metadata、归属和状态。

## 运行配置设计

新增环境变量建议：

```bash
MIEMIE_DATABASE_URL=postgresql+psycopg://miemie:${MIEMIE_POSTGRES_PASSWORD}@postgres:5432/miemie
MIEMIE_DATABASE_ENABLED=false
MIEMIE_DATABASE_WRITE_MODE=file
MIEMIE_DATABASE_READ_MODE=file
MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=
MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=
MIEMIE_DATABASE_READ_DOMAINS=
MIEMIE_DATABASE_JSON_FALLBACK_READ=true
MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=false
MIEMIE_DATABASE_RECONCILE_STRICT=false
```

模式含义：

- `file`：只使用现有 JSON。
- `shadow`：写 JSON，同时允许脚本回填/对账 PostgreSQL，业务读写不依赖 PostgreSQL。
- `dual_write`：业务写 JSON + PostgreSQL，读仍从 JSON 或按域切换。
- `postgres_read`：指定域从 PostgreSQL 读，写仍双写。
- `postgres_primary`：指定域 PostgreSQL 读写为主，`MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=true` 时可继续写 JSON 归档镜像，否则关闭 JSON 写入。

## Compose PostgreSQL 设计

第一刀只新增基础设施，不改业务代码：

```yaml
postgres:
  image: postgres:16-alpine
  restart: unless-stopped
  environment:
    POSTGRES_DB: ${MIEMIE_POSTGRES_DB:-miemie}
    POSTGRES_USER: ${MIEMIE_POSTGRES_USER:-miemie}
    POSTGRES_PASSWORD: ${MIEMIE_POSTGRES_PASSWORD:?set MIEMIE_POSTGRES_PASSWORD}
    TZ: ${TZ:-Asia/Shanghai}
  volumes:
    - postgres_data:/var/lib/postgresql/data
    - ./backend/backups/postgres:/backups
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
    interval: 10s
    timeout: 5s
    retries: 5
    start_period: 10s

volumes:
  postgres_data:
```

`api`、`worker`、`worker-video` 后续再加：

```yaml
depends_on:
  postgres:
    condition: service_healthy
environment:
  MIEMIE_DATABASE_URL: ${MIEMIE_DATABASE_URL:-postgresql+psycopg://miemie:${MIEMIE_POSTGRES_PASSWORD}@postgres:5432/miemie}
```

第一刀验收：

- `docker compose config` 通过。
- `docker compose up -d postgres` 后 `pg_isready` 通过。
- 不改变 `/api/health` 既有语义，最多新增 `database.configured/database.ok` 观测字段。
- PostgreSQL 停止时，`MIEMIE_DATABASE_ENABLED=false` 下现有服务仍可运行。

## 数据域迁移顺序

### P0：数据域清单与 schema 冻结

先列清楚现有 JSON 目录和最终表：

| 当前 JSON/目录 | 最终 PostgreSQL 域 | 第一阶段动作 |
|---|---|---|
| `projects` | `projects` | 第二批迁移 |
| `video_studio` | `video_studio_tasks` | 第一批迁移 |
| `studio` | `studio_tasks` | 第一批迁移后复用模式 |
| `audio_studio` | `audio_studio_tasks` | 第三批迁移 |
| `gallery` | `media_assets` + `gallery_images` | 第三批迁移 metadata |
| `video_library` | `media_assets` + `video_items` | 第三批迁移 metadata |
| `audio` | `media_assets` + `audio_items` | 第三批迁移 metadata |
| `text_library` | `text_items` | 第三批迁移 |
| `characters/scenes/props/frames/videos/styles` | 对应 domain tables | 项目表稳定后迁移 |
| `image/video_benchmark_*` | benchmark tables | 最后迁移 |
| `users.json/users/` | `users` + profile/config tables | 不做第一批，安全评估后迁移 |
| `sessions` | Redis active sessions + optional `user_sessions` audit | 暂不迁主路径 |

### P1：任务索引与任务状态

先迁任务，因为它最影响列表、状态观察、Worker 更新和未来 SSE。

建议表：

```sql
create table video_studio_tasks (
  id text primary key,
  user_id text not null,
  project_id text not null,
  task_kind text not null,
  task_type text not null,
  provider text not null,
  model_id text,
  name text,
  status text not null,
  progress integer not null default 0,
  group_count integer not null default 1,
  prompt text,
  negative_prompt text,
  input_assets jsonb not null default '{}'::jsonb,
  normalized_params jsonb not null default '{}'::jsonb,
  provider_payload_snapshot jsonb,
  provider_result_meta jsonb,
  task_ids jsonb not null default '[]'::jsonb,
  request_ids jsonb not null default '[]'::jsonb,
  video_urls jsonb not null default '[]'::jsonb,
  thumbnail_url text,
  error text,
  submit_attempt_id text,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  deleted_at timestamptz
);

create index idx_video_studio_tasks_user_project_updated
  on video_studio_tasks (user_id, project_id, updated_at desc)
  where deleted_at is null;

create index idx_video_studio_tasks_user_status_updated
  on video_studio_tasks (user_id, status, updated_at desc)
  where deleted_at is null;

create index idx_video_studio_tasks_submit_attempt
  on video_studio_tasks (submit_attempt_id)
  where submit_attempt_id is not null;
```

第一阶段只做：

- 回填现有 JSON 到 PostgreSQL。
- 保存任务时双写。
- 列表接口可通过开关从 PostgreSQL 读。
- 对账脚本比较 JSON 与 PostgreSQL 的关键字段。
- 失败时一键切回 JSON 读。

### P2：图片工作室任务复用任务迁移框架

迁 `studio_tasks`，复用 P1 的 repository、回填、双写和对账框架。

目标：

- 图片工作室任务状态也脱离全目录扫描。
- Worker 写任务状态具备数据库路径。
- 为未来统一 task event / SSE 打基础。

2026-06-07 progress: `studio_tasks` 本地 schema、Alembic migration、file/PostgreSQL/dual repository 边界已完成并通过本地验证；本地 backfill/reconcile 服务和维护脚本已完成，摘要保持脱敏，不包含 prompt body、provider payload、token/key 或私有 URL；runtime dual-write feature flag 已接入，显式开启后 JSON 主写成功再 shadow 写 PostgreSQL；read-switch + JSON fallback 已接入，显式开启后读取优先 PostgreSQL；PostgreSQL primary-write + JSON archive mirror 已接入，显式开启后保存/删除以 PostgreSQL 为主，主写失败不落 JSON 分叉状态。运行态默认仍为 JSON/file-only，服务器未启用该开关。证据见 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r8-studio-tasks-local-schema-repository/`、`docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r9-studio-tasks-backfill-reconcile/`、`docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r10-studio-tasks-runtime-dual-write/`、`docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r11-studio-tasks-read-switch/` 和 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r12-studio-tasks-primary-write/`。

### P3：项目表

迁 `projects`，但不立即迁所有子资源。

建议：

- `projects` 保存项目主信息、script JSONB、统计字段。
- 初期继续从 JSON 回填。
- 级联删除先不完全交给数据库外键，保留应用层删除逻辑，避免第一阶段行为差异。

2026-06-07 progress: `projects` 本地 schema、Alembic migration `20260607_0003_projects`、`ProjectRepository` 协议和 file/PostgreSQL/dual repository 边界已完成；表采用项目索引列 + `raw_project_snapshot` JSONB 的过渡模式。本地 backfill/reconcile 服务和维护脚本已完成，摘要保持脱敏，不包含项目名、描述、剧本内容、model config 细节、prompt body、token/key 或私有 URL。runtime dual-write feature flag 已接入，显式开启后 JSON 主写/删除成功再 shadow 写 PostgreSQL。默认运行态仍为 JSON/file-only，尚未接入 read-switch 或 primary-write。证据见 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r13-projects-local-schema-repository/`、`docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r14-projects-backfill-reconcile/` 和 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r15-projects-runtime-dual-write/`。

### P4：媒体库 metadata

迁图库、视频库、音频库、文本库 metadata。

原则：

- 文件本体仍在 OSS 或本地。
- DB 存 URL、project_id、user_id、source、size、duration、metadata、created_at。
- 列表查询走 DB 后，素材选择面板会明显受益。

2026-06-07 progress: media metadata 本地 schema/repository boundary 已完成；`media_assets` 覆盖图库、音频库和视频库 metadata，`text_items` 覆盖文本库内容与版本快照，文件本体继续保留在 OSS/URL。本地 backfill/reconcile 服务和维护脚本已完成，摘要保持脱敏，只比较安全索引字段，不包含文本内容、prompt、provider payload、token/key/password 或私有 URL。runtime dual-write feature flag 已接入，显式开启后图库、音频库、视频库和文本库 JSON 主写/删除成功再 shadow 写 PostgreSQL。read-switch + JSON fallback 已接入，显式开启后 get/list 可优先读 PostgreSQL。PostgreSQL primary-write + JSON archive mirror 已接入，显式开启后保存/删除以 PostgreSQL 为主，主写失败不落 JSON 分叉状态。运行态默认仍为 JSON/file-only，前端 smoke 和服务器灰度尚未完成。证据见 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r19-media-metadata-local-schema-repository/`、`docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r20-media-metadata-backfill-reconcile/`、`docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r21-media-metadata-runtime-dual-write/`、`docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r22-media-metadata-read-switch/` 和 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r23-media-metadata-primary-write/`。

### P5：角色/场景/道具/分镜/视频/风格

项目主数据稳定后迁这些编辑域。

原则：

- 先迁读多、列表多的数据。
- 每一类实体单独开关、单独对账。
- 不一次性替换所有 StorageService 方法。

2026-06-07 progress: 角色、场景、道具、首帧、视频和风格的本地 PostgreSQL schema/repository boundary 已完成。R24 采用统一 `project_entities` 表，按 `entity_kind` 区分实体类型，保留共享索引列和完整 `raw_entity_snapshot` JSONB；Alembic migration `20260607_0005_project_entities` 已加入迁移链。R25 已新增 project entities backfill/reconcile 服务和维护脚本，摘要保持脱敏，只比较安全索引字段，不包含名称、描述、prompt、text style body、provider task id、token/key/password 或私有 URL。R26 已接入 runtime dual-write feature flag，显式开启后 JSON 主写/删除成功再 shadow 写 PostgreSQL。R27 已接入 read-switch + JSON fallback，显式开启后 get/list、frame/video by-shot 和 video by-task 可优先读 PostgreSQL。运行态默认仍为 JSON/file-only，primary-write 和前端 smoke 尚未完成。证据见 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r24-project-entities-local-schema-repository/`、`docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r25-project-entities-backfill-reconcile/`、`docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r26-project-entities-runtime-dual-write/` 和 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r27-project-entities-read-switch/`。

### P6：用户、配置、审计

最后迁用户账号和配置，原因是安全敏感且回滚成本高。

建议：

- 用户密码 hash、账号状态、创建时间进入 `users`。
- 用户配置拆成 `user_configs`，敏感字段继续加密或保持现有安全边界。
- `audit_events` 记录关键写操作、登录、迁移差异和回滚动作。

## 代码架构计划

### 新增模块边界

```text
backend/app/db/
  __init__.py
  engine.py              # database URL, engine/session factory, healthcheck
  migrations/            # Alembic versions
  schema/                # SQLAlchemy table/model definitions

backend/app/repositories/
  __init__.py
  base.py                # repository protocol, source enum, dual-write result
  file_storage.py        # adapter over existing StorageService
  video_studio_tasks.py  # file/postgres/dual repository
  studio_tasks.py
  projects.py

backend/app/services/migration/
  backfill_video_studio_tasks.py
  reconcile_video_studio_tasks.py
  migration_report.py
```

### 关键原则

- 路由层不直接 import SQLAlchemy。
- Worker 不直接写 SQL，继续走 repository/service。
- `StorageService` 不一次性重写；先包一层 repository adapter。
- 双写失败必须记录日志和 audit event，不能静默吞掉。
- 对账脚本输出 JSON/Markdown artifact，不写 token/password。

## 迁移状态机

每个数据域都使用同一套状态：

```text
file_only
  -> pg_schema_ready
  -> pg_backfilled
  -> dual_write
  -> pg_read_shadow_compare
  -> pg_read_primary
  -> pg_write_primary
  -> json_archive_only
```

回滚策略：

- `pg_schema_ready` / `pg_backfilled`：删除或忽略 PG 数据即可。
- `dual_write`：切回 `file_only`，保留 PG 用于分析。
- `pg_read_primary`：切 `MIEMIE_DATABASE_READ_DOMAINS` 回空，读 JSON。
- `pg_write_primary`：必须先确认 JSON 镜像写仍开启，否则只能从 PG 导出 JSON 回滚。
- `json_archive_only`：回滚需要恢复归档 JSON 并重新对账。

## 对账标准

每个域至少对账：

- 记录数量一致。
- 主键集合一致。
- `user_id/project_id/status/updated_at/deleted_at` 等索引字段一致。
- JSONB 快照字段能 round-trip。
- 最近 N 条写入在双写后 30 秒内一致。

对账输出：

```json
{
  "domain": "video_studio_tasks",
  "json_count": 123,
  "postgres_count": 123,
  "missing_in_postgres": [],
  "missing_in_json": [],
  "field_differences": [],
  "checked_at": "2026-06-06T00:00:00+08:00",
  "ok": true
}
```

## 性能门禁

迁移前后都必须采集：

- `/api/health`
- 本机入口 `http://127.0.0.1:18100`
- 公网入口 `https://pre-studio.miemie.co`
- 任务列表、项目列表、视频工作室状态观察
- `docker stats --no-stream`
- PostgreSQL 连接数、慢查询、表大小、索引大小

最小通过线：

- 接口失败率 `<1%`
- 已迁读路径 p95 不高于迁移前基线
- PostgreSQL 慢查询无稳定热点
- 切回 JSON 后功能仍正常

## 备份与恢复

Compose 内 PostgreSQL 必须有：

- `pg_dump` 逻辑备份脚本。
- 数据卷快照策略。
- 恢复演练脚本。
- 迁移前 JSON 目录 tarball。

推荐脚本：

```bash
docker compose exec -T postgres pg_dump -U "$MIEMIE_POSTGRES_USER" "$MIEMIE_POSTGRES_DB" > backups/postgres/miemie-$(date +%Y%m%d-%H%M%S).sql
tar -czf backups/json/backend-data-$(date +%Y%m%d-%H%M%S).tar.gz backend/data
```

恢复演练必须在非生产目录执行，不直接覆盖现有 `backend/data`。

## 实施任务

### Task 1：更新数据库迁移 spec 和 ADR

**Files:**
- Modify: `docs/adr/ADR-0003-pre-database-architecture-checkpoint.md`
- Modify: `docs/specs/2026-04-step-04-postgres-domain-migration.md`
- Modify: `docs/README.md`
- Modify: `docs/CHANGELOG.md`

- [ ] 把 ADR-0003 状态从 Draft 调整为 Accepted 或 Superseded-by-plan。
- [ ] 明确选择 Compose PostgreSQL。
- [ ] 明确最终目标为核心业务状态全部进入数据库。
- [ ] 明确 JSON 过渡和对账窗口。
- [ ] 不加入任何业务代码。

### Task 2：新增 Compose PostgreSQL 基础设施

**Files:**
- Modify: `docker-compose.yml`
- Modify: `compose.env.example` 或现有 env 样例文件
- Modify: `docs/DEPLOYMENT.md`
- Test: `docker compose config`

- [ ] 新增 `postgres` service 和 `postgres_data` volume。
- [ ] 新增 `MIEMIE_POSTGRES_PASSWORD` 必填项。
- [ ] 不让 API 在默认模式强依赖 PostgreSQL。
- [ ] 本地执行 `docker compose config`。

### Task 3：数据库连接与 health 观测

**Files:**
- Create: `backend/app/db/engine.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_health.py` 或新增 health 测试

- [ ] 新增数据库配置读取。
- [ ] `MIEMIE_DATABASE_ENABLED=false` 时不连接数据库。
- [ ] `MIEMIE_DATABASE_ENABLED=true` 时 `/api/health` 暴露 `database.configured` 和 `database.ok`。
- [ ] PostgreSQL 不可用时 health 明确显示 false，不泄露连接字符串。

### Task 4：Alembic 与首批 schema

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/app/db/migrations/env.py`
- Create: `backend/app/db/schema/video_studio_tasks.py`
- Create: migration version for `video_studio_tasks`

- [ ] 引入 Alembic 和 psycopg 依赖。
- [ ] 创建 `video_studio_tasks` 表和索引。
- [ ] migration 可重复运行、可回滚。
- [ ] CI/本地可在临时 PostgreSQL 上跑 migration。

### Task 5：Video Studio 任务 repository shadow 模式

**Files:**
- Create: `backend/app/repositories/base.py`
- Create: `backend/app/repositories/video_studio_tasks.py`
- Modify: `backend/app/routers/video_studio.py`
- Modify: `backend/app/worker_tasks.py`
- Tests: video studio repository tests

- [ ] 写 repository contract。
- [ ] File repository 包装现有 `StorageService`。
- [ ] Postgres repository 实现 save/get/list/delete。
- [ ] Dual repository 在 `dual_write` 模式下先写 JSON，再写 PostgreSQL。
- [ ] 默认仍为 `file_only`。

### Task 6：回填与对账脚本

**Files:**
- Create: `backend/app/services/migration/backfill_video_studio_tasks.py`
- Create: `backend/app/services/migration/reconcile_video_studio_tasks.py`
- Create: `scripts/postgres_backfill_video_studio_tasks.py`
- Create: `scripts/postgres_reconcile_video_studio_tasks.py`
- Docs: artifact output format

- [ ] 从当前用户 JSON 目录扫描 `video_studio`。
- [ ] upsert 到 PostgreSQL。
- [ ] 生成对账 JSON 和 Markdown 摘要。
- [ ] 不输出 token、密码、私有 API key。

### Task 7：读切换灰度

**Files:**
- Modify: `backend/app/repositories/video_studio_tasks.py`
- Modify: `backend/app/routers/video_studio.py`
- Tests: route tests for read source switch

- [ ] `MIEMIE_DATABASE_READ_DOMAINS=video_studio_tasks` 时列表读 PostgreSQL。
- [ ] 单条 get 可按开关读 PostgreSQL，找不到时可 fallback JSON。
- [ ] 删除先保持双写删除或 soft delete。
- [ ] 压测本机入口与公网入口。

### Task 8：项目表迁移

**Files:**
- Create: `backend/app/db/schema/projects.py`
- Create: `backend/app/repositories/projects.py`
- Modify: `backend/app/routers/projects.py`
- Scripts: backfill/reconcile projects

- [x] `projects` schema 保留 script JSONB 和统计字段。
- [x] create/update/delete 双写。
- [ ] 项目删除的子资源级联仍先由应用层控制。
- [x] 对账通过后再读切换。

2026-06-07 进度：`projects` 已完成 schema/migration、repository boundary、backfill/reconcile、runtime dual-write、read-switch + JSON fallback 和 PostgreSQL primary-write + JSON archive mirror。本地默认仍为 file-only；服务器 live migration/backfill/reconcile、staging dual-write/read-switch/primary-write 尚未启用。下一步优先恢复服务器灰度验证；若服务器路径仍阻塞，本地进入 media metadata 域。

### Task 9：媒体库 metadata 迁移

**Files:**
- Create: `backend/app/db/schema/media_assets.py`
- Create: media repositories
- Modify: gallery/video_library/audio/text_library routers

- [x] 统一 media metadata 表或共享字段。
- [x] 不迁文件本体。
- [ ] 素材选择相关接口读切换后复跑前端 smoke。

2026-06-07 进度：media metadata 第一刀已完成本地 schema/repository boundary。`media_assets` 覆盖图库图片、音频库和视频库 metadata，`text_items` 独立覆盖文本库内容与版本快照；文件本体继续留在 OSS/URL，不迁入 PostgreSQL。运行态默认仍为 file-only，backfill/reconcile、runtime dual-write、read-switch、primary-write 和前端 smoke 尚未完成。
2026-06-07 追加进度：media metadata backfill/reconcile 已完成本地实现和维护脚本，摘要保持脱敏并只比较安全字段；runtime dual-write、read-switch + JSON fallback、primary-write + JSON archive mirror 已接入，默认仍为 file-only。下一步补前端素材选择 smoke；服务器路径恢复后执行 live migration/backfill/reconcile 和 staging 开关门禁。

### Task 10：剩余 domain 逐步迁移

**Files:**
- Characters/scenes/props/frames/videos/styles repositories
- Benchmark repositories
- User/config migration specs

- [ ] 每个域单独 schema。
- [ ] 每个域单独回填/对账/读切换。
- [ ] 用户和配置最后迁移。

2026-06-07 进度：P5 编辑域已开始，`project_entities` 统一表、repository boundary、backfill/reconcile 工具、脱敏对账摘要、runtime dual-write 和 read-switch 已完成；下一步补 project entity primary-write。

## 总体验收

- Compose 内 PostgreSQL 可启动、备份、恢复。
- 任务域至少完成回填、双写、对账、读切换和回滚演练。
- JSON 可作为过渡主数据保留一段时间。
- 最终路线明确为 PostgreSQL 主数据源。
- 前端和公开 API 语义不变。
- `npm run typecheck`、`npm run lint`、`npm run build`、`npm run test:e2e` 继续通过。
- 后端 pytest 关键集通过。
- S4/W2 关键 k6 门禁在切换前后都有对照证据。
