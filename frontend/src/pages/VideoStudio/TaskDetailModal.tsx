import type { ReactNode } from 'react'
import { Button, Card, Collapse, Col, Modal, Row, Space, Spin, Tag, theme } from 'antd'
import {
  CameraOutlined,
  CheckOutlined,
  CloseOutlined,
  EditOutlined,
  FlagFilled,
  FlagOutlined,
  ReloadOutlined,
  SaveOutlined,
  StarFilled,
  StarOutlined,
} from '@ant-design/icons'
import type { AudioItem, VideoStudioTask } from '../../services/api'
import {
  getTaskInputAssets,
  getTaskParameterEntries,
  getTaskSummaryLine,
} from './taskViewUtils'

interface TaskDetailModalProps {
  open: boolean
  task: VideoStudioTask | null
  audioItems: AudioItem[]
  extractingFrames: Set<string>
  regenerating: boolean
  renderTaskKindTag: (task: VideoStudioTask) => ReactNode
  renderStatusTag: (status: string) => ReactNode
  onClose: () => void
  onEdit: (task: VideoStudioTask) => void
  onRegenerate: (task: VideoStudioTask) => void
  onToggleVideoMarker: (taskId: string, videoUrl: string, markerKey: string) => void
  onSaveToLibrary: (videoUrl: string) => void
  onExtractLastFrame: (videoUrl: string) => void
}

