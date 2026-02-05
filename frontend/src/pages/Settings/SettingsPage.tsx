import { useEffect, useState } from 'react'
import { 
  Card, Form, Input, Button, Select, message, Spin, Alert, Divider, 
  Switch, InputNumber, Slider, Tooltip, Space, Row, Col 
} from 'antd'
import { 
  SaveOutlined, EyeInvisibleOutlined, EyeOutlined, 
  CheckCircleOutlined, CloseCircleOutlined, QuestionCircleOutlined,
  InfoCircleOutlined, CloudUploadOutlined, ApiOutlined
} from '@ant-design/icons'
import { settingsApi, ConfigResponse } from '../../services/api'

const SettingsPage = () => {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testingOSS, setTestingOSS] = useState(false)
  const [config, setConfig] = useState<ConfigResponse | null>(null)
  const [selectedLLMModel, setSelectedLLMModel] = useState<string>('')
  const [enableThinking, setEnableThinking] = useState(false)

  useEffect(() => {
    fetchSettings()
  }, [])

  const fetchSettings = async () => {
    try {
      const data = await settingsApi.getSettings()
      setConfig(data)
      setSelectedLLMModel(data.llm.model)
      setEnableThinking(data.llm.enable_thinking)
      
      form.setFieldsValue({
        api_region: data.api_region,
        // 文本模型配置
        llm_model: data.llm.model,
        llm_max_tokens: data.llm.max_tokens,
        llm_top_p: data.llm.top_p,
        llm_temperature: data.llm.temperature,
        llm_enable_thinking: data.llm.enable_thinking,
        llm_thinking_budget: data.llm.thinking_budget,
        llm_result_format: data.llm.result_format,
        llm_enable_search: data.llm.enable_search,
        // OSS 配置
        oss_enabled: data.oss.enabled,
        oss_bucket_name: data.oss.bucket_name,
        oss_endpoint: data.oss.endpoint,
        oss_prefix: data.oss.prefix,
      })
    } catch (error) {
      message.error('加载设置失败')
    } finally {
      setLoading(false)
    }
  }

  const handleSaveApiKey = async () => {
    const apiKey = form.getFieldValue('api_key')
    if (!apiKey) {
      message.warning('请输入 API Key')
      return
    }
    
    setSaving(true)
    try {
      await settingsApi.setApiKey(apiKey)
      message.success('API Key 已保存')
      form.setFieldValue('api_key', '')
      fetchSettings()
    } catch (error) {
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleSaveSettings = async () => {
    setSaving(true)
    try {
      const values = form.getFieldsValue()
      
      await settingsApi.updateSettings({
        api_region: values.api_region,
        llm: {
          model: values.llm_model,
          max_tokens: values.llm_max_tokens,
          top_p: values.llm_top_p,
          temperature: values.llm_temperature,
          enable_thinking: values.llm_enable_thinking,
          thinking_budget: values.llm_thinking_budget,
          result_format: values.llm_result_format,
          enable_search: values.llm_enable_search,
        },
        oss: {
          enabled: values.oss_enabled,
          access_key_id: values.oss_access_key_id || undefined,
          access_key_secret: values.oss_access_key_secret || undefined,
          bucket_name: values.oss_bucket_name,
          endpoint: values.oss_endpoint,
          prefix: values.oss_prefix,
        },
      })
      message.success('设置已保存')
      fetchSettings()
    } catch (error) {
      if (error instanceof Error) {
        message.error(error.message)
      } else {
        message.error('保存失败')
      }
    } finally {
      setSaving(false)
    }
  }

  // 检查当前选中的模型是否支持深度思考
  const currentModelSupportsThinking = () => {
    if (!config || !selectedLLMModel) return false
    const modelInfo = config.available_llm_models[selectedLLMModel]
    return modelInfo?.supports_thinking ?? false
  }

  // 获取当前模型的最大输出 token 数
  const getCurrentModelMaxTokens = () => {
    if (!config || !selectedLLMModel) return 32768
    const modelInfo = config.available_llm_models[selectedLLMModel]
    return modelInfo?.max_output_tokens ?? 32768
  }

  // 当模型改变时更新相关状态
  const handleModelChange = (value: string) => {
    setSelectedLLMModel(value)
    
    // 如果新模型不支持思考，关闭思考模式
    const modelInfo = config?.available_llm_models[value]
    if (!modelInfo?.supports_thinking) {
      form.setFieldValue('llm_enable_thinking', false)
      setEnableThinking(false)
    }
    
    // 调整 max_tokens 不超过模型最大值
    const currentMaxTokens = form.getFieldValue('llm_max_tokens')
    const modelMax = modelInfo?.max_output_tokens ?? 32768
    if (currentMaxTokens > modelMax) {
      form.setFieldValue('llm_max_tokens', modelMax)
    }
  }

  // 处理思考模式开关变化
  const handleThinkingChange = (checked: boolean) => {
    setEnableThinking(checked)
    // 思考模式下不支持 JSON Mode，自动切换回 message
    if (checked) {
      form.setFieldValue('llm_result_format', 'message')
    }
  }

  // 测试 OSS 连接
  const handleTestOSSConnection = async () => {
    setTestingOSS(true)
    try {
      const result = await settingsApi.testOSSConnection()
      if (result.success) {
        message.success(result.message)
      } else {
        message.error(result.message)
      }
    } catch (error) {
      message.error('测试连接失败')
    } finally {
      setTestingOSS(false)
    }
  }

  if (loading) {
    return (
      <div style={{ padding: 24, textAlign: 'center' }}>
        <Spin size="large" />
      </div>
    )
  }

  const maxTokensLimit = getCurrentModelMaxTokens()

  return (
    <div style={{ padding: 24, maxWidth: 900 }}>
      <h1 style={{ fontSize: 24, fontWeight: 600, marginBottom: 24, color: '#e0e0e0' }}>
        设置
      </h1>

      {/* 说明卡片 */}
      <Alert
        message="关于模型配置"
        description={
          <span>
            图像和视频模型的参数配置已移至各功能页面中，使用时可直接选择模型和参数。
            此页面仅保留全局配置项（API Key、文本模型、OSS 存储）。
          </span>
        }
        type="info"
        showIcon
        style={{ marginBottom: 24 }}
      />

      {/* API Key 设置 */}
      <Card 
        title="百炼 DashScope API Key" 
        style={{ marginBottom: 24, background: '#242424', borderColor: '#333' }}
      >
        <Alert
          message={
            config?.is_api_key_set ? (
              <span>
                <CheckCircleOutlined style={{ color: '#52c41a', marginRight: 8 }} />
                API Key 已设置：{config.api_key_masked}
              </span>
            ) : (
              <span>
                <CloseCircleOutlined style={{ color: '#ff4d4f', marginRight: 8 }} />
                尚未设置 API Key
              </span>
            )
          }
          type={config?.is_api_key_set ? 'success' : 'warning'}
          style={{ marginBottom: 16 }}
        />

        <Form form={form} layout="vertical">
          <Form.Item
            name="api_key"
            label="输入新的 API Key"
            extra="API Key 将被安全保存，您可以在阿里云百炼控制台获取"
          >
            <Input.Password
              placeholder="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
              iconRender={(visible) => (visible ? <EyeOutlined /> : <EyeInvisibleOutlined />)}
            />
          </Form.Item>
          <Button
            type="primary"
            icon={<SaveOutlined />}
            onClick={handleSaveApiKey}
            loading={saving}
          >
            保存 API Key
          </Button>
        </Form>
      </Card>

      {/* API 地域设置 */}
      <Card 
        title="API 地域" 
        style={{ marginBottom: 24, background: '#242424', borderColor: '#333' }}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="api_region"
            label="选择 API 服务地域"
            extra="不同地域的 API 端点不同，请根据您的需求选择"
          >
            <Select
              options={
                config ? Object.entries(config.available_regions).map(([key, info]) => ({
                  label: `${info.name} (${info.base_url})`,
                  value: key
                })) : []
              }
            />
          </Form.Item>
        </Form>
      </Card>

      {/* 文本模型配置 */}
      <Card 
        title="文本模型配置" 
        style={{ marginBottom: 24, background: '#242424', borderColor: '#333' }}
        extra={
          <Tooltip title="用于剧本生成、角色提取等文本处理任务">
            <InfoCircleOutlined style={{ color: '#888' }} />
          </Tooltip>
        }
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="llm_model"
            label="默认文本模型"
            extra="用于剧本生成、角色提取等文本处理任务"
          >
            <Select
              options={
                config ? Object.entries(config.available_llm_models).map(([key, info]) => ({
                  label: (
                    <span>
                      {info.name}
                      <span style={{ color: '#888', marginLeft: 8, fontSize: 12 }}>
                        (最大输出: {info.max_output_tokens?.toLocaleString()}
                        {info.supports_thinking ? ', 支持深度思考' : ''})
                      </span>
                    </span>
                  ),
                  value: key
                })) : []
              }
              onChange={handleModelChange}
            />
          </Form.Item>

          <Form.Item
            name="llm_max_tokens"
            label={
              <Space>
                最大输出长度
                <Tooltip title={`当前模型最大支持 ${maxTokensLimit.toLocaleString()} tokens`}>
                  <QuestionCircleOutlined style={{ color: '#888' }} />
                </Tooltip>
              </Space>
            }
          >
            <Slider 
              min={1} 
              max={maxTokensLimit} 
              marks={{
                1: '1',
                [Math.floor(maxTokensLimit / 2)]: `${Math.floor(maxTokensLimit / 2).toLocaleString()}`,
                [maxTokensLimit]: `${maxTokensLimit.toLocaleString()}`
              }}
            />
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="llm_result_format"
                label={
                  <Space>
                    返回格式
                    {enableThinking && (
                      <Tooltip title="深度思考模式下不支持 JSON 模式">
                        <InfoCircleOutlined style={{ color: '#faad14' }} />
                      </Tooltip>
                    )}
                  </Space>
                }
              >
                <Select
                  options={[
                    { label: '普通消息 (message)', value: 'message' },
                    { 
                      label: 'JSON 模式 (json_object)', 
                      value: 'json_object',
                      disabled: enableThinking
                    }
                  ]}
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="llm_enable_search"
                label="联网搜索"
                valuePropName="checked"
              >
                <Switch />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="llm_top_p"
                label={
                  <Space>
                    Top P
                    <Tooltip title="核采样参数，控制输出的多样性，值越小输出越确定">
                      <QuestionCircleOutlined style={{ color: '#888' }} />
                    </Tooltip>
                  </Space>
                }
              >
                <Slider min={0} max={1} step={0.01} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="llm_temperature"
                label={
                  <Space>
                    Temperature
                    <Tooltip title="温度参数，值越高输出越随机，值越低输出越确定">
                      <QuestionCircleOutlined style={{ color: '#888' }} />
                    </Tooltip>
                  </Space>
                }
              >
                <Slider min={0} max={2} step={0.01} />
              </Form.Item>
            </Col>
          </Row>

          {/* 深度思考设置 - 仅当模型支持时显示 */}
          {currentModelSupportsThinking() && (
            <>
              <Divider style={{ margin: '16px 0' }}>
                <span style={{ color: '#888', fontSize: 12 }}>深度思考设置</span>
              </Divider>

              <Alert
                message="深度思考模式"
                description="启用后模型会进行更深入的推理，但会消耗更多 token 且不支持 JSON 模式。"
                type="info"
                showIcon
                style={{ marginBottom: 16 }}
              />

              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    name="llm_enable_thinking"
                    label="启用深度思考"
                    valuePropName="checked"
                  >
                    <Switch onChange={handleThinkingChange} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name="llm_thinking_budget"
                    label={
                      <Space>
                        思考预算
                        <Tooltip title="深度思考时的最大 token 预算">
                          <QuestionCircleOutlined style={{ color: '#888' }} />
                        </Tooltip>
                      </Space>
                    }
                  >
                    <InputNumber 
                      min={1} 
                      max={38000} 
                      style={{ width: '100%' }} 
                      disabled={!enableThinking}
                    />
                  </Form.Item>
                </Col>
              </Row>
            </>
          )}
        </Form>
      </Card>

      {/* 阿里云 OSS 配置 */}
      <Card 
        title={
          <Space>
            <CloudUploadOutlined />
            阿里云 OSS 配置
          </Space>
        }
        style={{ marginBottom: 24, background: '#242424', borderColor: '#333' }}
        extra={
          <Tooltip title="OSS 用于存储生成的图片和视频，确保链接不会过期">
            <InfoCircleOutlined style={{ color: '#888' }} />
          </Tooltip>
        }
      >
        <Alert
          message={
            config?.oss.is_configured ? (
              <span>
                <CheckCircleOutlined style={{ color: '#52c41a', marginRight: 8 }} />
                OSS 已配置：{config.oss.bucket_name}
                {config.oss.enabled ? ' (已启用)' : ' (未启用)'}
              </span>
            ) : (
              <span>
                <CloseCircleOutlined style={{ color: '#ff4d4f', marginRight: 8 }} />
                OSS 尚未配置
              </span>
            )
          }
          type={config?.oss.is_configured ? 'success' : 'warning'}
          style={{ marginBottom: 16 }}
        />

        <Form form={form} layout="vertical">
          <Form.Item
            name="oss_enabled"
            label="启用 OSS 存储"
            valuePropName="checked"
            extra="启用后，生成的图片和视频将上传到 OSS，获得持久化链接"
          >
            <Switch />
          </Form.Item>

          <Alert
            message="配置说明"
            description={
              <ul style={{ paddingLeft: 16, marginBottom: 0 }}>
                <li>Access Key ID 和 Secret 在阿里云控制台获取</li>
                <li>Bucket 需要提前创建，并设置为公共读取（用于生成可访问的图片/视频链接）</li>
                <li>Endpoint 根据 Bucket 所在地域选择，必须以 https:// 开头</li>
              </ul>
            }
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="oss_access_key_id"
                label={
                  <Space>
                    Access Key ID
                    {config?.oss.access_key_id_masked && (
                      <span style={{ color: '#888', fontSize: 12 }}>
                        (当前: {config.oss.access_key_id_masked})
                      </span>
                    )}
                  </Space>
                }
                extra="留空表示不修改"
              >
                <Input.Password 
                  placeholder="输入新的 Access Key ID"
                  iconRender={(visible) => (visible ? <EyeOutlined /> : <EyeInvisibleOutlined />)}
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="oss_access_key_secret"
                label={
                  <Space>
                    Access Key Secret
                    {config?.oss.access_key_secret_masked && (
                      <span style={{ color: '#888', fontSize: 12 }}>
                        (当前: {config.oss.access_key_secret_masked})
                      </span>
                    )}
                  </Space>
                }
                extra="留空表示不修改"
              >
                <Input.Password 
                  placeholder="输入新的 Access Key Secret"
                  iconRender={(visible) => (visible ? <EyeOutlined /> : <EyeInvisibleOutlined />)}
                />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="oss_bucket_name"
                label="Bucket 名称"
                rules={[{ required: form.getFieldValue('oss_enabled'), message: '请输入 Bucket 名称' }]}
              >
                <Input placeholder="例如: my-bucket" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="oss_endpoint"
                label="Endpoint"
                rules={[
                  { required: form.getFieldValue('oss_enabled'), message: '请输入 Endpoint' },
                  { pattern: /^https:\/\//, message: 'Endpoint 必须以 https:// 开头' }
                ]}
              >
                <Input placeholder="https://oss-cn-beijing.aliyuncs.com" />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="oss_prefix"
            label="存储路径前缀"
            extra="文件将存储在此目录下，例如 aistudio/ 表示存储在 bucket/aistudio/ 目录"
          >
            <Input placeholder="例如: aistudio/" />
          </Form.Item>

          <Button
            icon={<ApiOutlined />}
            onClick={handleTestOSSConnection}
            loading={testingOSS}
          >
            测试连接
          </Button>
        </Form>
      </Card>

      {/* 保存按钮 */}
      <div style={{ textAlign: 'right', marginBottom: 24 }}>
        <Button
          type="primary"
          icon={<SaveOutlined />}
          onClick={handleSaveSettings}
          loading={saving}
          size="large"
        >
          保存所有设置
        </Button>
      </div>
    </div>
  )
}

export default SettingsPage
