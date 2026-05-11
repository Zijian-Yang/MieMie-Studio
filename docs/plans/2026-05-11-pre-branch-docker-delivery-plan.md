# pre 分支与 Docker 交付计划

## 背景

2026-05-11 决定建立 `pre` 高性能实验分支，与 `main` 稳定功能线并行。`pre` 先从最新 `origin/main` 创建，再迁入 Step 00 / Step 01 的 HA、Compose、压测、观测和文档资产。

## 执行策略

- 先对当前 HA 工作树做密钥扫描，排除 API key、服务器密码、`backend/data/`、日志和 Playwright 生成物。
- 将当前 HA 工作树保存为可回滚快照，再从最新 `origin/main` 创建 `pre`。
- 将 HA 快照迁入 `pre`，冲突解析原则为：保留 `main` 的新模型/测评/OSS 能力，叠加 HA 的生产运行时和压测能力。
- Compose 第一阶段只提供本机构建路径，不发布公共 Docker registry 镜像。
- 宝塔、域名、SSL、Nginx/Caddy/ALB 由使用者自管；项目只稳定提供应用端口和反代最低要求。

## 交付物

- `pre` 分支基于最新 `origin/main`。
- 根目录新增 `README.pre.md`，说明实验分支定位、Docker Compose 本机构建、反向代理边界和并行部署建议。
- Compose 默认绑定 `127.0.0.1:${MIEMIE_HOST_PORT}`，降低应用端口直接暴露公网的风险。
- `docs/DEPLOYMENT.md` 与 `docs/README.md` 更新 Compose / 反代边界说明。

## 验收

- `git ls-remote --heads origin pre` 能看到远端 `pre`。
- `docker compose config` 能通过静态校验。
- `/api/health` 在 Compose 模式返回 `200`，并包含 `X-Request-ID` 与 `X-Deployment-Version`。
- README 明确当前不是 `docker pull` 公共镜像交付，而是 clone 仓库后本机构建。

## 后续

- `pre` 稳定后，再增加 GHCR 发布 workflow，使用 `pre-latest` 和 `pre-<sha>` 标签。
- Redis / PostgreSQL / Worker / SSE 进入后续 Step 02+，不在本次分支开枝里提前实装。
