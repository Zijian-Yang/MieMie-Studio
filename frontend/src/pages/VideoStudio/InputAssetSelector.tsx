import { Select, Space, Spin, theme } from 'antd'
import { VideoCameraOutlined } from '@ant-design/icons'
import type {
  AudioItem,
  GalleryImage,
  HelpContent,
  VideoInputRole,
  VideoTaskKind,
  VideoLibraryItem,
} from '../../services/api'
import type { SourceVideoMetadata } from './MaskEditorPanel'
import VideoFieldLabel from './VideoFieldLabel'

interface InputAssetSelectorProps {
  role: VideoInputRole
  taskKind: VideoTaskKind
  isEditMode: boolean
  galleryImages: GalleryImage[]
  audioItems: AudioItem[]
  videoLibraryItems: VideoLibraryItem[]
  firstFrameUrl: string
  lastFrameUrl: string
  referenceFirstFrameUrl: string
  audioUrl: string
  firstClipUrl: string
  baseVideoUrl: string
  sourceVideoUrl: string
  sourceVideoPreparing: boolean
  sourceVideoMetadata: SourceVideoMetadata | null
  getAssetHelp: (role: VideoInputRole) => HelpContent | string | undefined
  onFirstFrameChange: (url: string) => void
  onLastFrameChange: (url: string) => void
  onReferenceFirstFrameChange: (url: string) => void
  onAudioChange: (url: string) => void
  onFirstClipChange: (url: string) => void
  onBaseVideoChange: (url: string) => void
  onSourceVideoChange: (url: string) => void
  onPrepareSourceVideo: (url: string) => void
}

