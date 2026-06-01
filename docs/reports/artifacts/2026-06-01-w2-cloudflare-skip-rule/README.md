# 2026-06-01 W2 Cloudflare Skip 规则复验

目标：在 Cloudflare 中为压测来源 IP `47.79.99.190` 和 `pre-studio.miemie.co/api/*` 临时部署 Skip 规则后，复跑 W2 状态观察 Cloudflare 真实入口 `100 VU / 120s`，验证 WAF / Bot / Rate Limiting 是否是 timeout 主因。

## Cloudflare 临时规则

规则名：`TEMP skip pre-studio API loadtest`

匹配条件：

```text
(http.host eq "pre-studio.miemie.co" and starts_with(http.request.uri.path, "/api/") and ip.src eq 47.79.99.190)
```

跳过组件：

- All rate limiting rules
- All managed rules
- All Super Bot Fight Mode Rules
- Browser Integrity Check

复验结束后，该临时规则应暂停或删除，避免长期放宽 `/api/*` 安全组件。

## 入口与前置状态

- 域名：`https://pre-studio.miemie.co`
- Cloudflare：代理开启
- Health：公网 `/api/health` 预检 `200`
- 响应头：`server: cloudflare`，`cf-cache-status: DYNAMIC`，`x-request-id` 和 `x-deployment-version` 存在
- 运行提交：`26e3824928a6d4deb86c830183e92310400e107e`
- k6：`k6 v2.0.0-rc1`

## 压测结果

| label | VU | duration | http_req_failed | P95 | P99 | http_reqs | check failures | gate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| cloudflare-status-100 | 100 | 120s | 0.0838% | 195.03ms | 2179.31ms | 17902 | 45 | 未通过 |

失败原因：

- k6 记录 15 个 `request timeout`。
- 每个 timeout 同时造成状态码、`X-Request-ID`、`X-Deployment-Version` 三类 check 缺失，所以 check failures 为 `45`。
- API 侧同窗口观察类 GET 状态码汇总为 `200 17906`、`500 1`。

timeout URL 分布：

- `/api/video-studio/<task_id>`：6 次
- `/api/video-studio?project_id=<project_id>`：5 次
- `/api/projects`：3 次
- `/api/video-studio/<task_id>/status`：1 次

## 新发现的应用侧 500

本轮首次在该状态观察链路中捕获到 1 个应用侧 500：

```text
GET /api/video-studio?project_id=<project_id> HTTP/1.1" 500
```

服务端 traceback 指向 `StorageService._write_json_with_lock()` 使用固定 `<task_id>.tmp`，在并发 `list_tasks` 内触发同一个视频任务 JSON 的临时文件竞争：

```text
FileNotFoundError: .../video_studio/<task_id>.tmp -> .../video_studio/<task_id>.json
```

这与此前已修复的 per-user config 首次并发初始化竞态同类，但位置不同：此前是 `backend/app/config.py`，本轮是 `backend/app/services/storage.py` 的通用 JSON 写入。

## 清理与后置状态

- 测试视频任务删除：`200`
- 测试项目删除：`200`
- logout：`200`
- 服务器 `/tmp/w2-cloudflare-skiprule-20260601/env.sh` 已删除
- 压测后公网 `/api/health`：`200`
- Compose：`api`、`redis`、`worker`、`worker-video` 均保持运行

## 结论

临时 Skip 规则未能消除 Cloudflare 入口 timeout，因此 WAF Managed Rules、Super Bot Fight Mode、Rate Limiting Rules 和 Browser Integrity Check 不是唯一解释。

下一步分两条处理：

1. 先暂停或删除 Cloudflare 临时 Skip 规则，恢复 `/api/*` 正常安全策略。
2. 修复 `StorageService._write_json_with_lock()` 的固定 tmp 文件竞态，补本地并发回归并部署到 pre；之后再复跑本机、DNS only、Cloudflare 入口对照，避免应用 500 与 Cloudflare timeout 混在一起判断。
