import React, { useEffect } from 'react'
import ReactDOM from 'react-dom/client'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import App from './App'
import { useThemeStore } from './stores/themeStore'
import { getThemeConfig } from './theme'
import './styles/index.css'
import './styles/global.css'

const savedTheme = JSON.parse(localStorage.getItem('theme-storage') || '{}')?.state?.mode || 'dark'
document.documentElement.setAttribute('data-theme', savedTheme)

function Root() {
  const mode = useThemeStore((s) => s.mode)
  const themeConfig = getThemeConfig(mode)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', mode)
    document.body.style.background = mode === 'dark' ? '#1a1a1a' : '#f0f2f5'
    document.body.style.color = mode === 'dark' ? '#e0e0e0' : '#262626'
  }, [mode])

  return (
    <ConfigProvider locale={zhCN} theme={themeConfig}>
      <App />
    </ConfigProvider>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>,
)
