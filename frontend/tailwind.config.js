/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // DaVinci Resolve 风格深色主题
        'studio': {
          'bg': '#1a1a1a',
          'panel': '#242424',
          'border': '#333333',
          'hover': '#2a2a2a',
          'active': '#3a3a3a',
          'text': '#e0e0e0',
          'text-secondary': '#888888',
          'accent': '#e5a84b',
          'accent-hover': '#f0b85c',
          'success': '#52c41a',
          'error': '#ff4d4f',
          'warning': '#faad14',
        }
      },
      fontFamily: {
        'sans': ['SF Pro Display', 'PingFang SC', 'Microsoft YaHei', 'sans-serif'],
      }
    },
  },
  plugins: [],
  corePlugins: {
    preflight: false, // 避免与 Ant Design 冲突
  }
}

