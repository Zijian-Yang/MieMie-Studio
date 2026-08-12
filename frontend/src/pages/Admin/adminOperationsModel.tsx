import { Tag } from 'antd'
import type { OperationRun } from '../../services/adminApi'

export const operationTypeLabel: Record<OperationRun['operation_type'], string> = {
  backup: '数据库备份',
  oss_test: 'OSS 测试',
  webhook_test: 'Webhook 测试',
  restore_rehearsal: '恢复演练',
}

export const operationStatusLabel: Record<OperationRun['status'], string> = {
  queued: '排队中',
  running: '执行中',
  succeeded: '成功',
  failed: '失败',
}

export const operationStatusTag = (status: OperationRun['status']) => (
  <Tag color={status === 'succeeded' ? 'success' : status === 'failed' ? 'error' : status === 'running' ? 'processing' : 'default'}>
    {operationStatusLabel[status]}
  </Tag>
)

export const partStatusLabel: Record<OperationRun['local_status'], string> = {
  pending: '等待',
  succeeded: '成功',
  failed: '失败',
  skipped: '跳过',
}
