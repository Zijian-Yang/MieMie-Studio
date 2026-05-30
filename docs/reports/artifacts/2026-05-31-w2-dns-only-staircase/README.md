# 2026-05-31 W2 DNS Only 状态观察阶梯

## 结论

- 本轮目标：Cloudflare 切到 DNS only 后，复跑公网状态观察阶梯，确认公网 timeout 是否消失。
- 运行版本：`26e3824928a6d4deb86c830183e92310400e107e`
- 入口状态：`pre-studio.miemie.co -> 47.79.99.190`，响应头为 `server: nginx`，未经过 Cloudflare。
- TLS 处理：源站证书链在服务器 curl/k6 环境中仍有校验问题，本轮 k6 使用 `insecureSkipTLSVerify: true`，证书链作为独立运维项记录。
- 测试方式：创建一次性用户、项目和 1 个无 key 视频任务，只读压测项目列表、视频任务列表、任务详情和 `/status`。
- 阶梯结果：DNS only 公网 `100 VU / 120s` 通过；`300 VU / 120s` 无失败、无 timeout、响应头 check 全通过，但 P95 `307.78ms` 略超 `300ms` 保守门槛，按规则停止，未进入 500 VU。

## 阶梯结果

| 阶段 | VU / 时长 | 请求数 | 失败率 | P95 | P99 | check 失败 | 结论 |
|---|---:|---:|---:|---:|---:|---:|---|
| dns-only-status | 100 / 120s | 23536 | 0% | 45.92ms | 215.69ms | 0 | 通过 |
| dns-only-status | 300 / 120s | 52000 | 0% | 307.78ms | 666.39ms | 0 | 停止 |

API 侧观察类 GET 状态码汇总：

```text
200 75537
```

## 判断

- Cloudflare 代理路径中的 60s timeout 在 DNS only 下没有复现；本轮 k6 error summary 为空。
- 300 VU 的平台侧读请求无 4xx/5xx、无 header 缺失，说明应用、Redis/session、Nginx 源站在该档位没有稳定性放大问题。
- 300 VU P95 `307.78ms` 只比保守门槛高约 `7.78ms`，更像当前单机 JSON 读路径加公网源站链路的边缘容量点；不建议直接下结论需要 PostgreSQL/SSE/RabbitMQ。
- 下一步应先修复源站证书链，随后复跑 DNS only 300 VU；若稳定低于 `300ms` 再进入 500 VU，若仍略超则分析列表/任务详情读路径热点。

## 清理与健康

- 测试视频任务删除返回 `200`。
- 测试项目删除返回 `200`。
- session logout 返回 `200`。
- 远端 `/tmp` token env 文件已删除；仓库 artifact 不包含 token/password。
- postcheck：DNS 仍为 `47.79.99.190`，公网 `/api/health` 为 `200`，`api`、`redis`、`worker`、`worker-video` 均保持运行。

## 归档文件

- `results.tsv`
- `dns-only-status-100.summary.json`
- `dns-only-status-300.summary.json`
- `dns-only-status-100.log`
- `dns-only-status-300.log`
- `api-status-code-summary.txt`
- `precheck.txt`
- `postcheck.txt`
- `cleanup-summary.txt`
- `w2-dns-only-status.js`
