# 维护指南

> 本文档面向部署和管理 MieMie-Studio 的运维人员，涵盖日常维护、更新、备份、故障排查等内容。

---

## 一、控制面板使用

MieMie-Studio 提供了交互式控制面板，运行 `./run.sh` 即可打开：

```
╔═══════════════════════════════════════════════╗
║         MieMie-Studio  控制面板              ║
╚═══════════════════════════════════════════════╝

  1)  启动服务        — 启动前后端，首次使用选这个
  2)  停止服务        — 关闭所有正在运行的服务
  3)  重启服务        — 先停止再启动，更新代码后需要重启
  4)  查看状态        — 检查服务和环境是否正常
  5)  查看日志        — 查看后端或前端运行日志
  6)  更新到最新版本  — 从 GitHub 拉取最新代码
  7)  自动更新设置    — 开启后每天自动检查并更新
  8)  版本回滚        — 更新后遇到问题？回退到上一个版本
  9)  安装/维护       — 安装依赖、清理缓存、重置环境
  v)  版本信息
  0)  退出
```

所有操作也支持命令行直接调用（适用于脚本和自动化）：

```bash
./run.sh optimize        # 检测服务器资源并应用推荐配置
./run.sh start --prod    # 启动生产模式
./run.sh stop            # 停止
./run.sh restart --prod  # 重启生产模式
./run.sh status          # 查看状态
./run.sh update          # 手动更新
```

其中：
- `./run.sh install`、`./run.sh start --prod` 和维护菜单中的“服务器优化建议”都会自动检测内核、CPU、内存与 Swap
- 脚本会推荐更稳妥的 Gunicorn workers 与前端构建内存上限，小内存 Linux 机器还会额外建议创建 Swap
- 所有推荐都需要用户确认后才会写入 `.miemie.conf`，并在应用后立即校验是否生效

---

## 二、更新流程

### 手动更新

```bash
./run.sh update
```

更新过程自动执行以下步骤：
1. 备份用户数据（`backend/data/` → `backups/pre_update_日期`）
2. 检测本地未提交的更改，询问是否暂存（`git stash`）
3. 从 GitHub 拉取最新代码
4. 检测 `requirements.txt` 或 `package.json` 是否变化，自动更新依赖
5. 提示用户重启服务

### 自动更新

```bash
# 开启自动更新（每日凌晨 3:00 执行）
./run.sh auto-update enable

# 查看状态
./run.sh auto-update status

# 关闭自动更新
./run.sh auto-update disable
```

自动更新的额外行为：
- 本地更改自动暂存（`git stash`）
- 如果服务正在运行，更新完成后自动重启
- 更新日志写入 `logs/update.log`

### 更新日志查看

```bash
# 查看最近的更新记录
tail -20 logs/update.log
```

---

## 三、备份与恢复

### 数据目录说明

```
backend/data/
├── users.json        # 用户账号（重要）
├── sessions.json     # 会话 Token
└── users/            # 所有用户的项目数据（重要）
    ├── <user-id>/
    │   ├── projects/
    │   ├── characters/
    │   ├── scenes/
    │   ├── props/
    │   ├── gallery/
    │   ├── studio/
    │   └── ...
    └── ...
```

### 手动备份

```bash
# 备份整个数据目录
cp -r backend/data /your/backup/path/miemie-data-$(date +%Y%m%d)
```

### 自动备份

每次执行更新（手动或自动）时，系统会自动备份数据到 `backups/` 目录，保留最近 10 个备份。

### 数据恢复

```bash
# 停止服务
./run.sh stop

# 恢复备份
cp -r /your/backup/path/miemie-data-20260228/* backend/data/

# 重启服务
./run.sh start --prod
```

---

## 四、版本回滚

如果更新后出现问题：

```bash
./run.sh rollback
```

回滚流程：
1. 显示最近 10 次提交记录
2. 备份当前用户数据
3. 代码回退到上一个版本
4. 用户数据保持不变（不会被回滚覆盖）

---

## 五、故障排查

### 快速诊断

```bash
# 1. 查看服务状态
./run.sh status

# 2. 查看后端日志
tail -50 logs/backend.log

# 3. 查看应用日志
tail -50 backend/logs/api_$(date +%Y%m%d).log

# 4. 健康检查
curl http://localhost:8000/api/health
```

### 常见问题及解决方案

#### 问题：页面打不开（白屏）

**可能原因**：前端构建产物缺失或过期。

```bash
# 重新构建并重启
./run.sh restart --prod
```

#### 问题：登录后提示"登录已过期"

**可能原因**：Token 过期（默认 7 天有效期），或 `sessions.json` 文件损坏。

```bash
# 用户重新登录即可。如果所有用户都无法登录：
cat backend/data/sessions.json
# 如果内容损坏，可以重置
echo '{}' > backend/data/sessions.json
# 用户重新登录会生成新 Token
```

#### 问题：API 返回 500 错误

