# 部署指南

> 本文档介绍如何将 MieMie-Studio 部署到生产环境服务器。

---

## 一、环境要求

### 硬件建议

| 规模 | CPU | 内存 | 磁盘 | 说明 |
|------|-----|------|------|------|
| 个人/小团队（1-10 用户） | 2 核 | 4 GB | 50 GB | 轻量使用足够 |
| 中型团队（10-100 用户） | 4 核 | 8 GB | 100 GB | 推荐配置 |
| 大规模（100+ 用户） | 8 核+ | 16 GB+ | 200 GB+ | 建议增加 Redis |

### 软件依赖

| 依赖 | 最低版本 | 说明 |
|------|---------|------|
| Python | 3.9+ | 推荐 3.10 或 3.11 |
| Node.js | 18+ | 推荐 LTS 版本 |
| npm | 9+ | 随 Node.js 安装 |
| Git | 2.0+ | 用于代码获取和自动更新 |
| screen | - | 后台进程管理 |

### 操作系统

- **推荐**：Ubuntu 22.04 LTS / Debian 12 / CentOS Stream 9
- **支持**：macOS 13+
- **未测试**：Windows（建议使用 WSL2）

---

## 二、快速部署

### 1. 获取代码

```bash
git clone https://github.com/Zian-Yang/MieMie-Studio.git
cd MieMie-Studio
```

### 2. 一键安装

```bash
chmod +x run.sh
./run.sh install
```

此命令会自动：
- 创建 Python 虚拟环境
- 安装后端依赖（FastAPI、Gunicorn 等）
- 安装前端依赖（React、Ant Design 等）
- 检测内核、CPU、内存和当前 Swap，并在用户确认后写入推荐运行参数

如果是服务器部署，建议在首次启动前主动执行一次：

```bash
./run.sh optimize
```

### 3. 启动生产模式

```bash
./run.sh start --prod
```

生产模式特点：
- **后端**：Gunicorn + 多 Worker，默认会按机器资源自动推荐更稳妥的值
- **前端**：构建为静态文件，由后端统一服务
- **访问地址**：`http://服务器IP:8000`
- **资源保护**：生产启动前会先检测资源并提示推荐配置，小内存 Linux 机器会额外建议创建 Swap

### 4. 验证部署

```bash
./run.sh status
```

或直接在浏览器访问 `http://服务器IP:8000`，应看到登录页面。

---

## 三、配置说明

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MIEMIE_WORKERS` | 自动推荐 | Gunicorn Worker 数量，优先兼顾稳定性和机器内存 |
| `NODE_BUILD_MEMORY_MB` | 自动推荐 | 前端生产构建时的 Node 内存上限（MB） |
| `MIEMIE_MODE` | dev | 运行模式：`dev`（开发）/ `prod`（生产） |

设置方式：

```bash
# 临时设置
export MIEMIE_WORKERS=2
export NODE_BUILD_MEMORY_MB=2048
./run.sh start --prod

