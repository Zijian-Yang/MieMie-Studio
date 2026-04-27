# HappyHorse 系列视频工作室接入执行计划

## 目标

- 将 HappyHorse 文生、图生、参考生、视频编辑 4 个模型接入视频工作室。
- 保持默认模型不变，复用现有 DashScope Key、异步任务、轮询、OSS 和开发者模式链路。

## 执行清单

- [x] 读取 4 份新官方镜像文档，提炼平台能力边界
- [x] 更新平台 spec、执行计划、变更日志与验证手册
- [x] 先补失败测试：capability、payload、validate、preview、Key 保存刷新
- [x] 扩展 HappyHorse adapter 支持 `text_to_video`、`image_to_video`、`reference_to_video`、`video_edit_global`
- [x] 扩展 capability schema 暴露 4 个 HappyHorse 模型与结构化帮助
- [x] 补前端 capability 类型/展示兼容
- [x] 跑后端 pytest、前端 typecheck、`git diff --check`
- [x] 重启本地平台并记录运行状态

## 验证记录

- 已执行红灯验证：`venv/bin/pytest backend/tests/test_video_studio_capabilities.py backend/tests/test_provider_key_and_manifest.py -q`
- 当前红灯结果：`10 failed, 38 passed`
- 失败集中在新增 `happyhorse-1.0-r2v`、`happyhorse-1.0-video-edit` 的 capability、payload 和校验 helper，符合预期。
- 已执行绿灯验证：`venv/bin/pytest backend/tests/test_video_studio_capabilities.py backend/tests/test_provider_key_and_manifest.py -q`
- 当前绿灯结果：`48 passed`
- 已执行前端验证：`cd frontend && npm run typecheck`
- 当前结果：退出码 0
- 已执行前端回归：`cd frontend && npm run test:video-capability-limits`
- 当前结果：退出码 0
- 已执行空白检查：`git diff --check`
- 当前结果：退出码 0
- 已重启本地平台：后端 `http://127.0.0.1:8000/api/health` 返回 `status=ok`，前端 `http://127.0.0.1:3001/` 返回 200。

## 手工收尾

- 白名单不是本轮阻塞项。
- 有可用权限时，分别提交 4 条 HappyHorse smoke，并核对开发者模式、OSS URL、`request_id`、`usage`、失败错误展示。
