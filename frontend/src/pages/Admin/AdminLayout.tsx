import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Space, Tabs, Typography, theme } from 'antd'
import {
  AlertOutlined,
  AuditOutlined,
  DashboardOutlined,
  DatabaseOutlined,
  TeamOutlined,
} from '@ant-design/icons'

const AdminLayout = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const { token } = theme.useToken()
  const selected = [
    '/admin/overview',
    '/admin/users',
    '/admin/backups',
    '/admin/alerts',
    '/admin/audit',
  ].find((path) => location.pathname.startsWith(path)) || '/admin/overview'

  return (
    <div style={{ minHeight: '100vh', background: token.colorBgLayout }}>
      <div
        style={{
          minHeight: 64,
          padding: '14px 24px',
          borderBottom: `1px solid ${token.colorBorderSecondary}`,
          background: token.colorBgContainer,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 16,
          flexWrap: 'wrap',
        }}
      >
        <Space direction="vertical" size={0}>
          <Typography.Title level={4} style={{ margin: 0 }}>平台管理</Typography.Title>
          <Typography.Text type="secondary">平台状态、用户权限、备份与告警</Typography.Text>
        </Space>
      </div>
      <div style={{ padding: '0 24px', background: token.colorBgContainer }}>
        <Tabs
          activeKey={selected}
          onChange={navigate}
          tabBarStyle={{ margin: 0 }}
          items={[
            { key: '/admin/overview', label: <Space size={6}><DashboardOutlined />概览</Space> },
            { key: '/admin/users', label: <Space size={6}><TeamOutlined />用户</Space> },
            { key: '/admin/backups', label: <Space size={6}><DatabaseOutlined />备份</Space> },
            { key: '/admin/alerts', label: <Space size={6}><AlertOutlined />告警</Space> },
            { key: '/admin/audit', label: <Space size={6}><AuditOutlined />审计</Space> },
          ]}
        />
      </div>
      <Outlet />
    </div>
  )
}

export default AdminLayout
