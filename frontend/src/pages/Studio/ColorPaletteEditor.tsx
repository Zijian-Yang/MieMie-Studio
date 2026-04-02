import { Button, InputNumber, Space, theme } from 'antd'
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons'
import type { ColorPaletteItem } from '../../services/api'

interface ColorPaletteEditorProps {
  value?: ColorPaletteItem[]
  onChange?: (items: ColorPaletteItem[]) => void
}

const DEFAULT_COLORS: ColorPaletteItem[] = [
  { hex: '#C2D1E6', ratio: '34.00%' },
  { hex: '#C0B5B4', ratio: '33.00%' },
  { hex: '#636574', ratio: '33.00%' },
]

const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max)

const ColorPaletteEditor = ({ value = DEFAULT_COLORS, onChange }: ColorPaletteEditorProps) => {
  const { token } = theme.useToken()
  const items = value.length > 0 ? value : DEFAULT_COLORS
  const total = items.reduce((sum, item) => sum + (Number(item.ratio.replace('%', '')) || 0), 0)

  const updateItem = (index: number, patch: Partial<ColorPaletteItem>) => {
    const next = items.map((item, itemIndex) => (
      itemIndex === index ? { ...item, ...patch } : item
    ))
    onChange?.(next)
  }

  return (
    <div>
      <div style={{ display: 'grid', gap: 8 }}>
        {items.map((item, index) => (
          <div
            key={`${item.hex}-${index}`}
            style={{
              display: 'grid',
              gridTemplateColumns: '48px 120px 1fr 56px',
              gap: 8,
              alignItems: 'center',
            }}
          >
            <input
              type="color"
              value={item.hex}
              onChange={(event) => updateItem(index, { hex: event.target.value.toUpperCase() })}
              style={{ width: 48, height: 32, border: `1px solid ${token.colorBorder}`, borderRadius: 6 }}
            />
            <input
              value={item.hex}
              onChange={(event) => updateItem(index, { hex: event.target.value })}
              style={{
                height: 32,
                padding: '0 8px',
                borderRadius: 6,
                border: `1px solid ${token.colorBorder}`,
              }}
            />
            <InputNumber
              min={0}
              max={100}
              step={0.01}
              style={{ width: '100%' }}
              value={Number(item.ratio.replace('%', '')) || 0}
              onChange={(num) => {
                const nextValue = clamp(Number(num || 0), 0, 100).toFixed(2)
                updateItem(index, { ratio: `${nextValue}%` })
              }}
              addonAfter="%"
            />
            <Button
              icon={<DeleteOutlined />}
              disabled={items.length <= 3}
              onClick={() => onChange?.(items.filter((_, itemIndex) => itemIndex !== index))}
            />
          </div>
        ))}
      </div>
      <div style={{ marginTop: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ color: total === 100 ? token.colorSuccess : token.colorWarning, fontSize: 12 }}>
          当前总和：{total.toFixed(2)}%。需保持 3-10 种颜色，比例总和精确为 100.00%。
        </div>
        <Space size={8}>
          <Button
            size="small"
            icon={<PlusOutlined />}
            disabled={items.length >= 10}
            onClick={() => onChange?.([...items, { hex: '#FFFFFF', ratio: '0.00%' }])}
          >
            添加颜色
          </Button>
          <Button size="small" onClick={() => onChange?.(DEFAULT_COLORS)}>
            重置示例
          </Button>
        </Space>
      </div>
    </div>
  )
}

export default ColorPaletteEditor
