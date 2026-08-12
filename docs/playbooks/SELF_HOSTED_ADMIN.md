# 自托管管理员与用户治理

## 首位管理员

公开注册默认关闭。首位管理员在安装期间创建，也可在服务器修复场景执行：

```bash
sudo miemie admin bootstrap admin
```

密码使用隐藏输入，或仅通过受控的 `MIEMIE_ADMIN_PASSWORD` 进程环境注入。平台完成 bootstrap 后会保护最后一个有效管理员，禁止降级、停用或删除导致系统失去管理员。

## 管理页面

管理员登录后可访问“平台管理”：

- 查看、筛选、创建和编辑用户
- 修改角色、状态、显示名和强制改密状态
- 重置密码、撤销会话和删除允许删除的用户
- 开放或关闭公开注册
- 查看脱敏管理员审计日志
- 配置数据库定时备份、本地保留策略、阿里云 OSS 副本和通用 Webhook
- 手动触发备份、OSS 测试、Webhook 测试并查看执行记录

敏感凭据加密存入 PostgreSQL，API 只返回“已配置”和掩码，不返回密文或明文。

## 服务器修复命令

```bash
sudo miemie admin promote <username>
sudo miemie admin reset-password <username>
sudo miemie backups
sudo miemie logs worker-ops
```

这些命令需要 root，并复用同一 Compose 配置。不要直接编辑数据库或旧 JSON 文件。

## 权限边界

管理页面不提供：

- Docker/Compose、Git 更新、shell 或宿主文件访问
- 数据库生产恢复
- 应用版本回滚
- 永久删除安装、卷、配置或备份

上述高风险操作只能由服务器管理员通过 `miemie` CLI 执行，并受到备份、确认和发布清单门禁保护。
