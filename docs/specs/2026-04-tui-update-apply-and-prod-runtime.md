# TUI 更新即生效与服务器生产化

## 标题

让 `./run.sh` 的 TUI 更新流程在服务器上默认“更新并生效”，并让运行模式、版本与前端服务方式可观测。

## 背景

- 真实用户路径主要是通过 `./run.sh` 的 TUI 菜单进行启动、重启和更新
- 旧版“更新到最新版本”只负责拉代码，是否重启、是否切到正确模式依赖人工操作
- 自动更新/手动更新都可能出现“代码已 pull，但运行中的进程没有真正切到新版本”的错觉
- 线上长期运行目标是生产模式；开发模式仅适合本地调试

## 目标

- TUI 中“更新到最新版本”默认更新并应用到当前运行服务
- 更新后自动校验运行中的进程是否已经切到最新 commit / mode
- 状态页可直接看到默认模式、实际模式、当前运行 commit 和前端服务方式
- 服务器长期偏向 `prod`，避免更新或自动任务意外回落到 `dev`
- `wan2.7` 图片与图片测评链路中的 OSS 转存失败具备可排障日志

## 非目标

- 不改动业务生成逻辑本身的成功/失败判定
- 不引入新的进程管理器（仍沿用 `screen + gunicorn/uvicorn`）
- 不替代现有反向代理/CDN 方案，只补充推荐配置

## 用户流 / 角色

- 运维在服务器执行 `./run.sh`，通过 TUI 选择“更新到最新版本”
- 脚本备份数据、拉取代码、刷新依赖，并在服务原本运行时按原模式自动重启
- 重启后脚本请求 `GET /api/health`，确认 `git_commit / run_mode / serve_frontend`
- 运维在 `./run.sh status` 中核对默认模式、实际模式、当前提交和前端方式

## 状态与数据契约

- `.miemie.conf` 新增 `DEFAULT_RUN_MODE`，作为持久化默认模式
- 后端健康检查新增运行时元信息：
  - `git_commit`
  - `run_mode`
  - `serve_frontend`
  - `started_at`
- 更新逻辑在内存中保留：
  - 更新前 commit
  - 更新前实际运行模式
  - 是否原本处于运行状态

## API / Schema / 表单约束

- `GET /api/health` 保持 `status: "ok"` 兼容，同时附带运行时元信息
- `./run.sh update --apply` 表示“拉取代码并立即应用”；TUI 更新入口默认采用该行为
- `./run.sh update` 继续保留“只拉代码不重启”的命令行能力

## 实现边界

- `run.sh` 负责：
  - 默认模式持久化
  - 实际运行模式识别
  - 更新后的依赖刷新、重启与健康校验
  - TUI 文案与状态页展示
- 后端负责：
  - 暴露运行时健康信息
  - OSS 转存失败日志
- 文档负责：
  - 服务器推荐长期使用 `prod`
  - Cloudflare -> Nginx/Caddy -> 127.0.0.1:8000 的部署建议

## 可观测性

- `logs/update.log` 记录更新后的健康校验结果
- `./run.sh status` 展示默认模式、实际模式、当前提交、前端方式
- `wan2.7` 图片工作室与图片测评在 OSS 转存失败时记录模型、项目、request/task id、原始 URL host 与失败原因

## 验收标准

- 自动化验证：
  - `GET /api/health` 返回 200，且包含运行时元信息字段
- 手工验证：
  - 以 `prod` 启动后，通过 TUI 更新，更新后仍是 `prod`
  - 更新多个提交时仍能识别 `requirements.txt` / `frontend/package.json` / lockfile 变化
  - `./run.sh status` 显示的运行中 commit 与健康检查返回一致
- 回归关注点：
  - `./run.sh update` 命令行仍可只拉代码
  - 图片测评结果在 OSS 转存失败时仍能留下明确日志

## 文档更新

- `docs/MAINTENANCE.md`
- `docs/DEPLOYMENT.md`
- `docs/CHANGELOG.md`
