# 自托管反向代理

## 责任边界

MieMie-Studio 只监听安装输出的 `127.0.0.1:<port>`。项目不申请域名和证书，不修改 Cloudflare、服务器防火墙、宝塔站点或 Nginx/Caddy 主配置。

推荐链路：

```text
Browser -> HTTPS/Cloudflare -> Nginx/Caddy -> 127.0.0.1:8000 -> Compose API
```

不要把 PostgreSQL、Redis 或 Docker API 暴露到公网。

## Nginx 最低配置

以下块放在用户自己的 HTTPS `server` 中，并按安装输出调整端口：

```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_connect_timeout 30s;
    proxy_send_timeout 600s;
    proxy_read_timeout 600s;
    client_max_body_size 512m;
}
```

API、登录态和管理接口不应被 CDN 缓存。Cloudflare Cache Rule 建议对 `/api/*` 使用 Bypass cache；不要创建缓存所有动态页面的规则。

## Cloudflare

- DNS 记录启用代理时，SSL/TLS 使用 Full (strict)，源站安装有效证书或 Cloudflare Origin Certificate。
- 保持 `/api/*` 动态直达源站；响应应为 `cf-cache-status: DYNAMIC` 或 BYPASS。
- WAF/限流策略不能挑战正常登录、轮询和受控任务提交；临时压测跳过规则用后立即关闭。
- 如排查 HTTP/3/QUIC 差异，可临时关闭后复测，但普通运行可按站点策略启用。
- 真正隐藏源站 IP 还需要服务器防火墙只允许 Cloudflare 官方代理网段访问 80/443，并单独保留受控 SSH 来源。

## 验证

```bash
curl -fsS http://127.0.0.1:8000/api/health
curl -fsS -D - https://your-domain.example/api/health -o /dev/null
```

公网响应应保留 `X-Request-ID`、`X-Deployment-Version` 和 `Cache-Control: no-store`。本机健康正常而公网异常时，优先检查 DNS、证书、WAF、缓存规则、超时和源站防火墙。
