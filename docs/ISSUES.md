# 已知问题与待优化项

> 本文档记录已发现的问题、技术债务和优化建议。
> 修复后请更新状态并记录解决方案。

## 🔴 待修复 Bug

### 1. ~~OSS 测试连接误报权限错误~~

**状态**: ✅ 已修复 (2024-12-24)

**问题**: 设置页 OSS 配置即使正确，点击测试连接仍显示"访问被拒绝，请检查 AccessKey 权限"，但实际上传功能正常。

**原因**: 测试方法使用了 `bucket.get_bucket_info()`，需要更高的 Bucket 管理权限。

**解决方案**: 改为上传并删除一个测试文件（`.connection_test`），只需要对象读写权限即可。

---

### 2. ~~StorageService 方法不一致~~

**状态**: ✅ 已修复 (2025-12-30)

**问题**: 部分存储方法使用文件锁 `_write_json_with_lock`，部分直接使用 `open()`，并发安全性不一致。

**解决方案**: 统一所有保存方法使用 `_write_json_with_lock` 和 `self._lock`。

---

### 3. ~~批量生成中断后状态残留~~

**状态**: ✅ 已修复 (2025-12-30)

**问题**: 批量生成被中断后，`generatingItems` Set 中的项目 ID 可能未被清除，导致无法重新生成。

**解决方案**: 在 `resetGeneration` 时同时清空 `generatingItems`。

---

## 🟡 性能优化

### 1. 文件遍历效率

**问题**: `get_xxx_by_project()` 方法遍历目录下所有 JSON 文件，项目多时效率低。

**当前代码**:
```python
for file_path in self.dir.glob("*.json"):
    with open(file_path) as f:
        data = json.load(f)
        if data.get("project_id") == project_id:
            items.append(...)
```

**建议**:
1. 建立索引文件（如 `index.json`）按 project_id 索引
2. 或改用 SQLite 数据库
3. 或使用目录结构 `projects/{project_id}/items/`

---

### 2. 图片 Base64 转换内存占用

**问题**: `wan2.6-image` 参考图处理时，将图片转为 Base64 会占用较多内存。

**位置**: `services/dashscope/text_to_image.py` - `validate_and_resize_reference_image`

**建议**: 考虑使用临时文件或流式处理大图片。

---

### 3. 前端状态持久化

**问题**: 部分 Zustand store 持久化了不必要的运行时状态。

**建议**: 检查各 store 的 `partialize` 配置，确保只持久化用户设置。

---

## 🟢 功能改进建议

### 1. 添加任务队列

**现状**: 多个生成任务同时发起，可能导致 API 限流或资源竞争。

**建议**: 实现任务队列，限制并发数量，支持任务优先级。

---

### 2. 添加生成历史

**现状**: 生成的图片/视频只保存最新结果，历史版本丢失。

**建议**: 为每个资源保存生成历史，支持回滚。

---

### 3. 错误重试机制

**现状**: API 调用失败后需要手动重试。

**建议**: 实现自动重试，支持配置重试次数和间隔。

---

### 4. 批量导入/导出

**现状**: 项目数据无法批量导入导出。

**建议**: 支持项目 ZIP 打包导出和导入。

---

## 🔧 代码质量

### 1. 日志 print 语句

**状态**: ✅ 已修复 (2026-03-28)

**问题**: 服务层大量使用 `print()` 输出日志，虽然会重定向到日志文件，但不够规范。

**解决方案**: `oss.py` 和 `studio.py` 中约 25 处 `print()` 替换为 `logging.getLogger(__name__)` 的 `logger.info/warning/error`。

---

### 2. 前端类型不完整

**问题**: `api.ts` 中部分接口使用 `any` 类型。

**建议**: 补充完整的 TypeScript 类型定义。

---

### 3. 配置重复定义

**状态**: 🔄 重构中

**问题**: 模型配置在 `config.py` 和前端 `api.ts` 中都有定义，需要同步维护。

**解决方案**: 实施统一模型配置中心重构，详见 [REFACTORING.md](./REFACTORING.md)

---

### 4. ~~CSS 变量系统不统一~~

**状态**: ✅ 已修复 (2026-02-05)

**问题**: 存在 3 套 CSS 变量系统（`--studio-*`、`--color-*`、Tailwind studio 颜色），互相冲突，且大量页面内联硬编码暗色值。

**解决方案**: 
- 移除 `--studio-*` 和 `--color-*` CSS 变量，改由 Ant Design ConfigProvider theme token 统一驱动
- 全站 22 个页面 + 5 个组件使用 `theme.useToken()` 替代硬编码颜色
- 实现日间/夜间双主题系统
- 详见 [UI_GUIDELINES.md](./UI_GUIDELINES.md)

---

### 5. ~~缺少单元测试~~

**状态**: ✅ 已修复 (2026-03-28)

**问题**: 项目缺少自动化测试。

**解决方案**: 新增 `backend/tests/test_fixes.py` 和 `backend/tests/test_video_studio_vace.py`，当前共 28 个 pytest 测试用例，覆盖认证流程（注册/登录/改密/登出）、bcrypt 密码哈希、CORS 配置、纯 ASGI 中间件、项目级联删除、原子文件写入、单例线程安全、登录/注册限流，以及 VACE 视频工作室流程。运行方式: `./run.sh test` 或 `cd backend && python -m pytest tests/ -v`。

---

## 📝 文档待补充

- [ ] 部署文档
- [ ] 用户使用手册
- [ ] API 变更日志
- [ ] 贡献指南

---

## 更新记录

| 日期 | 更新内容 |
|------|----------|
| 2026-03-28 | 标记 print→logger 和单元测试为已修复 |
| 2026-02-05 | 新增 CSS 变量统一问题（已修复） |
| 2025-12-30 | 创建文档，记录初始问题 |

---

*如发现新问题，请在此文档中添加并标注状态。*
