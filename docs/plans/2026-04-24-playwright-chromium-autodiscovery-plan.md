# Playwright Chromium 自动发现实现计划

> 本计划用于把前端 E2E 的 Chromium 路径发现逻辑收口到共享 helper，避免每次手工传 `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH`。

## 目标

- 在 `frontend` 测试基础设施中优先使用显式环境变量。
- 当环境变量未提供时，自动发现本机 `ms-playwright` 缓存中的 Chromium 可执行文件。
- `playwright.config.ts` 与 smoke 测试复用同一套解析逻辑。

## 步骤

- [x] 新增失败用例，覆盖环境变量优先与 macOS 缓存自动发现。
- [x] 运行用例，确认当前实现为红灯。
- [x] 新增共享 helper，封装 Chromium 路径解析逻辑。
- [x] 更新 `frontend/playwright.config.ts` 复用 helper。
- [x] 更新 `frontend/e2e/smoke.spec.ts` 复用 helper。
- [x] 运行 Node 用例、`npm run test:e2e` 与前端静态检查。
- [x] 更新 README / review 文档中的 E2E 使用说明与验证记录。
