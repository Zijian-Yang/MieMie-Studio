# 2026-06-17 PostgreSQL Connectivity Direct Rule Recheck

本轮用于验证用户新增 Clash 直连规则后，当前 Mac 命令行路径是否已经可以安全执行 PostgreSQL 服务器灰度序列。

## Result

- `MIEMIE_PREFLIGHT_SCOPE=network scripts/pre_studio_connectivity_preflight.sh` 仍为 `blocked`。
- DNS 仍返回 Clash fake-IP：`198.18.0.124`。
- 到源站 `47.79.99.190` 的 OS route 仍走 `gateway 198.18.0.1` / `interface utun1024`。
- 手动 TCP 22 检查通过：`nc -vz 47.79.99.190 22` succeeded。
- 手动 SSH echo 仍失败：`Connection timed out during banner exchange`。
- verbose SSH 显示 TCP 已建立并发送本地 SSH version string，但服务端 banner 未返回，30 秒后超时。

## Decision

不执行 `CONFIRM_REMOTE_SEQUENCE=run scripts/pre_studio_remote_postgres_sequence.sh`。

当前状态下远程自动化仍不能安全依赖本机 SSH 命令路径。下一步优先二选一：

1. 临时关闭 Clash TUN/fake-IP 后让 network/full preflight 退出 `0`。
2. 直接在服务器 `/opt/miemie-pre` 内执行 `CONFIRM_SERVER_SEQUENCE=run scripts/pre_studio_server_postgres_sequence.sh`。

本轮未修改服务器状态、未重启容器、未启用数据库业务开关。
