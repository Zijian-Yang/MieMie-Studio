# PostgreSQL 运营门禁手册

## 目的

用于 `miemie-pre` 完成 PostgreSQL-only 和 JSON 退场后的日常上线前/巡检门禁。它把以下检查收敛到一个可重复脚本：

- `compose.env` 是否仍是最终 PostgreSQL-only 策略。
- 本机与公网 `/api/health` 是否 `ok`，且 `database.ok=true`、`redis.ok=true`。
- Compose 容器和 `docker stats --no-stream` 是否可采集。
- 运行目录外是否只剩允许的非运行态 JSON：`backend/data/config.example.json`。
- 是否存在新鲜 PostgreSQL 备份；显式确认时创建新备份并做 restore rehearsal。

## 命令

只生成计划，不执行外部检查：

```bash
bash scripts/postgres_operational_readiness.sh
```

执行只读运营门禁。如果没有新鲜备份，这一步会 blocked：

```bash
CONFIRM_POSTGRES_OPERATIONAL_READINESS=run \
bash scripts/postgres_operational_readiness.sh
```

执行完整门禁，创建新 PostgreSQL dump 并恢复到隔离演练库：

```bash
CONFIRM_POSTGRES_OPERATIONAL_READINESS=run \
POSTGRES_OPS_BACKUP_RESTORE=run \
bash scripts/postgres_operational_readiness.sh
```

推荐在服务器 `/opt/miemie-pre` 运行，并显式指定 artifact：

```bash
RUN_ID=postgres-ops-$(date +%Y%m%d-%H%M%S) \
ARTIFACT_DIR=validation-artifacts/postgres-ops-$(date +%Y%m%d-%H%M%S) \
CONFIRM_POSTGRES_OPERATIONAL_READINESS=run \
POSTGRES_OPS_BACKUP_RESTORE=run \
bash scripts/postgres_operational_readiness.sh
```

## 通过标准

- `status.json` 为 `state=passed`。
- `results.tsv` 中没有 `blocked` 或 `failed`。
- `env:MIEMIE_DATABASE_WRITE_MODE=postgres`、`env:MIEMIE_DATABASE_READ_MODE=postgres`。
- `env:MIEMIE_DATABASE_JSON_FALLBACK_READ=false`、`env:MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=false`。
- `health:local` 与 `health:public` 通过。
- `remaining_json` 只包含 `backend/data/config.example.json`。
- `POSTGRES_OPS_BACKUP_RESTORE=run` 时，`postgres_backup` 与 `postgres_restore_rehearsal` 均通过。

## 证据边界

- PostgreSQL dump 文件保留在服务器 `backend/backups/postgres/`，不要拉回仓库。
- `validation-artifacts/<run_id>/` 可拉回仓库的文件只应包含摘要、headers、sanitized env、Compose 状态和 backup path。
- 拉回前建议扫描：

```bash
find <artifact-dir> \( -name '*.sql' -o -name '*.dump' -o -name '*.tar.gz' -o -name '*.bak' \) -print
rg -n "Bearer |token|password|MIEMIE_POSTGRES_PASSWORD=|postgresql\+psycopg://miemie:[^<*]" <artifact-dir>
```

命中 `<redacted>` 或 `token_written=false` 这类摘要字段可以接受；真实凭据、SQL dump、tarball 不应入仓库。

## 备份保留策略

只列出保留/删除候选，不删除：

```bash
RUN_ID=postgres-backup-retention-$(date +%Y%m%d-%H%M%S) \
ARTIFACT_DIR=validation-artifacts/postgres-backup-retention-$(date +%Y%m%d-%H%M%S) \
RETENTION_DAYS=14 \
MIN_KEEP=3 \
bash scripts/postgres_backup_retention.sh
```

确认删除超过保留期且不在最近 `MIN_KEEP` 个内的旧 dump：

```bash
RUN_ID=postgres-backup-retention-$(date +%Y%m%d-%H%M%S) \
ARTIFACT_DIR=validation-artifacts/postgres-backup-retention-$(date +%Y%m%d-%H%M%S) \
RETENTION_DAYS=14 \
MIN_KEEP=3 \
CONFIRM_POSTGRES_BACKUP_RETENTION=prune \
bash scripts/postgres_backup_retention.sh
```

当前建议保留策略：至少保留最近 `3` 个备份，同时保留 `14` 天内备份。后续如果真实用户量和数据增长加快，再把 dump 同步到对象存储或服务器快照体系。

## 定时巡检

生成 cron 预览，不安装：

```bash
RUN_ID=postgres-operational-cron-$(date +%Y%m%d-%H%M%S) \
ARTIFACT_DIR=validation-artifacts/postgres-operational-cron-$(date +%Y%m%d-%H%M%S) \
bash scripts/postgres_install_operational_cron.sh
```

确认安装到 `/etc/cron.d/miemie-postgres-ops`：

```bash
RUN_ID=postgres-operational-cron-$(date +%Y%m%d-%H%M%S) \
ARTIFACT_DIR=validation-artifacts/postgres-operational-cron-$(date +%Y%m%d-%H%M%S) \
CONFIRM_POSTGRES_OPERATIONAL_CRON=install \
bash scripts/postgres_install_operational_cron.sh
```

默认 cron 计划：

- 每天 `03:15` 执行 PostgreSQL operational readiness，并创建新备份与 restore rehearsal。
- 每天 `03:45` 执行备份保留策略，按 `RETENTION_DAYS=14`、`MIN_KEEP=3` 清理旧 dump。

cron 会在执行脚本前尝试加载服务器本地 `/etc/miemie-postgres-ops-alert.env`。该文件不要入仓库，可用于放置告警 webhook：

```bash
MIEMIE_OPS_ALERT_WEBHOOK_URL=https://example.invalid/webhook
```

默认不配置 webhook 时，失败只会在当前 artifact 的 `alerts.tsv` 记录 `skipped/no_webhook`，不会发外部请求。需要先演练告警但不发送网络请求时，可设置：

```bash
MIEMIE_OPS_ALERT_DRY_RUN=true
```

`scripts/postgres_operational_readiness.sh` 只在 `blocked/failed` 时发送 critical 告警；如需 warning 也告警，可设置 `MIEMIE_OPS_ALERT_ON_WARNING=true`。`scripts/postgres_backup_retention.sh` 在脚本异常退出时发送 critical 告警。

2026-06-20 已在 `miemie-pre` 安装 `/etc/cron.d/miemie-postgres-ops`，cron 服务状态为 `active`。安装证据见 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r117-postgres-operational-cron-install-20260620/`。

2026-06-20 已新增默认 no-op 的告警 helper，并用 dry-run webhook 归档告警证据，见 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r118-postgres-ops-alert-dry-run-20260620/`。同日已刷新服务器 cron，使其加载可选告警 env，证据见 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r118-postgres-ops-alert-cron-refresh-20260620/`。

后续每次修改 cron 内容后，都要重新归档：

- `/etc/cron.d/miemie-postgres-ops` 内容。
- cron 服务状态。
- 最近一次 cron log。
- 最近一次 operational readiness artifact。
