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
        // 文生图配置
        image_model: data.image.model,
        image_width: data.image.width,
        image_height: data.image.height,
        image_prompt_extend: data.image.prompt_extend,
        image_seed: data.image.seed,
        // 图像编辑配置
        image_edit_model: data.image_edit.model,
        image_edit_width: data.image_edit.width,
        image_edit_height: data.image_edit.height,
        image_edit_prompt_extend: data.image_edit.prompt_extend,
        image_edit_watermark: data.image_edit.watermark,
        image_edit_seed: data.image_edit.seed,
        // 图生视频配置
        video_model: data.video.model,
        video_resolution: data.video.resolution,
        video_duration: data.video.duration,
        video_prompt_extend: data.video.prompt_extend,
        video_watermark: data.video.watermark,
        video_seed: data.video.seed,
        video_audio: data.video.audio,
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
        image: {
          model: values.image_model,
          width: values.image_width,
          height: values.image_height,
          prompt_extend: values.image_prompt_extend,
          seed: values.image_seed || null,
        },
        image_edit: {
          model: values.image_edit_model,
          width: values.image_edit_width,
          height: values.image_edit_height,
          prompt_extend: values.image_edit_prompt_extend,
          watermark: values.image_edit_watermark,
          seed: values.image_edit_seed || null,
        },
        video: {
          model: values.video_model,
          resolution: values.video_resolution,
          duration: values.video_duration,
          prompt_extend: values.video_prompt_extend,
          watermark: values.video_watermark,
          seed: values.video_seed || null,
          audio: values.video_audio,
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

  // 获取当前文生图模型的常用尺寸选项
  const getImageSizeOptions = () => {
    if (!config) return []
    const imageModel = form.getFieldValue('image_model') || config.image.model
    const modelInfo = config.available_image_models[imageModel]
    return modelInfo?.common_sizes || []
  }

  // 获取当前文生图模型信息
  const getImageModelInfo = () => {
    if (!config) return null
    const imageModel = form.getFieldValue('image_model') || config.image.model
    return config.available_image_models[imageModel]
  }

  // 验证图片尺寸
  const validateImageSize = (width: number, height: number): string | null => {
    const modelInfo = getImageModelInfo()
    if (!modelInfo) return null
    
    const totalPixels = width * height
    const ratio = height > 0 ? width / height : 0
    
    if (totalPixels < modelInfo.min_pixels) {
      return `总像素 (${totalPixels.toLocaleString()}) 小于最小值 (${modelInfo.min_pixels.toLocaleString()})`
    }
    if (totalPixels > modelInfo.max_pixels) {
      return `总像素 (${totalPixels.toLocaleString()}) 大于最大值 (${modelInfo.max_pixels.toLocaleString()})`
    }
    if (ratio < modelInfo.min_ratio || ratio > modelInfo.max_ratio) {
      return `宽高比 (${ratio.toFixed(2)}) 超出范围 [${modelInfo.min_ratio}, ${modelInfo.max_ratio}]`
    }
    return null
  }

  // 应用预设尺寸
  const applyPresetSize = (width: number, height: number) => {
    form.setFieldsValue({ image_width: width, image_height: height })
  }

  // 获取当前视频模型的分辨率选项
  const getVideoResolutions = () => {
    if (!config) return []
    const videoModel = form.getFieldValue('video_model') || config.video.model
    const modelInfo = config.available_video_models[videoModel]
    return modelInfo?.resolutions || []
  }

  // 获取当前视频模型信息
  const getCurrentVideoModelInfo = () => {
    if (!config) return null
    const videoModel = form.getFieldValue('video_model') || config.video.model
    return config.available_video_models[videoModel]
  }

  // 获取当前图像编辑模型的常用尺寸选项
  const getImageEditSizeOptions = () => {
    if (!config) return []
    const editModel = form.getFieldValue('image_edit_model') || config.image_edit.model
    const modelInfo = config.available_image_edit_models[editModel]
    return modelInfo?.common_sizes || []
  }

  // 获取当前图像编辑模型信息
  const getImageEditModelInfo = () => {
    if (!config) return null
    const editModel = form.getFieldValue('image_edit_model') || config.image_edit.model
    return config.available_image_edit_models[editModel]
  }

  // 检查当前模型是否是 qwen 系列
  const isQwenImageEditModel = () => {
    const editModel = form.getFieldValue('image_edit_model') || config?.image_edit?.model
    return editModel?.startsWith('qwen-image-edit')
  }

  // 验证图像编辑尺寸
  const validateImageEditSize = (width: number, height: number): string | null => {
    const modelInfo = getImageEditModelInfo()
    if (!modelInfo) return null
    
    // qwen-image-edit-plus 使用不同的尺寸限制
    if (isQwenImageEditModel()) {
      const minSize = modelInfo.min_size || 512
      const maxSize = modelInfo.max_size || 2048
      if (width < minSize || width > maxSize) {
        return `宽度必须在 ${minSize} - ${maxSize} 之间`
      }
      if (height < minSize || height > maxSize) {
        return `高度必须在 ${minSize} - ${maxSize} 之间`
      }
      return null
    }
    
    // wan2.5-i2i-preview 使用像素和宽高比限制
    const totalPixels = width * height
    const ratio = height > 0 ? width / height : 0
    
    if (modelInfo.min_pixels && totalPixels < modelInfo.min_pixels) {
      return `总像素 (${totalPixels.toLocaleString()}) 小于最小值 (${modelInfo.min_pixels.toLocaleString()})`
    }
    if (modelInfo.max_pixels && totalPixels > modelInfo.max_pixels) {
      return `总像素 (${totalPixels.toLocaleString()}) 大于最大值 (${modelInfo.max_pixels.toLocaleString()})`
    }
    if (modelInfo.min_ratio && modelInfo.max_ratio && (ratio < modelInfo.min_ratio || ratio > modelInfo.max_ratio)) {
      return `宽高比 (${ratio.toFixed(2)}) 超出范围 [${modelInfo.min_ratio}, ${modelInfo.max_ratio}]`
    }
    return null
  }

  // 应用图像编辑预设尺寸
  const applyImageEditPresetSize = (sizeValue: string) => {
    // qwen-image-edit-plus 的 common_sizes 格式是 {value: "1024*1024", label: "..."}
    // wan2.5-i2i-preview 的 common_sizes 格式是 {width: 1024, height: 1024, label: "..."}
    if (sizeValue.includes('*')) {
      const [w, h] = sizeValue.split('*').map(Number)
      form.setFieldsValue({ image_edit_width: w, image_edit_height: h })
    } else if (sizeValue.includes('x')) {
      const [w, h] = sizeValue.split('x').map(Number)
      form.setFieldsValue({ image_edit_width: w, image_edit_height: h })
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
    <div style={{ padding: 24, maxWidth: 900, overflowY: 'auto', height: '100%' }}>
      <h1 style={{ fontSize: 24, fontWeight: 600, marginBottom: 24, color: '#e0e0e0' }}>
        设置
      </h1>

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

      {/* 文生图模型配置 */}
      <Card 
        title="文生图模型配置" 
        style={{ marginBottom: 24, background: '#242424', borderColor: '#333' }}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="image_model"
            label="文生图模型"
          >
            <Select
              options={
                config ? Object.entries(config.available_image_models).map(([key, info]) => ({
                  label: (
                    <span>
                      {info.name}
                      {info.description && (
                        <span style={{ color: '#888', marginLeft: 8, fontSize: 12 }}>
                          ({info.description})
                        </span>
                      )}
                    </span>
                  ),
                  value: key
                })) : []
              }
              onChange={() => {
                // 模型改变时重置为默认尺寸
                const sizes = getImageSizeOptions()
                if (sizes.length > 0) {
                  form.setFieldsValue({
                    image_width: sizes[0].width,
                    image_height: sizes[0].height
                  })
                }
              }}
            />
          </Form.Item>

          {/* 尺寸设置 */}
          <div style={{ marginBottom: 16 }}>
            <div style={{ marginBottom: 8, color: '#e0e0e0' }}>
              常用比例
              <span style={{ color: '#888', marginLeft: 8, fontSize: 12 }}>
                (点击快速设置)
              </span>
            </div>
            <Space wrap>
              {getImageSizeOptions().map((option, index) => (
                <Button 
                  key={index}
                  size="small"
                  onClick={() => applyPresetSize(option.width, option.height)}
                >
                  {option.label} ({option.width}×{option.height})
                </Button>
              ))}
            </Space>
          </div>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="image_width"
                label={
                  <Space>
                    图片宽度
                    <Tooltip title="根据模型限制，总像素需在 768×768 到 1440×1440 之间，宽高比 1:4 到 4:1">
                      <QuestionCircleOutlined style={{ color: '#888' }} />
                    </Tooltip>
                  </Space>
                }
                rules={[
                  { required: true, message: '请输入宽度' },
                  {
                    validator: (_, value) => {
                      const height = form.getFieldValue('image_height')
                      if (value && height) {
                        const error = validateImageSize(value, height)
                        if (error) return Promise.reject(error)
                      }
                      return Promise.resolve()
                    }
                  }
                ]}
              >
                <InputNumber 
                  min={192} 
                  max={2880} 
                  style={{ width: '100%' }} 
                  placeholder="宽度（像素）"
                  onChange={() => form.validateFields(['image_width', 'image_height'])}
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="image_height"
                label="图片高度"
                rules={[
                  { required: true, message: '请输入高度' },
                  {
                    validator: (_, value) => {
                      const width = form.getFieldValue('image_width')
                      if (value && width) {
                        const error = validateImageSize(width, value)
                        if (error) return Promise.reject(error)
                      }
                      return Promise.resolve()
                    }
                  }
                ]}
              >
                <InputNumber 
                  min={192} 
                  max={2880} 
                  style={{ width: '100%' }} 
                  placeholder="高度（像素）"
                  onChange={() => form.validateFields(['image_width', 'image_height'])}
                />
              </Form.Item>
            </Col>
          </Row>

          <Alert
            message="尺寸限制说明"
            description={
              <span>
                wan2.5-t2i-preview 模型要求：总像素在 <strong>768×768</strong> 到 <strong>1440×1440</strong> 之间，
                宽高比在 <strong>1:4</strong> 到 <strong>4:1</strong> 之间。
              </span>
            }
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="image_prompt_extend"
                label="智能改写"
                valuePropName="checked"
                tooltip="自动优化和扩展提示词，生成更丰富的图片"
              >
                <Switch />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="image_seed"
                label="随机种子"
                extra="留空表示随机，设置固定值可复现结果"
              >
                <InputNumber min={0} style={{ width: '100%' }} placeholder="留空为随机" />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Card>

      {/* 图像编辑模型配置 */}
      <Card 
        title="图像编辑模型配置" 
        style={{ marginBottom: 24, background: '#242424', borderColor: '#333' }}
        extra={
          <Tooltip title="用于风格迁移、局部编辑等图生图操作">
            <InfoCircleOutlined style={{ color: '#888' }} />
          </Tooltip>
        }
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="image_edit_model"
            label="图像编辑模型"
          >
            <Select
              options={
                config ? Object.entries(config.available_image_edit_models).map(([key, info]) => ({
                  label: info.name,
                  value: key
                })) : []
              }
              onChange={() => {
                const sizes = getImageEditSizeOptions()
                if (sizes.length > 0) {
                  form.setFieldsValue({ 
                    image_edit_width: sizes[0].width, 
                    image_edit_height: sizes[0].height 
                  })
                }
              }}
            />
          </Form.Item>

          {getImageEditModelInfo() && (
            <Alert
              message={isQwenImageEditModel() ? "qwen-image-edit-plus 说明" : "尺寸限制"}
              description={
                isQwenImageEditModel() ? (
                  <span>
                    宽高范围: {getImageEditModelInfo()!.min_size || 512} - {getImageEditModelInfo()!.max_size || 2048}，
                    最多输入{getImageEditModelInfo()!.max_images || 3}张图片，
                    最多输出{getImageEditModelInfo()!.max_output || 6}张图片。
                    设置输出尺寸时只能生成1张图片。
                  </span>
                ) : (
                  <span>
                    总像素: {getImageEditModelInfo()!.min_pixels?.toLocaleString()} - {getImageEditModelInfo()!.max_pixels?.toLocaleString()}，
                    宽高比: {getImageEditModelInfo()!.min_ratio} - {getImageEditModelInfo()!.max_ratio}
                  </span>
                )
              }
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
            />
          )}

          <Row gutter={16}>
            <Col span={8}>
              <Form.Item
                name="image_edit_width"
                label="图片宽度"
                rules={[{ required: true }]}
                validateStatus={validateImageEditSize(form.getFieldValue('image_edit_width'), form.getFieldValue('image_edit_height')) ? 'warning' : undefined}
                help={validateImageEditSize(form.getFieldValue('image_edit_width'), form.getFieldValue('image_edit_height'))}
              >
                <InputNumber min={512} max={2048} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                name="image_edit_height"
                label="图片高度"
                rules={[{ required: true }]}
              >
                <InputNumber min={512} max={2048} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="常用尺寸">
                <Select
                  placeholder="选择预设"
                  onChange={(value) => applyImageEditPresetSize(value)}
                  options={getImageEditSizeOptions().map((size: any) => {
                    // 支持两种格式：{value, label} 和 {width, height, label}
                    if (size.value !== undefined) {
                      return { label: size.label, value: size.value }
                    } else {
                      return { label: size.label, value: `${size.width}x${size.height}` }
                    }
                  })}
                />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={isQwenImageEditModel() ? 8 : 12}>
              <Form.Item
                name="image_edit_prompt_extend"
                label="智能改写"
                valuePropName="checked"
                tooltip="自动优化和扩展提示词"
              >
                <Switch />
              </Form.Item>
            </Col>
            {isQwenImageEditModel() && (
              <Col span={8}>
                <Form.Item
                  name="image_edit_watermark"
                  label="添加水印"
                  valuePropName="checked"
                  tooltip="在图像右下角添加 Qwen-Image 水印"
                >
                  <Switch />
                </Form.Item>
              </Col>
            )}
            <Col span={isQwenImageEditModel() ? 8 : 12}>
              <Form.Item
                name="image_edit_seed"
                label="随机种子"
                extra="留空表示随机，设置固定值可复现结果"
              >
                <InputNumber min={0} max={isQwenImageEditModel() ? 2147483647 : undefined} style={{ width: '100%' }} placeholder="留空为随机" />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Card>

      {/* 图生视频模型配置 */}
      <Card 
        title="图生视频模型配置" 
        style={{ marginBottom: 24, background: '#242424', borderColor: '#333' }}
      >
        <Form form={form} layout="vertical">
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="video_model"
                label="图生视频模型"
              >
                <Select
                  options={
                    config ? Object.entries(config.available_video_models).map(([key, info]) => ({
                      label: `${info.name}`,
                      value: key
                    })) : []
                  }
                  onChange={(value) => {
                    const modelInfo = config?.available_video_models[value]
                    if (modelInfo) {
                      form.setFieldValue('video_resolution', modelInfo.default_resolution)
                    }
                  }}
                />
              </Form.Item>
              {getCurrentVideoModelInfo()?.description && (
                <div style={{ fontSize: 12, color: '#888', marginTop: -16, marginBottom: 16 }}>
                  {getCurrentVideoModelInfo()?.description}
                </div>
              )}
            </Col>
            <Col span={12}>
              <Form.Item
                name="video_resolution"
                label="视频分辨率"
                extra={getCurrentVideoModelInfo()?.supports_audio === false ? '' : '分辨率由输入图像宽高比决定'}
              >
                <Select
                  options={getVideoResolutions().map(res => ({
                    label: res.label,
                    value: res.value
                  }))}
                />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="video_duration"
                label="默认时长"
                extra={getCurrentVideoModelInfo()?.id?.includes('wan2.5') 
                  ? 'wan2.5 支持 5 或 10 秒' 
                  : 'wanx2.1 支持 3/4/5 秒'
                }
              >
                <Select>
                  {(getCurrentVideoModelInfo()?.durations || [5]).map((d: number) => (
                    <Select.Option key={d} value={d}>{d} 秒</Select.Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="video_audio"
                label="自动生成音频"
                valuePropName="checked"
                tooltip="仅 wan2.5 支持，模型根据提示词和画面自动生成匹配的背景音频"
                extra={getCurrentVideoModelInfo()?.supports_audio 
                  ? '开启后默认自动配音，可在工作室中覆盖' 
                  : '当前模型不支持音频'
                }
              >
                <Switch disabled={!getCurrentVideoModelInfo()?.supports_audio} />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="video_prompt_extend"
                label="智能改写"
                valuePropName="checked"
                tooltip="使用大模型优化提示词，对较短的提示词效果更明显"
              >
                <Switch />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="video_watermark"
                label="添加水印"
                valuePropName="checked"
                tooltip="在视频右下角添加 'AI生成' 水印标识"
              >
                <Switch />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="video_seed"
            label="随机种子"
            extra="留空表示随机，固定种子可使结果相对稳定（但不保证完全一致）"
          >
            <InputNumber min={0} max={2147483647} style={{ width: '100%' }} placeholder="留空为随机" />
          </Form.Item>
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
