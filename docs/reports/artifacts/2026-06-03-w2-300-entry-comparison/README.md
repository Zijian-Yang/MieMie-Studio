# W2 300 VU 入口对照归档

## 范围

- 日期：2026-06-03
- 服务：`miemie-pre`
- 运行版本：`00091f21f5ee207f78a1092e7e5e164ab4567c7f`
- 目标：用同一批一次性用户、项目和无 key 视频任务，对比 300 VU 状态观察读路径在应用直连、Nginx 源站和 Cloudflare 真实入口下的尾延迟。
- 场景：`300 VU / 120s`，每轮查询 `/api/projects`、`/api/video-studio?project_id=<id>`、`/api/video-studio/<task_id>`、`/api/video-studio/<task_id>/status`。
- 安全边界：不触发真实 DashScope 生成；token/password 只留在服务器 `/tmp` 临时 env，cleanup 阶段已删除，仓库仅保留脱敏摘要。

## 结果

| 入口 | 失败率 | P95 | P99 | 请求数 | check failed | 结论 |
|---|---:|---:|---:|---:|---:|---|
| app direct `http://127.0.0.1:18100` | `0` | `244.29ms` | `489.41ms` | `62776` | `0` | 通过 |
| Nginx local forced `127.0.0.1` | `0` | `271.69ms` | `610.00ms` | `52756` | `0` | 通过 |
| Nginx origin IP forced `47.79.99.190` | `0` | `325.81ms` | `681.59ms` | `51636` | `0` | P95 略超 |
| public Cloudflare | `0.0020%` | `512.92ms` | `914.13ms` | `49908` | `3` | P95 超标，1 次连接超时 |

API 日志窗口内状态码汇总为 `200 217076`，未观察到应用 4xx/5xx 放大。测试视频任务删除 `200`、测试项目删除 `200`、logout `200`，压测后 app/public health 均为 `200`，`api`、`redis`、`worker`、`worker-video` 均保持运行。

## 慢样本

本轮按 `>=800ms` 记录慢请求或失败请求：

| 入口 | 慢/失败样本数 | 最大耗时 | 失败样本 |
|---|---:|---:|---:|
| app direct | `169` | `1855.11ms` | `0` |
| Nginx local | `126` | `987.22ms` | `0` |
| Nginx origin IP | `62` | `869.04ms` | `0` |
| public Cloudflare | `670` | `7462.09ms` | `1` |

Cloudflare 唯一失败样本为 `GET https://pre-studio.miemie.co/api/projects` 的 `dial: i/o timeout`；源站 API 同窗口仍记录为全 `200`。Cloudflare 慢样本均带 `server=cloudflare`、`cf-cache-status=DYNAMIC` 和 `cf-ray`，多数慢请求分布在 `waiting` / `receiving`，首轮连接还出现较高 `blocked` / `tls`。

## 结论

- 当前应用直连和本机 Nginx 源站在 `300 VU / 120s` 下仍能通过 W2 读路径保守门槛，说明应用、Redis、worker 和本机反代不是首要瓶颈。
- 源站公网 IP forced 路径 P95 `325.81ms`，比本机 Nginx 高约 `54ms`，说明从服务器自打公网 IP / 源站公网链路本身已有可见尾延迟。
- Cloudflare 真实入口 P95 `512.92ms`，比源站公网 IP forced 再高约 `187ms`，且出现 1 次客户端连接超时；本轮瓶颈主要落在 Cloudflare/公网边缘路径，而不是应用 5xx 或 JSON 写入竞态。
- 下一步不建议立刻引入 PostgreSQL/SSE/RabbitMQ；应先围绕 Cloudflare 入口做更小步的连接复用、TLS/边缘路径和压测来源位置对照，必要时把 W2 公网门槛拆为“源站能力门槛”和“Cloudflare 用户体验门槛”。

## 文件

- `run_300_entry_comparison.sh`：服务器控制脚本。
- `w2-entry-status.js`：k6 场景脚本。
- `results.tsv`：四入口汇总。
- `*-300.summary.json`：k6 summary。
- `*-300.gate.json`：门禁摘要。
- `*-300.sample-summary.json`：慢/失败样本摘要。
- `precheck.txt` / `postcheck.txt`：运行前后 health、Compose 和 Docker stats。
- `cleanup-summary.txt`：测试数据清理摘要。
