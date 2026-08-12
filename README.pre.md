# MieMie-Studio `pre` 自托管发行线

`pre` 是计划替代 `main` 的下一代单服务器发行线。它已经完成 PostgreSQL-only 主数据切换、Redis/Celery Worker、管理员用户治理、平台备份与通用 Webhook，并提供源码构建的一键安装、更新、回滚和恢复工具。

## 发行边界

- 项目提供绑定 `127.0.0.1:<port>` 的完整应用服务。
- 用户管理域名、DNS、HTTPS、Cloudflare、Nginx/Caddy/宝塔和服务器防火墙。
- 项目从当前 Git commit 本地构建 Docker 镜像，不要求公共镜像仓库。
- PostgreSQL 和 Redis 不发布宿主端口。
- API、Worker 和 scheduler 以固定非 root 用户运行，不挂载 Docker socket。
- Web 管理员可以治理用户、注册、备份、阿里云 OSS 副本与 Webhook，但不能执行 Docker、Git、恢复或永久删除。

## 推荐安装

```bash
git clone --branch pre --single-branch https://github.com/Zijian-Yang/MieMie-Studio.git
cd MieMie-Studio
sudo ./install.sh
```

安装完成后，从服务器执行：

```bash
sudo miemie status
sudo miemie doctor
sudo miemie update --check
```

再由部署者把域名反向代理到安装输出的 `127.0.0.1:<port>`。

## 并行部署

不要让旧 `main` 与 `pre` 共用源码目录、Compose 项目名、端口、数据库卷、Redis 卷或备份目录。升级旧环境前先完成数据库备份和隔离恢复演练。

## 当前发行门禁

完整完成定义、阶段状态和外部凭据门禁见：

- [自托管发行路线](docs/plans/2026-08-12-self-hosted-release-roadmap.md)
- [发行边界 ADR](docs/adr/ADR-0004-self-hosted-service-release-boundary.md)
- [安装手册](docs/playbooks/SELF_HOSTED_INSTALL.md)
- [更新与回滚](docs/playbooks/SELF_HOSTED_UPGRADE_ROLLBACK.md)
- [备份与恢复](docs/playbooks/SELF_HOSTED_BACKUP_RESTORE.md)

在阶段 7D 的干净系统矩阵、当前发行真实模型/OSS 与容量门禁全部归档前，`pre` 仍属于 release candidate，不应宣称为最终稳定版。
