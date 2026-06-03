# W2 本地客户端 Cloudflare 干净直连复测归档

## 范围

- 日期：2026-06-04
- 发起端：本地 Mac (`Darwin ... arm64`)
- 目标入口：`https://pre-studio.miemie.co`
- 运行版本：`00091f21f5ee207f78a1092e7e5e164ab4567c7f`
- 工具：本机 `k6 v2.0.0 (darwin/arm64)`
- 前置状态：已关闭 Clash TUN/fake-ip 对该域名的接管；保护性预检显示 DNS 为 Cloudflare 真实 IP，route 走 `en0`。
- 场景：状态观察读路径，计划按 `100 -> 200 -> 300 VU` 递进；每轮查询 `/api/projects`、`/api/video-studio?project_id=<id>`、`/api/video-studio/<task_id>`、`/api/video-studio/<task_id>/status`。
- 安全边界：不触发真实 DashScope 生成；token/password 只保存在 `/tmp/w2-client-cloudflare-clean-direct-20260604/env.sh`，cleanup 后已删除。

## 有效性说明

本目录 `events.log` 内包含一次 `16:38Z` 的无效尝试：当时新 artifact 目录缺少 `w2-client-cloudflare-status.js`，k6 未实际执行。本归档的有效结果以 `16:49Z` 开始的第二次运行、`results.tsv`、`client-cloudflare-100.summary.json` 与 `client-cloudflare-100.gate.json` 为准。

有效运行的预检证据：

- `dig +short pre-studio.miemie.co A` 返回 `172.67.201.59`、`104.21.85.29`
- `route -n get 172.67.201.59` 显示 `interface: en0`
- public health 为 `200`，响应头为 `server: cloudflare`

## 结果

| 档位 | 失败率 | P95 | P99 | 请求数 | check failed | 结论 |
|---|---:|---:|---:|---:|---:|---|
| `100 VU / 120s` | `0` | `734.57ms` | `1080.36ms` | `12684` | `0` | P95 超过原始 W2 读路径 `300ms` 保守门槛，停止后续档位 |

服务器 API 同窗口观察类 GET 状态码汇总为 `200 12685`，未观察到应用 4xx/5xx。测试视频任务删除 `200`、测试项目删除 `200`、logout `200`，压测后 public health 仍为 `200`。

## 慢样本

- `>=800ms` 慢样本：`505`
- 失败样本：`0`
- 最大耗时：`2965.68ms`
- Cloudflare colo 分布：`LAX 367`、`SJC 138`

相比 Clash TUN/fake-ip 和 domain DIRECT 但仍走 TUN 的两轮，本轮失败和 header 缺失清零，P95 也下降到 `734.57ms`。但从本地客户端访问 Cloudflare 美国西海岸 colo 的尾延迟仍明显高于服务器侧和源站侧对照。

## 结论

- 这轮是干净的本地客户端直连 Cloudflare 样本：DNS 不再是 `198.18.x.x`，route 不再走 `utun`。
- 本地客户端直连 Cloudflare `100 VU` 没有失败、没有响应头缺失，说明稳定性比 TUN/fake-ip 路径更好。
- P95 `734.57ms` 仍不满足原始 `300ms` W2 读路径门槛；但用户已确认该网站不关注大陆访问效果，因此本地大陆/跨境客户端样本不应作为面向目标用户的硬门禁。
- 后续 W2 结论应拆成两条 SLO：
  - 源站和 Cloudflare 入口平台侧承载：继续以服务器同窗口和非大陆 vantage 为主。
  - 大陆/跨境客户端访问体验：保留为参考风险，不阻塞当前阶段。

## 文件

- `w2-client-cloudflare-status.js`：k6 场景脚本。
- `results.tsv`：本轮有效档位汇总。
- `client-cloudflare-100.summary.json`：k6 summary。
- `client-cloudflare-100.gate.json`：门禁摘要。
- `client-cloudflare-100.sample-summary.json`：慢样本摘要。
- `precheck.txt` / `postcheck.txt`：本地网络、k6、DNS/route、public health 证据。
- `api-status-code-summary.txt`：服务器 API 同窗口状态码摘要。
- `cleanup-summary.txt`：测试数据清理摘要。
