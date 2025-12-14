/**
 * 动态模型参数表单组件
 * 
 * 根据后端返回的模型参数定义自动渲染表单
 * 支持所有参数类型：文本、数字、布尔、选择等
 */

import React, { useState, useEffect } from 'react'
import {
  Form,
  Input,
  InputNumber,
  Switch,
  Select,
  Collapse,
  Space,
  Tooltip,
  Button,
  Row,
  Col,
} from 'antd'
import { QuestionCircleOutlined, SettingOutlined } from '@ant-design/icons'

const { TextArea } = Input
const { Option } = Select
const { Panel } = Collapse

// 参数类型枚举
export type ParameterType =
  | 'string'
  | 'integer'
  | 'float'
  | 'boolean'
  | 'select'
  | 'multi_select'
  | 'text'
  | 'image_url'
  | 'image_urls'
  | 'audio_url'
  | 'video_url'
  | 'file'

// 选项定义
export interface SelectOption {
  value: any
  label: string
  description?: string
}

// 参数约束
export interface ParameterConstraint {
  min_value?: number
  max_value?: number
  min_length?: number
  max_length?: number
  pattern?: string
  options?: SelectOption[]
  depends_on?: string
  depends_value?: any
}

// 参数定义
export interface ModelParameter {
  name: string
  label: string
  type: ParameterType
  description?: string
  required?: boolean
  default?: any
  constraint?: ParameterConstraint
  group?: string
  advanced?: boolean
  order?: number
}

// 模型能力
export interface ModelCapability {
  supports_streaming?: boolean
  supports_batch?: boolean
  supports_async?: boolean
  supports_thinking?: boolean
  supports_search?: boolean
  supports_json_mode?: boolean
  supports_negative_prompt?: boolean
  supports_seed?: boolean
  supports_prompt_extend?: boolean
  supports_watermark?: boolean
  supports_audio?: boolean
}

// 模型信息
export interface ModelInfo {
  id: string
  name: string
  type: string
  description?: string
  capabilities?: ModelCapability
  parameters?: ModelParameter[]
  default_values?: Record<string, any>
  deprecated?: boolean
  deprecated_message?: string
}

interface DynamicModelFormProps {
  modelInfo: ModelInfo
  value?: Record<string, any>
  onChange?: (values: Record<string, any>) => void
  showAdvanced?: boolean
  layout?: 'vertical' | 'horizontal'
  columns?: number
  excludeParams?: string[]  // 排除的参数
  readOnly?: boolean
}

/**
 * 按分组组织参数
 */
const groupParameters = (parameters: ModelParameter[]) => {
  const groups: Record<string, ModelParameter[]> = {}
  
  for (const param of parameters) {
    const group = param.group || 'basic'
    if (!groups[group]) {
      groups[group] = []
    }
    groups[group].push(param)
  }
  
  // 每组内按 order 排序
  for (const group of Object.keys(groups)) {
    groups[group].sort((a, b) => (a.order || 0) - (b.order || 0))
  }
  
  return groups
}

/**
 * 分组名称映射
 */
const GROUP_LABELS: Record<string, string> = {
  basic: '基础参数',
  generation: '生成参数',
  size: '尺寸设置',
  reference: '参考图',
  audio: '音频设置',
  thinking: '思考模式',
  advanced: '高级参数',
}

/**
 * 渲染单个参数
 */
const ParameterField: React.FC<{
  param: ModelParameter
  value: any
  onChange: (value: any) => void
  allValues: Record<string, any>
  readOnly?: boolean
}> = ({ param, value, onChange, allValues, readOnly }) => {
  // 检查依赖条件
  if (param.constraint?.depends_on) {
    const dependValue = allValues[param.constraint.depends_on]
    const expectedValue = param.constraint.depends_value
    
    // 如果依赖值不匹配，隐藏参数
    if (expectedValue !== undefined && dependValue !== expectedValue) {
      return null
    }
    // 如果期望值为 null/undefined，表示依赖参数为空时才显示
    if (expectedValue === null && dependValue) {
      return null
    }
  }
  
  const label = (
    <Space>
      {param.label}
      {param.required && <span style={{ color: '#ff4d4f' }}>*</span>}
      {param.description && (
        <Tooltip title={param.description}>
          <QuestionCircleOutlined style={{ color: '#888' }} />
        </Tooltip>
      )}
    </Space>
  )
  
  const renderInput = () => {
    switch (param.type) {
      case 'string':
        return (
          <Input
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={param.description}
            disabled={readOnly}
            maxLength={param.constraint?.max_length}
          />
        )
      
      case 'text':
        return (
          <TextArea
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={param.description}
            disabled={readOnly}
            rows={3}
            maxLength={param.constraint?.max_length}
            showCount={!!param.constraint?.max_length}
          />
        )
      
      case 'integer':
        return (
          <InputNumber
            value={value}
            onChange={onChange}
            disabled={readOnly}
            min={param.constraint?.min_value}
            max={param.constraint?.max_value}
            style={{ width: '100%' }}
          />
        )
      
      case 'float':
        return (
          <InputNumber
            value={value}
            onChange={onChange}
            disabled={readOnly}
            min={param.constraint?.min_value}
            max={param.constraint?.max_value}
            step={0.1}
            style={{ width: '100%' }}
          />
        )
      
      case 'boolean':
        return (
          <Switch
            checked={value}
            onChange={onChange}
            disabled={readOnly}
          />
        )
      
      case 'select':
        return (
          <Select
            value={value}
            onChange={onChange}
            disabled={readOnly}
            style={{ width: '100%' }}
          >
            {param.constraint?.options?.map((opt) => (
              <Option key={opt.value} value={opt.value}>
                {opt.label}
                {opt.description && (
                  <span style={{ color: '#888', marginLeft: 8 }}>
                    {opt.description}
                  </span>
                )}
              </Option>
            ))}
          </Select>
        )
      
      case 'multi_select':
        return (
          <Select
            mode="multiple"
            value={value || []}
            onChange={onChange}
            disabled={readOnly}
            style={{ width: '100%' }}
          >
            {param.constraint?.options?.map((opt) => (
              <Option key={opt.value} value={opt.value}>
                {opt.label}
              </Option>
            ))}
          </Select>
        )
      
      case 'image_url':
      case 'audio_url':
      case 'video_url':
        return (
          <Input
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={`输入${param.label} URL`}
            disabled={readOnly}
          />
        )
      
      case 'image_urls':
        return (
          <TextArea
            value={Array.isArray(value) ? value.join('\n') : value}
            onChange={(e) => onChange(e.target.value.split('\n').filter(Boolean))}
            placeholder="每行一个图片URL"
            disabled={readOnly}
            rows={3}
          />
        )
      
      default:
        return (
          <Input
            value={value}
            onChange={(e) => onChange(e.target.value)}
            disabled={readOnly}
          />
        )
    }
  }
  
  return (
    <Form.Item
      label={label}
      style={{ marginBottom: 16 }}
    >
      {renderInput()}
    </Form.Item>
  )
}