```bash
# 查看详细错误
tail -100 backend/logs/api_$(date +%Y%m%d).log | grep -i error

# 常见原因：
# 1. 阿里云 API Key 未配置 → 进入设置页面配置
# 2. OSS 配置错误 → 检查 OSS 相关设置
# 3. 磁盘空间不足 → df -h 查看
```

#### 问题：服务启动失败

```bash
# 检查端口占用
lsof -i :8000

# 检查依赖
./run.sh status

# 如果依赖有问题，重新安装
./run.sh install

# 如果机器资源较小，先应用推荐配置再启动
./run.sh optimize
```

#### 问题：生成任务一直"处理中"

```bash
# 1. 检查 API Key 是否有效
# 2. 检查网络连接（需要访问阿里云 API）
curl -s https://dashscope.aliyuncs.com -o /dev/null -w "%{http_code}"

# 3. 查看任务相关日志
grep "工作室" backend/logs/api_$(date +%Y%m%d).log | tail -20
```

#### 问题：图片测评中 wan2.7 单元显示 `unsupported`

`unsupported` 可能是模型能力不支持，也可能是输入图预检失败。若错误类似“第 1 张输入图片无法读取”，优先排查输入图 URL。

```bash
# 1. 找出 unsupported 单元
jq -r '
  .id as $run
  | .dataset_id as $dataset
  | .cell_results[]?
  | select(.status=="unsupported")
  | [$run, $dataset, .case_id, .case_name, .model_id, (.error_message // "")]
  | @tsv
' backend/data/users/*/image_benchmark_runs/*.json

# 2. 查看某个 run/case 的输入图
RUN_ID="..."
CASE_ID="..."
jq -r --arg case "$CASE_ID" '
  .dataset_snapshot.items[]
  | select(.id==$case)
  | .name as $case_name
  | (.image_slots // [] | sort_by(.position)[])
  | [$case_name, ("图" + (.position|tostring)), (.image.name // ""), (.image.url // "")]
  | @tsv
' backend/data/users/*/image_benchmark_runs/${RUN_ID}.json

# 3. 在同一台服务器上探测 URL
curl -I -L -s "图片URL" | sed -n '1,8p'
```

判断标准：
- 正常：`HTTP 200` 且 `Content-Type` 为 `image/jpeg`、`image/png`、`image/webp` 等。
- 异常：`403/404`、`text/html`、`application/xml`、超时或 DNS 失败。

处理建议：
- 跨环境导入数据集时勾选“导入时转存图片到当前 OSS”。
- 若只是短暂网络抖动，可在测评详情页点击“重试失败/未支持任务”。
- 新版本错误会包含 URL 摘要、HTTP 状态或解码原因；旧运行记录不会自动补全错误详情，需要重试或重新运行。

#### 问题：内存不足 / 服务频繁重启

```bash
# 先让脚本根据 CPU / 内存给出推荐值
./run.sh optimize

# 再重启生产服务
./run.sh restart --prod

# 查看内存使用
free -h
```

说明：
- 小内存 Linux 服务器会被额外建议创建 Swap；脚本在用户确认后会自动创建并校验 `swapon --show`
- `./run.sh status` 会显示当前生效的 Workers 和 Node 构建内存，方便复核

---

## 六、清理与重置

通过控制面板 → 安装/维护 → 清理与重置：

| 选项 | 说明 | 影响 |
|------|------|------|
| 清理日志文件 | 删除 `logs/` 和 `backend/logs/` 下的日志 | 无影响 |
| 清理 Python 缓存 | 删除 `__pycache__` 目录 | 无影响 |
| 重置前端依赖 | 删除 `node_modules` 并重新安装 | 需要重新构建 |
| 重置后端依赖 | 删除虚拟环境并重建 | 需要重新安装 |
| 全部清理并重新安装 | 以上全部执行 | 耗时较长 |

> 以上操作均不影响用户数据（`backend/data/`）。

---

## 七、性能调优

### 资源推荐

```bash
./run.sh optimize
```

脚本会综合 CPU 核数、物理内存和当前 Swap 推荐：
- Gunicorn workers
- 前端 `vite build` 的 `Node` 内存上限
- Linux 小内存机器的额外 Swap

如果你手动覆盖，也可以这样做：

```bash
export MIEMIE_WORKERS=2
export NODE_BUILD_MEMORY_MB=2048
./run.sh restart --prod
```

### 速率限制

默认每个 IP 200 请求/分钟。如需调整，修改 `backend/app/main.py`：

```python
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
```

### 会话过期时间

默认 Token 有效期 7 天。如需调整，修改 `backend/app/services/user_service.py`：

```python
TOKEN_EXPIRE_DAYS = 7  # 修改此值
```

---

## 八、定期维护清单

### 每周

- [ ] 查看 `./run.sh status` 确认服务正常
- [ ] 查看磁盘空间 `df -h`

### 每月

- [ ] 检查自动更新日志 `tail -50 logs/update.log`
- [ ] 清理旧日志文件（控制面板 → 清理与重置）
- [ ] 手动备份用户数据到外部存储

### 每季度

- [ ] 检查系统和依赖安全更新
- [ ] 审计用户列表（如有需要）
- [ ] 检查阿里云 API 用量和配额
