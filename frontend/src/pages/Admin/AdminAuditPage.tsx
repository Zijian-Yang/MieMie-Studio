import { useCallback, useEffect, useState } from 'react'
import { Input, Table, Tag, Typography, message, theme } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import { adminApi } from '../../services/adminApi'
import type { AdminAuditItem } from '../../services/adminApi'
import { getApiErrorMessage } from '../../utils/apiError'

const AdminAuditPage = () => {
  const { token } = theme.useToken()
  const [items, setItems] = useState<AdminAuditItem[]>([])
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [total, setTotal] = useState(0)
  const [action, setAction] = useState('')
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await adminApi.listAuditLogs({ page, page_size: pageSize, action: action || undefined })
      setItems(result.items)
      setTotal(result.total)
    } catch (error) {
      message.error(getApiErrorMessage(error, '加载审计记录失败'))
    } finally {
      setLoading(false)
    }
  }, [action, page, pageSize])

  useEffect(() => { void load() }, [load])

  const columns: ColumnsType<AdminAuditItem> = [
    { title: '时间', dataIndex: 'created_at', width: 180, fixed: 'left', render: (value) => dayjs(value).format('YYYY-MM-DD HH:mm:ss') },
    { title: '动作', dataIndex: 'action', width: 230, render: (value) => <Typography.Text code>{value}</Typography.Text> },
    { title: '操作者', dataIndex: 'actor_user_id', width: 220 },
    { title: '对象', key: 'target', width: 260, render: (_, item) => `${item.target_type}:${item.target_id || '-'}` },
    { title: '请求 ID', dataIndex: 'request_id', width: 180, render: (value) => value || '-' },
    { title: '结果', dataIndex: 'result', width: 100, render: (value) => <Tag color={value === 'success' ? 'success' : 'error'}>{value}</Tag> },
    { title: '安全摘要', dataIndex: 'changes', width: 360, render: (value) => <Typography.Text>{JSON.stringify(value)}</Typography.Text> },
  ]

  return (
    <div style={{ padding: 24 }}>
      <Input
        allowClear placeholder="按动作精确筛选" value={action}
        onChange={(event) => { setAction(event.target.value); setPage(1) }}
        style={{ width: 280, marginBottom: 16 }}
      />
      <div style={{ border: `1px solid ${token.colorBorderSecondary}`, borderRadius: token.borderRadius }}>
        <Table<AdminAuditItem>
          rowKey="id" columns={columns} dataSource={items} loading={loading}
          scroll={{ x: 1530 }}
          pagination={{
            current: page, pageSize, total, showSizeChanger: true,
            showTotal: (value) => `共 ${value} 条记录`,
            onChange: (nextPage, nextPageSize) => { setPage(nextPage); setPageSize(nextPageSize) },
          }}
        />
      </div>
    </div>
  )
}

export default AdminAuditPage
