import { Button, Space, theme } from 'antd'
import { DeleteOutlined } from '@ant-design/icons'
import React, { useEffect, useMemo, useRef, useState } from 'react'

interface BBoxEditorProps {
  imageUrl: string
  value?: number[][]
  onChange?: (boxes: number[][]) => void
  maxBoxes?: number
}

type ResizeHandle = 'nw' | 'n' | 'ne' | 'e' | 'se' | 's' | 'sw' | 'w'

interface InteractionState {
  mode: 'draw' | 'move' | 'resize'
  index: number
  startX: number
  startY: number
  box: number[]
  originBox?: number[]
  handle?: ResizeHandle
}

const MIN_BOX_SIZE = 8

const HANDLE_POSITIONS: Array<{ handle: ResizeHandle; left: string; top: string; cursor: string }> = [
  { handle: 'nw', left: '-5px', top: '-5px', cursor: 'nwse-resize' },
  { handle: 'n', left: 'calc(50% - 5px)', top: '-5px', cursor: 'ns-resize' },
  { handle: 'ne', left: 'calc(100% - 5px)', top: '-5px', cursor: 'nesw-resize' },
  { handle: 'e', left: 'calc(100% - 5px)', top: 'calc(50% - 5px)', cursor: 'ew-resize' },
  { handle: 'se', left: 'calc(100% - 5px)', top: 'calc(100% - 5px)', cursor: 'nwse-resize' },
  { handle: 's', left: 'calc(50% - 5px)', top: 'calc(100% - 5px)', cursor: 'ns-resize' },
  { handle: 'sw', left: '-5px', top: 'calc(100% - 5px)', cursor: 'nesw-resize' },
  { handle: 'w', left: '-5px', top: 'calc(50% - 5px)', cursor: 'ew-resize' },
]

const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max)

const normalizeBox = (box: number[]) => {
  const [x1, y1, x2, y2] = box.map((item) => Math.round(item))
  const left = Math.min(x1, x2)
  const right = Math.max(x1, x2)
  const top = Math.min(y1, y2)
  const bottom = Math.max(y1, y2)
  return [left, top, right, bottom]
}

const clampBoxToBounds = (box: number[], width: number, height: number) => {
  const [left, top, right, bottom] = normalizeBox(box)
  return [
    clamp(left, 0, width),
    clamp(top, 0, height),
    clamp(right, 0, width),
    clamp(bottom, 0, height),
  ]
}

const getBoxSize = (box: number[]) => ({
  width: Math.abs(box[2] - box[0]),
  height: Math.abs(box[3] - box[1]),
})

