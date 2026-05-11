# Step 00 Linux staging 执行计划与阻塞记录

## 背景

Step 00 本地验证、压测脚本、报告模板与 Step 01 运行时起步资产已准备好。2026-05-08 已在真实 Ubuntu staging 上补齐首份 S0 基线报告。

## 当前状态

- 日期：2026-05-08
- 目标主机：`<staging-host>`
- 目标用户：`root`
- 目标端口：`22` 已确认可达
- 本地 Termius：用户确认可以连接
- 本会话 SSH：公钥认证已通过
- 密码记录策略：不在仓库文档中记录任何明文凭据
- S0 脚本生产模式：已启动
- S1 基线：已执行并通过
- S3 状态观察基线：已执行并通过
- S3 提交 smoke：已执行，因未配置真实供应商 key 记录为限制项

## 已执行诊断

- `nc -vz -w 5 <staging-host> 22`：成功
- `ssh -o BatchMode=yes root@<staging-host> ...`：本地默认公钥被拒绝
- `sshpass` root 密码认证：服务端拒绝
- `sshpass` keyboard-interactive/password：服务端拒绝
- 本机 `termius` CLI：未安装
- Termius 应用目录元信息搜索：未找到 `<staging-host>` 的可用明文 profile 配置
- 本机会话可用公钥指纹：`SHA256:b1iNKg9uWB0x6lhYwPKPUiAc6770gigwXuxJyIhN7YA`
- 用户通过 Termius 将本机会话公钥加入服务器后，`root@<staging-host>` 公钥登录成功
- 结论：SSH 阻塞已解除

## 执行结果

- 远端路径：`/root/miemie-studio-ha-lab`
- 远端 snapshot commit：`8fb46106a6347667bf527e6a4b3250088f9befb6`
- 运行命令：`MIEMIE_WORKERS=2 NODE_BUILD_MEMORY_MB=1536 ./run.sh start --prod`
- 健康检查：`GET /api/health` 返回 200，响应头包含 `X-Request-ID` / `X-Deployment-Version`
- S1：50 VUs, 60s, 0% HTTP 失败, P95 48.62ms, P99 246.18ms
- S3 observe：300 VUs, 60s, 3s 轮询, 0% HTTP 失败, P95 133.93ms, P99 229.67ms
- S3 submit smoke：5 VUs, 30s, 73/75 submit accepted, 75/75 status observed, 因无 DashScope key 未通过阈值

## 归档位置

- 报告：`docs/reports/2026-04-24-step-00-s0-linux-baseline-template.md`
- 原始结果：`docs/reports/artifacts/2026-05-08-step00-s0/`

## 已完成执行顺序

1. 服务器环境盘点：已完成。
2. 同步当前工作树快照到 staging：已完成。
3. 执行 S0 脚本生产模式：已完成。
4. 检查 `/api/health`、`X-Request-ID`、`X-Deployment-Version`、`git_commit`、`deployment_version`：已完成。
5. 执行 S1 纯读流量：已完成。
6. 执行 S3 任务提交 + 状态观察：已完成并记录限制项。
7. 回填 `docs/reports/2026-04-24-step-00-s0-linux-baseline-template.md`：已完成。
8. 更新 `docs/reports/2026-04-24-step-00-validation-package.md`：已完成。
9. 启动 Step 01 Linux runtime 验证：已完成首轮 Compose 验证。
10. 在 Step 01 Compose 路径补真实 DashScope 低频提交 smoke：已完成。

## 当前下一步

Step 01 Linux Compose 路径已完成首轮验证，并已补真实 DashScope 低频提交 smoke，详见 `docs/plans/2026-05-08-step-01-linux-compose-validation-plan.md` 与 `docs/reports/2026-05-08-step-01-linux-compose-validation.md`。

后续进入 Step 01 文档口径收口与 Step 02 Redis session/cache/rate-limit 准备；真实 OSS 转存仍需单独 staging 配置。
