# 自托管备份与恢复

## 创建与查看备份

```bash
sudo miemie backup --wait
sudo miemie backups
```

备份默认位于安装目录的 `backups/postgres/`。每个 CLI 备份都会生成 SHA-256 校验文件；管理员页面也可配置定时本地备份、阿里云 OSS 副本和通用 Webhook 告警。

## 恢复前提

- 仅接受安装目录 `backups/` 下的非空文件，拒绝目录逃逸和任意宿主文件。
- 如果存在同名 `.sha256` 文件，必须通过校验。
- PostgreSQL custom dump 先执行 `pg_restore --list`。
- 备份会先恢复到临时数据库并查询验证，临时数据库随后删除。
- 隔离验证通过后，系统再创建一份当前生产数据库安全备份。

## 执行恢复

传入相对于 `backups/` 的路径：

```bash
sudo miemie restore postgres/miemie-postgres-YYYYMMDD-HHMMSS-RUN.dump
```

命令会要求两次精确确认：备份文件名，以及 `RESTORE MIEMIE DATABASE`。确认后才会停止 API、worker 和 scheduler，替换生产数据库，执行最新迁移并重新验证健康状态。

恢复期间平台会短暂停机。不要同时运行更新、回滚、备份或第二次恢复；CLI 使用 root-only 文件锁拒绝并发操作。

## 恢复失败

如果生产替换或重启失败，输出会包含 `safety_backup=<path>`。此时不要反复重试或手工删除数据库：

1. 保留终端输出与 `sudo miemie logs api`。
2. 确认 PostgreSQL 容器仍在运行。
3. 使用输出中的安全备份重新执行隔离恢复，或由数据库管理员检查后再恢复。

## 卸载

默认卸载只停止服务并保留源码、配置、数据库卷和备份：

```bash
sudo miemie uninstall
```

永久删除需要：

```bash
sudo miemie uninstall --purge
```

并精确输入 `DELETE MIEMIE DATA`。该操作删除 Compose 卷、配置、源码和备份，无法撤销；管理页面不提供此权限。
