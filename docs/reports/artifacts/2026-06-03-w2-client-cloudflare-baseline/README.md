# W2 本地客户端 Cloudflare 入口复测归档

## 范围

- 日期：2026-06-03
- 发起端：本地 Mac (`Darwin ... arm64`)
- 目标入口：`https://pre-studio.miemie.co`
- 运行版本：`00091f21f5ee207f78a1092e7e5e164ab4567c7f`
- 工具：本机 Homebrew 安装 `k6 v2.0.0 (darwin/arm64)`
- 场景：状态观察读路径，`100 -> 200 -> 300 VU` 递进；每轮查询 `/api/projects`、`/api/video-studio?project_id=<id>`、`/api/video-studio/<task_id>`、`/api/video-studio/<task_id>/status`。
- 安全边界：不触发真实 DashScope 生成；token/password 只保存在 `/tmp/w2-client-cloudflare-baseline-20260603/env.sh`，cleanup 后已删除。

## 关键发现

本轮本地网络不是直连 Cloudflare：

- `dig +short pre-studio.miemie.co A` 返回 `198.18.2.211`
- `route -n get pre-studio.miemie.co` 显示目标走 `utun1024`
- 这符合 Clash Verge TUN / fake-ip 路径特征

因此本轮结论应标记为 **本地 Mac + Clash TUN 代理出口 -> Cloudflare**，不能代表普通用户直连 Cloudflare 的客户端侧门禁。

## 结果

| 档位 | 失败率 | P95 | P99 | 请求数 | check failed | 结论 |
|---|---:|---:|---:|---:|---:|---|
| `100 VU / 120s` | `0` | `925.75ms` | `1671.47ms` | `11168` | `0` | P95 超标，停止后续档位 |

服务器 API 同窗口观察类 GET 状态码汇总为 `200 11169`，未观察到应用 4xx/5xx。测试视频任务删除 `200`、测试项目删除 `200`、logout `200`，压测后 public health 仍为 `200`。

## 慢样本

- `>=800ms` 慢样本：`813`
- 失败样本：`0`
- 最大耗时：`10822.79ms`
- Cloudflare colo 分布：`LAX 503`、`SJC 310`

慢样本大量落在 `waiting` / `receiving`，且 Cloudflare 边缘从前一轮服务器自打的 `SIN` 变为本地代理出口侧的 `LAX/SJC`。这进一步说明“客户端所在出口/代理路径”会显著影响 Cloudflare 入口延迟。

## 结论

- 这轮验证证明：在当前本机 Clash TUN/fake-ip 路径下，即使没有失败和 header 缺失，Cloudflare 入口 `100 VU` 的 P95 也已达到 `925.75ms`，不满足 W2 读路径保守门槛。
- 源站同窗口仍全 `200`，所以这不是应用 5xx 或 Redis/JSON 读写错误。
- 下一步必须先获得“直连 Cloudflare”的客户端侧样本：在 Clash Verge 中为 `pre-studio.miemie.co` 添加 DIRECT 规则，或临时关闭 TUN/fake-ip 后复跑；直连样本完成前，不应把本轮结果当作真实用户直连性能结论。

## 文件

- `run_client_cloudflare_baseline.sh`：本地控制脚本。
- `w2-client-cloudflare-status.js`：k6 场景脚本。
- `results.tsv`：本轮档位汇总。
- `client-cloudflare-100.summary.json`：k6 summary。
- `client-cloudflare-100.gate.json`：门禁摘要。
- `client-cloudflare-100.sample-summary.json`：慢样本摘要。
- `precheck.txt` / `postcheck.txt`：本地网络、k6、DNS/route、public health 证据。
- `api-status-code-summary.txt`：服务器 API 同窗口状态码摘要。
- `cleanup-summary.txt`：测试数据清理摘要。
