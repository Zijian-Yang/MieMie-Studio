# W2 本地客户端 Cloudflare DIRECT 规则复测归档

## 范围

- 日期：2026-06-04
- 发起端：本地 Mac (`Darwin ... arm64`)
- 目标入口：`https://pre-studio.miemie.co`
- 运行版本：`00091f21f5ee207f78a1092e7e5e164ab4567c7f`
- 工具：本机 `k6 v2.0.0 (darwin/arm64)`
- 前置变更：用户已在 Clash Verge 为 `pre-studio.miemie.co` 添加 domain DIRECT 规则。
- 场景：状态观察读路径，计划按 `100 -> 200 -> 300 VU` 递进；每轮查询 `/api/projects`、`/api/video-studio?project_id=<id>`、`/api/video-studio/<task_id>`、`/api/video-studio/<task_id>/status`。
- 安全边界：不触发真实 DashScope 生成；token/password 只保存在 `/tmp/w2-client-cloudflare-direct-rule-20260604/env.sh`，cleanup 后已删除。

## 关键发现

DIRECT 规则添加后，本地系统层网络证据仍显示 Clash TUN / fake-ip 介入：

- `dig +short pre-studio.miemie.co A` 返回 `198.18.2.211`
- `route -n get pre-studio.miemie.co` 显示目标走 `utun1024`
- public health 为 `200`，响应头仍为 `server: cloudflare`

因此本轮结论应标记为 **本地 Mac + Clash DIRECT 规则但仍处于 TUN/fake-ip 路径 -> Cloudflare**。它能证明当前 Clash 配置没有改善客户端侧尾延迟，但不能代表真正关闭 TUN/fake-ip 后的直连 Cloudflare 样本。

## 结果

| 档位 | 失败率 | P95 | P99 | 请求数 | check failed | 结论 |
|---|---:|---:|---:|---:|---:|---|
| `100 VU / 120s` | `0.019%` | `969.79ms` | `1401.50ms` | `10524` | `6` | P95 超标，停止后续档位 |

服务器 API 同窗口观察类 GET 状态码汇总为 `200 10523`，未观察到应用 4xx/5xx 放大。测试视频任务删除 `200`、测试项目删除 `200`、logout `200`，压测后 public health 仍为 `200`。

## 慢样本

- `>=800ms` 慢样本：`1038`
- 失败样本：`2`
- 最大耗时：`6269.18ms`
- Cloudflare colo 分布：`DEN 1038`，另有 `2` 条失败样本未取得 colo

慢样本集中在 Cloudflare `DYNAMIC` 响应，且大量请求的 `waiting` 或 `receiving` 明显高于源站同类压测。结合服务器 API 同窗口全 `200`，本轮主要问题仍是客户端本地网络 / Cloudflare 边缘路径尾延迟，而不是应用 5xx。

## 结论

- Clash domain DIRECT 规则在当前 TUN/fake-ip 模式下没有形成干净直连样本：DNS 仍为 fake-ip，路由仍走 `utun1024`。
- 本轮 100 VU P95 `969.79ms`，比上一轮 Clash TUN/fake-ip 基线 P95 `925.75ms` 没有改善，且出现 2 个失败请求和 6 个 header/status check 失败。
- 源站同窗口 API 日志仍几乎全 `200`，所以不应把本轮失败归因到应用、Redis 或 JSON 存储。
- 下一步若要验证“本地直连 Cloudflare 客户端体验”，需要临时关闭 Clash TUN/fake-ip，或切换到真实 DNS 直连网络后复跑；也可以从另一台不经过 Clash 的客户端/VPS 发起对照。

## 文件

- `run_client_cloudflare_direct_rule.sh`：本地控制脚本。
- `w2-client-cloudflare-status.js`：k6 场景脚本。
- `results.tsv`：本轮档位汇总。
- `client-cloudflare-100.summary.json`：k6 summary。
- `client-cloudflare-100.gate.json`：门禁摘要。
- `client-cloudflare-100.sample-summary.json`：慢样本摘要。
- `precheck.txt` / `postcheck.txt`：本地网络、k6、DNS/route、public health 证据。
- `api-status-code-summary.txt`：服务器 API 同窗口状态码摘要。
- `cleanup-summary.txt`：测试数据清理摘要。