# 或者用脚本自动检测后持久化到 .miemie.conf
./run.sh optimize
```

### 推荐策略

- `./run.sh install`、`./run.sh start --prod` 和 `./run.sh optimize` 都会触发资源检测
- 脚本会根据 CPU 核数、总内存和当前 Swap 推荐 `MIEMIE_WORKERS` 与 `NODE_BUILD_MEMORY_MB`
- Linux 小内存机器会额外建议创建 Swap；只有在用户确认后才会执行
- 应用后脚本会立即检查配置是否生效，并在 `./run.sh status` 中显示当前值

---

## 四、反向代理配置（推荐）

### Nginx

生产环境建议使用 Nginx 作为反向代理，提供 SSL、负载均衡、静态文件缓存等能力。

```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate     /etc/ssl/certs/your-domain.crt;
    ssl_certificate_key /etc/ssl/private/your-domain.key;

    # 安全头
    add_header X-Frame-Options SAMEORIGIN;
    add_header X-Content-Type-Options nosniff;

    # 请求体大小限制（上传图片/视频需要）
    client_max_body_size 100M;

    # 代理到 MieMie-Studio 后端
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket 支持（如果将来需要）
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # 超时设置（AI 生成任务可能较慢）
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }

    # 前端静态资源缓存
    location /_static/ {
        proxy_pass http://127.0.0.1:8000/_static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

### Caddy（更简单的替代方案）

```
your-domain.com {
    reverse_proxy localhost:8000
}
```

Caddy 会自动处理 SSL 证书（通过 Let's Encrypt）。

---

## 五、安全加固

### 1. 防火墙

```bash
# Ubuntu/Debian (ufw)
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 80/tcp      # HTTP
sudo ufw allow 443/tcp     # HTTPS
sudo ufw enable

# 不要直接暴露 8000 端口，通过 Nginx 代理
```

### 2. API Key 安全

- 用户的阿里云 API Key 存储在各用户的独立配置目录中
- 每个用户只能看到自己的 API Key（已脱敏显示）
- 建议在阿里云控制台为每个用户创建独立的子账号和 API Key

### 3. 会话安全

- Token 有效期默认 7 天，过期自动失效
- 登出时 Token 立即失效
- 密码存储在服务器本地文件中，不暴露在 API 响应中

### 4. 定期备份

```bash
# 手动备份用户数据
cp -r backend/data /path/to/backup/$(date +%Y%m%d)

# 或使用内置的自动更新功能（更新前自动备份）
./run.sh auto-update enable
```

---

## 六、监控与日志

### 日志文件

| 日志 | 路径 | 内容 |
|------|------|------|
| 后端日志 | `logs/backend.log` | Gunicorn 访问日志和错误日志 |
| 前端构建日志 | `logs/frontend.log` | Vite 构建输出 |
| API 详细日志 | `backend/logs/api_YYYYMMDD.log` | 应用级别日志（按天滚动） |
| 自动更新日志 | `logs/update.log` | 自动更新执行记录 |

### 查看日志

```bash
# 通过控制面板
./run.sh logs backend

# 或直接查看
tail -f logs/backend.log
tail -f backend/logs/api_$(date +%Y%m%d).log
```

### 健康检查

```bash
curl http://localhost:8000/api/health
# 返回 {"status":"ok"} 表示服务正常
```

可以配合监控工具（如 UptimeRobot、Prometheus）定期检查。

---

## 七、常见问题

### 端口被占用

```bash
# 查看端口占用
lsof -i :8000

# 或使用控制面板自动处理
./run.sh start --prod
# 会提示是否终止占用进程
```

### 构建失败

```bash
# 清理缓存后重试
./run.sh clean
./run.sh start --prod
```

### 内存不足

```bash
./run.sh optimize
./run.sh restart --prod
```

如果机器内存很小，接受脚本的 Swap 建议通常比单纯增加 workers 更稳妥。

### 服务异常重启

```bash
./run.sh restart --prod
```

### 需要回滚到旧版本

```bash
./run.sh rollback
```

---

## 八、架构说明

### 开发模式 vs 生产模式

```
开发模式 (dev):
  浏览器 -> Vite(3000) --proxy--> FastAPI(8000)
                                      ↓
                                   Uvicorn (单 worker, 热重载)

生产模式 (prod):
  浏览器 -> [Nginx(443)] -> FastAPI(8000)
                                ↓
                           Gunicorn (多 worker)
                                ↓
                           UvicornWorker × N
                                ↓
                        ┌───────┴────────┐
                        │   API 路由     │
                        │   静态文件     │
                        │  (前端构建产物) │
                        └────────────────┘
```

### 数据隔离

```
backend/data/
├── users.json          # 用户账号信息
├── sessions.json       # 会话 Token（含过期时间）
└── users/
    ├── user-001/       # 用户 A 的所有数据
    │   ├── projects/
    │   ├── characters/
    │   ├── gallery/
    │   └── ...
    └── user-002/       # 用户 B 的所有数据
        └── ...
```

每个用户的数据完全隔离，互不可见。
