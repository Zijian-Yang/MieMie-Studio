# 2026-08-12 自托管发行实施路线

## 目标

把 `pre` 建设为后续替代 `main` 的单机自托管发行线。生产部署只提供绑定 `127.0.0.1:<port>` 的应用服务；HTTPS、Cloudflare 和反向代理由部署者管理。

权威设计：

- `docs/superpowers/specs/2026-08-12-self-hosted-release-and-admin-control-plane-design.md`
- `docs/adr/ADR-0004-self-hosted-service-release-boundary.md`

## 全局约束

- 新安装默认 PostgreSQL-only，不回到 JSON 主存储。
- Web 管理面不拥有 Docker、Git、root、shell、数据库恢复或永久删除权限。
- 公开注册默认关闭，首位管理员必须由安装/CLI 显式建立。
- 系统完成 bootstrap 后始终保留至少一个有效管理员。
- 密钥不得进入 Git、日志、artifact 或 API 明文响应。
- 每阶段采用测试先行，并维护 spec、ADR、计划、报告、changelog 和 docs 入口。

## 阶段 7A：管理员与用户治理

详细计划：`docs/superpowers/plans/2026-08-12-phase-7a-admin-user-governance.md`

当前状态：**进行中**。代码、管理界面、Compose migration 门禁和本地完整回归已通过；`pre` 服务器备份、部署和真实治理 smoke 待执行。

交付结果：

- `users` 具备角色、状态、强制改密和更新时间字段。
- `platform_settings` 至少承载公开注册开关。
- `admin_audit_logs` 记录脱敏管理员操作。
- bootstrap 状态和首位管理员 CLI 可用。
- 默认关闭公开注册。
- 管理员用户 CRUD、session 撤销和最后管理员保护完整。
- 前端 `/admin/users` 和管理员导航可用。

完成门禁：后端全量、前端静态门禁、管理员 E2E、容器 migration 和 `pre` 服务器 smoke 通过。

## 阶段 7B：备份、阿里云 OSS 与通用 Webhook

进入条件：7A 已部署，管理员权限和审计稳定。

交付结果：

- 平台级加密配置和 `operation_runs`。
- `worker-ops` 与 scheduler。
- 本地 PostgreSQL 备份、校验、保留策略和阿里云 OSS 上传。
- 通用 Webhook、有限重试和测试发送。
- 管理概览、备份、告警和审计页面。
- 原宿主机 cron 与新 scheduler 完成等价验证和无重复切换。

完成门禁：密钥泄漏扫描、真实 OSS 上传、真实 Webhook 接收、异地副本隔离恢复和失败告警通过。

## 阶段 7C：一键安装、升级与容器加固

进入条件：7B 的运维任务已全部在低权限 Compose 服务内稳定运行。

交付结果：

- PostgreSQL-only 发行环境模板。
- API、Worker、scheduler 非 root 运行。
- 幂等 `install.sh`。
- `/usr/local/bin/miemie` 状态、日志、诊断、更新、回滚、备份、恢复、管理员 bootstrap 和保留数据卸载命令。
- 更新前备份、fast-forward、固定 commit 构建、migration、health 和应用镜像回滚。
- 根 README 把生产安装和本地开发明确分开。

完成门禁：重复安装、失败恢复、更新、回滚、恢复和保留数据卸载演练通过。

## 阶段 7D：发行验收

进入条件：7A 至 7C 功能与自动化测试全部通过。

交付结果：

- Ubuntu 22.04、Ubuntu 24.04、Debian 12 干净服务器安装证据。
- `x86_64` 完整运行证据和 `arm64` 构建兼容证据或明确发布限制。
- 管理员/普通用户权限、注册开关、用户生命周期 E2E。
- 当前 release 的真实图片、真实视频、阿里云 OSS 持久化。
- 本地/异地备份、隔离恢复、通用 Webhook。
- Cloudflare 入口当前 release S4/W2 平台侧容量门禁。
- 安装、更新、回滚和故障恢复文档由陌生环境复现。

## 最终完成定义

只有以下证据全部存在时，才能宣布 `pre` 已达到替代 `main` 的自托管正式发行水准：

1. 四阶段计划全部标记完成且没有未解释的 warning/blocked。
2. README 的生产安装命令在干净服务器成功。
3. 默认部署只暴露回环应用端口，数据库和 Redis 不发布宿主机端口。
4. 管理员、备份、OSS、Webhook、升级和恢复功能均有自动化与真实环境证据。
5. 完整回归、真实供应商 smoke 和目标容量门禁通过。
6. 安全审计确认没有明文密钥、宿主机高权限 Web 接口或最后管理员破坏路径。
