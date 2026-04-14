# 前端开发规范

## 目录结构

```
frontend/src/
├── App.tsx              # 路由配置
├── main.tsx             # 应用入口
├── components/          # 通用组件
│   ├── Layout/          # 布局组件
│   │   └── MainLayout.tsx
│   └── ...
├── pages/               # 页面组件
│   ├── Login/           # 登录页
│   ├── Projects/        # 项目管理
│   ├── Settings/        # 设置页
│   ├── Script/          # 分镜脚本
│   ├── Characters/      # 角色管理
│   ├── Scenes/          # 场景管理
│   ├── Props/           # 道具管理
│   ├── Frames/          # 分镜首帧
│   ├── Videos/          # 视频生成
│   ├── Gallery/         # 图库
│   ├── Studio/          # 图片工作室
│   ├── VideoStudio/     # 视频工作室
│   └── ...
├── stores/              # Zustand 状态管理
│   ├── authStore.ts     # 认证状态
│   ├── themeStore.ts    # 主题状态（日间/夜间）
│   ├── projectStore.ts  # 项目状态
│   ├── generationStore.ts # 生成设置
│   └── scriptStore.ts   # 脚本状态
├── theme/               # 主题配置
│   └── index.ts         # 双主题 token 定义
├── services/            # API 服务
│   └── api.ts           # API 调用（类型定义在此）
├── styles/              # 全局样式（主题无关）
│   ├── global.css       # 动画、布局类
│   └── index.css        # Tailwind + 通用组件样式
└── types/               # TypeScript 类型
    └── index.ts
```

## 主题系统

平台支持日间/夜间双主题切换，详见 [UI_GUIDELINES.md](UI_GUIDELINES.md)。

关键要点：
- 使用 `theme.useToken()` 获取当前主题色值，禁止硬编码颜色
- 主题状态由 `themeStore.ts`（Zustand + persist）管理
- `main.tsx` 中 ConfigProvider 根据 mode 动态切换 ThemeConfig
- 登录页通过 CSS 类名 `theme-light` / `theme-dark` 区分主题
- Ant Design Card 等组件的颜色由 ConfigProvider 统一控制，不需手动设置

## 视频工作室新约定

### 能力优先的交互

视频工作室新建任务不再按“先选旧 task_type，再手写分支表单”工作，而是按：

1. 先选任务能力（`task_kind`）
2. 再选模型（`provider + model_id`）
3. 在同一任务骨架内动态显示该模型支持的参数

当前用户可见能力包括：
- 文生视频
- 首帧生视频
- 首尾帧生视频
- 参考生视频
- 视频编辑
- 局部编辑
- 视频重绘

### 参数帮助组件

视频工作室与动态参数表单统一使用 **Popover** 作为问号悬浮帮助组件，而不是短 Tooltip。

组件位置：
- `frontend/src/components/Help/HoverInfoPopover.tsx`

约定：
- 交互方式：鼠标悬浮问号触发
- 组件学名：`Popover`
- 用途：显示比 Tooltip 更长、更结构化的帮助内容

帮助内容分段固定为：
- 概览
- 含义
- 限制
- 怎么选
- 示例
- 补充说明

### 参数帮助数据来源

视频工作室参数帮助不在页面里硬编码，优先来自后端 `/api/video-studio/capabilities` 返回的 schema：
- 参数级：`parameter.help`
- 素材位：`task_profile.ui_hints.asset_help`
- Prompt：`task_profile.ui_hints.prompt_help`

前端只在少数素材位上保留兜底说明，避免后端帮助缺失时完全没有提示。

### 参数迁移提示

切模型时会做兼容参数迁移：
- 支持的参数值尽量保留
- 当前模型不支持的参数回退默认值

提示规则：
- 仅在**用户主动切换模型**时提示一次
- 新建任务首次打开不提示
- 切任务类型不提示
- 程序内部自动回退默认模型不提示

这样可以避免创建弹窗和编辑弹窗初始化时出现重复提示，影响操作体验。

## 页面组件规范

### 基本结构

