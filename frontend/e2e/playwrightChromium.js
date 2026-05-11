import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

function getCacheRoot(platform, homeDir) {
  if (platform === 'darwin') {
    return path.join(homeDir, 'Library', 'Caches', 'ms-playwright')
  }
  if (platform === 'linux') {
    return path.join(homeDir, '.cache', 'ms-playwright')
  }
  if (platform === 'win32') {
    return path.join(homeDir, 'AppData', 'Local', 'ms-playwright')
  }
  return null
}

function getChromiumRevisionDirs(cacheRoot) {
  if (!cacheRoot || !fs.existsSync(cacheRoot)) {
    return []
  }

  return fs.readdirSync(cacheRoot, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => {
      const match = entry.name.match(/^chromium-(\d+)$/)
      return match ? { name: entry.name, revision: Number(match[1]) } : null
    })
    .filter(Boolean)
    .sort((left, right) => right.revision - left.revision)
}

function getExecutableCandidates(revisionDir, platform) {
  if (!fs.existsSync(revisionDir)) {
    return []
  }

  if (platform === 'darwin') {
    return fs.readdirSync(revisionDir, { withFileTypes: true })
      .filter((entry) => entry.isDirectory() && entry.name.startsWith('chrome-mac'))
      .map((entry) => path.join(
        revisionDir,
        entry.name,
        'Google Chrome for Testing.app',
        'Contents',
        'MacOS',
        'Google Chrome for Testing',
      ))
  }

  if (platform === 'linux') {
    return [
      path.join(revisionDir, 'chrome-linux', 'chrome'),
      path.join(revisionDir, 'chrome-linux64', 'chrome'),
    ]
  }

  if (platform === 'win32') {
    return [
      path.join(revisionDir, 'chrome-win', 'chrome.exe'),
      path.join(revisionDir, 'chrome-win64', 'chrome.exe'),
    ]
  }

  return []
}

export function resolveChromiumExecutablePath({
  env = process.env,
  platform = process.platform,
  homeDir = os.homedir(),
} = {}) {
  const explicitPath = env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH?.trim()
  if (explicitPath) {
    return explicitPath
  }

  const cacheRoot = getCacheRoot(platform, homeDir)
  const revisionDirs = getChromiumRevisionDirs(cacheRoot)

  for (const revisionDir of revisionDirs) {
    const fullRevisionDir = path.join(cacheRoot, revisionDir.name)
    const executable = getExecutableCandidates(fullRevisionDir, platform)
      .find((candidate) => fs.existsSync(candidate))
    if (executable) {
      return executable
    }
  }

  return undefined
}
