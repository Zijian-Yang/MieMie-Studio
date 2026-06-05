import type { ReactNode } from 'react'
import { Button, List, Select, Space, Tag, theme } from 'antd'
import { DeleteOutlined } from '@ant-design/icons'
import type {
  AudioItem,
  GalleryImage,
  HelpContent,
  VideoInputRole,
  VideoReferenceMediaItem,
  VideoReferenceTokenRole,
  VideoTaskKind,
  VideoTaskProfile,
  VideoLibraryItem,
} from '../../services/api'
import { resolveReferenceCollectionLimits } from './capabilityLimits'
import VideoFieldLabel from './VideoFieldLabel'

export interface StructuredReferenceMediaItem extends VideoReferenceMediaItem {
  id: string
}

interface ReferenceCollectionsPanelProps {
  taskKind: VideoTaskKind
  currentProfile?: VideoTaskProfile
  isWan27ReferenceModel: boolean
  galleryImages: GalleryImage[]
  videoLibraryItems: VideoLibraryItem[]
  audioItems: AudioItem[]
  referenceImageUrls: string[]
  referenceVideoUrls: string[]
  referenceMediaItems: StructuredReferenceMediaItem[]
  getAssetHelp: (role: VideoInputRole) => HelpContent | string | undefined
  onAddReferenceImage: (url: string) => void
  onAddReferenceVideo: (url: string) => void
  onRemoveReferenceImage: (url: string) => void
  onRemoveReferenceVideo: (url: string) => void
  onAddReferenceMediaItem: (type: 'reference_image' | 'reference_video', url: string) => void
  onRemoveReferenceMediaItem: (id: string) => void
  onMoveReferenceMediaItem: (id: string, direction: -1 | 1) => void
  onUpdateReferenceMediaVoice: (id: string, referenceVoice?: string) => void
  renderReferenceTokenButton: (
    role: VideoReferenceTokenRole,
    roleIndex: number,
    roleCounts: Partial<Record<VideoReferenceTokenRole, number>>
  ) => ReactNode
}

