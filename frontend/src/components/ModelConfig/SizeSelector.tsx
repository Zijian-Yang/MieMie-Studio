/**
 * 尺寸选择器组件
 * 
 * 根据模型ID自动获取可用尺寸选项，并验证尺寸是否符合约束。
 * 
 * 使用示例：
 * ```tsx
 * <SizeSelector 
 *   modelId="wan2.6-t2i"
 *   value={selectedSize}
 *   onChange={setSelectedSize}
 * />
 * ```
 */

import React from 'react'
import { Select, Space, Tag, Tooltip } from 'antd'
import { InfoCircleOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons'
import { useModelRegistryStore } from '../../stores/modelRegistryStore'
import { SizeOption } from '../../services/api'

const { Option } = Select

interface SizeSelectorProps {
  /** 模型ID，用于获取该模型支持的尺寸选项 */
  modelId: string
  /** 当前选中的尺寸值 (格式: "width*height") */
  value?: string
  /** 尺寸变化回调 */
  onChange?: (value: string, sizeOption?: SizeOption) => void
  /** 手动传入尺寸选项（如果传入则不从 store 获取） */
  sizes?: SizeOption[]
  /** 是否显示像素信息 */
  showPixelInfo?: boolean
  /** 是否显示宽高比标签 */
  showAspectRatio?: boolean
  /** 是否显示验证状态 */
  showValidation?: boolean
  /** 禁用状态 */
  disabled?: boolean
  /** 占位符 */
  placeholder?: string
  /** 是否允许清空 */
  allowClear?: boolean
  /** 样式 */
  style?: React.CSSProperties
  /** Select 尺寸 */
  size?: 'small' | 'middle' | 'large'
}

const SizeSelector: React.FC<SizeSelectorProps> = ({
  modelId,
  value,
  onChange,
  sizes: propSizes,
  showPixelInfo = true,
  showAspectRatio = true,
  showValidation = true,
  disabled = false,
  placeholder = '选择尺寸',
  allowClear = false,
  style,
  size,
}) => {
  const { getSizeOptions, validateSize, getModel } = useModelRegistryStore()
  
  // 获取尺寸选项
  const sizeOptions = propSizes || getSizeOptions(modelId)
  
  // 获取模型信息（用于显示约束）
  const model = getModel(modelId)
  
  // 验证当前选中的尺寸
  const validation = React.useMemo(() => {
    if (!value || !showValidation) return { valid: true, message: '' }
    const [w, h] = value.split('*').map(Number)
    if (!w || !h) return { valid: true, message: '' }
    return validateSize(modelId, w, h)
  }, [modelId, value, showValidation, validateSize])
  
  const handleChange = (sizeValue: string) => {
    const option = sizeOptions.find(s => s.value === sizeValue)
    onChange?.(sizeValue, option)
  }
  
  // 获取选中的尺寸信息
  const selectedSize = React.useMemo(() => {
    if (!value) return undefined
    return sizeOptions.find(s => s.value === value)
  }, [value, sizeOptions])
  
  // 格式化像素数
  const formatPixels = (pixels: number) => {
    if (pixels >= 1000000) {
      return `${(pixels / 1000000).toFixed(2)}M`
    }
    return pixels.toLocaleString()
  }
  
  if (!modelId) {
    return (
      <Select
        disabled
        placeholder="请先选择模型"
        style={{ width: '100%', ...style }}
        size={size}
      />
    )
  }
  
  if (sizeOptions.length === 0) {
    return (
      <Select
        disabled
        placeholder="该模型无尺寸选项"
        style={{ width: '100%', ...style }}
        size={size}
      />
    )
  }
  
  return (
    <div>
      <Select
        value={value}
        onChange={handleChange}
        disabled={disabled}
        placeholder={placeholder}
        allowClear={allowClear}
        style={{ width: '100%', ...style }}
        status={showValidation && !validation.valid ? 'error' : undefined}
        size={size}
      >
        {sizeOptions.map((sizeOpt) => {
          const pixels = sizeOpt.width * sizeOpt.height
          return (
            <Option 
              key={sizeOpt.value} 
              value={sizeOpt.value}
              label={sizeOpt.label}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span>{sizeOpt.label}</span>
                <Space size={4}>
                  {showAspectRatio && sizeOpt.aspect_ratio && (
                    <Tag color="blue" style={{ margin: 0 }}>
                      {sizeOpt.aspect_ratio}
                    </Tag>
                  )}
                  {showPixelInfo && (
                    <span style={{ fontSize: 11, color: '#888' }}>
                      {formatPixels(pixels)} px
                    </span>
                  )}
                </Space>
              </div>
            </Option>
          )
        })}
      </Select>
      
      {/* 显示选中尺寸的详细信息 */}
      {selectedSize && showPixelInfo && (
        <div style={{ marginTop: 4, fontSize: 12, color: '#888' }}>
          <Space size={8}>
            <span>{selectedSize.width} × {selectedSize.height}</span>
            <span>({formatPixels(selectedSize.width * selectedSize.height)} 像素)</span>
            {validation.valid ? (
              <span style={{ color: '#52c41a' }}>
                <CheckCircleOutlined /> 符合要求
              </span>
            ) : (
              <span style={{ color: '#ff4d4f' }}>
                <CloseCircleOutlined /> {validation.message}
              </span>
            )}
          </Space>
        </div>
      )}
      
      {/* 显示尺寸约束提示 */}
      {model?.size_constraints && (
        <div style={{ marginTop: 4, fontSize: 11, color: '#999' }}>
          <Tooltip title={`总像素范围: ${model.size_constraints.min_pixels?.toLocaleString() || '无'} - ${model.size_constraints.max_pixels?.toLocaleString() || '无'}`}>
            <InfoCircleOutlined style={{ marginRight: 4 }} />
            像素约束: {formatPixels(model.size_constraints.min_pixels || 0)} - {formatPixels(model.size_constraints.max_pixels || 0)}
          </Tooltip>
        </div>
      )}
      
      {/* 验证错误提示 */}
      {showValidation && !validation.valid && (
        <div style={{ marginTop: 4, color: '#ff4d4f', fontSize: 12 }}>
          ⚠️ {validation.message}
        </div>
      )}
    </div>
  )
}

export default SizeSelector
