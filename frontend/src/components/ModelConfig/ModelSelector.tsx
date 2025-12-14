/**
 * 模型选择器组件
 * 
 * 用于选择模型，自动加载模型列表并显示模型信息
 */

import React, { useEffect, useState } from 'react'
import { Select, Space, Tag, Tooltip, Spin } from 'antd'
import {
  ThunderboltOutlined,
  ClockCircleOutlined,
  SoundOutlined,
  ApiOutlined,
} from '@ant-design/icons'
import type { ModelInfo } from './DynamicModelForm'

const { Option } = Select

interface ModelSelectorProps {
  modelType?: string  // llm, text_to_image, image_to_video, etc.
  value?: string
  onChange?: (modelId: string, modelInfo: ModelInfo) => void
  models?: Record<string, ModelInfo>  // 可选：直接传入模型列表
  loading?: boolean
  disabled?: boolean
  style?: React.CSSProperties
  showCapabilities?: boolean
}

/**
 * 渲染模型能力标签
 */
const CapabilityTags: React.FC<{ capabilities?: ModelInfo['capabilities'] }> = ({
  capabilities,
}) => {
  if (!capabilities) return null
  
  const tags = []
  
  if (capabilities.supports_streaming) {
    tags.push(
      <Tooltip key="streaming" title="支持流式输出">
        <Tag color="blue" style={{ marginRight: 4 }}>
          <ThunderboltOutlined /> 流式
        </Tag>
      </Tooltip>
    )
  }
  
  if (capabilities.supports_audio) {
    tags.push(
      <Tooltip key="audio" title="支持音频">
        <Tag color="purple" style={{ marginRight: 4 }}>
          <SoundOutlined /> 音频
        </Tag>
      </Tooltip>
    )
  }
  
  if (capabilities.supports_thinking) {
    tags.push(
      <Tooltip key="thinking" title="支持深度思考">
        <Tag color="orange" style={{ marginRight: 4 }}>
          深度思考
        </Tag>
      </Tooltip>
    )
  }
  
  if (capabilities.supports_async) {
    tags.push(
      <Tooltip key="async" title="支持异步调用">
        <Tag color="cyan" style={{ marginRight: 4 }}>
          <ClockCircleOutlined /> 异步
        </Tag>
      </Tooltip>
    )
  }
  
  return <Space size={0}>{tags}</Space>
}

const ModelSelector: React.FC<ModelSelectorProps> = ({
  modelType,
  value,
  onChange,
  models = {},
  loading = false,
  disabled = false,
  style,
  showCapabilities = true,
}) => {
  // 过滤指定类型的模型
  const filteredModels = Object.values(models).filter((m) => {
    if (!modelType) return true
    return m.type === modelType
  })
  
  const handleChange = (modelId: string) => {
    const modelInfo = models[modelId]
    if (modelInfo && onChange) {
      onChange(modelId, modelInfo)
    }
  }
  
  const selectedModel = value ? models[value] : undefined
  
  return (
    <div>
      <Select
        value={value}
        onChange={handleChange}
        loading={loading}
        disabled={disabled}
        style={{ width: '100%', ...style }}
        placeholder="选择模型"
        optionLabelProp="label"
      >
        {filteredModels.map((model) => (
          <Option
            key={model.id}
            value={model.id}
            label={model.name}
            disabled={model.deprecated}
          >
            <div>
              <div style={{ fontWeight: 500 }}>
                {model.name}
                {model.deprecated && (
                  <Tag color="red" style={{ marginLeft: 8 }}>
                    已废弃
                  </Tag>
                )}
              </div>
              {model.description && (
                <div style={{ fontSize: 12, color: '#888' }}>
                  {model.description}
                </div>
              )}
            </div>
          </Option>
        ))}
      </Select>
      
      {/* 显示选中模型的能力 */}
      {showCapabilities && selectedModel && (
        <div style={{ marginTop: 8 }}>
          <CapabilityTags capabilities={selectedModel.capabilities} />
        </div>
      )}
      
      {/* 废弃提示 */}
      {selectedModel?.deprecated && (
        <div style={{ marginTop: 8, color: '#ff4d4f', fontSize: 12 }}>
          ⚠️ {selectedModel.deprecated_message || '该模型已废弃，建议选择其他模型'}
        </div>
      )}
    </div>
  )
}

export default ModelSelector

