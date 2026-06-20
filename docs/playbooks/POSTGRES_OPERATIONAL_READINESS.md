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