const TaskDetailModal = ({
  open,
  task,
  audioItems,
  extractingFrames,
  regenerating,
  renderTaskKindTag,
  renderStatusTag,
  onClose,
  onEdit,
  onRegenerate,
  onToggleVideoMarker,
  onSaveToLibrary,
  onExtractLastFrame,
}: TaskDetailModalProps) => {
  const { token } = theme.useToken()

  const inputAssets = task ? getTaskInputAssets(task) : null
  const paramEntries = task ? getTaskParameterEntries(task) : []
  const sourceVideos = [...(inputAssets?.source_video || [])]
  const baseVideos = [...(inputAssets?.base_video || [])]
  const firstClips = [...(inputAssets?.first_clip || [])]
  const firstFrames = [...(inputAssets?.first_frame || [])]
  const lastFrames = [...(inputAssets?.last_frame || [])]
  const audioAssets = [...(inputAssets?.audio || [])]
  const referenceMedia = [...(inputAssets?.reference_media || [])]
  const referenceImages = [...(inputAssets?.reference_images || [])]
  const referenceVideos = [...(inputAssets?.reference_videos || [])]
  const maskImages = [...(inputAssets?.mask_image || [])]
  const hasInputAssets = sourceVideos.length > 0
    || baseVideos.length > 0
    || firstClips.length > 0
    || firstFrames.length > 0
    || lastFrames.length > 0
    || referenceImages.length > 0
    || referenceVideos.length > 0
    || maskImages.length > 0
    || audioAssets.length > 0

  return (
    <Modal
      title={
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingRight: 30 }}>
          <span>{task?.name || '任务详情'}</span>
          <Space>
            <Button
              size="small"
              icon={<EditOutlined />}
              onClick={() => task && onEdit(task)}
            >
              编辑
            </Button>
            <Button
              size="small"
              icon={<ReloadOutlined />}
              loading={regenerating}
              onClick={() => task && onRegenerate(task)}
              disabled={task?.status === 'processing'}
            >
              重新生成
            </Button>
          </Space>
        </div>
      }
      open={open}
      onCancel={onClose}
      footer={null}
      width={800}
    >
      {task && (
        <div>
          <div style={{ marginBottom: 16 }}>
            <Space>
              {renderTaskKindTag(task)}
              {task.provider && <Tag>{task.provider.toUpperCase()}</Tag>}
              {renderStatusTag(task.status)}
              <span style={{ color: token.colorTextSecondary }}>
                {getTaskSummaryLine(task)}
              </span>
            </Space>
          </div>

          {hasInputAssets && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontWeight: 500, marginBottom: 8 }}>输入素材</div>
              <Row gutter={16}>
                {sourceVideos.map((url, index) => (
                  <Col key={`source-${index}`} span={12}>
                    <Card size="small" title="源视频">
                      <video controls style={{ width: '100%' }} src={url} />
                    </Card>
                  </Col>
                ))}
                {baseVideos.map((url, index) => (
                  <Col key={`base-${index}`} span={12}>
                    <Card size="small" title="待编辑视频">
                      <video controls style={{ width: '100%' }} src={url} />
                    </Card>
                  </Col>
                ))}
                {firstClips.map((url, index) => (
                  <Col key={`first-clip-${index}`} span={12}>
                    <Card size="small" title="首段视频">
                      <video controls style={{ width: '100%' }} src={url} />
                    </Card>
                  </Col>
                ))}
                {firstFrames.map((url, index) => (
                  <Col key={`first-${index}`} span={12}>
                    <Card size="small" title="首帧图">
                      <img
                        src={url}
                        alt="首帧图"
                        style={{ width: '100%', borderRadius: 8, objectFit: 'cover' }}
                      />
                    </Card>
                  </Col>
                ))}
                {lastFrames.map((url, index) => (
                  <Col key={`last-${index}`} span={12}>
                    <Card size="small" title="尾帧图">
                      <img
                        src={url}
                        alt="尾帧图"
                        style={{ width: '100%', borderRadius: 8, objectFit: 'cover' }}
                      />
                    </Card>
                  </Col>
                ))}
                {referenceMedia.length > 0 ? referenceMedia.map((item: any, index) => (
                  <Col key={`ref-media-${index}`} span={12}>
                    <Card
                      size="small"
                      title={item.type === 'reference_image' ? `参考图 ${index + 1}` : `参考视频 ${index + 1}`}
                      extra={item.reference_voice ? <Tag color="gold">已绑定参考音色</Tag> : undefined}
                    >
                      {item.type === 'reference_image' ? (
                        <img
                          src={item.url}
                          alt="参考图"
                          style={{ width: '100%', borderRadius: 8, objectFit: 'cover' }}
                        />
                      ) : (
                        <video controls style={{ width: '100%' }} src={item.url} />
                      )}
                      {item.reference_voice && (
                        <div style={{ marginTop: 8, fontSize: 12, color: token.colorTextSecondary }}>
                          参考音频: {audioItems.find((audio) => audio.url === item.reference_voice)?.name || item.reference_voice}
                        </div>
                      )}
                    </Card>
                  </Col>
                )) : (
                  <>
                    {referenceImages.map((url, index) => (
                      <Col key={`ref-image-${index}`} span={12}>
                        <Card size="small" title="参考图">
                          <img
                            src={url}
                            alt="参考图"
                            style={{ width: '100%', borderRadius: 8, objectFit: 'cover' }}
                          />
                        </Card>
                      </Col>
                    ))}
                    {referenceVideos.map((url, index) => (
                      <Col key={`ref-video-${index}`} span={12}>
                        <Card size="small" title="参考视频">
                          <video controls style={{ width: '100%' }} src={url} />
                        </Card>
                      </Col>
                    ))}
                  </>
                )}
                {maskImages.map((url, index) => (
                  <Col key={`mask-${index}`} span={12}>
                    <Card size="small" title="Mask">
                      <img
                        src={url}
                        alt="Mask"
                        style={{ width: '100%', borderRadius: 8, objectFit: 'contain', background: token.colorBgLayout }}
                      />
                    </Card>
                  </Col>
                ))}
                {audioAssets.map((url, index) => (
                  <Col key={`audio-${index}`} span={12}>
                    <Card size="small" title="音频">
                      <audio controls style={{ width: '100%' }} src={url} />
                    </Card>
                  </Col>
                ))}
              </Row>
            </div>
          )}

          {paramEntries.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontWeight: 500, marginBottom: 8 }}>关键参数</div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {paramEntries.map((entry) => (
                  <Tag key={entry.key} style={{ padding: '4px 8px' }}>
                    {entry.label}: {entry.value}
                  </Tag>
                ))}
              </div>
            </div>
          )}

          {task.status === 'processing' && (
            <div style={{ textAlign: 'center', padding: 40 }}>
              <Spin size="large" />
              <div style={{ marginTop: 16, color: token.colorTextSecondary }}>
                正在生成视频... ({task.video_urls.length}/{task.group_count})
              </div>
            </div>
          )}

          {task.status === 'failed' && (
            <div style={{ padding: 20, background: token.colorErrorBg, borderRadius: 8, color: token.colorError }}>
              生成失败: {task.error_message || '未知错误'}
            </div>
          )}

          {task.video_urls.length > 0 && (
            <div>
              <div style={{ marginBottom: 16, fontWeight: 500 }}>生成结果</div>
              <Row gutter={16}>
                {task.video_urls.map((url, index) => {
                  const videoMarkers = task.video_markers?.[url] || []
                  return (
                    <Col key={index} span={12}>
                      <Card size="small" style={{ marginBottom: 16 }}>
                        <video
                          controls
                          style={{ width: '100%' }}
                          src={url}
                        />
                        <div style={{ display: 'flex', justifyContent: 'center', gap: 4, marginTop: 6 }}>
                          {([
                            { key: 'star', icon: <StarOutlined />, activeIcon: <StarFilled />, color: token.colorWarning, title: '星标' },
                            { key: 'flag', icon: <FlagOutlined />, activeIcon: <FlagFilled />, color: token.colorError, title: '红旗' },
                            { key: 'check', icon: <CheckOutlined />, activeIcon: <CheckOutlined />, color: token.colorSuccess, title: '对号' },
                            { key: 'cross', icon: <CloseOutlined />, activeIcon: <CloseOutlined />, color: token.colorError, title: '红叉' },
                          ] as const).map(marker => {
                            const active = videoMarkers.includes(marker.key)
                            return (
                              <Button
                                key={marker.key}
                                type="text"
                                size="small"
                                title={marker.title}
                                icon={active ? marker.activeIcon : marker.icon}
                                style={{
                                  color: active ? marker.color : token.colorTextQuaternary,
                                  fontSize: 14,
                                  padding: '2px 6px',
                                  height: 24,
                                  minWidth: 24,
                                }}
                                onClick={() => onToggleVideoMarker(task.id, url, marker.key)}
                              />
                            )
                          })}
                        </div>
                        <div style={{ marginTop: 6, textAlign: 'center', display: 'flex', justifyContent: 'center', gap: 8 }}>
                          <Button
                            type="primary"
                            size="small"
                            icon={<SaveOutlined />}
                            onClick={() => onSaveToLibrary(url)}
                          >
                            保存到视频库
                          </Button>
                          <Button
                            size="small"
                            icon={<CameraOutlined />}
                            loading={extractingFrames.has(url)}
                            onClick={() => onExtractLastFrame(url)}
                          >
                            保存尾帧
                          </Button>
                        </div>
                      </Card>
                    </Col>
                  )
                })}
              </Row>
            </div>
          )}

          {task.prompt && (
            <div style={{ marginTop: 16 }}>
              <div style={{ fontWeight: 500, marginBottom: 8 }}>提示词</div>
              <div style={{ background: token.colorBgContainer, padding: 12, borderRadius: 8 }}>
                {task.prompt}
              </div>
            </div>
          )}

          <Collapse
            style={{ marginTop: 16 }}
            items={[
              {
                key: 'developer-mode',
                label: '开发者模式',
                children: (
                  <div>
                    <div style={{ marginBottom: 8, fontWeight: 500 }}>Task IDs</div>
                    <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: 12, padding: 12, borderRadius: 8, background: token.colorBgLayout, marginBottom: 12 }}>
                      {JSON.stringify(task.task_ids || [], null, 2)}
                    </pre>
                    <div style={{ marginBottom: 8, fontWeight: 500 }}>Request IDs</div>
                    <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: 12, padding: 12, borderRadius: 8, background: token.colorBgLayout, marginBottom: 12 }}>
                      {JSON.stringify(task.request_ids || [], null, 2)}
                    </pre>
                    <div style={{ marginBottom: 8, fontWeight: 500 }}>厂商请求体快照</div>
                    <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: 12, padding: 12, borderRadius: 8, background: token.colorBgLayout, marginBottom: 12 }}>
                      {JSON.stringify(task.provider_payload_snapshot || {}, null, 2)}
                    </pre>
                    <div style={{ marginBottom: 8, fontWeight: 500 }}>厂商结果元信息</div>
                    <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: 12, padding: 12, borderRadius: 8, background: token.colorBgLayout }}>
                      {JSON.stringify(task.provider_result_meta || {}, null, 2)}
                    </pre>
                  </div>
                ),
              },
            ]}
          />
        </div>
      )}
    </Modal>
  )
}

export default TaskDetailModal