const BBoxEditor: React.FC<BBoxEditorProps> = ({
  imageUrl,
  value = [],
  onChange,
  maxBoxes = 2,
}) => {
  const { token } = theme.useToken()
  const containerRef = useRef<HTMLDivElement | null>(null)
  const imageRef = useRef<HTMLImageElement | null>(null)
  const [imageSize, setImageSize] = useState({ width: 0, height: 0 })
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null)
  const [interaction, setInteraction] = useState<InteractionState | null>(null)

  useEffect(() => {
    if (selectedIndex !== null && selectedIndex >= value.length) {
      setSelectedIndex(value.length ? value.length - 1 : null)
    }
  }, [selectedIndex, value.length])

  const getImagePoint = (clientX: number, clientY: number) => {
    const image = imageRef.current
    if (!image || imageSize.width === 0 || imageSize.height === 0) return null
    const rect = image.getBoundingClientRect()
    if (!rect.width || !rect.height) return null
    return {
      x: clamp(((clientX - rect.left) / rect.width) * imageSize.width, 0, imageSize.width),
      y: clamp(((clientY - rect.top) / rect.height) * imageSize.height, 0, imageSize.height),
      rect,
    }
  }

  const updateInteractionBox = (event: MouseEvent) => {
    const point = getImagePoint(event.clientX, event.clientY)
    if (!point || !interaction) return

    if (interaction.mode === 'draw') {
      setInteraction({
        ...interaction,
        box: clampBoxToBounds([interaction.startX, interaction.startY, point.x, point.y], imageSize.width, imageSize.height),
      })
      return
    }

    if (!interaction.originBox) return

    const deltaX = point.x - interaction.startX
    const deltaY = point.y - interaction.startY
    let nextBox = [...interaction.originBox]

    if (interaction.mode === 'move') {
      const boxWidth = interaction.originBox[2] - interaction.originBox[0]
      const boxHeight = interaction.originBox[3] - interaction.originBox[1]
      const left = clamp(interaction.originBox[0] + deltaX, 0, imageSize.width - boxWidth)
      const top = clamp(interaction.originBox[1] + deltaY, 0, imageSize.height - boxHeight)
      nextBox = [left, top, left + boxWidth, top + boxHeight]
    } else if (interaction.mode === 'resize' && interaction.handle) {
      nextBox = [...interaction.originBox]
      if (interaction.handle.includes('w')) nextBox[0] = interaction.originBox[0] + deltaX
      if (interaction.handle.includes('e')) nextBox[2] = interaction.originBox[2] + deltaX
      if (interaction.handle.includes('n')) nextBox[1] = interaction.originBox[1] + deltaY
      if (interaction.handle.includes('s')) nextBox[3] = interaction.originBox[3] + deltaY
      nextBox = clampBoxToBounds(nextBox, imageSize.width, imageSize.height)
      const normalized = normalizeBox(nextBox)
      const { width, height } = getBoxSize(normalized)
      if (width < MIN_BOX_SIZE || height < MIN_BOX_SIZE) {
        nextBox = interaction.box
      } else {
        nextBox = normalized
      }
    }

    setInteraction({
      ...interaction,
      box: nextBox,
    })
  }

  const commitInteraction = () => {
    if (!interaction) return
    const normalizedBox = normalizeBox(interaction.box)
    const { width, height } = getBoxSize(normalizedBox)

    if (width < MIN_BOX_SIZE || height < MIN_BOX_SIZE) {
      setInteraction(null)
      return
    }

    if (interaction.mode === 'draw') {
      if (value.length >= maxBoxes) {
        setInteraction(null)
        return
      }
      const nextBoxes = [...value, normalizedBox]
      onChange?.(nextBoxes)
      setSelectedIndex(nextBoxes.length - 1)
    } else if (interaction.index >= 0) {
      const normalizedOrigin = normalizeBox(interaction.originBox || [])
      if (
        normalizedOrigin[0] === normalizedBox[0] &&
        normalizedOrigin[1] === normalizedBox[1] &&
        normalizedOrigin[2] === normalizedBox[2] &&
        normalizedOrigin[3] === normalizedBox[3]
      ) {
        setSelectedIndex(interaction.index)
        setInteraction(null)
        return
      }
      const nextBoxes = value.map((box, index) => (
        index === interaction.index ? normalizedBox : box
      ))
      onChange?.(nextBoxes)
      setSelectedIndex(interaction.index)
    }

    setInteraction(null)
  }

  useEffect(() => {
    if (!interaction) return

    const handleMouseMove = (event: MouseEvent) => {
      updateInteractionBox(event)
    }

    const handleMouseUp = () => {
      commitInteraction()
    }

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [interaction, value])

  const workingBoxes = useMemo(() => {
    if (!interaction) return value
    if (interaction.mode === 'draw') {
      return [...value, interaction.box]
    }
    return value.map((box, index) => (
      index === interaction.index ? interaction.box : box
    ))
  }, [interaction, value])

  const displayBoxes = useMemo(() => {
    if (!imageRef.current || imageSize.width === 0 || imageSize.height === 0) return []
    const renderedWidth = imageRef.current.clientWidth
    const renderedHeight = imageRef.current.clientHeight
    const scaleX = renderedWidth / imageSize.width
    const scaleY = renderedHeight / imageSize.height
    return workingBoxes.map((box) => {
      const normalized = normalizeBox(box)
      return {
        left: normalized[0] * scaleX,
        top: normalized[1] * scaleY,
        width: (normalized[2] - normalized[0]) * scaleX,
        height: (normalized[3] - normalized[1]) * scaleY,
      }
    })
  }, [imageSize.height, imageSize.width, workingBoxes])

  const handleBackgroundMouseDown = (event: React.MouseEvent<HTMLDivElement>) => {
    if (value.length >= maxBoxes) {
      containerRef.current?.focus()
      setSelectedIndex(null)
      return
    }
    const point = getImagePoint(event.clientX, event.clientY)
    if (!point) return
    containerRef.current?.focus()
    setSelectedIndex(null)
    setInteraction({
      mode: 'draw',
      index: value.length,
      startX: point.x,
      startY: point.y,
      box: [point.x, point.y, point.x, point.y],
    })
  }

  const handleBoxMouseDown = (index: number, event: React.MouseEvent<HTMLDivElement>) => {
    event.stopPropagation()
    const point = getImagePoint(event.clientX, event.clientY)
    if (!point) return
    containerRef.current?.focus()
    setSelectedIndex(index)
    setInteraction({
      mode: 'move',
      index,
      startX: point.x,
      startY: point.y,
      box: [...value[index]],
      originBox: [...value[index]],
    })
  }

  const handleResizeMouseDown = (index: number, handle: ResizeHandle, event: React.MouseEvent<HTMLDivElement>) => {
    event.stopPropagation()
    const point = getImagePoint(event.clientX, event.clientY)
    if (!point) return
    containerRef.current?.focus()
    setSelectedIndex(index)
    setInteraction({
      mode: 'resize',
      index,
      handle,
      startX: point.x,
      startY: point.y,
      box: [...value[index]],
      originBox: [...value[index]],
    })
  }

  const handleDeleteSelected = () => {
    if (selectedIndex === null) return
    onChange?.(value.filter((_, index) => index !== selectedIndex))
    setSelectedIndex((current) => {
      if (current === null) return null
      if (value.length <= 1) return null
      return Math.max(0, current - 1)
    })
  }

  const selectedBox = selectedIndex !== null ? normalizeBox(value[selectedIndex] || []) : null

  return (
    <div>
      <div
        ref={containerRef}
        tabIndex={0}
        style={{
          position: 'relative',
          border: `1px solid ${token.colorBorder}`,
          borderRadius: 8,
          overflow: 'hidden',
          background: token.colorBgLayout,
          userSelect: 'none',
          cursor: value.length >= maxBoxes ? 'default' : 'crosshair',
          outline: 'none',
        }}
        onMouseDown={handleBackgroundMouseDown}
        onKeyDown={(event) => {
          if ((event.key === 'Delete' || event.key === 'Backspace') && selectedIndex !== null) {
            event.preventDefault()
            handleDeleteSelected()
          }
          if (event.key === 'Escape') {
            setInteraction(null)
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
            onMouseDown={(event) => handleBoxMouseDown(index, event)}
            style={{
              position: 'absolute',
              left: box.left,
              top: box.top,
              width: box.width,
              height: box.height,
              border: selectedIndex === index ? '2px solid #1677ff' : '2px solid #ff4d4f',
              background: selectedIndex === index ? 'rgba(22,119,255,0.12)' : 'rgba(255,77,79,0.12)',
              cursor: 'move',
            }}
          >
            <div
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                background: selectedIndex === index ? '#1677ff' : '#ff4d4f',
                color: '#fff',
                padding: '0 4px',
                fontSize: 10,
                lineHeight: '18px',
              }}
            >
              框 {index + 1}
            </div>
            {selectedIndex === index && HANDLE_POSITIONS.map((item) => (
              <div
                key={item.handle}
                onMouseDown={(event) => handleResizeMouseDown(index, item.handle, event)}
                style={{
                  position: 'absolute',
                  left: item.left,
                  top: item.top,
                  width: 10,
                  height: 10,
                  borderRadius: 999,
                  background: '#fff',
                  border: '1px solid #1677ff',
                  cursor: item.cursor,
                }}
              />
            ))}
          </div>
        ))}
      </div>
      <div style={{ marginTop: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
        <div style={{ color: token.colorTextSecondary, fontSize: 12 }}>
          当前 {value.length}/{maxBoxes} 个框。拖拽空白区域新增框，点击已有框后可移动、缩放、按 Delete 删除。
          {selectedBox && (
            <div style={{ marginTop: 4 }}>
              已选框坐标：[{selectedBox[0]}, {selectedBox[1]}, {selectedBox[2]}, {selectedBox[3]}]
            </div>
          )}
        </div>
        <Space size={8}>
          <Button size="small" icon={<DeleteOutlined />} disabled={selectedIndex === null} onClick={handleDeleteSelected}>
            删除选中框
          </Button>
          {value.length > 0 && (
            <Button size="small" onClick={() => { onChange?.([]); setSelectedIndex(null) }}>
              清空
            </Button>
          )}
        </Space>
      </div>
    </div>
  )
}

export default BBoxEditor
