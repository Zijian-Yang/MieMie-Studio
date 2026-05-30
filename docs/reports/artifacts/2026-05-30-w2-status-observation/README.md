# 2026-05-30 W2 状态观察阶梯

## 结论

- 本轮目标：补齐 W2 平台侧状态观察请求阶梯，不触发真实 DashScope 生成。
- 运行版本：`26e3824928a6d4deb86c830183e92310400e107e`
- 测试方式：创建一次性用户、项目和 1 个无 key 视频任务，然后只读压测项目列表、视频任务列表、任务详情和 `/status`。
- 阶梯结果：本机 `100 VU / 120s` 通过；公网 `100 VU / 120s` 按保守门禁停止。
- 公网停止原因：4 个公网 GET 请求在 k6 侧 `request timeout`，导致 `query status acceptable`、`query has request id`、`query has deployment version` 各失败 4 次，共 12 个 check 失败。
- 应用侧观察：API 日志窗口内观察类 GET 状态码汇总为 `200 43785`，未观察到应用 4xx/5xx 放大。

## 阶梯结果

| 阶段 | 入口 | VU / 时长 | 请求数 | 失败率 | P95 | P99 | check 失败 | 结论 |
|---|---|---:|---:|---:|---:|---:|---:|---|
| status | 本机 | 100 / 120s | 23872 | 0% | 17.37ms | 68.23ms | 0 | 通过 |
| status | 公网 | 100 / 120s | 19911 | 0.020% | 138.40ms | 1603.56ms | 12 | 停止 |

公网 k6 超时明细：

```text
18:31:53 GET /api/video-studio/{task_id} request timeout
18:32:45 GET /api/video-studio/{task_id} request timeout
18:32:51 GET /api/projects request timeout
18:32:57 GET /api/video-studio?project_id={project_id} request timeout
```

## 判断

- 本机 100 VU 结果说明应用侧 JSON 读路径、Redis/session 和 API 容器在这一档有余量。
- 公网 100 VU 的 P95 仍低于 `300ms`，失败率也低于 `1%`，但 4 个 60s timeout 会破坏响应头与状态码 check，严格门禁不能继续上 300/500。
- 由于 API 日志窗口内相关 GET 全部为 `200`，这次瓶颈更像公网入口链路尾部抖动，优先怀疑 Cloudflare/Nginx/TLS/连接复用或 k6 到公网域名路径，而不是应用返回 5xx。

## 清理与健康

- 测试视频任务删除返回 `200`。
- 测试项目删除返回 `200`。
- session logout 返回 `200`。
- 远端 `/tmp` token env 文件已删除；仓库 artifact 不包含 token/password。
- postcheck：本机与公网 `/api/health` 均为 `200`，`api`、`redis`、`worker`、`worker-video` 均保持运行。

## 后续建议

1. 不进入 300/500 公网状态观察阶梯，先拆公网 60s timeout。
2. 复跑一个对照组：公网域名但绕过 Cloudflare 或直接命中 Nginx 源站，以区分 Cloudflare 与 aaPanel/Nginx。
3. 若公网 timeout 复现，继续采集 Nginx access/error log、Cloudflare analytics、k6 `--http-debug` 小流量样本。
4. 若绕过公网链路正常，再评估 Nginx keepalive、HTTP/2/HTTP/3、Cloudflare 代理模式和回源连接参数。

## 归档文件

- `results.tsv`
- `local-status-100.summary.json`
- `public-status-100.summary.json`
- `local-status-100.log`
- `public-status-100.log`
- `api-status-code-summary.txt`
- `precheck.txt`
- `postcheck.txt`
- `cleanup-summary.txt`
- `run_status_observation.sh`