```tsx
// pages/NewFeature/NewFeaturePage.tsx
import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { Card, Button, message, Modal, Form, Input, theme } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { newFeatureApi, NewFeatureItem } from '../../services/api'
import { useProjectStore } from '../../stores/projectStore'

const NewFeaturePage = () => {
  const { projectId } = useParams<{ projectId: string }>()
  const { fetchProject } = useProjectStore()

  // 状态
  const [items, setItems] = useState<NewFeatureItem[]>([])
  const [loading, setLoading] = useState(true)
  const [modalVisible, setModalVisible] = useState(false)
  const [form] = Form.useForm()

  // 加载数据
  useEffect(() => {
    if (projectId) {
      fetchProject(projectId)
      loadData()
    }
  }, [projectId, fetchProject])

  const loadData = async () => {
    if (!projectId) return
    setLoading(true)
    try {
      const res = await newFeatureApi.list(projectId)
      setItems(res.items)
    } catch (error: any) {
      message.error(error.message || '加载失败')
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async () => {
    try {
      const values = await form.validateFields()
      await newFeatureApi.create({
        project_id: projectId!,
        ...values
      })
      message.success('创建成功')
      setModalVisible(false)
      form.resetFields()
      loadData()
    } catch (error: any) {
      message.error(error.message || '创建失败')
    }
  }

  return (
    <div style={{ padding: 24 }}>
      <Card
        title="新功能"
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setModalVisible(true)}
          >
            新建
          </Button>
        }
        style={{ background: '#1a1a1a', borderColor: '#333' }}
      >
        {/* 内容 */}
      </Card>

      <Modal
        title="新建"
        open={modalVisible}
        onOk={handleCreate}
        onCancel={() => setModalVisible(false)}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default NewFeaturePage
```

### 添加路由

```tsx
// App.tsx
import NewFeaturePage from './pages/NewFeature/NewFeaturePage'

// 在路由配置中添加
<Route path="project/:projectId">
  {/* ... 现有路由 */}
  <Route path="new-feature" element={<NewFeaturePage />} />
</Route>
```

### 添加导航

```tsx
// components/Layout/MainLayout.tsx
const menuItems = [
  // ... 现有菜单项
  {
    key: 'new-feature',
    icon: <NewIcon />,
    label: '新功能',
  },
]
```

## API 服务规范

### 添加新 API

```typescript
// services/api.ts

// 1. 定义接口
export interface NewFeatureItem {
  id: string
  project_id: string
  name: string
  // ... 其他字段
  created_at: string
  updated_at: string
}

// 2. 定义 API 对象
export const newFeatureApi = {
  // 列表
  list: (projectId: string) =>
    api.get<any, { items: NewFeatureItem[] }>('/new-feature', {
      params: { project_id: projectId }
    }),

  // 获取单个
  get: (id: string) =>
    api.get<any, NewFeatureItem>(`/new-feature/${id}`),

  // 创建
  create: (data: {
    project_id: string
    name: string
    // ... 其他字段
  }) =>
    api.post<any, { item: NewFeatureItem }>('/new-feature', data),

  // 更新
  update: (id: string, data: Partial<NewFeatureItem>) =>
    api.put<any, NewFeatureItem>(`/new-feature/${id}`, data),

  // 删除
  delete: (id: string) =>
    api.delete(`/new-feature/${id}`),
}
```

## 状态管理（Zustand）

### 创建新 Store

```typescript
// stores/newStore.ts
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface NewState {
  // 状态
  setting1: string
  setting2: boolean

  // Actions
  setSetting1: (value: string) => void
  setSetting2: (value: boolean) => void
  reset: () => void
}

export const useNewStore = create<NewState>()(
  persist(
    (set) => ({
      // 默认值
      setting1: 'default',
      setting2: true,

      // Actions
      setSetting1: (value) => set({ setting1: value }),
      setSetting2: (value) => set({ setting2: value }),
      reset: () => set({ setting1: 'default', setting2: true }),
    }),
    {
      name: 'new-storage',  // localStorage key
      // 选择性持久化
      partialize: (state) => ({
        setting1: state.setting1,
        setting2: state.setting2,
      }),
    }
  )
)
```

### 使用 Store

```tsx
import { useNewStore } from '../../stores/newStore'

const Component = () => {
  const { setting1, setSetting1 } = useNewStore()

  return (
    <Input
      value={setting1}
      onChange={(e) => setSetting1(e.target.value)}
    />
  )
}
```

## 样式规范

### 深色主题

本项目使用深色主题，遵循以下配色：

