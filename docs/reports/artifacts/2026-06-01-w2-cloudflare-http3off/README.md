# 2026-06-01 W2 Cloudflare HTTP/3 关闭复验

目标：在用户关闭 Cloudflare `HTTP/3 (with QUIC)` 后，复跑 W2 状态观察 Cloudflare 真实入口 `100 VU / 120s`，确认此前 timeout 是否由 HTTP/3/QUIC 引入。

## 入口与前置状态

- 域名：`https://pre-studio.miemie.co`
- Cloudflare：代理开启，公共 DNS 返回 `104.21.85.29` / `172.67.201.59`
- Health：公网 `/api/health` 预检 `200`
- 响应头：`server: cloudflare`，`cf-cache-status: DYNAMIC`，`x-request-id` 和 `x-deployment-version` 存在
- HTTP/3 关闭证据：公网 health 响应头未再出现 `alt-svc: h3`
- 运行提交：`26e3824928a6d4deb86c830183e92310400e107e`
- k6：`k6 v2.0.0-rc1`

## 压测结果

| label | VU | duration | http_req_failed | P95 | P99 | http_reqs | check failures | gate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| cloudflare-status-100 | 100 | 120s | 0.0257% | 190.14ms | 1702.97ms | 19448 | 15 | 未通过 |

失败原因：

- k6 记录 5 个 `request timeout`。
- 每个 timeout 同时造成状态码、`X-Request-ID`、`X-Deployment-Version` 三类 check 缺失，所以 check failures 为 `15`。
- API 侧同窗口观察类 GET 状态码汇总为 `200 19451`，未观察到应用 4xx/5xx 放大。

timeout URL 分布：

- `/api/video-studio?project_id=<project_id>`：1 次
- `/api/projects`：1 次
- `/api/video-studio/<task_id>`：2 次
- `/api/video-studio/<task_id>/status`：1 次

## 与关闭前对比

| 场景 | timeout | check failures | P95 | P99 | 结论 |
| --- | ---: | ---: | ---: | ---: | --- |
| Cloudflare HTTP/3 开启 | 9 | 27 | 207.86ms | 2554.39ms | 未通过 |
| Cloudflare HTTP/3 关闭 | 5 | 15 | 190.14ms | 1702.97ms | 有改善，但未通过 |

关闭 HTTP/3/QUIC 后尾部延迟和 timeout 数量下降，但仍未清零；因此 HTTP/3 不是唯一根因。

## 清理与后置状态

- 测试视频任务删除：`200`
- 测试项目删除：`200`
- logout：`200`
- 服务器 `/tmp/w2-cloudflare-http3off-20260601/env.sh` 已删除
- 压测后公网 `/api/health`：`200`
- Compose：`api`、`redis`、`worker`、`worker-video` 均保持运行

## 结论

Cloudflare 真实入口仍不能进入 300/500 VU 阶梯。当前证据链为：

- 应用直连、Nginx 本机源站、Nginx 源站公网 IP 均已通过 100 VU 对照。
- DNS only 公网 100 VU 通过，300 VU 无失败、无 timeout，仅 P95 略超保守门槛。
- 恢复 Cloudflare 代理后 timeout 复现。
- 关闭 HTTP/3/QUIC 后 timeout 减少但没有消失。

下一步应优先查 Cloudflare 侧 `/api/*` 的 Security Events、WAF、Bot Fight / Super Bot Fight、Rate Limiting、缓存规则命中与 Ray ID，而不是先改应用架构或引入 PostgreSQL/SSE/RabbitMQ。
