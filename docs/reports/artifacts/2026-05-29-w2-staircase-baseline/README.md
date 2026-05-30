# 2026-05-29 W2 阶梯压测 v1

## 结论

- 执行目标：在 `miemie-pre` 上验证单机 Compose + Redis + Worker + aaPanel/Nginx + Cloudflare 入口对 W2 平台侧流量的第一版保守承载能力。
- 性能结果：本机与公网只读阶梯 `50 -> 100 -> 200 VU` 全部达到失败率 `<1%`、P95 `<300ms`；preview 阶梯 `10 -> 20 -> 30 VU` 全部达到失败率 `<1%`、P95 `<800ms`。
- 严格门禁结论：**不完全通过**。服务端日志在 `local-preview-10` 首轮并发 preview 提交中发现 `1` 次 `500`，违反“任一档出现 5xx 立即停止”的计划门禁。
- 初步原因：新测试用户首次并发访问 `preview-payload` 时触发 per-user `config.json` 初始化写入竞态，`os.replace(config.tmp, config.json)` 有一次找不到同名临时文件。
- 本轮未触发真实 DashScope 供应商生成；提交阶段仅使用 `/api/video-studio/preview-payload`。

## 执行环境

- 实际执行窗口：`2026-05-30 14:09:54 +0800` 至 `2026-05-30 14:34:05 +0800`
- 运行版本：`32ff189a57ca13cafcc73f7dd6e956ca1d8ce1e9`
- Compose project：`miemie-pre`
- 运行入口：`127.0.0.1:18100->8000/tcp`
- 公网入口：`https://pre-studio.miemie.co`
- k6：`k6 v2.0.0-rc1`
- 测试项目：`1d28d27e-4fc5-4edb-afa1-a71a5cc31d2c`
- 测试用户：`w2_0530140957-18159`

## 阶梯结果

| 阶段 | 入口 | VU / 时长 | 失败率 | P95 | P99 | 性能门槛 |
|---|---|---:|---:|---:|---:|---|
| read | 本机 | 50 / 120s | 0% | 13.10ms | 42.48ms | 通过 |
| read | 公网 | 50 / 120s | 0.038% | 107.44ms | 1532.96ms | 通过 |
| read | 本机 | 100 / 180s | 0% | 15.42ms | 70.43ms | 通过 |
| read | 公网 | 100 / 180s | 0.013% | 126.66ms | 1433.40ms | 通过 |
| read | 本机 | 200 / 180s | 0% | 18.53ms | 60.16ms | 通过 |
| read | 公网 | 200 / 180s | 0.017% | 177.44ms | 1459.18ms | 通过 |
| preview | 本机 | 10 / 60s | 0.164% | 13.10ms | 17.23ms | 性能通过，5xx 门禁失败 |
| preview | 公网 | 10 / 60s | 0.198% | 41.15ms | 604.26ms | 通过 |
| preview | 本机 | 20 / 60s | 0% | 23.09ms | 30.75ms | 通过 |
| preview | 公网 | 20 / 60s | 0% | 64.32ms | 1237.38ms | 通过 |
| preview | 本机 | 30 / 60s | 0% | 30.48ms | 51.33ms | 通过 |
| preview | 公网 | 30 / 60s | 0% | 88.89ms | 1277.13ms | 通过 |

## 5xx 分类

- `api-preview-status-summary.txt`：`POST /api/video-studio/preview-payload` 共 `120` 次，其中 `200=119`、`500=1`。
- `api-preview-500-excerpt.log`：`500` 发生在 `local-preview-10` 首轮并发提交，traceback 指向 `backend/app/config.py` 的 per-user 配置初始化写入：
  - `FileNotFoundError: ... config.tmp -> ... config.json`
- 该 500 没有持续放大；后续 preview 20/30 本机与公网阶段均为 `http_req_failed=0`。
- 但按本轮计划，出现任何 5xx 都应视为门禁失败，因此下一步应先修配置写入竞态，再复跑 preview 阶梯。

## 清理与健康

- 测试项目删除返回 `200`。
- session logout 返回 `200`。
- 远端 `/tmp` token env 文件已删除；仓库 artifact 不包含 token/password。
- postcheck：本机与公网 `/api/health` 均返回 `200`，`redis.ok=true`。
- postcheck：`miemie-pre-api-1`、`redis`、`worker`、`worker-video` 均保持运行；API 容器仍为 `healthy`。

## 观察

- 本机读链路在 200 VU 下 P95 仍低于 `20ms`，说明当前 JSON 读路径在本轮测试数据规模下不是主要瓶颈。
- 公网入口 P95 随 VU 上升，从约 `107ms` 到 `177ms`，仍低于读接口 `300ms` SLO；P99 长期在 `1.4s-1.5s` 区间，主要风险更像公网/Cloudflare/Nginx/TLS 尾部抖动。
- preview 公网 P99 在 `604ms-1277ms`，P95 仍低于 `90ms`；尾部需要继续观察，但当前硬阻塞是 per-user config 首次并发初始化的单次 500。
- 首次尝试因控制脚本未兼容 k6 v2 summary JSON 结构而误停，已保留在 `attempt-1-parser-failure/`；该尝试真实 `local-read-50` 指标为失败率 `0`、P95 约 `14.97ms`。

## 归档文件

- `results.tsv`
- `*.summary.json`
- `*.gate.json`
- `*.log`
- `precheck.txt`
- `postcheck.txt`
- `cleanup-summary.txt`
- `api-preview-status-summary.txt`
- `api-preview-500-excerpt.log`
- `attempt-1-parser-failure/`
