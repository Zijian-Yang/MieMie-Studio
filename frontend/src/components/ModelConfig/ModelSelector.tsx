/**
 * 模型选择器组件
 * 
 * 统一的模型选择器，支持：
 * - 自动从 modelRegistryStore 加载模型
 * - 按类型/分类过滤
 * - 显示推荐标签
 * - 显示模型能力标签
 * - 废弃模型警告
 * 
 * 使用示例：
 * ```tsx
 * // 自动加载所有图像模型
 * <ModelSelector 
 *   category={['text_to_image', 'image_to_image']}
 *   value={selectedModel}
 *   onChange={setSelectedModel}
 * />
 * 
 * // 手动传入模型列表
 * <ModelSelector 
 *   models={customModels}
 *   value={selectedModel}
 *   onChange={(modelId, modelInfo) => handleChange(modelId, modelInfo)}
 * />
 * ```
 */

import React from 'react'
import { Select, Space, Tag, Tooltip } from 'antd'
import {
  ThunderboltOutlined,
  ClockCircleOutlined,
  SoundOutlined,
  PictureOutlined,
  VideoCameraOutlined,
  StarOutlined,
} from '@ant-design/icons'
import { useModelRegistry } from '../../hooks/useModelRegistry'
import { RegisteredModelInfo, ModelCapabilities } from '../../services/api'
import { ModelCategory } from '../../stores/modelRegistryStore'

const { Option } = Select

interface ModelSelectorProps {
  /** 模型分类过滤 */
  category?: ModelCategory | ModelCategory[]
  /** 自定义过滤函数 */
  filter?: (model: RegisteredModelInfo) => boolean
  /** 当前选中的模型ID */
  value?: string
  /** 选中模型变化回调 */
  onChange?: (modelId: string, modelInfo?: RegisteredModelInfo) => void
  /** 手动传入模型列表（如果传入则不自动加载） */
  models?: Record<string, RegisteredModelInfo> | RegisteredModelInfo[]
  /** 加载状态 */
  loading?: boolean
  /** 禁用状态 */
  disabled?: boolean
  /** 样式 */
  style?: React.CSSProperties
  /** 是否显示能力标签 */
  showCapabilities?: boolean
  /** 是否显示描述 */
  showDescription?: boolean
  /** 占位符文本 */
  placeholder?: string
  /** 是否允许清空 */
  allowClear?: boolean
  /** Select 尺寸 */
  size?: 'small' | 'middle' | 'large'
}

/**
 * 渲染模型能力标签
 */
const CapabilityTags: React.FC<{ 
  capabilities?: ModelCapabilities
  recommended?: boolean 
}> = ({ capabilities, recommended }) => {
  if (!capabilities && !recommended) return null
  
  const tags = []
  
  if (recommended) {
    tags.push(
      <Tooltip key="recommended" title="推荐模型">
        <Tag color="gold" style={{ marginRight: 4 }}>
          <StarOutlined /> 推荐
        </Tag>
      </Tooltip>
    )
  }
  
  if (capabilities?.supports_reference_images) {
    tags.push(
      <Tooltip key="ref" title="支持参考图">
        <Tag color="green" style={{ marginRight: 4 }}>
          <PictureOutlined /> 参考图
        </Tag>
      </Tooltip>
    )
  }
  
  if (capabilities?.supports_interleave) {
    tags.push(
      <Tooltip key="interleave" title="支持图文混合">
        <Tag color="purple" style={{ marginRight: 4 }}>
          图文混合
        </Tag>
      </Tooltip>
    )
  }
  
  if (capabilities?.supports_audio) {
    tags.push(
      <Tooltip key="audio" title="支持音频">
        <Tag color="blue" style={{ marginRight: 4 }}>
          <SoundOutlined /> 音频
        </Tag>
      </Tooltip>
    )
  }
  
  if (capabilities?.supports_streaming) {
    tags.push(
      <Tooltip key="streaming" title="支持流式输出">
        <Tag color="cyan" style={{ marginRight: 4 }}>
          <ThunderboltOutlined /> 流式
        </Tag>
      </Tooltip>
    )
  }
  
  return tags.length > 0 ? <Space size={0} wrap>{tags}</Space> : null
}

const ModelSelector: React.FC<ModelSelectorProps> = ({
  category,
  filter,
  value,
  onChange,
  models: propModels,
  loading: propLoading,
  disabled = false,
  style,
  showCapabilities = true,
  showDescription = true,
  placeholder = '选择模型',
  allowClear = false,
  size,
}) => {
  // 如果没有传入 models，则从 store 获取
  const store = useModelRegistry({ 
    disableAutoFetch: !!propModels 
  })
  
  // 获取模型列表
  const getModels = (): RegisteredModelInfo[] => {
    if (propModels) {
      // 支持数组或对象格式
      return Array.isArray(propModels) 
        ? propModels 
        : Object.values(propModels)
    }
    return Object.values(store.models)
  }
  
  // 过滤模型
  const filteredModels = React.useMemo(() => {
    let models = getModels()
    
    // 按分类过滤
    if (category) {
      const categories = Array.isArray(category) ? category : [category]
      models = models.filter(m => categories.includes(m.type as ModelCategory))
    }
    
    // 自定义过滤
    if (filter) {
      models = models.filter(filter)
    }
    
    // 排序：推荐的在前，废弃的在后
    return models.sort((a, b) => {
      if (a.recommended && !b.recommended) return -1
      if (!a.recommended && b.recommended) return 1
      if (a.deprecated && !b.deprecated) return 1
      if (!a.deprecated && b.deprecated) return -1
      return 0
    })
  }, [propModels, store.models, category, filter])
  
  const isLoading = propLoading !== undefined ? propLoading : store.loading
  
  const handleChange = (modelId: string) => {
    const allModels = getModels()
    const modelInfo = allModels.find(m => m.id === modelId)
    onChange?.(modelId, modelInfo)
  }
  
  const selectedModel = React.useMemo(() => {
    if (!value) return undefined
    const allModels = getModels()
    return allModels.find(m => m.id === value)
  }, [value, propModels, store.models])
  
  return (
    <div>
      <Select
        value={value}
        onChange={handleChange}
        loading={isLoading}
        disabled={disabled}
        style={{ width: '100%', ...style }}
        placeholder={placeholder}
        optionLabelProp="label"
        allowClear={allowClear}
        size={size}
      >
        {filteredModels.map((model) => (
          <Option
            key={model.id}
            value={model.id}
            label={model.name}
            disabled={model.deprecated}
          >
            <div>
              <div style={{ fontWeight: 500, display: 'flex', alignItems: 'center', gap: 8 }}>
                <span>{model.name}</span>
                {model.recommended && (
                  <Tag color="gold" style={{ margin: 0 }}>
                    <StarOutlined /> 推荐
                  </Tag>
                )}
                {model.deprecated && (
                  <Tag color="red" style={{ margin: 0 }}>
                    已废弃
                  </Tag>
                )}
              </div>
              {showDescription && model.description && (
                <div style={{ fontSize: 12, color: '#888', marginTop: 2 }}>
                  {model.description}
                </div>
              )}
            </div>
          </Option>
        ))}
      </Select>
      
      {/* 显示选中模型的能力标签 */}
      {showCapabilities && selectedModel && (
        <div style={{ marginTop: 8 }}>
          <CapabilityTags 
            capabilities={selectedModel.capabilities} 
            recommended={selectedModel.recommended}
          />
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
