# HappyHorse 视频工作室接入计划

> 注：本计划记录首批 T2V/I2V 接入；4 模型系列扩展以 `2026-04-27-happyhorse-series-video-studio-integration.md` 为后续超集计划。

## 目标

- 在视频工作室新增 `happyhorse-1.0-t2v` 与 `happyhorse-1.0-i2v`
- 保持默认模型不变
- 复用现有 DashScope/Wan 密钥与 OSS 链路
- 完成文档、测试与验证要求

## 已确认决策

- 使用独立 `provider=happyhorse`
- 设置页新增独立 `happyhorse_key_profile` 字段
- 不进入 legacy 视频模型常量和通用模型注册接口
- 以 capability schema + adapter 作为唯一接入入口

## 执行清单

- [x] 补 HappyHorse 失败测试（provider、capability、payload、validate、preview）
- [x] 新增 HappyHorse adapter，并接入 provider 推断与分发
- [x] 为 `happyhorse` 提供独立 `happyhorse_key_profile`，并复用现有测试/生产 DashScope Key 池
- [x] 扩展 `/api/video-studio/capabilities` 暴露 HH 两模型与结构化帮助
- [x] 设置页可单独选择 HappyHorse 使用测试 Key 或生产 Key
- [x] 提交阶段失败时保留 `provider_result_meta.submit_error.raw_response`
- [x] 补 spec、验证手册、README 入口与变更日志
- [ ] 完成真实模型 smoke（受白名单与账号激活状态影响，需人工执行）

## 验证记录

- 已执行：`/Users/zane/Project/Miemie-studio/venv/bin/pytest -o cache_dir=/tmp/pytest-hh-cache backend/tests/test_video_studio_capabilities.py backend/tests/test_provider_key_and_manifest.py -q`
- 当前结果：`35 passed`
- 追加验证：提交阶段失败元信息回归测试通过

## 手工收尾

- 确认 HappyHorse 白名单与百炼控制台登录激活状态
- 运行 1 条 T2V + 1 条 I2V smoke
- 记录失败路径与厂商错误文案
