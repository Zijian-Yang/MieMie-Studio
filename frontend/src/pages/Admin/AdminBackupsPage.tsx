import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  Button,
  Checkbox,
  Col,
  Form,
  Input,
  InputNumber,
  Row,
  Space,
  Switch,
  Typography,
  message,
} from 'antd'
import { CloudUploadOutlined, DatabaseOutlined, ReloadOutlined, SaveOutlined } from '@ant-design/icons'
import { adminApi } from '../../services/adminApi'
import type {
  OperationRun,
  PlatformOperationsSettings,
  PlatformOperationsSettingsPatch,
} from '../../services/adminApi'
import { getApiErrorMessage } from '../../utils/apiError'
import AdminOperationHistory from './AdminOperationHistory'

interface BackupFormValues {
  backup_enabled: boolean
  backup_schedule: string
  backup_retention_days: number
  backup_min_keep: number
  backup_local_subdirectory: string
  backup_oss_enabled: boolean
  backup_oss_endpoint?: string
  backup_oss_bucket_name?: string
  backup_oss_prefix: string
  backup_oss_access_key_id?: string
  backup_oss_access_key_secret?: string
  clear_backup_oss_credentials?: boolean
}

const AdminBackupsPage = () => {
  const [form] = Form.useForm<BackupFormValues>()
  const ossEnabled = Form.useWatch('backup_oss_enabled', form)
  const clearCredentials = Form.useWatch('clear_backup_oss_credentials', form)
  const [settings, setSettings] = useState<PlatformOperationsSettings>()
  const [items, setItems] = useState<OperationRun[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [runningAction, setRunningAction] = useState<'backup' | 'oss' | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [nextSettings, history] = await Promise.all([
        adminApi.getPlatformSettings(),
        adminApi.listOperationRuns({ page, page_size: pageSize }),
      ])
      setSettings(nextSettings)
      form.setFieldsValue({
        backup_enabled: nextSettings.backup_enabled,
        backup_schedule: nextSettings.backup_schedule,
        backup_retention_days: nextSettings.backup_retention_days,
        backup_min_keep: nextSettings.backup_min_keep,
        backup_local_subdirectory: nextSettings.backup_local_subdirectory,
        backup_oss_enabled: nextSettings.backup_oss_enabled,
        backup_oss_endpoint: nextSettings.backup_oss_endpoint || undefined,
        backup_oss_bucket_name: nextSettings.backup_oss_bucket_name || undefined,
        backup_oss_prefix: nextSettings.backup_oss_prefix,
        backup_oss_access_key_id: undefined,
        backup_oss_access_key_secret: undefined,
        clear_backup_oss_credentials: false,
      })
      setItems(history.items)
      setTotal(history.total)
    } catch (error) {
      message.error(getApiErrorMessage(error, '加载备份设置失败'))
    } finally {
      setLoading(false)
    }
  }, [form, page, pageSize])

  useEffect(() => { void load() }, [load])

  const save = async (values: BackupFormValues) => {
    const accessKeyId = values.backup_oss_access_key_id?.trim()
    const accessKeySecret = values.backup_oss_access_key_secret?.trim()
    if (Boolean(accessKeyId) !== Boolean(accessKeySecret)) {
      message.error('替换 OSS 凭证时需要同时填写 AccessKey ID 和 Secret')
      return
    }
    setSaving(true)
    try {
      const patch: PlatformOperationsSettingsPatch = {
        backup_enabled: values.backup_enabled,
        backup_schedule: values.backup_schedule,
        backup_retention_days: values.backup_retention_days,
        backup_min_keep: values.backup_min_keep,
        backup_local_subdirectory: values.backup_local_subdirectory,
        backup_oss_enabled: values.backup_oss_enabled,
        backup_oss_endpoint: values.backup_oss_endpoint?.trim() || undefined,
        backup_oss_bucket_name: values.backup_oss_bucket_name?.trim() || undefined,
        backup_oss_prefix: values.backup_oss_prefix,
      }
      if (values.clear_backup_oss_credentials) {
        patch.clear_backup_oss_credentials = true
      } else if (accessKeyId && accessKeySecret) {
        patch.backup_oss_access_key_id = accessKeyId
        patch.backup_oss_access_key_secret = accessKeySecret
      }
      await adminApi.patchPlatformSettings(patch)
      message.success('备份设置已保存')
      await load()
    } catch (error) {
      message.error(getApiErrorMessage(error, '保存备份设置失败'))
    } finally {
      setSaving(false)
    }
  }

  const runBackup = async () => {
    setRunningAction('backup')
    try {
      await adminApi.createBackup()
      message.success('备份任务已进入队列')
      await load()
    } catch (error) {
      message.error(getApiErrorMessage(error, '创建备份任务失败'))
    } finally {
      setRunningAction(null)
    }
  }

  const testOss = async () => {
    setRunningAction('oss')
    try {
      await adminApi.testBackupOss()
      message.success('OSS 测试已进入队列')
      await load()
    } catch (error) {
      message.error(getApiErrorMessage(error, '创建 OSS 测试失败'))
    } finally {
      setRunningAction(null)
    }
  }

  return (
    <div style={{ padding: 24, maxWidth: 1200 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', flexWrap: 'wrap', marginBottom: 20 }}>
        <Space direction="vertical" size={0}>
          <Typography.Title level={5} style={{ margin: 0 }}>数据库备份</Typography.Title>
          <Typography.Text type="secondary">每天按 Asia/Shanghai 时区执行，恢复操作仅允许在服务器命令行完成。</Typography.Text>
        </Space>
        <Space wrap>
          <Button icon={<ReloadOutlined />} loading={loading} onClick={() => void load()} />
          <Button icon={<CloudUploadOutlined />} loading={runningAction === 'oss'} onClick={() => void testOss()}>测试 OSS</Button>
          <Button type="primary" icon={<DatabaseOutlined />} loading={runningAction === 'backup'} onClick={() => void runBackup()}>立即备份</Button>
        </Space>
      </div>

      <Form<BackupFormValues> form={form} layout="vertical" onFinish={save} disabled={loading}>
        <Typography.Title level={5}>计划与保留</Typography.Title>
        <Row gutter={16}>
          <Col xs={24} md={8}><Form.Item name="backup_enabled" label="启用每日备份" valuePropName="checked"><Switch /></Form.Item></Col>
          <Col xs={24} md={8}><Form.Item name="backup_schedule" label="执行时间" rules={[{ required: true }, { pattern: /^([01]\d|2[0-3]):[0-5]\d$/, message: '请输入 HH:MM' }]}><Input placeholder="03:00" /></Form.Item></Col>
          <Col xs={24} md={8}><Form.Item name="backup_local_subdirectory" label="本地子目录" rules={[{ required: true }]}><Input prefix="/var/lib/miemie/backups/" /></Form.Item></Col>
          <Col xs={24} md={8}><Form.Item name="backup_retention_days" label="保留天数" rules={[{ required: true }]}><InputNumber min={1} max={3650} style={{ width: '100%' }} /></Form.Item></Col>
          <Col xs={24} md={8}><Form.Item name="backup_min_keep" label="最少保留份数" dependencies={['backup_retention_days']} rules={[{ required: true }, ({ getFieldValue }) => ({ validator: (_, value) => value <= getFieldValue('backup_retention_days') ? Promise.resolve() : Promise.reject(new Error('不能超过保留天数')) })]}><InputNumber min={1} max={365} style={{ width: '100%' }} /></Form.Item></Col>
        </Row>

        <Typography.Title level={5}>阿里云 OSS 异地副本</Typography.Title>
        <Row gutter={16}>
          <Col xs={24} md={8}><Form.Item name="backup_oss_enabled" label="启用 OSS 上传" valuePropName="checked"><Switch /></Form.Item></Col>
          <Col xs={24} md={8}><Form.Item name="backup_oss_endpoint" label="Endpoint" rules={[{ required: ossEnabled, message: '请输入 HTTPS Endpoint' }, { type: 'url' }]}><Input placeholder="https://oss-cn-hangzhou.aliyuncs.com" /></Form.Item></Col>
          <Col xs={24} md={8}><Form.Item name="backup_oss_bucket_name" label="Bucket" rules={[{ required: ossEnabled }]}><Input /></Form.Item></Col>
          <Col xs={24} md={8}><Form.Item name="backup_oss_prefix" label="对象前缀" rules={[{ required: true }]}><Input placeholder="miemie/backups" /></Form.Item></Col>
        </Row>

        <Alert
          type={settings?.backup_oss_credentials_configured ? 'success' : 'info'}
          showIcon
          message={settings?.backup_oss_credentials_configured ? `凭证已配置：${settings.backup_oss_access_key_id_masked}` : '尚未配置平台备份 OSS 凭证'}
          description="下方输入留空会保留现有凭证；平台不会把已保存的明文凭证返回浏览器。"
          style={{ marginBottom: 16 }}
        />
        <Row gutter={16}>
          <Col xs={24} md={8}><Form.Item name="backup_oss_access_key_id" label="替换 AccessKey ID"><Input autoComplete="off" disabled={clearCredentials} /></Form.Item></Col>
          <Col xs={24} md={8}><Form.Item name="backup_oss_access_key_secret" label="替换 AccessKey Secret"><Input.Password autoComplete="new-password" disabled={clearCredentials} /></Form.Item></Col>
          <Col xs={24} md={8}><Form.Item name="clear_backup_oss_credentials" valuePropName="checked" label="凭证操作"><Checkbox>清除已保存凭证</Checkbox></Form.Item></Col>
        </Row>
        <Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={saving}>保存备份设置</Button>
      </Form>

      <Space direction="vertical" size={12} style={{ display: 'flex', marginTop: 32 }}>
        <Typography.Title level={5} style={{ margin: 0 }}>运行历史</Typography.Title>
        <AdminOperationHistory
          items={items} loading={loading} total={total} page={page} pageSize={pageSize}
          onPageChange={(nextPage, nextPageSize) => { setPage(nextPage); setPageSize(nextPageSize) }}
        />
      </Space>
    </div>
  )
}

export default AdminBackupsPage
