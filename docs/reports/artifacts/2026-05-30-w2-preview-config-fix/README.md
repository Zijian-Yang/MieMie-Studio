# 2026-05-30 W2 Preview 配置并发修复复跑

## 结论

- 修复目标：解除 W2 阶梯压测 v1 中 `preview-payload` 首轮并发出现的 `1` 次 `500`。
- 修复版本：`26e3824928a6d4deb86c830183e92310400e107e`
- 复跑结果：preview `10 -> 20 -> 30 VU` 本机与公网六档均通过，服务端日志统计 `POST /api/video-studio/preview-payload` 为 `200 120`，无 4xx/5xx。
- 本轮不触发真实 DashScope 供应商生成；提交阶段仅使用 `/api/video-studio/preview-payload`。

## 修复内容

- `backend/app/config.py` 的配置写入临时文件从固定 `config.tmp` 改为包含 pid、thread id 和 uuid 的唯一临时文件。
- 保留同目录 `os.replace()` 原子替换语义，避免多个 worker 进程首次为同一用户初始化 `config.json` 时争用同一个 tmp 文件。
- 新增回归测试 `backend/tests/test_config_manager.py`，用两个独立 `ConfigManager` 指向同一目录并同步触发 `os.replace()`，覆盖旧实现的 `FileNotFoundError`。

## 本地验证

- 红灯：旧实现下 `venv/bin/pytest backend/tests/test_config_manager.py -q` 复现 `FileNotFoundError: config.tmp -> config.json`。
- 绿灯：修复后 `venv/bin/pytest backend/tests/test_config_manager.py -q` 通过。
- 相关回归：`venv/bin/pytest backend/tests/test_config_manager.py backend/tests/test_fixes.py backend/tests/test_provider_key_and_manifest.py -q`，`43 passed`。
- 全量后端：`venv/bin/pytest backend/tests -q`，`234 passed`。

## 服务器验证

- `/opt/miemie-pre` 已更新到 `26e3824928a6d4deb86c830183e92310400e107e`。
- `compose.env` 的 `MIEMIE_RUNTIME_GIT_COMMIT` 已对齐。
- `docker compose -p miemie-pre --env-file compose.env -f docker-compose.yml -f docker-compose.pre.override.yml config` 通过。
- `api`、`worker`、`worker-video` 已重建并重启，Redis 未重建。
- 本机与公网 `/api/health` 均返回 `200`，`git_commit=26e3824928a6d4deb86c830183e92310400e107e`，`redis.ok=true`。
- `worker` 和 `worker-video` 的 Celery `inspect ping` 均返回 `pong`。

## 复跑结果

| 阶段 | 入口 | VU / 时长 | 失败率 | P95 | P99 |
|---|---|---:|---:|---:|---:|
| preview | 本机 | 10 / 60s | 0% | 12.70ms | 18.59ms |
| preview | 公网 | 10 / 60s | 0.176% | 34.92ms | 567.97ms |
| preview | 本机 | 20 / 60s | 0% | 21.94ms | 32.53ms |
| preview | 公网 | 20 / 60s | 0% | 61.64ms | 1147.11ms |
| preview | 本机 | 30 / 60s | 0% | 29.89ms | 52.07ms |
| preview | 公网 | 30 / 60s | 0% | 71.63ms | 1429.53ms |

服务端提交状态码：

```text
200 120
```

## 清理与健康

- 测试项目删除返回 `200`。
- session logout 返回 `200`。
- 远端 `/tmp` token env 文件已删除；仓库 artifact 不包含 token/password。
- postcheck：本机与公网 `/api/health` 均为 `200`，`api`、`redis`、`worker`、`worker-video` 均保持运行。

## 归档文件

- `results.tsv`
- `api-preview-status-summary.txt`
- `api-preview-log-excerpt.log`
- `*.summary.json`
- `*.gate.json`
- `*.log`
- `precheck.txt`
- `postcheck.txt`
- `cleanup-summary.txt`
