# 2026-05-29 S4 公网反代后性能基线预检

## 结论

- 计划执行目标：在 `miemie-pre` 上运行 S4 两段式基线，对比服务器本机 `http://127.0.0.1:18100` 与公网 `https://pre-studio.miemie.co`。
- 当前状态：未进入 k6 压测。阻塞在 SSH 预检阶段，无法进入服务器确认 `k6 version`、Compose 状态、Docker stats 或本机回环入口。
- 公网入口仍健康：`https://pre-studio.miemie.co/api/health` 返回 `200`，运行版本 `32ff189a57ca13cafcc73f7dd6e956ca1d8ce1e9`，`run_mode=prod`，`serve_frontend=true`，`redis.ok=true`。

## 阻塞证据

本机到服务器 22 端口 TCP 可达：

```text
Connection to 47.79.99.190 port 22 [tcp/ssh] succeeded!
```

但 SSH 在交换服务端 banner 前被远端关闭：

```text
kex_exchange_identification: Connection closed by remote host
Connection closed by 47.79.99.190 port 22
```

`ssh-keyscan -T 5 47.79.99.190` 未返回 host key。

## 已确认边界

- 未创建测试用户。
- 未创建测试项目。
- 未触发 `preview-payload`。
- 未触发真实 DashScope 供应商调用。
- 未改 Nginx 主配置。

## 恢复后补跑清单

1. 先恢复 SSH，使 `ssh root@47.79.99.190 'echo ok'` 能返回。
2. 在 `/opt/miemie-pre` 执行预检：本机/public health、`k6 version`、Compose ps、Docker stats。
3. 创建一次性测试用户和项目，拿到 token 与 project id。
4. 运行 S4 只读本机入口与公网入口。
5. 只读通过后运行 S4 preview 受控提交本机入口与公网入口。
6. 删除测试项目、登出 token，并归档 k6 summary JSON 与资源快照。
