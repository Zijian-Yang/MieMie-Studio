import { useEffect } from 'react'
import { Button, Drawer, Form, Input, Select, Switch } from 'antd'
import type {
  AdminUser,
  AdminUserCreateInput,
  AdminUserUpdateInput,
} from '../../services/adminApi'

type FormValues = AdminUserCreateInput & AdminUserUpdateInput

interface AdminUserDrawerProps {
  open: boolean
  mode: 'create' | 'edit'
  user?: AdminUser | null
  loading: boolean
  securityLocked?: boolean
  onClose: () => void
  onSubmit: (values: FormValues) => Promise<void>
}

const AdminUserDrawer = ({
  open,
  mode,
  user,
  loading,
  securityLocked = false,
  onClose,
  onSubmit,
}: AdminUserDrawerProps) => {
  const [form] = Form.useForm<FormValues>()

  useEffect(() => {
    if (!open) return
    if (mode === 'edit' && user) {
      form.setFieldsValue({
        username: user.username,
        display_name: user.display_name,
        role: user.role,
        status: user.status,
      })
    } else {
      form.resetFields()
      form.setFieldsValue({ role: 'member', must_change_password: true })
    }
  }, [form, mode, open, user])

  return (
    <Drawer
      title={mode === 'create' ? '创建平台用户' : `编辑 ${user?.username || ''}`}
      open={open}
      onClose={onClose}
      width={440}
      destroyOnClose
      extra={
        <Button type="primary" loading={loading} onClick={() => form.submit()}>
          保存
        </Button>
      }
    >
      <Form form={form} layout="vertical" onFinish={onSubmit} requiredMark="optional">
        <Form.Item
          name="username"
          label="用户名"
          rules={[{ required: true, message: '请输入用户名' }, { max: 64 }]}
        >
          <Input autoComplete="off" />
        </Form.Item>
        <Form.Item name="display_name" label="显示名称" rules={[{ max: 128 }]}>
          <Input />
        </Form.Item>
        {mode === 'create' && (
          <Form.Item
            name="password"
            label="临时密码"
            rules={[{ required: true, message: '请输入临时密码' }, { min: 8 }]}
          >
            <Input.Password autoComplete="new-password" />
          </Form.Item>
        )}
        <Form.Item name="role" label="角色" rules={[{ required: true }]}>
          <Select disabled={securityLocked} options={[{ value: 'member', label: '普通用户' }, { value: 'admin', label: '管理员' }]} />
        </Form.Item>
        {mode === 'edit' && (
          <Form.Item name="status" label="状态" rules={[{ required: true }]}>
            <Select disabled={securityLocked} options={[{ value: 'active', label: '启用' }, { value: 'disabled', label: '已禁用' }]} />
          </Form.Item>
        )}
        {mode === 'create' && (
          <Form.Item name="must_change_password" label="首次登录修改密码" valuePropName="checked">
            <Switch />
          </Form.Item>
        )}
      </Form>
    </Drawer>
  )
}

export default AdminUserDrawer
