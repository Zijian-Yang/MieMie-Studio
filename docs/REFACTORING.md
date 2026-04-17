# 重构计划：统一模型配置中心

> 解决模型配置分散、前后端不一致的问题

## 一、问题背景

### 当前架构问题

```
config.py (硬编码) ──┬──► settings.py ──► SettingsPage（配置了但没用）
                    │
                    ├──► studio.py ──► StudioPage（各自获取）
                    │
                    ├──► frames.py ──► FramesPage（硬编码）
                    │
                    └──► characters.py ──► CharactersPage
```

**问题清单：**
- `config.py` 包含 6 个硬编码模型字典，与 `models_registry/` 并存
- 前端各页面各自获取模型配置，方式不一致
- FramesPage 有完全硬编码的模型列表
- 添加新模型需要同时修改多处

---

## 二、目标架构

```
┌─────────────────────────────────────────────────────────────┐
│                    ModelRegistry (后端)                      │
│  - 所有模型统一注册                                          │
│  - 单一数据源                                                │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │  GET /api/models/*     │
              │  统一 API 端点          │
              └────────────┬───────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                     前端 ModelContext                         │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              modelRegistryStore (Zustand)               │ │
│  │  - 启动时加载一次，全局缓存                              │ │
│  │  - 提供 getImageModels(), getVideoModels() 等方法       │ │
│  └────────────────────────────────────────────────────────┘ │
│                           │                                  │
│         ┌─────────────────┼─────────────────┐               │
│         ▼                 ▼                 ▼               │
│   ┌──────────┐      ┌──────────┐      ┌──────────┐         │
│   │StudioPage│      │FramesPage│      │VideosPage│  ...    │
│   └──────────┘      └──────────┘      └──────────┘         │
│                                                              │
│   统一使用 <ModelSelector> 和 <SizeSelector> 组件            │
└──────────────────────────────────────────────────────────────┘
```

---

## 三、实施步骤

### Phase 1: 后端模型迁移

1. 将 `config.py` 中的模型迁移到 `models_registry/`
2. 增强 `ModelInfo` 添加 `SizeConstraints` 和 `common_sizes`
3. 统一后端 API 端点 `/api/models/*`

### Phase 2: 前端基础设施

1. 创建 `modelRegistryStore` (Zustand)
2. 创建 `useModelRegistry` Hook
3. 增强 `ModelSelector` 组件
4. 新建 `SizeSelector` 组件

### Phase 3: 页面迁移

1. 迁移 FramesPage 使用新组件（移除硬编码）
2. 迁移 StudioPage 使用新组件
3. 迁移其他页面 (Characters, Scenes, Props, Videos)

### Phase 4: 清理

1. 简化 SettingsPage（移除无用的模型默认参数）
2. 清理后端 `config.py` 中已迁移的模型字典
3. 清理前端冗余的模型获取逻辑

---

## 四、关键文件

### 新建文件

| 文件 | 说明 |
|------|------|
| `backend/app/models_registry/image/wan26_*.py` | wan2.6 图像模型定义 |
| `backend/app/models_registry/video/wan26_*.py` | wan2.6 视频模型定义 |
| `frontend/src/stores/modelRegistryStore.ts` | 模型配置全局 Store |
| `frontend/src/hooks/useModelRegistry.ts` | 统一访问 Hook |
| `frontend/src/components/ModelConfig/SizeSelector.tsx` | 尺寸选择组件 |

### 主要修改文件

| 文件 | 变更内容 |
|------|---------|
| `backend/app/models_registry/base.py` | 添加 SizeOption, SizeConstraints |
| `backend/app/routers/models.py` | 统一 API 端点 |
| `backend/app/config.py` | 移除模型字典，保留配置类 |
| `frontend/src/pages/Frames/FramesPage.tsx` | 移除硬编码，使用新组件 |
| `frontend/src/pages/Studio/StudioPage.tsx` | 统一使用新系统 |
| `frontend/src/pages/Settings/SettingsPage.tsx` | 简化配置项 |

---

## 五、验收标准

1. **单一数据源**: 所有模型信息仅在 `models_registry` 中定义
2. **API 统一**: 前端仅通过 `/api/models/*` 获取模型信息
3. **零硬编码**: 前端无任何硬编码的模型配置
4. **组件复用**: 所有模型选择使用 `ModelSelector` 组件

---

## 六、分支

```bash
git checkout -b refactor/unified-model-registry
```

---

*创建日期: 2025-02-05*
