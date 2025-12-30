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
│   ├── projectStore.ts  # 项目状态
│   ├── generationStore.ts # 生成设置
│   └── scriptStore.ts   # 脚本状态
├── services/            # API 服务
│   └── api.ts           # 🔧 API 调用（类型定义在此！）
├── styles/              # 全局样式
│   ├── global.css
│   └── index.css
└── types/               # TypeScript 类型
    └── index.ts
```

## 页面组件规范

### 基本结构

```tsx
// pages/NewFeature/NewFeaturePage.tsx
import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { Card, Button, message, Modal, Form, Input } from 'antd'
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

---

*最后更新: 2025-12-30*

