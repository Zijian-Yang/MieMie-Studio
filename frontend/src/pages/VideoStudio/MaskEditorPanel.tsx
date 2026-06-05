import type { RefObject } from 'react'
import { Button, Typography, theme } from 'antd'
import MaskEditor, { type MaskEditorHandle, type MaskEditorTool } from './MaskEditor'
import VideoFieldLabel from './VideoFieldLabel'
import type { HelpContent } from '../../services/api'

const { Text } = Typography
const MASK_BRUSH_SIZES = [8, 16, 32, 64]

export interface SourceVideoMetadata {
  width: number
  height: number
  fps: number
  duration: number
  frame_count: number
  file_size: number
  format: string
  warnings: string[]
}

interface MaskEditorPanelProps {
  isEditMode: boolean
  existingMaskImageUrl: string
  sourceVideoWarnings: string[]
  sourceVideoPreviewDataUrl: string
  sourceVideoMetadata: SourceVideoMetadata | null
  maskTool: MaskEditorTool
  maskBrushSize: number
  maskEditorRef: RefObject<MaskEditorHandle>
  maskHelp?: HelpContent | string
  onMaskToolChange: (tool: MaskEditorTool) => void
  onMaskBrushSizeChange: (size: number) => void
  onMaskContentChange: (hasContent: boolean) => void
}

const MaskEditorPanel = ({
  isEditMode,
  existingMaskImageUrl,
  sourceVideoWarnings,
  sourceVideoPreviewDataUrl,
  sourceVideoMetadata,
  maskTool,
  maskBrushSize,
  maskEditorRef,
  maskHelp,
  onMaskToolChange,
  onMaskBrushSizeChange,
  onMaskContentChange,
}: MaskEditorPanelProps) => {
  const { token } = theme.useToken()

  if (isEditMode) {
    return (
      <div style={{ marginBottom: 16 }}>
        <div style={{ marginBottom: 8 }}><VideoFieldLabel label="局部编辑 Mask" help={maskHelp} /></div>
        <div style={{ marginBottom: 12, padding: 12, borderRadius: 8, background: token.colorBgLayout }}>
          <Text type="secondary">编辑模式会复用任务已有的 Mask，本阶段不支持重新绘制。</Text>
        </div>
        {existingMaskImageUrl ? (
          <img
            src={existingMaskImageUrl}
            alt="局部编辑蒙版"
            style={{ width: '100%', borderRadius: 8, objectFit: 'contain', background: token.colorBgLayout }}
          />
        ) : (
          <div style={{ padding: 16, borderRadius: 8, background: token.colorWarningBg, color: token.colorWarningText }}>
            当前任务没有可复用的蒙版，无法在编辑模式下修改。请重新创建局部编辑任务。
          </div>
        )}
      </div>
    )
  }

  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ marginBottom: 8 }}><VideoFieldLabel label="局部编辑 Mask" help={maskHelp} required /></div>
      <div style={{ marginBottom: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <Button type={maskTool === 'brush' ? 'primary' : 'default'} onClick={() => onMaskToolChange('brush')}>画笔</Button>
        <Button type={maskTool === 'polygon' ? 'primary' : 'default'} onClick={() => onMaskToolChange('polygon')}>多边形</Button>
        <Button type={maskTool === 'eraser' ? 'primary' : 'default'} onClick={() => onMaskToolChange('eraser')}>橡皮擦</Button>
        {MASK_BRUSH_SIZES.map((sizeValue) => (
          <Button
            key={sizeValue}
            type={maskBrushSize === sizeValue ? 'primary' : 'default'}
            onClick={() => onMaskBrushSizeChange(sizeValue)}
            disabled={maskTool === 'polygon'}
          >
            {sizeValue}px
          </Button>
        ))}
        <Button onClick={() => {
          maskEditorRef.current?.clearMask()
          onMaskContentChange(false)
        }}>
          清空蒙版
        </Button>
      </div>
      {sourceVideoWarnings.length > 0 && (
        <div style={{ marginBottom: 8, padding: 10, borderRadius: 8, background: token.colorWarningBg }}>
          {sourceVideoWarnings.map((warning, index) => (
            <div key={index} style={{ fontSize: 12, color: token.colorWarningText }}>{warning}</div>
          ))}
        </div>
      )}
      {sourceVideoPreviewDataUrl && sourceVideoMetadata ? (
        <MaskEditor
          ref={maskEditorRef}
          backgroundImageUrl={sourceVideoPreviewDataUrl}
          width={sourceVideoMetadata.width}
          height={sourceVideoMetadata.height}
          tool={maskTool}
          brushSize={maskBrushSize}
          onMaskStateChange={onMaskContentChange}
        />
      ) : (
        <div style={{ padding: 16, borderRadius: 8, background: token.colorBgLayout, color: token.colorTextSecondary }}>
          选择源视频后，系统会提取首帧并显示可编辑区域。
        </div>
      )}
    </div>
  )
}

export default MaskEditorPanel
