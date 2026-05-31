# 2026-05-31 W2 Cloudflare 入口复验

## 结论

- 本轮目标：恢复 Cloudflare 代理后，复验真实公网入口的 W2 状态观察 100 VU。
- 运行版本：`26e3824928a6d4deb86c830183e92310400e107e`
- 入口状态：`pre-studio.miemie.co` 解析到 Cloudflare IP，响应头为 `server: cloudflare`。
- 测试方式：创建一次性用户、项目和 1 个无 key 视频任务，只读压测项目列表、视频任务列表、任务详情和 `/status`。
- 结果：Cloudflare 入口 `100 VU / 120s` P95 `207.86ms` 低于 `300ms` 门槛，但出现 9 个 k6 `request timeout`，导致 27 个响应 check 失败，严格门禁停止，未进入 300/500。
- API 侧观察类 GET 状态码汇总为 `200 18253`，未观察到应用 4xx/5xx 放大。

## 复验结果

| 阶段 | VU / 时长 | 请求数 | 失败率 | P95 | P99 | check 失败 | 结论 |
|---|---:|---:|---:|---:|---:|---:|---|
| cloudflare-status | 100 / 120s | 18247 | 0.049% | 207.86ms | 2554.39ms | 27 | 停止 |

Timeout 明细：

```text
22:24:45 GET /api/video-studio/{task_id} request timeout
22:24:57 GET /api/projects request timeout
22:25:13 GET /api/projects request timeout
22:25:21 GET /api/projects request timeout
22:25:23 GET /api/video-studio?project_id={project_id} request timeout
22:25:25 GET /api/video-studio/{task_id} request timeout
22:25:45 GET /api/projects request timeout
22:26:01 GET /api/video-studio/{task_id}/status request timeout
22:26:01 GET /api/video-studio?project_id={project_id} request timeout
```

## 判断

- DNS only 复跑时 100 VU 无失败，300 VU 无 timeout；恢复 Cloudflare 后 100 VU 再次出现 60s timeout。
- API 容器日志窗口内相关 GET 均为 200，说明应用、Redis/session、Nginx 源站不是本轮 timeout 的主要来源。
- Cloudflare 真实入口仍需要单独调优；在 timeout 清零前，不应继续 Cloudflare 300/500 VU 阶梯。

## 建议的 Cloudflare 调优顺序

1. 对 `/api/*` 建独立规则：禁用缓存、禁用性能改写、禁用 Rocket Loader/自动优化类功能。
2. A/B 关闭 HTTP/3/QUIC，再复跑 `100 VU / 120s`。
3. 检查 WAF、Bot Fight、Rate Limiting、DDoS 规则是否对 k6 或源站回源触发。
4. 保持 SSL 为 `Full` 或 `Full (strict)`，Cloudflare Origin Certificate 可继续用于回源。
5. 若仍 timeout，采集 Cloudflare analytics / Ray ID 维度和 Nginx `request_time` / `upstream_response_time` 对照。

## 清理与健康

- 测试视频任务删除返回 `200`。
- 测试项目删除返回 `200`。
- session logout 返回 `200`。
- 远端 `/tmp` token env 文件已删除；仓库 artifact 不包含 token/password。
- postcheck：公网 `/api/health` 为 `200`，`api`、`redis`、`worker`、`worker-video` 均保持运行。

## 归档文件

- `results.tsv`
- `cloudflare-status-100.summary.json`
- `cloudflare-status-100.log`
- `k6-error-summary.log`
- `api-status-code-summary.txt`
- `precheck.txt`
- `postcheck.txt`
- `cleanup-summary.txt`
- `w2-cloudflare-status.js`
