import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type PointerEvent as ReactPointerEvent,
} from 'react'
import { theme } from 'antd'

export type MaskEditorTool = 'brush' | 'eraser' | 'polygon'

export interface MaskEditorHandle {
  exportMask: () => Promise<Blob | null>
  clearMask: () => void
  hasMask: () => boolean
}

interface MaskEditorProps {
  backgroundImageUrl: string
  width: number
  height: number
  tool: MaskEditorTool
  brushSize: number
  onMaskStateChange?: (hasMask: boolean) => void
}

const MaskEditor = forwardRef<MaskEditorHandle, MaskEditorProps>(function MaskEditor(
  { backgroundImageUrl, width, height, tool, brushSize, onMaskStateChange },
  ref
) {
  const { token } = theme.useToken()
  const overlayCanvasRef = useRef<HTMLCanvasElement | null>(null)
  const previewCanvasRef = useRef<HTMLCanvasElement | null>(null)
  const maskCanvasRef = useRef<HTMLCanvasElement | null>(null)
  const drawingRef = useRef(false)
  const lastPointRef = useRef<{ x: number; y: number } | null>(null)
  const polygonPointsRef = useRef<Array<{ x: number; y: number }>>([])
  const polygonHoverPointRef = useRef<{ x: number; y: number } | null>(null)
  const [maskPresent, setMaskPresent] = useState(false)
  const [polygonPointCount, setPolygonPointCount] = useState(0)

  useEffect(() => {
    if (!width || !height) return

    const overlayCanvas = overlayCanvasRef.current
    const previewCanvas = previewCanvasRef.current
    if (!overlayCanvas || !previewCanvas) return

    overlayCanvas.width = width
    overlayCanvas.height = height
    previewCanvas.width = width
    previewCanvas.height = height
    const overlayCtx = overlayCanvas.getContext('2d')
    const previewCtx = previewCanvas.getContext('2d')
    if (overlayCtx) {
      overlayCtx.clearRect(0, 0, width, height)
    }
    if (previewCtx) {
      previewCtx.clearRect(0, 0, width, height)
    }

    const maskCanvas = document.createElement('canvas')
    maskCanvas.width = width
    maskCanvas.height = height
    const maskCtx = maskCanvas.getContext('2d')
    if (maskCtx) {
      maskCtx.fillStyle = '#000000'
      maskCtx.fillRect(0, 0, width, height)
    }
    maskCanvasRef.current = maskCanvas
    polygonPointsRef.current = []
    polygonHoverPointRef.current = null
    drawingRef.current = false
    lastPointRef.current = null
    setMaskPresent(false)
    setPolygonPointCount(0)
    onMaskStateChange?.(false)
  }, [width, height, onMaskStateChange])

  useEffect(() => {
    if (tool !== 'polygon') {
      polygonPointsRef.current = []
      polygonHoverPointRef.current = null
      setPolygonPointCount(0)
      const previewCtx = previewCanvasRef.current?.getContext('2d')
      previewCtx?.clearRect(0, 0, width, height)
    }
  }, [tool, width, height])

  const syncMaskState = () => {
    const maskCtx = maskCanvasRef.current?.getContext('2d')
    if (!maskCtx || !width || !height) return
    const data = maskCtx.getImageData(0, 0, width, height).data
    let hasMask = false
    for (let i = 0; i < data.length; i += 4) {
      if (data[i] === 255) {
        hasMask = true
        break
      }
    }
    setMaskPresent(hasMask)
    onMaskStateChange?.(hasMask)
  }

  const getPoint = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    const canvas = overlayCanvasRef.current
    if (!canvas) return null
    const rect = canvas.getBoundingClientRect()
    return {
      x: ((event.clientX - rect.left) / rect.width) * width,
      y: ((event.clientY - rect.top) / rect.height) * height,
    }
  }

  const drawSegment = (from: { x: number; y: number }, to: { x: number; y: number }) => {
    const overlayCtx = overlayCanvasRef.current?.getContext('2d')
    const maskCtx = maskCanvasRef.current?.getContext('2d')
    if (!overlayCtx || !maskCtx) return

    overlayCtx.save()
    overlayCtx.lineCap = 'round'
    overlayCtx.lineJoin = 'round'
    overlayCtx.lineWidth = brushSize

    maskCtx.save()
    maskCtx.lineCap = 'round'
    maskCtx.lineJoin = 'round'
    maskCtx.lineWidth = brushSize

    if (tool === 'brush') {
      overlayCtx.globalCompositeOperation = 'source-over'
      overlayCtx.strokeStyle = 'rgba(255, 122, 69, 0.55)'
      maskCtx.strokeStyle = '#ffffff'
    } else {
      overlayCtx.globalCompositeOperation = 'destination-out'
      overlayCtx.strokeStyle = 'rgba(0, 0, 0, 1)'
      maskCtx.strokeStyle = '#000000'
    }

    overlayCtx.beginPath()
    overlayCtx.moveTo(from.x, from.y)
    overlayCtx.lineTo(to.x, to.y)
    overlayCtx.stroke()
    overlayCtx.restore()

    maskCtx.beginPath()
    maskCtx.moveTo(from.x, from.y)
    maskCtx.lineTo(to.x, to.y)
    maskCtx.stroke()
    maskCtx.restore()
  }

  const redrawPolygonPreview = () => {
    const previewCtx = previewCanvasRef.current?.getContext('2d')
    if (!previewCtx) return

    previewCtx.clearRect(0, 0, width, height)

    const points = polygonPointsRef.current
    if (points.length === 0) return

    previewCtx.save()
    previewCtx.lineWidth = 2
    previewCtx.lineJoin = 'round'
    previewCtx.lineCap = 'round'
    previewCtx.strokeStyle = 'rgba(255, 122, 69, 0.95)'
    previewCtx.fillStyle = 'rgba(255, 122, 69, 0.95)'

    previewCtx.beginPath()
    previewCtx.moveTo(points[0].x, points[0].y)
    points.slice(1).forEach((point) => {
      previewCtx.lineTo(point.x, point.y)
    })
    if (polygonHoverPointRef.current) {
      previewCtx.lineTo(polygonHoverPointRef.current.x, polygonHoverPointRef.current.y)
    }
    previewCtx.stroke()

    points.forEach((point) => {
      previewCtx.beginPath()
      previewCtx.arc(point.x, point.y, 4, 0, Math.PI * 2)
      previewCtx.fill()
    })

    previewCtx.restore()
  }

  const applyPolygonMask = () => {
    const points = polygonPointsRef.current
    if (points.length < 3) return

    const overlayCtx = overlayCanvasRef.current?.getContext('2d')
    const maskCtx = maskCanvasRef.current?.getContext('2d')
    if (!overlayCtx || !maskCtx) return

    overlayCtx.save()
    overlayCtx.globalCompositeOperation = 'source-over'
    overlayCtx.fillStyle = 'rgba(255, 122, 69, 0.55)'
    overlayCtx.beginPath()
    overlayCtx.moveTo(points[0].x, points[0].y)
    points.slice(1).forEach((point) => {
      overlayCtx.lineTo(point.x, point.y)
    })
    overlayCtx.closePath()
    overlayCtx.fill()
    overlayCtx.restore()

    maskCtx.save()
    maskCtx.fillStyle = '#ffffff'
    maskCtx.beginPath()
    maskCtx.moveTo(points[0].x, points[0].y)
    points.slice(1).forEach((point) => {
      maskCtx.lineTo(point.x, point.y)
    })
    maskCtx.closePath()
    maskCtx.fill()
    maskCtx.restore()

    polygonPointsRef.current = []
    polygonHoverPointRef.current = null
    setPolygonPointCount(0)
    redrawPolygonPreview()
    syncMaskState()
  }

  const handlePointerDown = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    const point = getPoint(event)
    if (!point) return
    if (tool === 'polygon') {
      event.currentTarget.focus()
      polygonPointsRef.current = [...polygonPointsRef.current, point]
      polygonHoverPointRef.current = point
      setPolygonPointCount(polygonPointsRef.current.length)
      redrawPolygonPreview()
      return
    }
    drawingRef.current = true
    lastPointRef.current = point
    drawSegment(point, point)
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  const handlePointerMove = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    if (tool === 'polygon') {
      const point = getPoint(event)
      if (!point) return
      polygonHoverPointRef.current = point
      redrawPolygonPreview()
      return
    }
    if (!drawingRef.current || !lastPointRef.current) return
    const point = getPoint(event)
    if (!point) return
    drawSegment(lastPointRef.current, point)
    lastPointRef.current = point
  }

  const finishDrawing = () => {
    drawingRef.current = false
    lastPointRef.current = null
    syncMaskState()
  }

  const handleKeyDown = (event: ReactKeyboardEvent<HTMLCanvasElement>) => {
    if (tool !== 'polygon') return

    if (event.key === 'Enter') {
      if (polygonPointsRef.current.length >= 3) {
        event.preventDefault()
        applyPolygonMask()
      }
    } else if (event.key === 'Escape') {
      polygonPointsRef.current = []
      polygonHoverPointRef.current = null
      setPolygonPointCount(0)
      redrawPolygonPreview()
    }
  }

  useImperativeHandle(ref, () => ({
    exportMask: async () => {
      const canvas = maskCanvasRef.current
      if (!canvas) return null
      return await new Promise<Blob | null>((resolve) => {
        canvas.toBlob((blob) => resolve(blob), 'image/png')
      })
    },
    clearMask: () => {
      const overlayCtx = overlayCanvasRef.current?.getContext('2d')
      const previewCtx = previewCanvasRef.current?.getContext('2d')
      const maskCtx = maskCanvasRef.current?.getContext('2d')
      if (!overlayCtx || !maskCtx) return
      overlayCtx.clearRect(0, 0, width, height)
      previewCtx?.clearRect(0, 0, width, height)
      maskCtx.fillStyle = '#000000'
      maskCtx.fillRect(0, 0, width, height)
      polygonPointsRef.current = []
      polygonHoverPointRef.current = null
      setMaskPresent(false)
      setPolygonPointCount(0)
      onMaskStateChange?.(false)
    },
    hasMask: () => maskPresent,
  }), [height, maskPresent, onMaskStateChange, width])

  if (!backgroundImageUrl || !width || !height) {
    return null
  }

  return (
    <div>
      <div
        style={{
          width: '100%',
          maxWidth: 560,
          position: 'relative',
          borderRadius: 12,
          overflow: 'hidden',
          border: `1px solid ${token.colorBorder}`,
          background: token.colorBgLayout,
        }}
      >
        <img
          src={backgroundImageUrl}
          alt="源视频首帧"
          style={{
            display: 'block',
            width: '100%',
            aspectRatio: `${width} / ${height}`,
            objectFit: 'contain',
            background: token.colorBgContainer,
          }}
        />
        <canvas
          ref={overlayCanvasRef}
          style={{
            position: 'absolute',
            inset: 0,
            width: '100%',
            height: '100%',
            cursor: tool === 'brush' ? 'crosshair' : tool === 'eraser' ? 'cell' : 'copy',
            touchAction: 'none',
          }}
        />
        <canvas
          ref={previewCanvasRef}
          tabIndex={0}
          style={{
            position: 'absolute',
            inset: 0,
            width: '100%',
            height: '100%',
            cursor: tool === 'brush' ? 'crosshair' : tool === 'eraser' ? 'cell' : 'copy',
            touchAction: 'none',
            outline: 'none',
          }}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onKeyDown={handleKeyDown}
          onPointerUp={() => {
            if (tool !== 'polygon') finishDrawing()
          }}
          onPointerLeave={() => {
            if (tool === 'polygon') {
              polygonHoverPointRef.current = null
              redrawPolygonPreview()
            } else if (drawingRef.current) {
              finishDrawing()
            }
          }}
          onPointerCancel={() => {
            if (tool !== 'polygon') finishDrawing()
          }}
        />
      </div>

      <div style={{ marginTop: 8, fontSize: 12, color: token.colorTextSecondary }}>
        画布原始分辨率：{width} × {height}，当前工具：{tool === 'brush' ? '涂抹' : tool === 'eraser' ? '擦除' : '多边形'}，{tool === 'polygon' ? `已打点：${polygonPointCount}` : `当前笔刷：${brushSize}px`}，已绘制：{maskPresent ? '是' : '否'}
      </div>
      <div style={{ marginTop: 4, fontSize: 12, color: token.colorTextSecondary }}>
        {tool === 'polygon'
          ? '点击逐点连线，按 Enter 闭环填充，按 Esc 取消当前未闭合多边形。'
          : '白色区域会被编辑，未涂抹区域保持不变。'}
      </div>
    </div>
  )
})

export default MaskEditor
