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
import { ReloadOutlined, SaveOutlined, SendOutlined } from '@ant-design/icons'
import { adminApi } from '../../services/adminApi'
import type { OperationRun, PlatformOperationsSettings, PlatformOperationsSettingsPatch } from '../../services/adminApi'
import { getApiErrorMessage } from '../../utils/apiError'
import AdminOperationHistory from './AdminOperationHistory'

interface AlertFormValues {
  webhook_enabled: boolean
  webhook_url?: string
  clear_webhook_url?: boolean
  webhook_timeout_seconds: number
  webhook_retry_count: number
  webhook_alert_on_warning: boolean
}

const AdminAlertsPage = () => {
  const [form] = Form.useForm<AlertFormValues>()
  const clearUrl = Form.useWatch('clear_webhook_url', form)
  const [settings, setSettings] = useState<PlatformOperationsSettings>()
  const [items, setItems] = useState<OperationRun[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [nextSettings, history] = await Promise.all([
        adminApi.getPlatformSettings(),
        adminApi.listOperationRuns({ page, page_size: pageSize, operation_type: 'webhook_test' }),
      ])
      setSettings(nextSettings)
      form.setFieldsValue({
        webhook_enabled: nextSettings.webhook_enabled,
        webhook_url: undefined,
        clear_webhook_url: false,
        webhook_timeout_seconds: nextSettings.webhook_timeout_seconds,
        webhook_retry_count: nextSettings.webhook_retry_count,
        webhook_alert_on_warning: nextSettings.webhook_alert_on_warning,
      })
      setItems(history.items)
      setTotal(history.total)
    } catch (error) {
      message.error(getApiErrorMessage(error, '加载告警设置失败'))
    } finally {
      setLoading(false)
    }
  }, [form, page, pageSize])

  useEffect(() => { void load() }, [load])

  const save = async (values: AlertFormValues) => {
    setSaving(true)
    try {
      const patch: PlatformOperationsSettingsPatch = {
        webhook_enabled: values.webhook_enabled,
        webhook_timeout_seconds: values.webhook_timeout_seconds,
        webhook_retry_count: values.webhook_retry_count,
        webhook_alert_on_warning: values.webhook_alert_on_warning,
      }
      if (values.clear_webhook_url) patch.clear_webhook_url = true
      else if (values.webhook_url?.trim()) patch.webhook_url = values.webhook_url.trim()
      await adminApi.patchPlatformSettings(patch)
      message.success('Webhook 告警设置已保存')
      await load()
    } catch (error) {
      message.error(getApiErrorMessage(error, '保存告警设置失败'))
    } finally {
      setSaving(false)
    }
  }

  const testWebhook = async () => {
    setTesting(true)
    try {
      await adminApi.testWebhook()
      message.success('Webhook 测试已进入队列')
      await load()
    } catch (error) {
      message.error(getApiErrorMessage(error, '创建 Webhook 测试失败'))
    } finally {
      setTesting(false)
    }
  }

  return (
    <div style={{ padding: 24, maxWidth: 1200 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', flexWrap: 'wrap', marginBottom: 20 }}>
        <Space direction="vertical" size={0}>
          <Typography.Title level={5} style={{ margin: 0 }}>通用 Webhook</Typography.Title>
          <Typography.Text type="secondary">告警仅包含平台事件元数据，不包含用户内容、密钥或私有资源地址。</Typography.Text>
        </Space>
        <Space>
          <Button icon={<ReloadOutlined />} loading={loading} onClick={() => void load()} />
          <Button type="primary" icon={<SendOutlined />} loading={testing} onClick={() => void testWebhook()}>发送测试</Button>
        </Space>
      </div>

      <Form<AlertFormValues> form={form} layout="vertical" onFinish={save} disabled={loading}>
        <Row gutter={16}>
          <Col xs={24} md={8}><Form.Item name="webhook_enabled" label="启用 Webhook" valuePropName="checked"><Switch /></Form.Item></Col>
          <Col xs={24} md={8}><Form.Item name="webhook_timeout_seconds" label="超时秒数" rules={[{ required: true }]}><InputNumber min={1} max={30} style={{ width: '100%' }} /></Form.Item></Col>
          <Col xs={24} md={8}><Form.Item name="webhook_retry_count" label="失败重试次数" rules={[{ required: true }]}><InputNumber min={0} max={3} style={{ width: '100%' }} /></Form.Item></Col>
          <Col xs={24} md={8}><Form.Item name="webhook_alert_on_warning" label="警告级事件" valuePropName="checked"><Switch /></Form.Item></Col>
        </Row>

        <Alert
          type={settings?.webhook_configured ? 'success' : 'info'}
          showIcon
          message={settings?.webhook_configured ? `Webhook 已配置：${settings.webhook_url_masked}` : '尚未配置 Webhook 地址'}
          description="新地址留空会保留现有地址；已保存地址不会以明文返回浏览器。"
          style={{ marginBottom: 16 }}
        />
        <Row gutter={16}>
          <Col xs={24} md={16}><Form.Item name="webhook_url" label="替换 Webhook HTTPS 地址" rules={[{ type: 'url' }]}><Input.Password autoComplete="new-password" disabled={clearUrl} /></Form.Item></Col>
          <Col xs={24} md={8}><Form.Item name="clear_webhook_url" valuePropName="checked" label="地址操作"><Checkbox>清除已保存地址</Checkbox></Form.Item></Col>
        </Row>
        <Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={saving}>保存告警设置</Button>
      </Form>

      <Space direction="vertical" size={12} style={{ display: 'flex', marginTop: 32 }}>
        <Typography.Title level={5} style={{ margin: 0 }}>测试历史</Typography.Title>
        <AdminOperationHistory
          items={items} loading={loading} total={total} page={page} pageSize={pageSize}
          onPageChange={(nextPage, nextPageSize) => { setPage(nextPage); setPageSize(nextPageSize) }}
        />
      </Space>
    </div>
  )
}

export default AdminAlertsPage
