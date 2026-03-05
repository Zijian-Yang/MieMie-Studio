import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'fs'
import path from 'path'

function loadAllowedHosts(): string[] | undefined {
  const confPath = path.resolve(__dirname, '..', '.miemie.conf')
  try {
    const content = fs.readFileSync(confPath, 'utf-8')
    const match = content.match(/^ALLOWED_DOMAINS="(.+)"$/m)
    if (match && match[1].trim()) {
      return match[1].split(',').map(d => d.trim()).filter(Boolean)
    }
  } catch {
    // config file doesn't exist yet
  }
  return undefined
}

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    assetsDir: '_static',
  },
  server: {
    port: 3000,
    allowedHosts: loadAllowedHosts(),
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/assets': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
