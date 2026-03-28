import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'fs'
import path from 'path'

function loadMiemieConf(): Record<string, string> {
  const confPath = path.resolve(__dirname, '..', '.miemie.conf')
  const result: Record<string, string> = {}
  try {
    const content = fs.readFileSync(confPath, 'utf-8')
    for (const line of content.split('\n')) {
      const match = line.match(/^(\w+)="(.+)"$/)
      if (match) {
        result[match[1]] = match[2]
      }
    }
  } catch {
    // config file doesn't exist yet
  }
  return result
}

const conf = loadMiemieConf()

function loadAllowedHosts(): string[] | undefined {
  const domains = conf.ALLOWED_DOMAINS
  if (domains && domains.trim()) {
    return domains.split(',').map(d => d.trim()).filter(Boolean)
  }
  return undefined
}

const frontendPort = Number(process.env.MIEMIE_FRONTEND_PORT || conf.FRONTEND_PORT) || 3000
const backendPort = Number(process.env.MIEMIE_BACKEND_PORT || conf.BACKEND_PORT) || 8000
const backendTarget = `http://localhost:${backendPort}`

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    assetsDir: '_static',
  },
  server: {
    port: frontendPort,
    allowedHosts: loadAllowedHosts(),
    proxy: {
      '/api': {
        target: backendTarget,
        changeOrigin: true
      },
      '/assets': {
        target: backendTarget,
        changeOrigin: true
      }
    }
  }
})
