import { useCallback, useEffect, useState } from 'react'
import {
  Button,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
  theme,
} from 'antd'
import {
  DeleteOutlined,
  EditOutlined,
  KeyOutlined,
  PlusOutlined,
  ReloadOutlined,
  SearchOutlined,
  StopOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import { adminApi } from '../../services/adminApi'
import type { AdminUser, AdminUserCreateInput, AdminUserUpdateInput } from '../../services/adminApi'
import { useAuthStore } from '../../stores/authStore'
import { getApiErrorMessage } from '../../utils/apiError'
import AdminUserDrawer from './AdminUserDrawer'
import { cannotMutateOwnSecurity, roleLabel, statusLabel } from './adminUserModel'

const AdminUsersPage = () => {
  const { token } = theme.useToken()
  const [passwordForm] = Form.useForm<{ password: string }>()
  const currentUserId = useAuthStore((state) => state.user?.id || '')
  const [items, setItems] = useState<AdminUser[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [query, setQuery] = useState('')
  const [role, setRole] = useState<AdminUser['role']>()
  const [status, setStatus] = useState<AdminUser['status']>()
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [drawerMode, setDrawerMode] = useState<'create' | 'edit'>('create')
  const [target, setTarget] = useState<AdminUser | null>(null)
  const [registrationEnabled, setRegistrationEnabled] = useState(false)
  const [registrationSaving, setRegistrationSaving] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [users, settings] = await Promise.all([
        adminApi.listUsers({ page, page_size: pageSize, query: query || undefined, role, status }),
        adminApi.getPlatformSettings(),
      ])
      setItems(users.items)
      setTotal(users.total)
      setRegistrationEnabled(settings.registration_enabled)
    } catch (error) {
      message.error(getApiErrorMessage(error, '加载平台用户失败'))
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, query, role, status])

  useEffect(() => { void load() }, [load])

  const openCreate = () => {
    setTarget(null)
    setDrawerMode('create')
    setDrawerOpen(true)
  }

  const openEdit = (user: AdminUser) => {
    setTarget(user)
    setDrawerMode('edit')
    setDrawerOpen(true)
  }

  const saveUser = async (values: AdminUserCreateInput & AdminUserUpdateInput) => {
    setSaving(true)
    try {
      if (drawerMode === 'create') {
        await adminApi.createUser(values)
        message.success('平台用户已创建')
      } else if (target) {
        const update: AdminUserUpdateInput = {
          username: values.username,
          display_name: values.display_name,
          role: values.role,
          status: values.status,
        }
        await adminApi.updateUser(target.id, update)
        message.success('用户信息已更新')
      }
      setDrawerOpen(false)
      await load()
    } catch (error) {
      message.error(getApiErrorMessage(error, '保存用户失败'))
    } finally {
      setSaving(false)
    }
  }

  const toggleStatus = async (user: AdminUser) => {
    try {
      await adminApi.updateUser(user.id, {
        status: user.status === 'active' ? 'disabled' : 'active',
      })
      message.success(user.status === 'active' ? '用户已禁用' : '用户已启用')
      await load()
    } catch (error) {
      message.error(getApiErrorMessage(error, '修改用户状态失败'))
    }
  }

  const resetPassword = (user: AdminUser) => {
    passwordForm.resetFields()
    Modal.confirm({
      title: `重置 ${user.username} 的密码`,
      content: (
        <Form form={passwordForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="password" label="新临时密码" rules={[{ required: true }, { min: 8 }]}>
            <Input.Password autoComplete="new-password" />
          </Form.Item>
        </Form>
      ),
      okText: '重置并撤销会话',
      cancelText: '取消',
      onOk: async () => {
        const values = await passwordForm.validateFields()
        await adminApi.resetPassword(user.id, {
          new_password: values.password,
          must_change_password: true,
        })
        message.success('密码已重置，现有会话已撤销')
        await load()
      },
    })
  }

  const deleteUser = (user: AdminUser) => {
    let confirmation = ''
    Modal.confirm({
      title: `软删除 ${user.username}`,
      content: (
        <Space direction="vertical" style={{ width: '100%' }}>
          <Typography.Text>业务数据将保留，账户不能继续登录。</Typography.Text>
          <Input placeholder={`输入 ${user.username} 确认`} onChange={(event) => { confirmation = event.target.value }} />
        </Space>
      ),
      okText: '删除账户',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: async () => {
        if (confirmation !== user.username) throw new Error('请输入完整用户名确认')
        await adminApi.deleteUser(user.id)
        message.success('账户已软删除，业务数据已保留')
        await load()
      },
    })
  }

  const updateRegistration = async (checked: boolean) => {
    setRegistrationSaving(true)
    try {
      const result = await adminApi.updatePlatformSettings(checked)
      setRegistrationEnabled(result.registration_enabled)
      message.success(checked ? '公开注册已开启' : '公开注册已关闭')
    } catch (error) {
      message.error(getApiErrorMessage(error, '更新注册策略失败'))
    } finally {
      setRegistrationSaving(false)
    }
  }

  const columns: ColumnsType<AdminUser> = [
    {
      title: '用户', key: 'user', width: 220, fixed: 'left',
      render: (_, user) => (
        <Space direction="vertical" size={0}>
          <Typography.Text strong>{user.display_name}</Typography.Text>
          <Typography.Text type="secondary">@{user.username}</Typography.Text>
        </Space>
      ),
    },
    { title: '角色', dataIndex: 'role', width: 100, render: (value) => <Tag>{roleLabel(value)}</Tag> },
    {
      title: '状态', dataIndex: 'status', width: 100,
      render: (value) => <Tag color={value === 'active' ? 'success' : 'default'}>{statusLabel(value)}</Tag>,
    },
    {
      title: '首次改密', dataIndex: 'must_change_password', width: 100,
      render: (value) => value ? '需要' : '否',
    },
    { title: '最近登录', dataIndex: 'last_login', width: 170, render: (value) => value ? dayjs(value).format('YYYY-MM-DD HH:mm') : '从未登录' },
    { title: '更新时间', dataIndex: 'updated_at', width: 170, render: (value) => dayjs(value).format('YYYY-MM-DD HH:mm') },
    {
      title: '操作', key: 'actions', width: 188, fixed: 'right',
      render: (_, user) => {
        const selfProtected = cannotMutateOwnSecurity(currentUserId, user)
        return (
          <Space size={2}>
            <Tooltip title="编辑"><Button type="text" icon={<EditOutlined />} onClick={() => openEdit(user)} /></Tooltip>
            <Tooltip title="重置密码"><Button type="text" icon={<KeyOutlined />} onClick={() => resetPassword(user)} /></Tooltip>
            <Tooltip title={selfProtected ? '不能禁用自己的账户' : user.status === 'active' ? '禁用' : '启用'}>
              <Button type="text" disabled={selfProtected} icon={<StopOutlined />} onClick={() => toggleStatus(user)} />
            </Tooltip>
            <Tooltip title={selfProtected ? '不能删除自己的账户' : '软删除'}>
              <Button type="text" danger disabled={selfProtected} icon={<DeleteOutlined />} onClick={() => deleteUser(user)} />
            </Tooltip>
          </Space>
        )
      },
    },
  ]

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: 'flex', gap: 12, justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', marginBottom: 16 }}>
        <Space wrap>
          <Input
            allowClear prefix={<SearchOutlined />} placeholder="用户名或显示名称"
            value={query} onChange={(event) => { setQuery(event.target.value); setPage(1) }} style={{ width: 240 }}
          />
          <Select allowClear placeholder="角色" value={role} onChange={(value) => { setRole(value); setPage(1) }} style={{ width: 120 }} options={[{ value: 'admin', label: '管理员' }, { value: 'member', label: '普通用户' }]} />
          <Select allowClear placeholder="状态" value={status} onChange={(value) => { setStatus(value); setPage(1) }} style={{ width: 120 }} options={[{ value: 'active', label: '启用' }, { value: 'disabled', label: '已禁用' }]} />
          <Button icon={<ReloadOutlined />} onClick={() => void load()} />
        </Space>
        <Space wrap>
          <Typography.Text type="secondary">公开注册</Typography.Text>
          <Switch checked={registrationEnabled} loading={registrationSaving} onChange={updateRegistration} />
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>创建用户</Button>
        </Space>
      </div>
      <div style={{ border: `1px solid ${token.colorBorderSecondary}`, borderRadius: token.borderRadius }}>
        <Table<AdminUser>
          rowKey="id"
          columns={columns}
          dataSource={items}
          loading={loading}
          scroll={{ x: 1048 }}
          pagination={{
            current: page, pageSize, total, showSizeChanger: true,
            showTotal: (value) => `共 ${value} 位用户`,
            onChange: (nextPage, nextPageSize) => { setPage(nextPage); setPageSize(nextPageSize) },
          }}
        />
      </div>
      <AdminUserDrawer
        open={drawerOpen} mode={drawerMode} user={target} loading={saving}
        securityLocked={Boolean(target && cannotMutateOwnSecurity(currentUserId, target))}
        onClose={() => setDrawerOpen(false)} onSubmit={saveUser}
      />
    </div>
  )
}

export default AdminUsersPage
