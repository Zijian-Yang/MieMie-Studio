import { useCallback, useEffect, useState } from 'react'
import { Badge, Button, Descriptions, Space, Table, Typography, message, theme } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import { adminApi } from '../../services/adminApi'
import type { OperationRun, PlatformHealth, PlatformOperationsSettings } from '../../services/adminApi'
import { getApiErrorMessage } from '../../utils/apiError'
import { operationStatusTag, operationTypeLabel } from './adminOperationsModel'

const AdminOverviewPage = () => {
  const { token } = theme.useToken()
  const [health, setHealth] = useState<PlatformHealth>()
  const [settings, setSettings] = useState<PlatformOperationsSettings>()
  const [runs, setRuns] = useState<OperationRun[]>([])
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [nextHealth, nextSettings, history] = await Promise.all([
        adminApi.getPlatformHealth(),
        adminApi.getPlatformSettings(),
        adminApi.listOperationRuns({ page: 1, page_size: 5 }),
      ])
      setHealth(nextHealth)
      setSettings(nextSettings)
      setRuns(history.items)
    } catch (error) {
      message.error(getApiErrorMessage(error, '加载平台概览失败'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const columns: ColumnsType<OperationRun> = [
    { title: '时间', dataIndex: 'created_at', width: 180, render: (value) => dayjs(value).format('YYYY-MM-DD HH:mm:ss') },
    { title: '类型', dataIndex: 'operation_type', width: 130, render: (value) => operationTypeLabel[value as OperationRun['operation_type']] },
    { title: '状态', dataIndex: 'status', width: 100, render: (value) => operationStatusTag(value) },
    { title: '错误分类', dataIndex: 'error_category', render: (value) => value || '-' },
  ]

  return (
    <div style={{ padding: 24, maxWidth: 1200 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <Typography.Title level={5} style={{ margin: 0 }}>运行状态</Typography.Title>
        <Button icon={<ReloadOutlined />} loading={loading} onClick={() => void load()} />
      </div>
      <Descriptions bordered size="small" column={{ xs: 1, sm: 2, lg: 3 }}>
        <Descriptions.Item label="API"><Badge status={health?.status === 'ok' ? 'success' : 'error'} text={health?.status === 'ok' ? '正常' : '异常'} /></Descriptions.Item>
        <Descriptions.Item label="PostgreSQL"><Badge status={health?.database?.ok ? 'success' : 'error'} text={health?.database?.ok ? '正常' : '异常'} /></Descriptions.Item>
        <Descriptions.Item label="Redis"><Badge status={health?.redis.ok ? 'success' : 'error'} text={health?.redis.ok ? '正常' : '异常'} /></Descriptions.Item>
        <Descriptions.Item label="运行模式">{health?.run_mode || '-'}</Descriptions.Item>
        <Descriptions.Item label="版本"><Typography.Text copyable>{health?.git_commit || '-'}</Typography.Text></Descriptions.Item>
        <Descriptions.Item label="启动时间">{health?.started_at ? dayjs(health.started_at).format('YYYY-MM-DD HH:mm:ss') : '-'}</Descriptions.Item>
        <Descriptions.Item label="定时备份"><Badge status={settings?.backup_enabled ? 'processing' : 'default'} text={settings?.backup_enabled ? `每天 ${settings.backup_schedule}` : '未启用'} /></Descriptions.Item>
        <Descriptions.Item label="OSS 异地副本"><Badge status={settings?.backup_oss_enabled ? 'processing' : 'default'} text={settings?.backup_oss_enabled ? '已启用' : '未启用'} /></Descriptions.Item>
        <Descriptions.Item label="Webhook"><Badge status={settings?.webhook_enabled ? 'processing' : 'default'} text={settings?.webhook_enabled ? '已启用' : '未启用'} /></Descriptions.Item>
      </Descriptions>

      <Space direction="vertical" size={12} style={{ display: 'flex', marginTop: 24 }}>
        <Typography.Title level={5} style={{ margin: 0 }}>最近运维任务</Typography.Title>
        <div style={{ border: `1px solid ${token.colorBorderSecondary}`, borderRadius: token.borderRadius }}>
          <Table<OperationRun>
            rowKey="id" columns={columns} dataSource={runs} loading={loading}
            pagination={false} scroll={{ x: 660 }} locale={{ emptyText: '暂无运行记录' }}
          />
        </div>
      </Space>
    </div>
  )
}

export default AdminOverviewPage
