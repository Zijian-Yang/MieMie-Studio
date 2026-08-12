# 自托管更新与回滚

## 适用范围

本文只适用于 `install.sh` 安装的单机 Compose 生产服务。平台只监听本机端口；HTTPS、Cloudflare 和反向代理仍由服务器管理员维护。

## 更新

先检查远端 `pre` 是否存在可快进版本：

```bash
sudo miemie update --check
```

应用更新：

```bash
sudo miemie update --apply
```

命令会依次执行：

1. 拒绝有受版本控制改动或非快进历史的源码目录。
2. 创建并验证 PostgreSQL 自定义格式备份。
3. 使用目标 Git commit 构建不可变本地镜像标签。
4. 执行 Alembic `upgrade head`，再切换服务。
5. 验证本机健康接口和全部 worker 进程。
6. 失败时恢复旧源码 commit 与旧镜像，并保留失败发布清单。

发布清单保存在 `/var/lib/miemie/releases/`，权限为 root-only。自动应用回滚不会降级数据库 schema；失败输出会给出更新前备份路径。

## 显式回滚

回到当前发布清单记录的上一版本：

```bash
sudo miemie rollback
```

也可以传入 `/var/lib/miemie/releases/` 下的清单文件名，或本机已有镜像对应的完整 commit：

```bash
sudo miemie rollback release-YYYYMMDDTHHMMSSZ-abcdef123456.env
```

回滚前仍会创建数据库备份。回滚只切换应用版本，不自动降级 schema；若旧应用与前向 schema 不兼容，应按备份恢复手册显式恢复更新前备份。

## 故障判断

```bash
sudo miemie status
sudo miemie doctor
sudo miemie logs api
sudo miemie logs worker
```

- `stage=backup state=failed`：服务未切换，先修复 PostgreSQL/备份目录。
- `action=application_rollback`：应用已自动切回旧版本，检查发布清单与日志。
- `action=restore_pre_rollback_release`：显式回滚目标未通过健康门禁，原版本已重新启用。
- `schema=forward_only`：数据库 schema 没有降级，只有显式恢复才会替换数据。