```css
/* 背景色 */
--bg-primary: #141414;     /* 页面背景 */
--bg-secondary: #1a1a1a;   /* 卡片背景 */
--bg-tertiary: #242424;    /* 次级元素背景 */

/* 边框色 */
--border-color: #333;

/* 文字色 */
--text-primary: #e0e0e0;
--text-secondary: #888;

/* 主题色 */
--primary-color: #e5a84b;  /* 金色 */
--primary-hover: #f0b86b;
```

### 内联样式（推荐）

```tsx
<Card
  style={{
    background: '#1a1a1a',
    borderColor: '#333'
  }}
>
  <div style={{ color: '#888', fontSize: 12 }}>
    次级文字
  </div>
</Card>
```

### CSS Modules

```tsx
// NewFeature.module.css
.container {
  padding: 24px;
  background: #1a1a1a;
}

// NewFeaturePage.tsx
import styles from './NewFeature.module.css'

<div className={styles.container}>
```

## UI 组件规范

### 模型选择组件

所有涉及模型选择的下拉框，选项显示格式必须为 **"模型名称 模型ID"**：

```tsx
// 正确 ✓
<Select
  options={Object.values(models).map(m => ({
    label: `${m.name} ${m.id}`,  // 如: "万相2.6 文生图 wan2.6-t2i"
    value: m.id
  }))}
/>

// 错误 ✗
<Select
  options={Object.values(models).map(m => ({
    label: m.name,  // 只有名称，缺少ID
    value: m.id
  }))}
/>
```

**适用范围：**
- 图片工作室模型选择
- 视频工作室模型选择（图生视频、文生视频、参考生视频、视频重绘、局部编辑等）
- 脚本页面 LLM 模型选择
- ModelSelector 通用组件

### 尺寸/分辨率选择组件

所有尺寸或分辨率选择组件，选项必须包含 **方向/形状** 信息：

```tsx
// 图片尺寸格式
"1920×1080 横向"    // 宽 > 高
"1080×1920 竖向"    // 宽 < 高
"1280×1280 正方形"  // 宽 = 高

// 视频分辨率格式
"1920×1080 (16:9 横屏)"
"1080×1920 (9:16 竖屏)"
"1440×1440 (1:1 方形)"

// 视频质量档位
"1080P 档位"
"720P 档位"
"480P 档位"
```

**辅助函数（图片尺寸）：**

```tsx
const formatSizeLabel = (size: string | { width: number; height: number; label?: string }) => {
  if (typeof size === 'object' && size.label) {
    return size.label
  }

  let width: number, height: number
  if (typeof size === 'string') {
    const parts = size.split('*')
    width = parseInt(parts[0], 10)
    height = parseInt(parts[1], 10)
  } else {
    width = size.width
    height = size.height
  }

  const sizeStr = `${width}×${height}`
  if (width > height) return `${sizeStr} 横向`
  if (width < height) return `${sizeStr} 竖向`
  return `${sizeStr} 正方形`
}
```

### 动态参数面板

当页面包含多个模型的参数面板时，使用 `Form.useWatch` 监听模型选择变化，实现参数面板的动态切换：

```tsx
const [form] = Form.useForm()
const watchedModel = Form.useWatch('model', form)

// 根据选中的模型显示对应的参数面板
{watchedModel === 'model-a' && (
  <div>模型A参数面板</div>
)}
{watchedModel === 'model-b' && (
  <div>模型B参数面板</div>
)}
```

**注意：** 不要使用 `form.getFieldValue()` 在渲染条件中，因为它不会触发重新渲染。

## 常用模式

### 轮询任务状态

```tsx
const pollingRef = useRef<Set<string>>(new Set())
const isMountedRef = useRef(true)

useEffect(() => {
  isMountedRef.current = true
  return () => {
    isMountedRef.current = false
  }
}, [])

const startPolling = (taskId: string) => {
  if (pollingRef.current.has(taskId)) return
  pollingRef.current.add(taskId)

  const poll = async () => {
    if (!pollingRef.current.has(taskId) || !isMountedRef.current) return

    try {
      const result = await api.getStatus(taskId)

      if (isMountedRef.current) {
        // 更新状态
        setTasks(prev => prev.map(t =>
          t.id === taskId ? result.task : t
        ))
      }

      if (result.task.status === 'succeeded' || result.task.status === 'failed') {
        pollingRef.current.delete(taskId)
        message.success('完成')
      } else {
        setTimeout(poll, 5000)  // 5秒后再次查询
      }
    } catch (error) {
      pollingRef.current.delete(taskId)
      console.error('轮询错误:', error)
    }
  }

  poll()
}
```

