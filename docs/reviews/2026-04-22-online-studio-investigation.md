# 线上工作室卡顿与生成无响应调查记录

## 摘要

- **时间**：2026-04-22 10:47–11:02 CST
- **环境**：Microsoft Edge、本机浏览器、生产站 `https://studio.miemie.co/`
- **账号**：`guest` 测试账号，未记录 token、密码或其它敏感凭据
- **项目**：`76ff3a16-2b57-4e6c-9647-0f671e8ef99a`，页面为“图片工作室”
- **结论**：生产站入口与健康检查正常，但图片工作室相关业务接口在浏览器 Console 中出现大量 `520/522/524`；“开始生成”按钮点击后没有及时进入 `generating`，与用户反馈的“点了无效/卡住”一致。

## 浏览器复现

### 页面切换

1. 打开生产站并进入项目“重庆非拍不可影视传媒有限公司”。
2. 在“图库 → 图片工作室 → 文本库 → 图片工作室”之间切换。
3. 观察到图片工作室进入时有全页转圈；本次短测中约数秒恢复，但现象与用户反馈的“切换页面时转圈”一致。

### 生成按钮

1. 打开图片工作室任务 `4`，状态为“待生成”。
2. 点击“开始生成”按钮。
3. 再用键盘 `Space` 与 `Enter` 激活已聚焦按钮。
4. 页面仍停留在“任务详情 - 4 待生成”，按钮仍显示“开始生成”，没有立即出现“已开始生成”、`generating` 状态或轮询反馈。

## DevTools 证据

Edge DevTools Console 中出现约 50 条请求失败，核心模式如下：

- `POST https://studio.miemie.co/api/studio/preview-payload` 多次失败，状态码包含 `520`、`524`。
- `POST https://studio.miemie.co/api/studio/9414dd44-f5f5-4ab2-a184-5d7dd2c570ec/generate` 失败，状态码 `520`。
- `GET https://studio.miemie.co/api/studio/586f3855-8bd5-406a-8f3c-b47d32cbc982` 失败，状态码 `522`。

这些状态码由生产站前面的 Cloudflare 层返回，说明浏览器请求已经发出，但业务接口与上游/源站之间出现异常或超时；这比单纯前端点击事件失效更接近当前主因。

## 连通性抽查

```bash
curl -I -L -s https://studio.miemie.co/
curl -s -o /tmp/miemie_health.txt -w 'status=%{http_code} time_total=%{time_total}\n' https://studio.miemie.co/api/health
```

结果：

- 首页 `HTTP/2 200`，响应头显示 `server: cloudflare`。
- `/api/health` 返回 `status=200 time_total=1.086210`。
- 健康检查响应：`{"status":"ok","git_commit":"0fc3cbe1b4d3b91ddcb9382c2a19ca2f9f93be70","run_mode":"prod","serve_frontend":true,"started_at":"2026-04-22T02:20:51Z"}`。

这表明生产站基础入口可达，问题集中在图片工作室的业务接口路径，不是整站完全不可用。

## 代码路径观察

### 前端

- `frontend/src/pages/Studio/StudioPage.tsx` 的 `requestPayloadPreview()` 在弹窗打开时无条件触发，并且监听大量表单字段变化后 350ms debounce 再请求 `/studio/preview-payload`。
- `frontend/src/services/api.ts` 全局 axios timeout 为 6 分钟；业务接口长时间 pending 时，用户会感觉“点击无效/一直转圈”。
- `handleGenerateExistingTask()` 只有在 `studioApi.generate()` 返回后才把任务状态更新为 `generating` 并启动轮询；如果 `/generate` 被 Cloudflare/源站超时挡住，前端不会提前给出“已提交”的即时反馈。

### 后端

- `backend/app/routers/studio.py` 中 `/preview-payload` 会调用 `_inspect_and_validate_wan27_images()`。
- `/studio/{task_id}/generate` 注释写明“立即返回，后台执行”，但返回前同样会对 `wan2.7-image` 参考图调用 `_inspect_and_validate_wan27_images()`。
- `_inspect_and_validate_wan27_images()` 内部会逐张调用 `inspect_remote_image()`。
- `backend/app/services/remote_media_validation.py` 的 `inspect_remote_image()` 会完整下载远程图片，timeout 为 `httpx.Timeout(20.0, read=120.0)`；外层还会按 `0.5s`、`1.5s` 重试。

## 初步根因假设

当前证据最支持以下链路：

1. 图片工作室弹窗打开或表单变化后，前端频繁调用 `/api/studio/preview-payload`。
2. 预览接口在请求路径中同步下载并解析参考图片。
3. 线上环境下载参考图或访问源站资源较慢时，接口在 Cloudflare/源站链路中超时或异常，表现为 `520/522/524`。
4. “开始生成”接口同样在返回前做同步图片探测，违反“立即返回”的用户体验预期；失败或超时期间前端保持原状态，用户看到的就是“点击生成无效/卡住”。

## 建议修复方向

1. **预览接口轻量化**：`/preview-payload` 只做 payload 组装，不在默认路径完整下载参考图；图片元数据校验改为短 timeout、缓存或开发者模式手动触发。
2. **生成接口真正异步**：`/generate` 先落库为 `generating` 并立即返回，把图片探测、供应商请求和失败写回任务状态都放进后台任务。
3. **前端请求取消**：为 payload 预览增加 AbortController 或请求序号，只保留最后一次请求，避免旧请求堆积和旧错误覆盖新状态。
4. **按钮即时反馈**：生成按钮点击后立即进入提交中状态；接口失败时展示明确错误，包括 `520/522/524` 与“可能为源站超时”提示。
5. **生产日志核对**：在 2026-04-22 03:00 UTC 左右检查源站日志、Cloudflare 日志、应用日志，重点查 `/api/studio/preview-payload`、`/api/studio/*/generate` 的耗时、异常栈与并发量。

## 当前状态

- 已在本地 Edge 复现“开始生成”点击后无即时反馈。
- 已确认生产站基础健康检查正常。
- 已确认 Console 中存在与症状吻合的工作室 API `520/522/524`。
- 尚未直接读取生产源站日志；根因仍需结合源站日志最终确认。

## 代码修复进展（2026-04-22）

- 已新增修复规格：`docs/specs/2026-04-studio-prod-latency-hardening.md`
- 已完成前端修复：
  - 开发者模式未展开时，不再自动请求 `/api/studio/preview-payload`
  - 预览请求增加取消/去重
  - 生成按钮增加“提交中”即时反馈
  - 生成按钮新增同步防重入保护，降低极快双击导致的重复提交概率
- 已完成后端修复：
  - `/api/studio/{task_id}/generate` 不再在返回前同步探测 wan2.7 远程参考图
  - 远程图探测、bbox 归一化与最终 payload 构建移入后台任务
  - 同一任务重复调用 `/generate` 时，后端直接返回当前 `generating` 任务，不重复调度后台任务
- 本地验证结果：
  - `venv/bin/pytest backend/tests/test_studio_capabilities.py -v` → `33 passed`
  - `cd frontend && npm run typecheck` → 通过
