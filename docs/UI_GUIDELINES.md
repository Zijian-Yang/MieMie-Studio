# UI 设计规范

> 本文档定义了淸水Studio 平台的 UI 设计规范，包括双主题系统、色彩体系、组件使用规范和最佳实践。

## 主题系统

平台支持 **日间模式** 和 **夜间模式** 双主题切换，基于 Ant Design 5 的 ConfigProvider + theme token 实现。

### 架构

```
stores/themeStore.ts     ← Zustand + persist，管理 mode: 'light' | 'dark'
theme/index.ts           ← 双主题 ThemeConfig 定义
main.tsx                 ← ConfigProvider 根据 mode 动态切换主题
各页面/组件              ← 通过 theme.useToken() 获取当前主题色值
```

### 日间模式（蓝白色系）

| Token | 色值 | 用途 |
|-------|------|------|
| colorPrimary | `#1677ff` | 主色（Ant Design 蓝） |
| colorBgContainer | `#ffffff` | 容器背景 |
| colorBgElevated | `#ffffff` | 悬浮背景 |
| colorBgLayout | `#f0f2f5` | 页面/布局背景 |
| colorBorder | `#d9d9d9` | 边框 |
| colorText | `#262626` | 主文本 |
| colorTextSecondary | `#8c8c8c` | 次要文本 |

### 夜间模式（灰金色系）

| Token | 色值 | 用途 |
|-------|------|------|
| colorPrimary | `#e5a84b` | 主色（金色） |
| colorBgContainer | `#242424` | 容器背景 |
| colorBgElevated | `#2a2a2a` | 悬浮背景 |
| colorBgLayout | `#1a1a1a` | 页面/布局背景 |
| colorBorder | `#333333` | 边框 |
| colorText | `#e0e0e0` | 主文本 |
| colorTextSecondary | `#888888` | 次要文本 |

### 主题切换

- 切换按钮位于侧边栏左下角，用户名右侧
- 使用 `SunOutlined` / `MoonOutlined` 图标
- 主题偏好持久化到 localStorage（key: `theme-storage`）

## 色彩使用规范

### 禁止硬编码颜色

所有组件中禁止使用硬编码的十六进制颜色值。必须通过 `theme.useToken()` 获取 token 值：

```tsx
// ✅ 正确
import { theme } from 'antd'

const MyComponent = () => {
  const { token } = theme.useToken()
  
  return (
    <div style={{ 
      color: token.colorText,
      background: token.colorBgContainer,
      border: `1px solid ${token.colorBorder}`,
    }}>
      <p style={{ color: token.colorTextSecondary }}>次要文本</p>
    </div>
  )
}

// ❌ 错误 - 硬编码颜色
<div style={{ color: '#e0e0e0', background: '#242424', border: '1px solid #333' }}>
```

### 常用 Token 映射

| 场景 | Token |
|------|-------|
| 主文本 | `token.colorText` |
| 次要文本 | `token.colorTextSecondary` |
| 辅助文本 | `token.colorTextTertiary` |
| 页面背景 | `token.colorBgLayout` |
| 卡片/容器背景 | `token.colorBgContainer` |
| 弹窗/悬浮背景 | `token.colorBgElevated` |
| 边框 | `token.colorBorder` |
| 次要边框 | `token.colorBorderSecondary` |
| 成功色 | `token.colorSuccess` |
| 警告色 | `token.colorWarning` |
| 错误色 | `token.colorError` |
| 主色 | `token.colorPrimary` |
| 微弱填充 | `token.colorFillQuaternary` |

### CSS 中的颜色

CSS 文件中不应包含主题相关的硬编码颜色。布局类的颜色通过以下方式处理：

1. **Ant Design 组件**：由 ConfigProvider theme 自动控制，不需要额外 CSS
2. **自定义样式**：使用 `opacity` 代替硬编码颜色（如 `opacity: 0.65` 代替 `color: #888`）
3. **不依赖颜色的样式**：布局、间距、动画等可以保留在 CSS 中

## 组件规范

### Card 组件

不要手动设置 Card 的 `background` 和 `borderColor`，这些由 ConfigProvider 统一控制：

```tsx
// ✅ 正确
<Card hoverable>内容</Card>

// ❌ 错误
<Card style={{ background: '#242424', borderColor: '#333' }}>内容</Card>
```

### 模型选择组件

所有模型选择下拉框必须显示 **"模型名称 模型ID"** 格式：

```tsx
<Select options={models.map(m => ({ label: `${m.name} ${m.id}`, value: m.id }))} />
```

### 尺寸/分辨率选择

选项必须包含方向/形状信息：

```
"1920×1080 横向" / "1080×1920 竖向" / "1280×1280 正方形"
```

### 动态参数面板

使用 `Form.useWatch` 监听表单值变化：

```tsx
const watchedModel = Form.useWatch('model', form)
{watchedModel === 'model-a' && <PanelA />}
```

## 间距与排版

- 页面内边距：`24px`
- 卡片间距：`16px` 或 `20px`
- 表单项间距：使用 Ant Design Form 默认间距
- 圆角：`8px`（全局 token `borderRadius: 8`）

## 登录页

登录页通过 CSS 类名 `theme-light` / `theme-dark` 区分主题，支持：
- 不同的渐变背景色
- 不同的毛玻璃卡片效果
- 不同的表单输入框样式
