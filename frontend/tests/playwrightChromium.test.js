import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

import { resolveChromiumExecutablePath } from '../e2e/playwrightChromium.js'

test('优先使用显式 PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH', () => {
  const executablePath = '/tmp/custom-chromium'

  const resolved = resolveChromiumExecutablePath({
    env: {
      PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH: executablePath,
    },
    platform: 'darwin',
    homeDir: '/Users/tester',
  })

  assert.equal(resolved, executablePath)
})

test('macOS 下自动发现 ms-playwright 缓存中的最新 Chromium', () => {
  const tempHome = fs.mkdtempSync(path.join(os.tmpdir(), 'miemie-playwright-home-'))
  const cacheRoot = path.join(tempHome, 'Library', 'Caches', 'ms-playwright')
  const olderExecutable = path.join(
    cacheRoot,
    'chromium-1208',
    'chrome-mac-arm64',
    'Google Chrome for Testing.app',
    'Contents',
    'MacOS',
    'Google Chrome for Testing',
  )
  const newerExecutable = path.join(
    cacheRoot,
    'chromium-1217',
    'chrome-mac-arm64',
    'Google Chrome for Testing.app',
    'Contents',
    'MacOS',
    'Google Chrome for Testing',
  )

  fs.mkdirSync(path.dirname(olderExecutable), { recursive: true })
  fs.writeFileSync(olderExecutable, '')
  fs.mkdirSync(path.dirname(newerExecutable), { recursive: true })
  fs.writeFileSync(newerExecutable, '')

  const resolved = resolveChromiumExecutablePath({
    env: {},
    platform: 'darwin',
    homeDir: tempHome,
  })

  assert.equal(resolved, newerExecutable)

  fs.rmSync(tempHome, { recursive: true, force: true })
})
