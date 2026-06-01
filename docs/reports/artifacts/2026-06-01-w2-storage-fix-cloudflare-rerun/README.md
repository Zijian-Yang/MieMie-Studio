# 2026-06-01 StorageService 修复部署与 Cloudflare 复跑

目标：部署 `StorageService._write_json_with_lock()` 唯一临时文件修复后，复跑 Cloudflare 真实入口 `100 VU / 120s`，确认应用侧 JSON 写入竞态 500 是否清零，并继续观察 Cloudflare timeout 是否独立存在。

## 修复内容

- 提交：`00091f21f5ee207f78a1092e7e5e164ab4567c7f`
- 修改：`backend/app/services/storage.py`
- 行为：通用 JSON 原子写入的临时文件从固定 `<name>.tmp` 改为 pid/thread/uuid 唯一路径。
- 回归：新增 `backend/tests/test_storage_service.py`，按 TDD 确认旧实现会复现 `FileNotFoundError`，修复后通过。

本地验证：

```text
venv/bin/pytest backend/tests/test_storage_service.py -q
1 passed

venv/bin/pytest backend/tests/test_config_manager.py -q
1 passed

venv/bin/pytest backend/tests -q
235 passed
```

服务器部署验证：

- `/opt/miemie-pre` 已 fast-forward 到 `00091f21f5ee207f78a1092e7e5e164ab4567c7f`
- `docker compose config` 通过
- `api`、`worker`、`worker-video` 已重建，Redis 未重建
- `compose.env` 的 `MIEMIE_RUNTIME_GIT_COMMIT` 已同步为 `00091f21f5ee207f78a1092e7e5e164ab4567c7f`
- 容器内回归：`pytest backend/tests/test_storage_service.py backend/tests/test_config_manager.py -q` 为 `2 passed`
- 本机与公网 `/api/health` 均为 `200`，响应头 `x-deployment-version` 为 `00091f21f5ee207f78a1092e7e5e164ab4567c7f`

## Cloudflare 复跑结果

| label | VU | duration | http_req_failed | P95 | P99 | http_reqs | check failures | gate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| cloudflare-status-100 | 100 | 120s | 0.0364% | 170.64ms | 1978.19ms | 19256 | 21 | 未通过 |

API 侧状态码：

```text
200 19263
```

本轮未再观察到应用 500，说明 `StorageService` 固定 tmp 文件竞态已解除；Cloudflare 入口仍有 7 个 k6 `request timeout`，因此 Cloudflare/公网边缘链路 timeout 仍是独立问题。

timeout URL 分布：

- `/api/projects`：2 次
- `/api/video-studio?project_id=<project_id>`：2 次
- `/api/video-studio/<task_id>/status`：3 次

## 清理与后置状态

- 测试视频任务删除：`200`
- 测试项目删除：`200`
- logout：`200`
- 服务器 `/tmp/w2-storage-fix-cloudflare-rerun-20260601/env.sh` 已删除
- 压测后公网 `/api/health`：`200`
- Compose：`api`、`redis`、`worker`、`worker-video` 均保持运行

## 结论

应用侧 500 阻塞项已清零；W2 Cloudflare 入口仍未通过严格门禁，因为 timeout 仍存在。下一步应聚焦 Cloudflare/公网链路尾部 timeout，而不是继续追应用 JSON 写入竞态。
