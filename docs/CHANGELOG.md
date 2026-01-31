# 变更日志

> 记录平台的重要变更、新功能和 Bug 修复。
> 格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/)。

## [Unreleased]

### 变更 (Changed)
- 创建开发文档目录 (`docs/`)

### 修复 (Fixed)
- StorageService 所有保存方法统一使用文件锁，确保并发安全
- 批量生成重置时同时清空 `generatingItems` 状态

---

## [1.0.0] - 2025-12-30

### 新增 (Added)

#### 核心功能
- 多用户支持：用户注册、登录、数据隔离
- 项目管理：创建、编辑、删除项目
- 分镜脚本：AI 生成/优化、手动编辑、多版本对比
- 角色/场景/道具管理：从脚本提取、图片生成、多版本选择
- 分镜首帧生成：基于分镜自动生成首帧图
- 视频生成：首帧转视频、批量生成

#### 工作室
- 图片工作室：灵活的图片生成任务管理
- 视频工作室：图生视频、视频生视频任务管理

#### 媒体库
- 图库：图片上传、URL 导入、分类管理
- 音频库：音频上传管理
- 视频库：视频上传管理
- 文本库：文本片段管理

#### 模型支持
- 文生图：wan2.6-t2i, wan2.5-t2i-preview, wan2.6-image
- 图生图：wan2.5-i2i-preview, qwen-image-edit-plus
- 图生视频：wan2.5-i2v-preview, wan2.6-i2v-preview, wanx2.1-i2v-preview
- 视频生视频：wan2.6-r2v
- LLM：qwen3-max, qwen-plus-latest

#### 集成
- 阿里云 OSS 图片/视频持久化存储
- DashScope API 集成（文生图、图生视频、LLM）

### 变更 (Changed)
- 平台名称从 "AI 视频工作室" 改为 "MieMie-Studio"
- 模型显示名称标准化为 "x生x <model code>" 格式

### 修复 (Fixed)
- OSS 测试连接误报权限错误
- 批量生成首帧按钮不响应
- wan2.6-r2v 前端只能选择 2 个参考视频（已改为 3 个）
- 图片工作室文生图任务无法设置输出尺寸

---

## 版本规范

### 版本号格式

`MAJOR.MINOR.PATCH`

- MAJOR: 不兼容的 API 变更
- MINOR: 向后兼容的新功能
- PATCH: 向后兼容的 Bug 修复

### 变更类型

- **Added**: 新功能
- **Changed**: 现有功能变更
- **Deprecated**: 即将移除的功能
- **Removed**: 已移除的功能
- **Fixed**: Bug 修复
- **Security**: 安全相关修复

### 示例条目

```markdown
## [1.1.0] - 2025-01-15

### Added
- 新增 xxx 功能 (#issue-number)
- 支持 xxx 模型

### Changed
- 优化 xxx 性能
- 调整 xxx 默认值

### Fixed
- 修复 xxx 问题 (#issue-number)
```

---

*请在每次发布时更新此文档。*

