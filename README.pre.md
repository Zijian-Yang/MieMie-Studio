# MieMie-Studio pre 分支说明

`pre` 是 MieMie-Studio 的高性能/生产运行时实验分支，目标是在不打断 `main` 稳定功能线的前提下，持续验证 Linux 单机生产部署、Docker Compose、本地压测、运行态可观测性，以及后续 Redis / PostgreSQL / Worker / SSE 改造。

## 分支定位

| 分支 | 定位 | 使用建议 |
|------|------|----------|
| `main` | 稳定功能线，持续接收模型接入、工作室能力和常规修复 | 普通用户优先使用 |
| `pre` | 高性能实验线，优先验证生产运行边界和扩容路线 | 预生产、自测、压测和愿意反馈问题的用户使用 |

`pre` 会阶段性从 `main` 合入新功能；当高性能路径稳定后，再把已验证的运行时能力反向合回 `main` 或 release 分支。

## Docker 交付现状

当前 `pre` 不是公共 registry 的预构建镜像交付方式。第一阶段交付口径是：

1. 用户拉取仓库或切到 `pre` 分支。
2. 在本机或服务器上使用 Docker Compose 构建本地镜像。
3. 由用户自管宝塔 / Nginx / Caddy / 云负载均衡，把域名反代到应用端口。

```bash
git clone https://github.com/Zijian-Yang/MieMie-Studio.git
cd MieMie-Studio
git switch pre
cp compose.env.example compose.env
sed -i.bak "s/replace-with-git-commit/$(git rev-parse HEAD)/" compose.env
docker compose --env-file compose.env up -d --build
docker compose --env-file compose.env ps
curl -i http://127.0.0.1:8000/api/health
```

后续所有 Compose 运维命令（`config`、`build`、`up`、`ps`、`logs`、
`exec`）也必须显式带 `--env-file compose.env`。否则 Compose 会回落到示例默认值，
例如把应用端口改回 `8000`，导致与同机服务冲突。

Compose 默认将应用绑定到 `127.0.0.1:8000`。如需修改端口，请编辑未纳入 Git 的 `compose.env`：

```env
MIEMIE_HOST_BIND=127.0.0.1
MIEMIE_HOST_PORT=8000
MIEMIE_WORKERS=2
MIEMIE_RUNTIME_GIT_COMMIT=replace-with-git-commit
```

## 域名与反向代理边界

本项目只提供应用端口，不接管域名、DNS、SSL、宝塔站点或 Nginx 配置。

推荐生产链路：

```text
用户域名 / HTTPS
        ↓
用户自管反向代理（宝塔 / Nginx / Caddy / 云负载均衡）
        ↓
127.0.0.1:${MIEMIE_HOST_PORT}
        ↓
miemie-studio Compose API 容器
```

最低反代要求：

- 透传 `Host`、`X-Forwarded-For`、`X-Forwarded-Proto`
- 上传体积限制覆盖图片/视频素材
- 读取超时覆盖 AI 任务提交和状态查询
- 未来启用 SSE 时关闭事件流缓冲

## 并行部署建议

如果同一台服务器同时部署 `main` 与 `pre`：

- 使用不同目录，例如 `/opt/miemie-main` 与 `/opt/miemie-pre`
- 使用不同端口，例如 `main=8000`、`pre=18000`
- 不共用 `backend/data/`，避免账号、会话、任务和配置互相污染
- 分别备份 `backend/data/` 与 `backend/logs/`

## 后续镜像计划

当 `pre` 的 Compose 路径稳定后，再考虑增加 GitHub Actions 发布 GHCR 镜像：

- `ghcr.io/<owner>/miemie-studio:pre-latest`
- `ghcr.io/<owner>/miemie-studio:pre-<git-sha>`
- 稳定 release 再发布不可变版本标签

在此之前，官方口径保持“clone 仓库后本机构建镜像”。
