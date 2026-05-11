import { defineConfig } from '@playwright/test'
import { resolveChromiumExecutablePath } from './e2e/playwrightChromium.js'

const chromiumExecutablePath = resolveChromiumExecutablePath()

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  fullyParallel: false,
  expect: {
    timeout: 5_000,
  },
  use: {
    baseURL: 'http://127.0.0.1:4173',
    headless: true,
    launchOptions: chromiumExecutablePath ? { executablePath: chromiumExecutablePath } : {},
  },
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 4173',
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: true,
    timeout: 120_000,
  },
})