### 批量生成控制

```tsx
import { useGenerationStore } from '../../stores/generationStore'

const { shouldStop, setStopGeneration } = useGenerationStore()
const shouldStopRef = useRef(shouldStop)

// 同步 ref
useEffect(() => {
  shouldStopRef.current = shouldStop
}, [shouldStop])

const generateAll = async () => {
  setStopGeneration(false)

  for (const item of items) {
    if (shouldStopRef.current) {
      message.info('已停止生成')
      break
    }

    await generateOne(item)
  }

  setStopGeneration(false)
}
```

### 防止卸载后更新状态

```tsx
const isMountedRef = useRef(true)

useEffect(() => {
  isMountedRef.current = true
  return () => {
    isMountedRef.current = false
  }
}, [])

const safeSetState = <T,>(setter: React.Dispatch<React.SetStateAction<T>>, value: T) => {
  if (isMountedRef.current) {
    setter(value)
  }
}

// 使用
safeSetState(setLoading, false)
```

## 任务轮询模式

图片工作室 (`StudioPage`) 和视频工作室 (`VideoStudioPage`) 使用统一的轮询模式获取后台任务进度：

### 实现模式

```typescript
const pollingRef = useRef<Set<string>>(new Set())
const isMountedRef = useRef(true)

const startPolling = useCallback((taskId: string) => {
  if (pollingRef.current.has(taskId)) return
  pollingRef.current.add(taskId)

  const poll = async () => {
    if (!pollingRef.current.has(taskId) || !isMountedRef.current) return
    const task = await api.get(taskId)
    // 更新状态...
    if (task.status === 'completed' || task.status === 'failed') {
      pollingRef.current.delete(taskId)
    } else {
      setTimeout(poll, 3000)  // 3秒间隔
    }
  }
  setTimeout(poll, 2000)
}, [])
```

### 关键要点

1. **非阻塞**：`/generate` API 立即返回 `status: "generating"`，UI 不会被阻塞
2. **多任务并发**：每个任务独立轮询，用户可同时提交多个生成任务
3. **页面恢复**：页面加载时自动恢复 `status === "generating"` 的任务轮询
4. **清理**：组件卸载时清空 `pollingRef`，停止所有轮询
5. **per-task 状态**：不再使用全局 `isGenerating` 状态，改用 `task.status` 判断单个任务状态

---

### 视频尾帧提取

视频工作室和分镜首帧页面均支持从视频中提取最后一帧：

**视频工作室（VideoStudioPage）**
- 每个生成视频结果下方显示"保存尾帧"按钮（`CameraOutlined` 图标）
- 点击后调用 `videoStudioApi.extractLastFrame`，提取尾帧并保存到图库
- 支持 loading 状态（`extractingFrames` Set 按 videoUrl 追踪）

**分镜首帧（FramesPage）**
- 编辑弹窗"首帧生成"标签页中，当上一个镜头有 `video_url` 时显示"上一视频尾帧"按钮（`VideoCameraOutlined` 图标）
- 点击后调用 `framesApi.setFromVideoLastFrame`，提取上一个镜头视频尾帧并直接设为当前镜头首帧
- 提取的图片同时保存到图库
- 按钮带 Tooltip 显示来源镜头编号

---

### 视频局部编辑 Mask 编辑器

视频工作室的 `video_edit` 任务在新建弹窗中使用独立的 `MaskEditor` 组件：

- 选中源视频后，前端先调用 `/api/video-studio/prepare-source-video`，提取首帧并返回原始分辨率、帧率、时长等元数据
- 编辑器画布按源视频原始分辨率创建，显示时再等比缩放，确保导出的 Mask 与源视频尺寸严格一致
- 当前支持 3 种工具：
  - `画笔`：自由涂抹白色编辑区域
  - `橡皮擦`：擦除已涂抹区域
  - `多边形`：鼠标逐点点击连线，按 `Enter` 闭环填充，按 `Esc` 取消当前未闭合区域
- 画笔模式提供 `8 / 16 / 32 / 64 px` 四档粗细
- 创建任务前通过 `maskEditorRef.exportMask()` 导出 PNG，并调用 `/api/video-studio/upload-mask` 上传
- 服务端会把上传的 Mask 规范化为严格黑白二值图，再传给 `wanx2.1-vace-plus`
- 编辑弹窗当前仅支持复用已有 Mask；如需重绘，需新建局部编辑任务

