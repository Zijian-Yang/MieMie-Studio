import { Table, Tag, Typography, theme } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import type { OperationRun } from '../../services/adminApi'
import {
  operationStatusTag,
  operationTypeLabel,
  partStatusLabel,
} from './adminOperationsModel'

interface Props {
  items: OperationRun[]
  loading: boolean
  total: number
  page: number
  pageSize: number
  onPageChange: (page: number, pageSize: number) => void
}

const AdminOperationHistory = ({ items, loading, total, page, pageSize, onPageChange }: Props) => {
  const { token } = theme.useToken()
  const columns: ColumnsType<OperationRun> = [
    {
      title: '时间', dataIndex: 'created_at', width: 170, fixed: 'left',
      render: (value) => dayjs(value).format('YYYY-MM-DD HH:mm:ss'),
    },
    { title: '类型', dataIndex: 'operation_type', width: 130, render: (value) => operationTypeLabel[value as OperationRun['operation_type']] },
    { title: '状态', dataIndex: 'status', width: 100, render: (value) => operationStatusTag(value) },
    { title: '本地', dataIndex: 'local_status', width: 80, render: (value) => <Tag>{partStatusLabel[value as OperationRun['local_status']]}</Tag> },
    { title: 'OSS', dataIndex: 'oss_status', width: 80, render: (value) => <Tag>{partStatusLabel[value as OperationRun['oss_status']]}</Tag> },
    { title: '触发', dataIndex: 'trigger_source', width: 90, render: (value) => value === 'scheduled' ? '定时' : value === 'manual' ? '手动' : '命令行' },
    { title: '大小', dataIndex: 'size_bytes', width: 110, render: (value) => typeof value === 'number' ? `${(value / 1024 / 1024).toFixed(2)} MB` : '-' },
    { title: '错误分类', dataIndex: 'error_category', width: 190, render: (value) => value ? <Typography.Text code>{value}</Typography.Text> : '-' },
    { title: '运行 ID', dataIndex: 'id', width: 260, render: (value) => <Typography.Text copyable>{value}</Typography.Text> },
  ]

  return (
    <div style={{ border: `1px solid ${token.colorBorderSecondary}`, borderRadius: token.borderRadius }}>
      <Table<OperationRun>
        rowKey="id"
        columns={columns}
        dataSource={items}
        loading={loading}
        scroll={{ x: 1210 }}
        locale={{ emptyText: '暂无运行记录' }}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          showTotal: (value) => `共 ${value} 条记录`,
          onChange: onPageChange,
        }}
      />
    </div>
  )
}

export default AdminOperationHistory
