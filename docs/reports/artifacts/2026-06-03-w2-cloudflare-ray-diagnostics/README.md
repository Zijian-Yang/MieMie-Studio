# 2026-06-03 W2 Cloudflare Ray 诊断

目标：在 `StorageService` 并发写入竞态已修复、Cloudflare 临时 Skip 规则已关闭后，复跑 Cloudflare 真实入口，并采集慢响应 / 失败响应的 `cf-ray`、状态码、URL 与 k6 timings，用于判断剩余问题是否仍是 Cloudflare timeout、应用 5xx，或 300 VU 下的尾部延迟。

## 前置状态

- 入口：`https://pre-studio.miemie.co`
- Cloudflare：代理开启，响应头为 `server: cloudflare`
- HTTP/3：仍关闭，health 响应头未出现 `alt-svc: h3`
- 运行版本：`00091f21f5ee207f78a1092e7e5e164ab4567c7f`
- 诊断脚本：`run_cf_ray_diagnostics.sh`
- 慢样本阈值：`SLOW_SAMPLE_MS=800`
- 不触发真实供应商生成：测试任务为平台侧无 key 状态观察任务

## 结果

| label | VU | duration | http_req_failed | P95 | P99 | http_reqs | check failures | gate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| cf-ray-status-100 | 100 | 120s | 0 | 36.75ms | 187.71ms | 23060 | 0 | 通过 |
| cf-ray-status-300 | 300 | 120s | 0 | 351.64ms | 715.18ms | 49576 | 0 | 未通过 |

API 侧状态码：

```text
100 VU: 200 23061
300 VU: 200 49577
```

慢 / 失败样本：

```text
100 VU: sample_count=0
300 VU: sample_count=0
```

解释：

- 两档均无 k6 request timeout。
- 两档均无响应 header check failure。
- 两档 API 侧均无 4xx/5xx。
- 300 VU 未通过的唯一原因是 P95 `351.64ms` 超过 `300ms` 保守门槛。
- 因慢样本阈值为 `800ms` 且 sample_count 为 `0`，本轮 300 VU 的 P95 超标不是少量超慢尖刺造成，而是较多请求落在 `300-715ms` 区间。

## 清理与后置状态

- 两档测试任务删除：`200`
- 两档测试项目删除：`200`
- 两档 logout：`200`
- 远端 `/tmp/<run_id>/env.sh` 已删除
- 压测后公网 `/api/health`：`200`
- Compose：`api`、`redis`、`worker`、`worker-video` 均保持运行

## 结论

Cloudflare 真实入口当前已恢复到可通过 100 VU 保守门禁的状态；此前的 100 VU timeout 并非稳定复现的应用瓶颈。300 VU 下已没有 timeout 或应用 5xx，但 P95 超过 `300ms`，下一步应做同时间窗口的 300 VU 本机 / Nginx 源站 / Cloudflare 对照，判断 300 VU 尾部延迟主要来自应用 JSON I/O、Nginx/源站网络，还是 Cloudflare 代理层。
