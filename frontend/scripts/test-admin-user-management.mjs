import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8')

const [layout, users, drawer, audit, model, app] = await Promise.all([
  read('../src/pages/Admin/AdminLayout.tsx'),
  read('../src/pages/Admin/AdminUsersPage.tsx'),
  read('../src/pages/Admin/AdminUserDrawer.tsx'),
  read('../src/pages/Admin/AdminAuditPage.tsx'),
  read('../src/pages/Admin/adminUserModel.ts'),
  read('../src/App.tsx'),
])

assert.match(app, /<AdminLayout \/>/)
assert.match(layout, /<Outlet \/>/)
assert.match(layout, /用户管理/)
assert.match(layout, /审计记录/)
assert.match(users, /adminApi\.listUsers/)
assert.match(users, /adminApi\.updatePlatformSettings/)
assert.match(users, /<Table<AdminUser>/)
assert.match(users, /scroll=\{\{ x:/)
assert.match(users, /AdminUserDrawer/)
assert.match(users, /resetPassword/)
assert.match(users, /deleteUser/)
assert.match(users, /user\.username/)
assert.match(drawer, /mode === 'create'/)
assert.match(drawer, /must_change_password/)
assert.match(drawer, /disabled=\{securityLocked\}/)
assert.match(audit, /adminApi\.listAuditLogs/)
assert.match(audit, /<Table<AdminAuditItem>/)
assert.match(model, /cannotMutateOwnSecurity/)
assert.match(model, /currentUserId === target\.id/)

console.log('admin user management contract passed')