const InputAssetSelector = ({
  role,
  taskKind,
  isEditMode,
  galleryImages,
  audioItems,
  videoLibraryItems,
  firstFrameUrl,
  lastFrameUrl,
  referenceFirstFrameUrl,
  audioUrl,
  firstClipUrl,
  baseVideoUrl,
  sourceVideoUrl,
  sourceVideoPreparing,
  sourceVideoMetadata,
  getAssetHelp,
  onFirstFrameChange,
  onLastFrameChange,
  onReferenceFirstFrameChange,
  onAudioChange,
  onFirstClipChange,
  onBaseVideoChange,
  onSourceVideoChange,
  onPrepareSourceVideo,
}: InputAssetSelectorProps) => {
  const { token } = theme.useToken()

  if (role === 'first_frame') {
    const required = taskKind !== 'reference_to_video'
    return (
      <div style={{ marginBottom: 16 }}>
        <div style={{ marginBottom: 8 }}>
          <VideoFieldLabel label="首帧图" help={getAssetHelp('first_frame')} required={required} />
          {!required && <span style={{ marginLeft: 6, color: token.colorTextSecondary }}>（可选）</span>}
        </div>
        <Select
          style={{ width: '100%' }}
          value={(taskKind === 'reference_to_video' ? referenceFirstFrameUrl : firstFrameUrl) || undefined}
          onChange={(value) => {
            if (taskKind === 'reference_to_video') onReferenceFirstFrameChange(value || '')
            else onFirstFrameChange(value || '')
          }}
          placeholder="从图库选择图片"
          allowClear
          optionLabelProp="label"
        >
          {galleryImages.map((image) => (
            <Select.Option key={image.id} value={image.url} label={image.name}>
              <Space>
                <img src={image.url} alt="" style={{ width: 32, height: 32, objectFit: 'cover', borderRadius: 4 }} />
                {image.name}
              </Space>
            </Select.Option>
          ))}
        </Select>
      </div>
    )
  }

  if (role === 'last_frame') {
    const required = taskKind === 'keyframe_to_video'
    return (
      <div style={{ marginBottom: 16 }}>
        <div style={{ marginBottom: 8 }}>
          <VideoFieldLabel label="尾帧图" help={getAssetHelp('last_frame')} required={required} />
          {!required && <span style={{ marginLeft: 6, color: token.colorTextSecondary }}>（可选）</span>}
        </div>
        <Select
          style={{ width: '100%' }}
          value={lastFrameUrl || undefined}
          onChange={(value) => onLastFrameChange(value || '')}
          placeholder={required ? '从图库选择尾帧图' : '从图库选择尾帧图（可选）'}
          optionLabelProp="label"
        >
          {galleryImages.map((image) => (
            <Select.Option key={image.id} value={image.url} label={image.name}>
              <Space>
                <img src={image.url} alt="" style={{ width: 32, height: 32, objectFit: 'cover', borderRadius: 4 }} />
                {image.name}
              </Space>
            </Select.Option>
          ))}
        </Select>
      </div>
    )
  }

  if (role === 'audio') {
    const audioLabel = taskKind === 'text_to_video' ? '自定义音频' : '驱动音频'
    return (
      <div style={{ marginBottom: 16 }}>
        <div style={{ marginBottom: 8 }}><VideoFieldLabel label={audioLabel} help={getAssetHelp('audio')} /></div>
        <Select
          style={{ width: '100%' }}
          value={audioUrl || undefined}
          onChange={(value) => onAudioChange(value || '')}
          placeholder="从音频库选择"
          allowClear
        >
          {audioItems.map((audio) => (
            <Select.Option key={audio.id} value={audio.url}>
              {audio.name}
            </Select.Option>
          ))}
        </Select>
      </div>
    )
  }

  if (role === 'first_clip') {
    return (
      <div style={{ marginBottom: 16 }}>
        <div style={{ marginBottom: 8 }}><VideoFieldLabel label="首段视频" help={getAssetHelp('first_clip')} required /></div>
        <Select
          style={{ width: '100%' }}
          value={firstClipUrl || undefined}
          onChange={(value) => onFirstClipChange(value || '')}
          placeholder="从视频库选择首段视频"
          optionLabelProp="label"
        >
          {videoLibraryItems.map((video) => (
            <Select.Option key={video.id} value={video.url} label={video.name}>
              <Space>
                <VideoCameraOutlined />
                {video.name}
              </Space>
            </Select.Option>
          ))}
        </Select>
      </div>
    )
  }

  if (role === 'base_video' || role === 'source_video') {
    const currentValue = role === 'base_video' ? baseVideoUrl : sourceVideoUrl
    const disableSelector = isEditMode && taskKind === 'video_edit_local' && role === 'source_video'
    const label = role === 'base_video' ? '待编辑视频' : '源视频'
    return (
      <div style={{ marginBottom: 16 }}>
        <div style={{ marginBottom: 8 }}><VideoFieldLabel label={label} help={getAssetHelp(role)} required /></div>
        <Select
          style={{ width: '100%' }}
          value={currentValue || undefined}
          disabled={disableSelector}
          onChange={(value) => {
            if (role === 'base_video') {
              onBaseVideoChange(value || '')
            } else {
              onSourceVideoChange(value || '')
              if (value) {
                onPrepareSourceVideo(value)
              }
            }
          }}
          placeholder="从视频库选择视频"
          optionLabelProp="label"
        >
          {videoLibraryItems.map((video) => (
            <Select.Option key={video.id} value={video.url} label={video.name}>
              <Space>
                <VideoCameraOutlined />
                {video.name}
              </Space>
            </Select.Option>
          ))}
        </Select>
        {role === 'source_video' && sourceVideoPreparing && (
          <div style={{ marginTop: 8 }}>
            <Space size={8}>
              <Spin size="small" />
              <span style={{ color: token.colorTextSecondary }}>正在提取首帧与视频元数据...</span>
            </Space>
          </div>
        )}
        {role === 'source_video' && sourceVideoMetadata && (
          <div style={{ marginTop: 8, fontSize: 12, color: token.colorTextSecondary }}>
            {sourceVideoMetadata.width} × {sourceVideoMetadata.height} · {sourceVideoMetadata.fps.toFixed(2)} FPS · {sourceVideoMetadata.duration.toFixed(2)} 秒
          </div>
        )}
      </div>
    )
  }

  return null
}

export default InputAssetSelector
