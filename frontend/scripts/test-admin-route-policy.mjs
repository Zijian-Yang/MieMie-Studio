import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8')

const [
  adminApi,
  apiEntry,
  authStore,
  app,
  adminRoute,
  layout,
  login,
] = await Promise.all([
  read('../src/services/adminApi.ts'),
  read('../src/services/api.ts'),
  read('../src/stores/authStore.ts'),
  read('../src/App.tsx'),
  read('../src/components/AdminRoute.tsx'),
  read('../src/components/Layout/MainLayout.tsx'),
  read('../src/pages/Login/LoginPage.tsx'),
])

assert.match(adminApi, /export interface AdminUser/)
assert.match(adminApi, /role: 'admin' \| 'member'/)
assert.match(adminApi, /status: 'active' \| 'disabled'/)
assert.match(adminApi, /export const adminApi/)
assert.match(adminApi, /\/admin\/users/)
assert.match(adminApi, /\/bootstrap\/status/)
assert.match(apiEntry, /from '\.\/adminApi'/)
assert.match(authStore, /role: 'admin' \| 'member'/)
assert.match(authStore, /must_change_password: boolean/)
assert.match(adminRoute, /user\?\.role !== 'admin'/)
assert.match(adminRoute, /Navigate to="\/projects"/)
assert.match(app, /path="admin"/)
assert.match(app, /<AdminRoute>/)
assert.match(layout, /user\?\.role === 'admin'/)
assert.match(layout, /key: '\/admin\/users'/)
assert.match(login, /adminApi\.bootstrapStatus\(\)/)
assert.match(login, /registration_enabled/)

console.log('admin route policy contract passed')