---

### 结果标记组件规范

所有工作室的生成结果均支持星标、红旗、对号、红叉四种用户标记：

| 标记 | key | 激活图标 | 颜色 | 用途 |
|------|-----|----------|------|------|
| 星标 | `star` | StarFilled | `#faad14`（金色） | 收藏/重要 |
| 红旗 | `flag` | FlagFilled | `#ff4d4f`（红色） | 关注/待处理 |
| 对号 | `check` | CheckOutlined | `#52c41a`（绿色） | 已确认/满意 |
| 红叉 | `cross` | CloseOutlined | `#ff4d4f`（红色） | 不满意/丢弃 |

- 未激活态使用 `Outlined` 图标 + `token.colorTextQuaternary` 颜色
- 激活态使用 `Filled` 或 `Outlined` 图标 + 对应高亮颜色
- 按钮统一为 `type="text" size="small"`，高度 22-24px
- 图片/视频工作室的标记按钮位于每个生成结果下方居中排列
- 音频工作室的标记按钮位于任务标题行右侧内联排列
- 用户可同时选择多个标记（非互斥）

---

*最后更新: 2026-03-30*
# 视频工作室补充说明

## 参数帮助
- 视频工作室中的模型参数与素材位帮助统一使用 Popover 渲染
- 帮助内容结构为：概览、含义、限制、怎么选、示例、补充说明
- `DynamicModelForm` 负责模型参数 Popover，`CapabilityCreateModal` 负责素材位和任务级帮助

## 开发者模式
- 新建任务弹窗底部提供“开发者模式”折叠面板
- 面板展示 canonical 请求体、厂商 payload 预览和验证 warning
- 已提交任务详情页底部展示 task ids、request ids、provider_payload_snapshot、provider_result_meta

## 通知与轮询
- 视频工作室任务轮询不依赖页面焦点状态，页面失焦时仍继续检查任务状态
- 当任务从处理中进入成功或失败时，可根据设置页开关触发浏览器通知
# 图片工作室更新

- 图片工作室继续沿用单页工作台，但已补齐 `task_kind` 主入口
- `wan2.7` 相关交互包含：
  - 顺序化输入图片列表
  - 交互式编辑 `bbox_list` 可视化编辑器
  - `color_palette` 结构化编辑器
  - 开发者模式 payload 预览
- 图片工作室的问号帮助统一使用 `HoverInfoPopover`
- 图片任务完成通知受设置页 `image_task_notifications_enabled` 控制
- 图片测评新增两个独立页面：
  - 数据集页：管理项目级可复用样例，支持图片槽位、交互式编辑 bbox 画框、批量导入 prompt、批量填充图片、拖拽排序和 JSON 导入导出
  - 测评页：基于数据集创建多模型矩阵测评，展示每个 case × model 的状态、输出图和详情
- 数据集页的交互式编辑任务复用图片工作室 `BBoxEditor`：
  - 每个输入图槽位下方可绘制最多 2 个框
  - 拖拽调整图片槽位顺序时，bbox 组会随对应图片一起移动
  - 保存后写入 `bbox_list`，导出数据集再导入不会丢失
- 数据集页导入 JSON 时提供“导入时转存图片到当前 OSS”开关：
  - 默认关闭，保留 JSON 中原始图片 URL
  - 开启后后端会返回 `migration_report`，前端根据成功/失败数量提示用户
- 测评页单元详情弹窗展示：
  - Effective Params
  - 自动重试次数
  - Task IDs / Request IDs
  - Canonical Request
  - Provider Payload
- 测评页的手动重试按钮覆盖 `failed` 和 `unsupported` 单元，文案为“重试失败/未支持任务”
- 视频工作室已新增 `视频续写` 能力，对应 `wan2.7-i2v`
- `wan2.7-i2v` 在视频工作室支持：
  - 图生视频：首帧图，可选驱动音频
  - 首尾帧生视频：首帧图 + 尾帧图，可选驱动音频
  - 视频续写：首段视频必填，尾帧图可选，不显示驱动音频
- `wan2.7-videoedit` 归入现有“视频编辑”，输入为 1 个待编辑视频 + 0-3 张参考图
- 相关参数 `ratio`、`audio_setting`、`first_clip` 均已进入能力 schema 和开发者模式预览
