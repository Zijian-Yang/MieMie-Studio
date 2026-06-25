# R125 pre-studio 入口审计 bodyless 复跑

目标：使用不归档静态 JS 正文的入口审计脚本，复验 `pre-studio.miemie.co` 经 Cloudflare -> aaPanel/Nginx -> `127.0.0.1:18100` 的入口健康、响应头和静态资源缓存口径。

## 结果

- 状态：`passed_with_warnings`
- 公网 `/api/health`：`200`，`status=ok`，`redis.ok=true`，`database.ok=true`
- 公网 API 头：`server=cloudflare`，`cf-cache-status=DYNAMIC`，`cache-control=no-store`
- 本机 origin `/api/health`：`200`，`status=ok`，`redis.ok=true`，`database.ok=true`
- 静态资源：首页引用 `/_static/index-D-1V5NKu.js`，二次请求 `cf-cache-status=HIT`，`cache-control=public, max-age=604800, immutable`
- 静态 JS 正文不入仓库；`responses.summary.json` 只记录 `body_sha256` 与 `body_bytes`

## Warnings

- `public_health_http3_advertised`：Cloudflare 当前响应 `alt-svc` 仍广告 `h3`。
- `local_health_no_store`：本机 origin health 未返回 `cache-control=no-store`；公网 API 经过入口后已满足 no-store。
- `deployment_version_match`：公网 health 运行版本为 `c948b8116ede4bc3d26df135a1f2a52542ed4710`，静态资源响应头版本为 `34441611bf06b07ca26fb6fb7b9c58655ad2424d`。该差异不影响本次入口硬门禁，但应在后续发布一致性检查中收口。

## 关键文件

- `status.json`
- `results.tsv`
- `responses.summary.json`
- `public-health.headers`
- `local-health.headers`
- `public-static-second.headers`