/**
 * 动态模型参数表单
 */
const DynamicModelForm: React.FC<DynamicModelFormProps> = ({
  modelInfo,
  value = {},
  onChange,
  showAdvanced = false,
  layout = 'vertical',
  columns = 2,
  excludeParams = [],
  readOnly = false,
}) => {
  const [showAdvancedPanel, setShowAdvancedPanel] = useState(showAdvanced)
  const [formValues, setFormValues] = useState<Record<string, any>>({})
  
  // 初始化表单值
  useEffect(() => {
    const initialValues = {
      ...modelInfo.default_values,
      ...value,
    }
    setFormValues(initialValues)
  }, [modelInfo, value])
  
  // 处理值变化
  const handleValueChange = (paramName: string, paramValue: any) => {
    const newValues = {
      ...formValues,
      [paramName]: paramValue,
    }
    setFormValues(newValues)
    onChange?.(newValues)
  }
  
  // 过滤参数
  const parameters = (modelInfo.parameters || []).filter(
    (p) => !excludeParams.includes(p.name)
  )
  
  // 按分组组织参数
  const groupedParams = groupParameters(parameters)
  
  // 分离基础参数和高级参数
  const basicGroups = Object.entries(groupedParams).filter(
    ([group]) => group !== 'advanced' && !groupedParams[group].every(p => p.advanced)
  )
  const advancedParams = parameters.filter(p => p.advanced || p.group === 'advanced')
  
  const renderGroup = (group: string, params: ModelParameter[]) => {
    const visibleParams = params.filter(p => !p.advanced)
    if (visibleParams.length === 0) return null
    
    return (
      <div key={group} style={{ marginBottom: 24 }}>
        <div style={{ 
          marginBottom: 12, 
          fontWeight: 500, 
          color: '#e0e0e0',
          borderBottom: '1px solid #333',
          paddingBottom: 8,
        }}>
          {GROUP_LABELS[group] || group}
        </div>
        <Row gutter={16}>
          {visibleParams.map((param) => (
            <Col key={param.name} span={24 / columns}>
              <ParameterField
                param={param}
                value={formValues[param.name]}
                onChange={(v) => handleValueChange(param.name, v)}
                allValues={formValues}
                readOnly={readOnly}
              />
            </Col>
          ))}
        </Row>
      </div>
    )
  }
  
  return (
    <Form layout={layout}>
      {/* 基础参数分组 */}
      {basicGroups.map(([group, params]) => renderGroup(group, params))}
      
      {/* 高级参数 */}
      {advancedParams.length > 0 && (
        <Collapse
          ghost
          activeKey={showAdvancedPanel ? ['advanced'] : []}
          onChange={(keys) => setShowAdvancedPanel(keys.includes('advanced'))}
          style={{ marginTop: 16, background: '#1a1a1a' }}
        >
          <Panel
            header={
              <Space>
                <SettingOutlined />
                高级参数
              </Space>
            }
            key="advanced"
          >
            <Row gutter={16}>
              {advancedParams.map((param) => (
                <Col key={param.name} span={24 / columns}>
                  <ParameterField
                    param={param}
                    value={formValues[param.name]}
                    onChange={(v) => handleValueChange(param.name, v)}
                    allValues={formValues}
                    readOnly={readOnly}
                  />
                </Col>
              ))}
            </Row>
          </Panel>
        </Collapse>
      )}
    </Form>
  )
}

export default DynamicModelForm

