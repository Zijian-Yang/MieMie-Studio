# 自托管安装与首次启动

## 支持环境

- Ubuntu 22.04、Ubuntu 24.04、Debian 12
- `x86_64` 或 `arm64`
- root/sudo 权限、可访问 GitHub 与 Docker 官方软件源
- 建议 2 核 CPU、4 GB 内存、20 GB 可用磁盘
- 一个未占用的本机端口，默认 `8000`

安装器只适用于 Linux 生产服务器。macOS/Windows 请使用 README 的本地开发流程。

## 安装

```bash
git clone --branch pre --single-branch https://github.com/Zijian-Yang/MieMie-Studio.git
cd MieMie-Studio
sudo ./install.sh
```

安装器会：

1. 检查系统、架构、磁盘和端口。
2. 通过 Docker 官方仓库安装缺失的 Docker Engine、Buildx 和 Compose。
3. 把发行源码安装到 `/opt/miemie-studio`。
4. 创建 mode-600 的 `compose.env`，生成数据库密码、实例 ID 和平台加密密钥。
5. 本地构建当前 Git commit，启动 PostgreSQL/Redis，执行 Alembic migration。
6. 通过隐藏输入创建首位管理员。
7. 启动所有非 root 应用服务并验证本机健康接口。
8. 安装 `/usr/local/bin/miemie`。

重复执行不会重置已有密钥、管理员、数据库卷、备份或端口。

## 自定义端口与自动化管理员

安装前可覆盖端口：

```bash
sudo MIEMIE_HOST_PORT=18100 ./install.sh
```

无人值守环境可使用进程环境传入管理员信息；密码不会进入命令参数或日志：

```bash
sudo MIEMIE_ADMIN_USERNAME=admin \
  MIEMIE_ADMIN_PASSWORD='<通过安全渠道注入>' \
  ./install.sh
```

不要把密码写进 shell 历史、仓库、截图或自动化日志。

## 安装后验证

```bash
sudo miemie status
sudo miemie doctor
curl -fsS http://127.0.0.1:8000/api/health
```

健康响应应包含 `status=ok`、当前 `git_commit`、PostgreSQL 与 Redis 正常状态。然后按反向代理手册配置域名。

## 文件位置

| 路径 | 用途 |
|---|---|
| `/opt/miemie-studio` | 源码、Compose 配置、数据目录与本地备份 |
| `/opt/miemie-studio/compose.env` | root-only 发行配置与密钥 |
| `/etc/miemie/miemie.conf` | 管理命令定位配置 |
| `/var/lib/miemie/releases` | root-only 发布清单与操作锁 |
| `/var/log/miemie/install.log` | 不含密钥的安装阶段日志 |

## 常见失败

- `unsupported_host`：只支持列出的 Debian/Ubuntu 版本。
- `host_port_in_use`：换一个 `MIEMIE_HOST_PORT`，不要直接关闭未知服务。
- `source_tracked_changes`：生产源码有受版本控制改动；先备份并恢复干净状态。
- `health_failed`：运行 `sudo miemie status` 和 `sudo miemie logs api`，不要重复清空数据库卷。
