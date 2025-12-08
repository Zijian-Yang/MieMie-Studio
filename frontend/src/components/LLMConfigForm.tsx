import { useEffect, useState } from 'react'
import { 
  Form, Select, Slider, Switch, InputNumber, Tooltip, Space, Row, Col, 
  Divider, Alert 
} from 'antd'
import { QuestionCircleOutlined, InfoCircleOutlined } from '@ant-design/icons'
import type { FormInstance } from 'antd'
import type { LLMModelInfo, LLMConfig } from '../services/api'

interface LLMConfigFormProps {
  form: FormInstance
  availableModels: Record<string, LLMModelInfo>
  selectedModel: string
  onModelChange?: (model: string) => void
  compact?: boolean  // 紧凑模式，用于弹窗
  hideModelSelect?: boolean  // 隐藏模型选择器
}

/**
 * 可复用的 LLM 配置表单组件
 * 用于设置页面和项目级别的模型配置弹窗
 */
const LLMConfigForm = ({ 
  form, 
  availableModels, 
  selectedModel,
  onModelChange,
  compact = false,
  hideModelSelect = false
}: LLMConfigFormProps) => {
  const [enableThinking, setEnableThinking] = useState(false)

  // 检查当前选中的模型是否支持深度思考
  const currentModelSupportsThinking = () => {
    const modelInfo = availableModels[selectedModel]
    return modelInfo?.supports_thinking ?? false
  }

  // 获取当前模型的最大输出 token 数
  const getCurrentModelMaxTokens = () => {
    const modelInfo = availableModels[selectedModel]
    return modelInfo?.max_output_tokens ?? 32768
  }

  // 当模型改变时更新相关状态
  const handleModelChange = (value: string) => {
    onModelChange?.(value)
    
    // 如果新模型不支持思考，关闭思考模式
    const modelInfo = availableModels[value]
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

  // 同步 enableThinking 状态
  useEffect(() => {
    const thinkingValue = form.getFieldValue('llm_enable_thinking')
    setEnableThinking(!!thinkingValue)
  }, [form])

  const maxTokensLimit = getCurrentModelMaxTokens()
  const colSpan = compact ? 12 : 12

  return (
    <>
      {!hideModelSelect && (
        <Form.Item
          name="llm_model"
          label="文本模型"
          extra={compact ? undefined : "用于剧本生成、角色提取等文本处理任务"}
        >
          <Select
            options={
              Object.entries(availableModels).map(([key, info]) => ({
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
              }))
            }
            onChange={handleModelChange}
          />
        </Form.Item>
      )}

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
          marks={compact ? {
            1: '1',
            [maxTokensLimit]: `${maxTokensLimit.toLocaleString()}`
          } : {
            1: '1',
            [Math.floor(maxTokensLimit / 2)]: `${Math.floor(maxTokensLimit / 2).toLocaleString()}`,
            [maxTokensLimit]: `${maxTokensLimit.toLocaleString()}`
          }}
        />
      </Form.Item>

      <Row gutter={16}>
        <Col span={colSpan}>
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
                { label: '普通消息', value: 'message' },
                { 
                  label: 'JSON 模式', 
                  value: 'json_object',
                  disabled: enableThinking
                }
              ]}
            />
          </Form.Item>
        </Col>
        <Col span={colSpan}>
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
        <Col span={colSpan}>
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
        <Col span={colSpan}>
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
          <Divider style={{ margin: '12px 0' }}>
            <span style={{ color: '#888', fontSize: 12 }}>深度思考设置</span>
          </Divider>

          {!compact && (
            <Alert
              message="深度思考模式"
              description="启用后模型会进行更深入的推理，但会消耗更多 token 且不支持 JSON 模式。"
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
            />
          )}

          <Row gutter={16}>
            <Col span={colSpan}>
              <Form.Item
                name="llm_enable_thinking"
                label="启用深度思考"
                valuePropName="checked"
              >
                <Switch onChange={handleThinkingChange} />
              </Form.Item>
            </Col>
            <Col span={colSpan}>
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
    </>
  )
}

export default LLMConfigForm

