import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { loadConfigFromFile } from 'vite'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const configPath = path.resolve(__dirname, '..', 'vite.config.ts')

const loaded = await loadConfigFromFile(
  { command: 'build', mode: 'production' },
  configPath,
)

assert.ok(loaded?.config, 'vite config should load')

const manualChunks = loaded.config.build?.rollupOptions?.output?.manualChunks
assert.equal(typeof manualChunks, 'function', 'manualChunks should be configured')

const chunkFor = (id) => manualChunks(id)

assert.equal(
  chunkFor('/repo/frontend/node_modules/antd/es/button/index.js'),
  'antd-vendor',
  'AntD components should stay in a single chunk to avoid production init cycles',
)
assert.equal(
  chunkFor('/repo/frontend/node_modules/antd/es/form/index.js'),
  'antd-vendor',
  'AntD form internals should not be split into a separate component chunk',
)
assert.equal(
  chunkFor('/repo/frontend/node_modules/antd/lib/_util/warning.js'),
  'antd-vendor',
  'AntD utility internals should stay with AntD vendor code',
)
assert.equal(
  chunkFor('/repo/frontend/node_modules/@ant-design/icons/es/icons/PlusOutlined.js'),
  'icons-vendor',
  'Ant Design icon packages can remain in the icons vendor chunk',
)
assert.equal(
  chunkFor('/repo/frontend/node_modules/react-router/dist/index.js'),
  'react-vendor',
  'React ecosystem dependencies should stay with React vendor code',
)

