# 2026-05-29 S4 公网反代后性能基线

## 结论

- 计划执行目标：在 `miemie-pre` 上运行 S4 两段式基线，对比服务器本机 `http://127.0.0.1:18100` 与公网 `https://pre-studio.miemie.co`。
- 结果：保守门禁通过。四组 k6 均为 `http_req_failed=0`、checks failed `0`，P95 均低于 `800ms`。
- 本轮不触发真实 DashScope 供应商调用；少量提交仅使用 `/api/video-studio/preview-payload`。

## 执行环境

- 运行版本：`32ff189a57ca13cafcc73f7dd6e956ca1d8ce1e9`
- Compose project：`miemie-pre`
- 运行入口：`127.0.0.1:18100->8000/tcp`
- k6：`k6 v2.0.0-rc1`
- 测试项目：`67949802-2bb1-4e7e-a943-90c22e6c74bd`
- 测试用户：`s40529_020497`

## 结果摘要

| 场景 | 入口 | VU / 时长 | 请求数 | 失败率 | P95 | P99 | checks failed |
|---|---|---:|---:|---:|---:|---:|---:|
| 只读查询 | 本机 `127.0.0.1:18100` | 30 / 90s | 4050 | 0% | 22.58ms | 47.93ms | 0 |
| 只读查询 | 公网 `pre-studio.miemie.co` | 30 / 90s | 3918 | 0% | 29.99ms | 77.32ms | 0 |
| 查询 + preview | 本机 `127.0.0.1:18100` | 20 / 60s | 1220 | 0% | 22.79ms | 30.41ms | 0 |
| 查询 + preview | 公网 `pre-studio.miemie.co` | 20 / 60s | 1216 | 0% | 38.33ms | 86.22ms | 0 |

## 归档文件

- `s4-local-read-summary.json` / `s4-local-read.log`
- `s4-public-read-summary.json` / `s4-public-read.log`
- `s4-local-preview-summary.json` / `s4-local-preview.log`
- `s4-public-preview-summary.json` / `s4-public-preview.log`
- `test-data-summary.json`
- `cleanup-summary.json`
- `postcheck.txt`

## 清理

- 测试项目删除返回 `200`：`{"message":"项目已删除"}`
- 登出返回 `200`：`{"success":true}`
- 登出后 token 失效，后续项目查询返回 `401`
- 测试用户未删除；公开 API 当前仅支持项目删除和 session 登出。

## 观察

- SSH 在公网只读和本机 preview 两次 k6 收尾阶段断开，但远端 k6 进程完成并生成 summary/log；本轮结论以远端 artifact 为准。
- 压测后本机与公网 `/api/health` 均为 `status=ok`，`redis.ok=true`。
- 压测后 `miemie-pre-api-1`、`redis`、`worker`、`worker-video` 均保持运行。
