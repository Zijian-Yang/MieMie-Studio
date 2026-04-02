import { Button, Space, theme } from 'antd'
import { DeleteOutlined } from '@ant-design/icons'
import React, { useMemo, useRef, useState } from 'react'

interface BBoxEditorProps {
  imageUrl: string
  value?: number[][]
  onChange?: (boxes: number[][]) => void
  maxBoxes?: number
}

interface DraftBox {
  startX: number
  startY: number
  currentX: number
  currentY: number
}

const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max)

const BBoxEditor: React.FC<BBoxEditorProps> = ({
  imageUrl,
  value = [],
  onChange,
  maxBoxes = 2,
}) => {
  const { token } = theme.useToken()
  const containerRef = useRef<HTMLDivElement | null>(null)
  const imageRef = useRef<HTMLImageElement | null>(null)
  const [draftBox, setDraftBox] = useState<DraftBox | null>(null)
  const [imageSize, setImageSize] = useState({ width: 0, height: 0 })

  const displayBoxes = useMemo(() => {
    if (!imageRef.current || imageSize.width === 0 || imageSize.height === 0) return []
    const renderedWidth = imageRef.current.clientWidth
    const renderedHeight = imageRef.current.clientHeight
    const scaleX = renderedWidth / imageSize.width
    const scaleY = renderedHeight / imageSize.height
    return value.map((box) => ({
      left: box[0] * scaleX,
      top: box[1] * scaleY,
      width: (box[2] - box[0]) * scaleX,
      height: (box[3] - box[1]) * scaleY,
    }))
  }, [imageSize.height, imageSize.width, value])

  const getRelativePoint = (clientX: number, clientY: number) => {
    const image = imageRef.current
    if (!image) return null
    const rect = image.getBoundingClientRect()
    if (rect.width === 0 || rect.height === 0) return null
    return {
      x: clamp(clientX - rect.left, 0, rect.width),
      y: clamp(clientY - rect.top, 0, rect.height),
      rect,
    }
  }

  const handleMouseDown = (event: React.MouseEvent<HTMLDivElement>) => {
    if (value.length >= maxBoxes) return
    const point = getRelativePoint(event.clientX, event.clientY)
    if (!point) return
    setDraftBox({
      startX: point.x,
      startY: point.y,
      currentX: point.x,
      currentY: point.y,
    })
  }

  const handleMouseMove = (event: React.MouseEvent<HTMLDivElement>) => {
    if (!draftBox) return
    const point = getRelativePoint(event.clientX, event.clientY)
    if (!point) return
    setDraftBox({
      ...draftBox,
      currentX: point.x,
      currentY: point.y,
    })
  }

  const handleMouseUp = () => {
    if (!draftBox || !imageRef.current || imageSize.width === 0 || imageSize.height === 0) {
      setDraftBox(null)
      return
    }

    const renderedWidth = imageRef.current.clientWidth
    const renderedHeight = imageRef.current.clientHeight
    const scaleX = imageSize.width / renderedWidth
    const scaleY = imageSize.height / renderedHeight

    const left = Math.min(draftBox.startX, draftBox.currentX)
    const top = Math.min(draftBox.startY, draftBox.currentY)
    const right = Math.max(draftBox.startX, draftBox.currentX)
    const bottom = Math.max(draftBox.startY, draftBox.currentY)

    if (Math.abs(right - left) < 8 || Math.abs(bottom - top) < 8) {
      setDraftBox(null)
      return
    }

    const nextBoxes = [
      ...value,
      [
        Math.round(left * scaleX),
        Math.round(top * scaleY),
        Math.round(right * scaleX),
        Math.round(bottom * scaleY),
      ],
    ]
    onChange?.(nextBoxes)
    setDraftBox(null)
  }

  const draftStyle = useMemo(() => {
    if (!draftBox) return null
    const left = Math.min(draftBox.startX, draftBox.currentX)
    const top = Math.min(draftBox.startY, draftBox.currentY)
    return {
      left,
      top,
      width: Math.abs(draftBox.currentX - draftBox.startX),
      height: Math.abs(draftBox.currentY - draftBox.startY),
    }
  }, [draftBox])

  return (
    <div>
      <div
        ref={containerRef}
        style={{
          position: 'relative',
          border: `1px solid ${token.colorBorder}`,
          borderRadius: 8,
          overflow: 'hidden',
          background: token.colorBgLayout,
          userSelect: 'none',
          cursor: value.length >= maxBoxes ? 'default' : 'crosshair',
        }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={() => {
          if (draftBox) {
            handleMouseUp()
          }
        }}
      >
        <img
          ref={imageRef}
          src={imageUrl}
          alt="bbox"
          style={{ display: 'block', width: '100%', maxHeight: 360, objectFit: 'contain' }}
          onLoad={(event) => {
            setImageSize({
              width: event.currentTarget.naturalWidth,
              height: event.currentTarget.naturalHeight,
            })
          }}
        />
        {displayBoxes.map((box, index) => (
          <div
            key={`${box.left}-${box.top}-${index}`}
            style={{
              position: 'absolute',
              left: box.left,
              top: box.top,
              width: box.width,
              height: box.height,
              border: '2px solid #ff4d4f',
              background: 'rgba(255,77,79,0.12)',
            }}
          >
            <div
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                background: '#ff4d4f',
                color: '#fff',
                padding: '0 4px',
                fontSize: 10,
                lineHeight: '18px',
              }}
            >
              框 {index + 1}
            </div>
          </div>
        ))}
        {draftStyle && (
          <div
            style={{
              position: 'absolute',
              ...draftStyle,
              border: '2px dashed #1677ff',
              background: 'rgba(22,119,255,0.12)',
            }}
          />
        )}
      </div>
      <div style={{ marginTop: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ color: token.colorTextSecondary, fontSize: 12 }}>
          当前 {value.length}/{maxBoxes} 个框。拖拽图片区域可新增框选。
        </div>
        <Space size={8}>
          {value.map((_, index) => (
            <Button
              key={`del-${index}`}
              size="small"
              icon={<DeleteOutlined />}
              onClick={() => onChange?.(value.filter((__, boxIndex) => boxIndex !== index))}
            >
              删除框 {index + 1}
            </Button>
          ))}
          {value.length > 0 && (
            <Button size="small" onClick={() => onChange?.([])}>
              清空
            </Button>
          )}
        </Space>
      </div>
    </div>
  )
}

export default BBoxEditor
