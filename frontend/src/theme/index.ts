import { theme, ThemeConfig } from 'antd'
import type { ThemeMode } from '../stores/themeStore'

const commonToken = {
  borderRadius: 8,
  fontFamily:
    "'SF Pro Display', 'PingFang SC', 'Microsoft YaHei', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
}

const lightTheme: ThemeConfig = {
  algorithm: theme.defaultAlgorithm,
  token: {
    ...commonToken,
    colorPrimary: '#1677ff',
    colorBgContainer: '#ffffff',
    colorBgElevated: '#ffffff',
    colorBgLayout: '#f0f2f5',
    colorBorder: '#d9d9d9',
    colorText: '#262626',
    colorTextSecondary: '#8c8c8c',
  },
  components: {
    Layout: {
      siderBg: '#ffffff',
      headerBg: '#ffffff',
      bodyBg: '#f0f2f5',
    },
    Menu: {
      itemBg: '#ffffff',
      subMenuItemBg: '#ffffff',
      itemSelectedBg: '#e6f4ff',
      itemSelectedColor: '#1677ff',
      itemHoverBg: '#f0f0f0',
    },
    Card: {
      colorBgContainer: '#ffffff',
    },
    Modal: {
      contentBg: '#ffffff',
      headerBg: '#ffffff',
    },
    Table: {
      colorBgContainer: '#ffffff',
      headerBg: '#fafafa',
    },
    Input: {
      colorBgContainer: '#ffffff',
    },
    Select: {
      colorBgContainer: '#ffffff',
    },
  },
}

const darkTheme: ThemeConfig = {
  algorithm: theme.darkAlgorithm,
  token: {
    ...commonToken,
    colorPrimary: '#e5a84b',
    colorBgContainer: '#242424',
    colorBgElevated: '#2a2a2a',
    colorBgLayout: '#1a1a1a',
    colorBorder: '#333333',
    colorText: '#e0e0e0',
    colorTextSecondary: '#888888',
  },
  components: {
    Layout: {
      siderBg: '#1a1a1a',
      headerBg: '#1a1a1a',
    },
    Menu: {
      darkItemBg: '#1a1a1a',
      darkSubMenuItemBg: '#1a1a1a',
      darkItemSelectedBg: 'rgba(229, 168, 75, 0.15)',
      darkItemSelectedColor: '#e5a84b',
    },
    Card: {
      colorBgContainer: '#242424',
    },
    Modal: {
      contentBg: '#242424',
      headerBg: '#242424',
    },
    Table: {
      colorBgContainer: '#242424',
      headerBg: '#1a1a1a',
    },
    Input: {
      colorBgContainer: '#2a2a2a',
    },
    Select: {
      colorBgContainer: '#2a2a2a',
    },
  },
}

export function getThemeConfig(mode: ThemeMode): ThemeConfig {
  return mode === 'light' ? lightTheme : darkTheme
}