const ReferenceCollectionsPanel = ({
  taskKind,
  currentProfile,
  isWan27ReferenceModel,
  galleryImages,
  videoLibraryItems,
  audioItems,
  referenceImageUrls,
  referenceVideoUrls,
  referenceMediaItems,
  getAssetHelp,
  onAddReferenceImage,
  onAddReferenceVideo,
  onRemoveReferenceImage,
  onRemoveReferenceVideo,
  onAddReferenceMediaItem,
  onRemoveReferenceMediaItem,
  onMoveReferenceMediaItem,
  onUpdateReferenceMediaVoice,
  renderReferenceTokenButton,
}: ReferenceCollectionsPanelProps) => {
  const { token } = theme.useToken()

  if (
    taskKind !== 'reference_to_video' &&
    taskKind !== 'video_edit_global' &&
    taskKind !== 'video_edit_local' &&
    taskKind !== 'video_repainting'
  ) {
    return null
  }

  const { maxReferenceImages, maxReferenceVideos, maxReferenceTotal } = resolveReferenceCollectionLimits(taskKind, currentProfile)
  const referenceImageHelp = currentProfile?.ui_hints?.asset_help?.reference_image || getAssetHelp('reference_image')
  const referenceVideoHelp = currentProfile?.ui_hints?.asset_help?.reference_video || getAssetHelp('reference_video')

  if (isWan27ReferenceModel) {
    const selectedReferenceUrls = new Set(referenceMediaItems.map((item) => item.url))
    const selectedImageCount = referenceMediaItems.filter((item) => item.type === 'reference_image').length
    const selectedVideoCount = referenceMediaItems.filter((item) => item.type === 'reference_video').length

    return (
      <>
        {maxReferenceImages > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ marginBottom: 8 }}>
              <VideoFieldLabel label="参考图片" help={referenceImageHelp} />
            </div>
            <Select
              style={{ width: '100%' }}
              value={undefined}
              onChange={(value) => {
                if (!value || selectedImageCount >= maxReferenceImages || referenceMediaItems.length >= maxReferenceTotal) return
                onAddReferenceMediaItem('reference_image', value)
              }}
              placeholder="从图库添加参考图"
              disabled={selectedImageCount >= maxReferenceImages || referenceMediaItems.length >= maxReferenceTotal}
              optionLabelProp="label"
            >
              {galleryImages.filter((item) => !selectedReferenceUrls.has(item.url)).map((image) => (
                <Select.Option key={image.id} value={image.url} label={image.name}>
                  <Space>
                    <img src={image.url} alt="" style={{ width: 32, height: 32, objectFit: 'cover', borderRadius: 4 }} />
                    {image.name}
                  </Space>
                </Select.Option>
              ))}
            </Select>
          </div>
        )}
        {maxReferenceVideos > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ marginBottom: 8 }}>
              <VideoFieldLabel label="参考视频" help={referenceVideoHelp} />
            </div>
            <Select
              style={{ width: '100%' }}
              value={undefined}
              onChange={(value) => {
                if (!value || selectedVideoCount >= maxReferenceVideos || referenceMediaItems.length >= maxReferenceTotal) return
                onAddReferenceMediaItem('reference_video', value)
              }}
              placeholder="从视频库添加参考视频"
              disabled={selectedVideoCount >= maxReferenceVideos || referenceMediaItems.length >= maxReferenceTotal}
            >
              {videoLibraryItems.filter((item) => !selectedReferenceUrls.has(item.url)).map((video) => (
                <Select.Option key={video.id} value={video.url}>
                  {video.name}
                </Select.Option>
              ))}
            </Select>
          </div>
        )}
        {referenceMediaItems.length > 0 && (
          <div style={{ marginBottom: 16, padding: 12, borderRadius: 8, background: token.colorBgLayout }}>
            <div style={{ marginBottom: 8, fontWeight: 500 }}>已选参考素材</div>
            <Space direction="vertical" style={{ width: '100%' }}>
              {referenceMediaItems.map((item, index) => {
                const image = galleryImages.find((entry) => entry.url === item.url)
                const video = videoLibraryItems.find((entry) => entry.url === item.url)
                const audio = audioItems.find((entry) => entry.url === item.reference_voice)
                const roleCounts = {
                  reference_image: selectedImageCount,
                  reference_video: selectedVideoCount,
                }
                const roleIndex = referenceMediaItems
                  .slice(0, index)
                  .filter((entry) => entry.type === item.type)
                  .length
                return (
                  <div key={item.id} style={{ padding: 12, borderRadius: 8, background: token.colorBgContainer }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                      <Space size={8} wrap>
                        <Tag color={item.type === 'reference_image' ? 'green' : 'blue'}>
                          {item.type === 'reference_image' ? '图片' : '视频'}
                        </Tag>
                        <span>{image?.name || video?.name || item.url}</span>
                        {audio && <Tag color="gold">音色: {audio.name}</Tag>}
                      </Space>
                      <Space size={4}>
                        {renderReferenceTokenButton(item.type, roleIndex, roleCounts)}
                        <Button type="text" disabled={index === 0} onClick={() => onMoveReferenceMediaItem(item.id, -1)}>上移</Button>
                        <Button type="text" disabled={index === referenceMediaItems.length - 1} onClick={() => onMoveReferenceMediaItem(item.id, 1)}>下移</Button>
                        <Button type="text" danger icon={<DeleteOutlined />} onClick={() => onRemoveReferenceMediaItem(item.id)} />
                      </Space>
                    </div>
                    <Select
                      style={{ width: '100%' }}
                      value={item.reference_voice}
                      allowClear
                      placeholder="从音频库选择该素材的参考音色（可选）"
                      onChange={(value) => onUpdateReferenceMediaVoice(item.id, value)}
                    >
                      {audioItems.map((audioItem) => (
                        <Select.Option key={audioItem.id} value={audioItem.url}>
                          {audioItem.name}
                        </Select.Option>
                      ))}
                    </Select>
                  </div>
                )
              })}
            </Space>
          </div>
        )}
      </>
    )
  }

  return (
    <>
      {maxReferenceImages > 0 && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ marginBottom: 8 }}>
            <VideoFieldLabel label="参考图片" help={referenceImageHelp} />
            {taskKind !== 'reference_to_video' && <span style={{ marginLeft: 6, color: token.colorTextSecondary }}>（可选）</span>}
          </div>
          <Select
            style={{ width: '100%' }}
            value={undefined}
            onChange={(value) => {
              if (!value || referenceImageUrls.length >= maxReferenceImages) return
              onAddReferenceImage(value)
            }}
            placeholder="从图库添加参考图"
            disabled={referenceImageUrls.length >= maxReferenceImages}
            optionLabelProp="label"
          >
            {galleryImages.filter((item) => !referenceImageUrls.includes(item.url)).map((image) => (
              <Select.Option key={image.id} value={image.url} label={image.name}>
                <Space>
                  <img src={image.url} alt="" style={{ width: 32, height: 32, objectFit: 'cover', borderRadius: 4 }} />
                  {image.name}
                </Space>
              </Select.Option>
            ))}
          </Select>
        </div>
      )}
      {maxReferenceVideos > 0 && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ marginBottom: 8 }}>
            <VideoFieldLabel label="参考视频" help={referenceVideoHelp} />
            {taskKind === 'reference_to_video' && <span style={{ marginLeft: 6, color: token.colorTextSecondary }}>（可选）</span>}
          </div>
          <Select
            style={{ width: '100%' }}
            value={undefined}
            onChange={(value) => {
              if (!value || referenceVideoUrls.length >= maxReferenceVideos) return
              onAddReferenceVideo(value)
            }}
            placeholder="从视频库添加参考视频"
            disabled={referenceVideoUrls.length >= maxReferenceVideos}
          >
            {videoLibraryItems.filter((item) => !referenceVideoUrls.includes(item.url)).map((video) => (
              <Select.Option key={video.id} value={video.url}>
                {video.name}
              </Select.Option>
            ))}
          </Select>
        </div>
      )}
      {(referenceImageUrls.length > 0 || referenceVideoUrls.length > 0) && (
        <div style={{ marginBottom: 16, padding: 12, borderRadius: 8, background: token.colorBgLayout }}>
          <div style={{ marginBottom: 8, fontWeight: 500 }}>已选参考素材</div>
          <List
            size="small"
            dataSource={[
              ...referenceImageUrls.map((url, index) => ({ url, type: 'image' as const, role: 'reference_image' as const, roleIndex: index })),
              ...referenceVideoUrls.map((url, index) => ({ url, type: 'video' as const, role: 'reference_video' as const, roleIndex: index })),
            ]}
            renderItem={(item) => {
              const image = galleryImages.find((entry) => entry.url === item.url)
              const video = videoLibraryItems.find((entry) => entry.url === item.url)
              const roleCounts = {
                reference_image: referenceImageUrls.length,
                reference_video: referenceVideoUrls.length,
              }
              return (
                <List.Item
                  actions={[
                    <span key="reference-token">
                      {renderReferenceTokenButton(item.role, item.roleIndex, roleCounts)}
                    </span>,
                    <Button
                      key="delete"
                      type="text"
                      danger
                      icon={<DeleteOutlined />}
                      onClick={() => item.type === 'image' ? onRemoveReferenceImage(item.url) : onRemoveReferenceVideo(item.url)}
                    />,
                  ]}
                >
                  <Space>
                    <Tag color={item.type === 'image' ? 'green' : 'blue'}>
                      {item.type === 'image' ? '图片' : '视频'}
                    </Tag>
                    <span>{image?.name || video?.name || item.url}</span>
                  </Space>
                </List.Item>
              )
            }}
          />
        </div>
      )}
    </>
  )
}

export default ReferenceCollectionsPanel
