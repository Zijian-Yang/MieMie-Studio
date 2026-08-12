import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8')

const [layout, overview, backups, alerts, history, api, app] = await Promise.all([
  read('../src/pages/Admin/AdminLayout.tsx'),
  read('../src/pages/Admin/AdminOverviewPage.tsx'),
  read('../src/pages/Admin/AdminBackupsPage.tsx'),
  read('../src/pages/Admin/AdminAlertsPage.tsx'),
  read('../src/pages/Admin/AdminOperationHistory.tsx'),
  read('../src/services/adminApi.ts'),
  read('../src/App.tsx'),
])

for (const label of ['概览', '用户', '备份', '告警', '审计']) assert.match(layout, new RegExp(label))
assert.match(app, /AdminOverviewPage/)
assert.match(app, /AdminBackupsPage/)
assert.match(app, /AdminAlertsPage/)
assert.match(overview, /adminApi\.getPlatformHealth/)
assert.match(overview, /PostgreSQL/)
assert.match(overview, /最近运维任务/)
assert.match(backups, /adminApi\.createBackup/)
assert.match(backups, /adminApi\.testBackupOss/)
assert.match(backups, /clear_backup_oss_credentials/)
assert.match(backups, /backup_oss_access_key_id\?\.trim/)
assert.doesNotMatch(backups, /setFieldsValue\([\s\S]*backup_oss_access_key_secret:\s*settings/)
assert.match(alerts, /adminApi\.testWebhook/)
assert.match(alerts, /clear_webhook_url/)
assert.match(alerts, /webhook_url:\s*undefined/)
assert.match(history, /<Table<OperationRun>/)
assert.match(history, /scroll=\{\{ x:/)
assert.match(api, /patchPlatformSettings/)
assert.match(api, /createBackup/)
assert.match(api, /testBackupOss/)
assert.match(api, /testWebhook/)
assert.match(api, /listOperationRuns/)

console.log('admin operations contract passed')
