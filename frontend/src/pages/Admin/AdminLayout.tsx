import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Segmented, Space, Typography, theme } from 'antd'
import { AuditOutlined, TeamOutlined } from '@ant-design/icons'

const AdminLayout = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const { token } = theme.useToken()
  const selected = location.pathname.includes('/audit') ? '/admin/audit' : '/admin/users'

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
          <Typography.Text type="secondary">用户权限、注册策略与操作审计</Typography.Text>
        </Space>
        <Segmented
          value={selected}
          onChange={(value) => navigate(String(value))}
          options={[
            { value: '/admin/users', label: '用户管理', icon: <TeamOutlined /> },
            { value: '/admin/audit', label: '审计记录', icon: <AuditOutlined /> },
          ]}
        />
      </div>
      <Outlet />
    </div>
  )
}

export default AdminLayout
