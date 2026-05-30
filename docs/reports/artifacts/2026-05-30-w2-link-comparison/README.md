# 2026-05-30 W2 公网链路对照

## 结论

- 本轮目标：拆解 W2 状态观察公网 60s timeout 属于应用、Nginx 源站还是 Cloudflare 公网代理链路。
- 运行版本：`26e3824928a6d4deb86c830183e92310400e107e`
- 测试方式：复用一次性用户、项目和 1 个无 key 视频任务，只读压测项目列表、视频任务列表、任务详情和 `/status`。
- 对照组：同样 `100 VU / 120s`，分别命中 FastAPI 应用直连、Nginx 本机源站、Nginx 源站公网 IP 和 Cloudflare 公网域名。
- 结果：前三组均失败率 `0`、check 失败 `0`；Cloudflare 公网域名复测失败，P95 `409.26ms`，出现 5 个 k6 `request timeout`。
- API 侧观察类 GET 状态码汇总为 `200 88423`，未观察到应用 4xx/5xx 放大。

## 对照结果

| 阶段 | 入口 | VU / 时长 | 请求数 | 失败率 | P95 | P99 | check 失败 | 结论 |
|---|---|---:|---:|---:|---:|---:|---:|---|
| app-direct | `http://127.0.0.1:18100` | 100 / 120s | 23764 | 0% | 22.67ms | 155.83ms | 0 | 通过 |
| nginx-local | `https://pre-studio.miemie.co` forced to `127.0.0.1` | 100 / 120s | 23640 | 0% | 28.93ms | 205.25ms | 0 | 通过 |
| nginx-origin-ip | `https://pre-studio.miemie.co` forced to `47.79.99.190` | 100 / 120s | 23600 | 0% | 23.63ms | 200.21ms | 0 | 通过 |
| public-cloudflare | `https://pre-studio.miemie.co` normal DNS | 100 / 120s | 17414 | 0.029% | 409.26ms | 2119.39ms | 15 | 失败 |

Cloudflare 公网域名 timeout 明细：

```text
00:04:55 GET /api/projects request timeout
00:05:04 GET /api/video-studio/{task_id} request timeout
00:05:06 GET /api/projects request timeout
00:05:20 GET /api/video-studio/{task_id}/status request timeout
00:05:22 GET /api/video-studio?project_id={project_id} request timeout
```

## 判断

- 应用直连、Nginx 本机源站和 Nginx 源站公网 IP 均通过，说明 FastAPI/JSON 读路径、Redis/session、aaPanel/Nginx 本身在 100 VU 状态观察档有余量。
- Cloudflare 公网域名连续两轮复现 60s timeout，且本轮 P95 超过 `300ms` 门槛，问题更像 Cloudflare 代理链路、HTTP/3/QUIC、回源连接复用或 Cloudflare 到源站网络尾部抖动。
- 在定位完成前，不建议继续公网 300/500 VU 状态观察档；否则会把 Cloudflare 尾部抖动误判成应用容量瓶颈。

## 清理与健康

- 测试视频任务删除返回 `200`。
- 测试项目删除返回 `200`。
- session logout 返回 `200`。
- 远端 `/tmp` token env 文件已删除；仓库 artifact 不包含 token/password。
- postcheck：应用直连和公网 `/api/health` 均为 `200`，`api`、`redis`、`worker`、`worker-video` 均保持运行。

## 后续建议

1. 先在 Cloudflare 侧临时切换 DNS only 或新增仅源站直连测试域名，复跑公网同域名 100 VU。
2. 检查 Cloudflare HTTP/3、0-RTT、缓存/代理模式和回源 keepalive；必要时临时关闭 HTTP/3/QUIC 做 A/B。
3. 同步采集 Nginx access/error log 中 request_time/upstream_response_time，判断 timeout 请求是否已到源站。
4. Cloudflare 公网 100 VU 无 timeout 后，再恢复 W2 状态观察 300/500 阶梯。

## 归档文件

- `results.tsv`
- `*-100.summary.json`
- `*-100.gate.json`
- `*-100.log`
- `k6-error-summary.log`
- `api-status-code-summary.txt`
- `precheck.txt`
- `postcheck.txt`
- `cleanup-summary.txt`
- `w2-status-hosts.js`
