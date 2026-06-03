# W2 本地客户端 Cloudflare 美国代理样本归档

## 范围

- 日期：2026-06-04
- 发起端：本地 Mac + Clash TUN/fake-ip
- 出口：用户选择的美国代理节点，Cloudflare colo 显示 `DEN`
- 目标入口：`https://pre-studio.miemie.co`
- 运行版本：`00091f21f5ee207f78a1092e7e5e164ab4567c7f`
- 工具：本机 `k6 v2.0.0 (darwin/arm64)`
- 场景：状态观察读路径，计划按 `100 -> 200 -> 300 VU` 递进；每轮查询 `/api/projects`、`/api/video-studio?project_id=<id>`、`/api/video-studio/<task_id>`、`/api/video-studio/<task_id>/status`。
- 安全边界：不触发真实 DashScope 生成；token/password 只保存在 `/tmp/w2-client-cloudflare-us-proxy-20260604/env.sh`，cleanup 后已删除。

## 有效性说明

本目录 `events.log` 和 `results.tsv` 内包含两次运行记录；归档结论以最新的 `client-cloudflare-100.gate.json`、`client-cloudflare-100.summary.json` 与 `client-cloudflare-100.sample-summary.json` 为准。

预检证据：

- `dig +short pre-studio.miemie.co A` 返回 `198.18.2.211`
- `route -n get pre-studio.miemie.co` 显示 `interface: utun1024`
- public health 为 `200`，响应头为 `server: cloudflare`
- 外层预检响应 `cf-ray` 为 `DEN`

因此本轮是 **本地 Mac -> Clash 美国代理节点 -> Cloudflare -> 源站** 的代理出口样本，不是美国 VPS 原生网络样本。

## 结果

| 档位 | 失败率 | P95 | P99 | 请求数 | check failed | 结论 |
|---|---:|---:|---:|---:|---:|---|
| `100 VU / 120s` | `0` | `960.63ms` | `1315.98ms` | `10436` | `0` | P95 超过原始 W2 读路径 `300ms` 保守门槛，停止后续档位 |

服务器 API 同窗口观察类 GET 状态码汇总为 `200 11159`，未观察到应用 4xx/5xx。测试视频任务删除 `200`、测试项目删除 `200`、logout `200`，压测后 public health 仍为 `200`。

## 慢样本

- `>=800ms` 慢样本：`1173`
- 失败样本：`0`
- 最大耗时：`3537.92ms`
- Cloudflare colo 分布：`DEN 1173`

慢样本主要表现为 `waiting` 或 `receiving` 拉长，且服务器 API 同窗口全 `200`。这说明美国代理路径的高 P95 没有转化为应用错误，更像代理出口质量、代理隧道、本机到代理节点、Cloudflare 边缘到源站的组合尾延迟。

## 阶段结论

- 本轮补齐了一个美国代理入口参考样本：稳定性通过，但 P95 不满足原始 `300ms` 门槛。
- 由于用户确认网站不关注大陆访问效果，本机大陆直连和代理出口样本不作为 W2 平台侧硬门禁。
- W2 平台侧阶段可以收口：应用直连 / 本机 Nginx 300 VU 已通过，应用侧并发 JSON 写入 500 已修复，Cloudflare 入口未再暴露应用 4xx/5xx 放大。
- 若后续要定义目标市场真实入口 SLO，建议从美国或目标地区 VPS 原生网络跑 k6，而不是继续使用本机代理链路。

## 文件

- `w2-client-cloudflare-status.js`：k6 场景脚本。
- `results.tsv`：本轮原始档位汇总，含重复运行记录。
- `client-cloudflare-100.summary.json`：最新 k6 summary。
- `client-cloudflare-100.gate.json`：最新门禁摘要。
- `client-cloudflare-100.sample-summary.json`：最新慢样本摘要。
- `precheck.txt` / `postcheck.txt`：本地网络、k6、DNS/route、public health 证据。
- `api-status-code-summary.txt`：服务器 API 同窗口状态码摘要。
- `cleanup-summary.txt`：测试数据清理摘要。
