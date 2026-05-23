# 2026-05-23 项目进度盘点报告

## 基本信息

- 日期：2026-05-23
- 分支：`pre`
- HEAD：`25aab54 docs: 记录pre服务器验证进展与SSH阻塞`
- 工作树：盘点开始时干净
- 文件规模：`rg --files` 统计 337 个仓库文件

## 当前总体结论

项目当前处于 `pre` 高性能/生产运行时实验分支阶段。功能主线已包含图片工作室、视频工作室、音频、图库、图片测评、视频测评、多模型接入、限流能力 schema、后台状态协调器、Docker/Compose 第一阶段交付与压测资产。

本地代码健康度良好：后端全量测试、前端类型检查、lint、生产构建和 Compose 静态配置均通过。当前真正未闭环的工作不在本地代码可运行性，而在服务器 `pre` 独立部署后的 S1/S3 k6、低频 DashScope smoke、压测后资源快照补跑，以及后续 Redis / Worker / PostgreSQL / SSE 架构步骤尚未实装。

## 已完成进度

- 文档体系已建立：`docs/README.md`、spec、ADR、checklist、playbook、review、plan、report 分层清晰。
- `pre` 分支已建立，并与 `main` 稳定功能线分离。
- Compose 第一阶段交付已具备：`Dockerfile`、`docker-compose.yml`、`compose.env.example`、`README.pre.md`、部署文档均已存在。
- 本地 Compose 静态配置通过，默认绑定 `127.0.0.1:${MIEMIE_HOST_PORT:-8000}`。
- 2026-05-18 服务器报告显示：`pre` 可在 Ubuntu staging 独立 Compose project `miemie-pre` 构建启动，`/api/health` 与 `GET /` 已通过。
- 2026-05-08 Step 01 报告显示：Compose 路径曾完成 S1、S3、真实 DashScope 低频 smoke 和资源快照。
- 后端测试覆盖已扩展到 220 项，覆盖 auth、CORS、middleware、storage、OSS staging、模型限流、图片测评、视频测评、图片/视频工作室能力等。

## 本轮验证证据

```text
./run.sh test
220 passed in 69.04s
```

```text
npm run typecheck
通过
```

```text
npm run lint
通过
```

```text
npm run build
通过，3156 modules transformed，built in 2.98s
提示：Browserslist/caniuse-lite 数据约 6 个月未更新
```

```text
docker compose config
通过；默认发布端口为 127.0.0.1:8000->8000/tcp
```

## 未完成项

1. `pre` 服务器 2026-05-18 验证未闭环：
   - S1 纯读 k6 未补跑
   - S3 状态观察 k6 未补跑
   - 低频真实 DashScope smoke 未补跑
   - 压测后 `docker stats` 资源快照未补跑

2. 线上图片工作室卡顿修复仍标记为本地已修复、待线上验证。

3. 架构路线仍停留在 Step 00 / Step 01 基础设施验证阶段：
   - Step 02 Redis session/cache/rate-limit 尚未实装
   - Step 03 Celery + Redis Worker 尚未实装
   - Step 04 PostgreSQL 业务状态迁移尚未实装
   - Step 05 SSE / 上传卸载尚未实装
   - Step 06 发布门禁与观测固化尚未实装

4. 代码治理 backlog 仍存在：
   - `frontend/src/services/api.ts` 约 2910 行
   - `frontend/src/pages/VideoStudio/VideoStudioPage.tsx` 约 3972 行
   - `frontend/src/pages/Studio/StudioPage.tsx` 约 3968 行
   - `frontend/src/pages/Frames/FramesPage.tsx` 约 2043 行
   - `backend/app/routers/studio.py` 约 3559 行
   - 前端 smoke tests 仍需补强

## 日志观察

本轮测试生成 `backend/logs/api_20260523.log`。日志主要来自测试过程中的 slowapi limiter reset、OSS 未启用时保留供应商 URL、测试用例中模拟的 `Model.AccessDenied` 提交失败等，未发现阻断本轮验证的运行时异常。

## 下一步建议

1. 先补跑 `pre` 服务器验证闭环，按 `docs/reports/2026-05-18-pre-server-validation.md` 的 SSH 恢复后清单执行。
2. 将补跑结果写回 2026-05-18 服务器报告，并归档 k6 summary / smoke summary。
3. 完成线上图片工作室修复的线上验证，更新 `docs/ISSUES.md` 状态。
4. 若服务器验证通过，进入 Step 02：Redis session/cache/rate-limit 的最小实装。
5. 在架构改造前，优先拆分 `frontend/src/services/api.ts` 和 `VideoStudioPage`，降低后续 Step 02/03 改动风险。
