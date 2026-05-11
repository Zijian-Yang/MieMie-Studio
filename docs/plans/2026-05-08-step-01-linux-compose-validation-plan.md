# Step 01 Linux Compose 验证计划与状态记录

## 背景

Step 00 已完成 Linux staging S0 脚本生产模式基线。Step 01 采用“脚本兼容 + Compose 推荐”的双路径，本计划记录第一轮 Compose 推荐路径的验证过程和结果。

## 当前状态

- 日期：2026-05-08
- 目标主机：`<staging-host>`
- 远端路径：`/root/miemie-studio-ha-lab`
- Compose 宿主端口：`18000`
- 远端 snapshot commit：`cebf8b4e49cbb963b9e8bfad16925cf9cf390936`
- Docker / Compose：已安装并可用
- Compose API 容器：已启动，状态 `healthy`
- 前端入口：`GET /` 已验证 200
- 健康检查：`GET /api/health` 已验证 200，包含 `X-Request-ID` 与 `X-Deployment-Version`
- S1 Compose 基线：已执行并通过
- S3 Compose 状态观察基线：已执行并通过
- S3 提交承载：已完成真实 DashScope 低频 smoke

## 已执行事项

1. 在 Linux staging 安装并确认 Docker 与 Docker Compose。
2. 运行 `docker compose config` 验证 Compose 配置可解析。
3. 运行 `docker compose up -d --build` 构建并启动容器。
4. 定位 Compose 容器启动失败：`sh -lc` 作为 login shell 重置 `PATH`，导致找不到 venv 中的 `gunicorn`。
5. 增加 `backend/tests/test_docker_runtime.py` 回归测试。
6. 修复 Dockerfile：改用 `sh -c` 并显式执行 `/opt/venv/bin/gunicorn`。
7. 在远端创建修复快照 commit：`2e1cd0d7875d4cb29dd2db25a9015d4f0d27e83e`。
8. 使用新 commit 重建并启动 Compose API 容器。
9. 验证健康检查、前端入口、响应头和部署版本。
10. 复跑 S1 / S3 observe Compose 基线。
11. 拉取 k6 原始结果到本地 artifacts。
12. 更新 Step 01 报告、Step 00 验证包与变更日志。
13. 通过 `/api/settings/api-key` 为 staging 测试用户配置 DashScope key，密钥不进入仓库。
14. 执行真实 DashScope `wan2.7-t2v` 文生视频提交 smoke。
15. 修复 OSS 未启用时成功供应商结果被标记失败的问题。
16. 修复成功状态保留旧 provider error_message 的开发者元信息污染。
17. 重新部署 Compose 并把真实供应商 smoke 脱敏摘要归档。

## 验证结果摘要

- Compose 状态：`Up ... (healthy)`
- 端口映射：`0.0.0.0:18000->8000/tcp`
- `GET /api/health`：200
- `GET /`：200
- S1：50 VUs, 60s, 0% HTTP 失败, P95 44.30ms, P99 120.41ms
- S3 observe：300 VUs, 60s, 3s 轮询, 0% HTTP 失败, P95 141.16ms, P99 193.99ms
- S3 real provider smoke：`wan2.7-t2v`, 1 个任务, 1 个供应商 task id, 1 个 request id, 1 个视频结果, 平台状态 `succeeded`

## 归档位置

- 报告：`docs/reports/2026-05-08-step-01-linux-compose-validation.md`
- 原始结果：`docs/reports/artifacts/2026-05-08-step01-compose/`
- 真实供应商 smoke 脱敏摘要：`docs/reports/artifacts/2026-05-08-step01-provider-smoke/`

## 当前限制项

- 真实 OSS 未启用：供应商视频 URL 已保留在平台任务记录中，但未转存到长期 OSS。
- 真实供应商高并发提交未验证：本轮只做低频 smoke，避免费用和限流风险。
- 本机 Docker daemon 仍未运行：本机 Docker 构建未作为验收证据，Linux staging Compose 构建已作为替代证据。
- 远端 `loadtest/results/` 中保留运行产物，未纳入远端 snapshot commit。

## 下一步

1. Step 01 文档口径收口：确认部署文档、运行模式矩阵和反向代理边界没有冲突。
2. 如需长期资产闭环，补 OSS staging 配置并复跑一次真实供应商结果转存。
3. 进入 Step 02：Redis session/cache/rate-limit 的设计与最小实装准备。
