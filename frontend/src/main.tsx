import React from 'react'
import ReactDOM from 'react-dom/client'
import { ConfigProvider, theme } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import App from './App'
import './styles/index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorPrimary: '#e5a84b',
          colorBgContainer: '#242424',
          colorBgElevated: '#2a2a2a',
          colorBgLayout: '#1a1a1a',
          colorBorder: '#333333',
          colorText: '#e0e0e0',
          colorTextSecondary: '#888888',
          borderRadius: 6,
          fontFamily: 'SF Pro Display, PingFang SC, Microsoft YaHei, sans-serif',
        },
        components: {
          Menu: {
            darkItemBg: '#1a1a1a',
            darkSubMenuItemBg: '#1a1a1a',
            darkItemSelectedBg: '#2a2a2a',
          },
          Layout: {
            siderBg: '#1a1a1a',
            headerBg: '#1a1a1a',
          },
          Card: {
            colorBgContainer: '#242424',
          },
          Modal: {
            contentBg: '#242424',
            headerBg: '#242424',
          }
        }
      }}
    >
      <App />
    </ConfigProvider>
  </React.StrictMode>,
)
