import { useEffect, useState, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { 
  Card, Button, Modal, Form, Input, Empty, Spin, message, 
  Image, Tag, Tooltip, Divider, Upload, Space,
  Select, Switch, InputNumber, Row, Col
} from 'antd'
import { 
  PlayCircleOutlined, ReloadOutlined, VideoCameraOutlined,
  LoadingOutlined, CheckCircleOutlined, CloseCircleOutlined,
  SoundOutlined, UploadOutlined, SettingOutlined
} from '@ant-design/icons'
import { videosApi, framesApi, settingsApi, Video, Shot, Frame, VideoModelInfo } from '../../services/api'
import { useProjectStore } from '../../stores/projectStore'
import { useGenerationStore } from '../../stores/generationStore'

const { TextArea } = Input
const { Option } = Select

const VideosPage = () => {
  const { projectId } = useParams<{ projectId: string }>()
  const { currentProject, fetchProject } = useProjectStore()
  const {
    videoGroupCount,
    setVideoGroupCount,
    videoModel,
    setVideoModel,
    videoSize,
    setVideoSize,
    videoPromptExtend,
    setVideoPromptExtend,
    videoWatermark,
    setVideoWatermark,
    videoSeed,
    setVideoSeed,
    resetVideoSettings,
  } = useGenerationStore()
  
  const [videos, setVideos] = useState<Video[]>([])
  const [frames, setFrames] = useState<Frame[]>([])
  const [shots, setShots] = useState<Shot[]>([])
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [selectedShot, setSelectedShot] = useState<Shot | null>(null)
  const [selectedVideo, setSelectedVideo] = useState<Video | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [settingsModalVisible, setSettingsModalVisible] = useState(false)
  const [singleGenerating, setSingleGenerating] = useState(false)
  const [form] = Form.useForm()
  
  // 视频模型配置
  const [videoModels, setVideoModels] = useState<Record<string, VideoModelInfo>>({})
  const [systemVideoConfig, setSystemVideoConfig] = useState<{model: string, size: string, prompt_extend: boolean, watermark: boolean}>({
    model: 'wan2.5-i2v-preview',
    size: '1280*720',
    prompt_extend: true,
    watermark: false
  })
  
  // 轮询状态更新
  const pollingRef = useRef<Set<string>>(new Set())
  const isMountedRef = useRef(true)
  const videosRef = useRef<Video[]>([])
  
  // 保持 videosRef 同步
  useEffect(() => {
    videosRef.current = videos
  }, [videos])

  useEffect(() => {
    const loadData = async () => {
      if (!projectId) return
      
      setLoading(true)
      try {
        // 不阻塞加载
        fetchProject(projectId).catch(() => {})
        const [videosRes, framesRes, settingsRes] = await Promise.all([
          videosApi.list(projectId),
          framesApi.list(projectId),
          settingsApi.getSettings(),
        ])
        setVideos(videosRes.videos)
        setFrames(framesRes.frames)
        setVideoModels(settingsRes.available_video_models)
        setSystemVideoConfig({
          model: settingsRes.video.model,
          size: settingsRes.video.size,
          prompt_extend: settingsRes.video.prompt_extend,
          watermark: settingsRes.video.watermark,
        })
        
        // 启动轮询检查进行中的任务
        videosRes.videos.forEach(v => {
          if (v.task?.status === 'processing') {
            startPolling(v.task.task_id)
          }
        })
      } catch (error) {
        message.error('加载失败')
      } finally {
        setLoading(false)
      }
    }
    loadData()
    
    return () => {
      // 组件卸载时标记
      isMountedRef.current = false
      // 注意：不清理 pollingRef，让轮询继续运行
      // 这样下次加载时可以从后端获取最新状态
    }
  }, [projectId, fetchProject])
  
  // 组件挂载时重置标记
  useEffect(() => {
    isMountedRef.current = true
    return () => {
      isMountedRef.current = false
    }
  }, [])

  useEffect(() => {
    if (currentProject?.script?.shots) {
      setShots(currentProject.script.shots)
    }
  }, [currentProject])

  // 获取分镜的首帧图URL
  const getFrameUrl = (shotId: string) => {
    const frame = frames.find(f => f.shot_id === shotId)
    if (frame?.image_groups?.[frame.selected_group_index]?.url) {
      return frame.image_groups[frame.selected_group_index].url
    }
    return null
  }

  // 轮询任务状态
  const startPolling = (taskId: string) => {
    if (pollingRef.current.has(taskId)) return
    pollingRef.current.add(taskId)
    
    const poll = async () => {
      // 检查是否还需要继续轮询
      if (!pollingRef.current.has(taskId)) return
      
      try {
        const result = await videosApi.getStatus(taskId)
        
        if (result.status === 'SUCCEEDED' || result.status === 'FAILED') {
          pollingRef.current.delete(taskId)
          
          // 只有组件仍然挂载时才更新状态
          if (isMountedRef.current) {
            // 更新视频列表
            setVideos(prev => prev.map(v => {
              if (v.task?.task_id === taskId) {
                return {
                  ...v,
                  video_url: result.video_url,
                  task: {
                    ...v.task!,
                    status: result.status.toLowerCase() as 'succeeded' | 'failed'
                  }
                }
              }
              return v
            }))
            
            // 同步更新 selectedVideo
            setSelectedVideo(prev => {
              if (prev?.task?.task_id === taskId) {
                return {
                  ...prev,
                  video_url: result.video_url,
                  task: {
                    ...prev.task!,
                    status: result.status.toLowerCase() as 'succeeded' | 'failed'
                  }
                }
              }
              return prev
            })
            
            if (result.status === 'SUCCEEDED') {
              message.success('视频生成完成')
            } else if (result.status === 'FAILED') {
              message.error('视频生成失败')
            }
          }
        } else {
          // 继续轮询（即使组件卸载也继续，以便下次加载时能获取到最新状态）
          setTimeout(poll, 5000)
        }
      } catch (error) {
        console.error('轮询视频状态失败:', error)
        // 出错时也继续轮询，避免状态丢失
        setTimeout(poll, 10000)
      }
    }
    
    poll()
  }

  // 获取当前有效的视频设置（页面设置优先于系统设置）
  const getEffectiveVideoSettings = () => {
    return {
      model: videoModel || systemVideoConfig.model,
      size: videoSize || systemVideoConfig.size,
      prompt_extend: videoPromptExtend !== null ? videoPromptExtend : systemVideoConfig.prompt_extend,
      watermark: videoWatermark !== null ? videoWatermark : systemVideoConfig.watermark,
      seed: videoSeed,
    }
  }

  // 获取当前模型的分辨率选项
  const getCurrentModelSizes = () => {
    const currentModel = videoModel || systemVideoConfig.model
    const modelInfo = videoModels[currentModel]
    return modelInfo?.sizes || []
  }

  // 获取当前模型信息
  const getCurrentModelInfo = () => {
    const currentModel = videoModel || systemVideoConfig.model
    return videoModels[currentModel]
  }

  // 构建视频提示词
  const buildVideoPrompt = (shot: Shot) => {
    const promptParts = []
    
    // 动作描述（最重要）
    if (shot.character_action) {
      promptParts.push(`动作: ${shot.character_action}`)
    }
    
    // 镜头设计
    if (shot.shot_design) {
      promptParts.push(`镜头: ${shot.shot_design}`)
    }
    
    // 情绪基调
    if (shot.mood) {
      promptParts.push(`氛围: ${shot.mood}`)
    }
    
    // 角色表现
    if (shot.characters?.length) {
      let charDesc = `角色: ${shot.characters.join(', ')}`
      if (shot.character_appearance) {
        charDesc += ` (${shot.character_appearance})`
      }
      promptParts.push(charDesc)
    }
    
    // 光线
    if (shot.lighting) {
      promptParts.push(`光线: ${shot.lighting}`)
    }
    
    if (promptParts.length > 0) {
      return promptParts.join(', ') + ', 流畅自然的动作, 电影级画质'
    } else {
      return '流畅的摄像机运动, 自然的场景变化, 电影级画质'
    }
  }

  // 批量生成视频
  const generateAllVideos = async () => {
    if (!projectId) return
    
    // 检查是否有首帧图
    const shotsWithFrames = shots.filter(s => s.first_frame_url || getFrameUrl(s.id))
    if (shotsWithFrames.length === 0) {
      message.warning('请先生成分镜首帧')
      return
    }
    
    setGenerating(true)
    
    try {
      const settings = getEffectiveVideoSettings()
      const result = await videosApi.generateBatch(projectId, {
        model: settings.model,
        size: settings.size,
        prompt_extend: settings.prompt_extend,
        watermark: settings.watermark,
        seed: settings.seed,
      })
      setVideos(prev => [...prev, ...result.videos])
      
      // 启动轮询
      result.videos.forEach(v => {
        if (v.task?.task_id) {
          startPolling(v.task.task_id)
        }
      })
      
      if (result.errors.length > 0) {
        message.warning(`${result.success_count} 个已提交，${result.error_count} 个失败`)
      } else {
        message.success(`成功提交 ${result.success_count} 个视频生成任务`)
      }
    } catch (error) {
      message.error('批量生成失败')
    } finally {
      setGenerating(false)
    }
  }

  // 打开单个视频编辑
  const openVideoModal = (shot: Shot) => {
    setSelectedShot(shot)
    // 找到最新的该镜头视频（优先显示处理中的，否则显示最新的）
    const shotVideos = videos.filter(v => v.shot_id === shot.id)
    const processingVideo = shotVideos.find(v => v.task?.status === 'processing')
    const latestVideo = shotVideos.length > 0 
      ? shotVideos.reduce((latest, v) => 
          new Date(v.created_at) > new Date(latest.created_at) ? v : latest
        )
      : null
    const video = processingVideo || latestVideo
    setSelectedVideo(video)
    
    // 使用改进的提示词生成
    form.setFieldsValue({
      prompt: video?.prompt || buildVideoPrompt(shot)
    })
    
    setIsModalOpen(true)
    
    // 如果视频正在处理中，确保轮询正在运行
    if (video?.task?.status === 'processing' && video.task.task_id) {
      startPolling(video.task.task_id)
    }
  }

  // 生成单个视频
  const generateSingleVideo = async () => {
    if (!projectId || !selectedShot) return
    
    // 获取首帧URL（优先从Frame获取）
    const frameUrl = getFrameUrl(selectedShot.id) || selectedShot.first_frame_url
    
    if (!frameUrl) {
      message.warning('请先生成首帧图')
      return
    }
    
    const values = await form.validateFields()
    const settings = getEffectiveVideoSettings()
    
    setSingleGenerating(true)
    try {
      const result = await videosApi.generate({
        project_id: projectId,
        shot_id: selectedShot.id,
        shot_number: selectedShot.shot_number,
        first_frame_url: frameUrl,
        prompt: values.prompt,
        duration: Math.min(selectedShot.duration || 5, 10), // 确保不超过10秒
        // 使用页面设置
        model: settings.model,
        size: settings.size,
        prompt_extend: settings.prompt_extend,
        watermark: settings.watermark,
        seed: settings.seed,
      })
      
      // 添加新视频到列表（不替换旧的，因为可能想保留历史记录）
      setVideos(prev => [...prev, result.video])
      
      setSelectedVideo(result.video)
      
      // 启动轮询
      if (result.task_id) {
        startPolling(result.task_id)
      }
      
      message.success('视频生成任务已提交')
    } catch (error) {
      message.error('视频生成失败')
    } finally {
      setSingleGenerating(false)
    }
  }

  // 获取视频状态标签
  const getStatusTag = (video?: Video | null) => {
    if (!video?.task) return null
    
    const status = video.task.status
    switch (status) {
      case 'processing':
        return <Tag icon={<LoadingOutlined />} color="processing">生成中</Tag>
      case 'succeeded':
        return <Tag icon={<CheckCircleOutlined />} color="success">已完成</Tag>
      case 'failed':
        return <Tag icon={<CloseCircleOutlined />} color="error">失败</Tag>
      default:
        return <Tag color="default">等待中</Tag>
    }
  }

  if (loading) {
    return (
      <div style={{ padding: 24, textAlign: 'center' }}>
        <Spin size="large" />
      </div>
    )
  }

  return (
    <div style={{ padding: 24 }}>
      <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 600, margin: 0, color: '#e0e0e0' }}>
            视频生成
          </h1>
          <p style={{ color: '#888', margin: '4px 0 0', fontSize: 13 }}>
            {currentProject?.name} - 共 {shots.length} 个分镜
          </p>
        </div>
        <Space>
          <Button 
            icon={<SettingOutlined />} 
            onClick={() => setSettingsModalVisible(true)}
          >
            设置
          </Button>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            onClick={generateAllVideos}
            loading={generating}
            disabled={shots.length === 0}
          >
            批量生成视频
          </Button>
        </Space>
      </div>
      
      {/* 当前设置预览 */}
      <Card size="small" style={{ marginBottom: 16, background: '#1a1a1a' }}>
        <div style={{ display: 'flex', gap: 24, fontSize: 12, color: '#888' }}>
          <span>
            <strong>模型：</strong>
            {getCurrentModelInfo()?.name || (videoModel || systemVideoConfig.model)}
          </span>
          <span>
            <strong>分辨率：</strong>
            {videoSize || systemVideoConfig.size}
          </span>
          <span>
            <strong>智能改写：</strong>
            {(videoPromptExtend !== null ? videoPromptExtend : systemVideoConfig.prompt_extend) ? '开' : '关'}
          </span>
          {videoModel && <Tag color="blue" style={{ marginLeft: 8 }}>自定义设置</Tag>}
        </div>
      </Card>

      {shots.length === 0 ? (
        <Empty 
          description="请先在分镜脚本页面解析分镜" 
          style={{ marginTop: 100 }} 
        />
      ) : (
        <div className="timeline" style={{ flexWrap: 'wrap' }}>
          {shots.map((shot) => {
            // 找到该镜头的最新视频（优先显示处理中的，否则显示最新的）
            const shotVideos = videos.filter(v => v.shot_id === shot.id)
            const processingVideo = shotVideos.find(v => v.task?.status === 'processing')
            const latestVideo = shotVideos.length > 0
              ? shotVideos.reduce((latest, v) => 
                  new Date(v.created_at) > new Date(latest.created_at) ? v : latest
                )
              : null
            const video = processingVideo || latestVideo
            const videoUrl = video?.video_url || shot.video_url
            const frameUrl = getFrameUrl(shot.id) || shot.first_frame_url
            
            return (
              <Tooltip 
                key={shot.id} 
                title={shot.shot_design || `镜头 ${shot.shot_number}`}
              >
                <div 
                  className="timeline-item"
                  onClick={() => openVideoModal(shot)}
                >
                  <div className="timeline-item-preview" style={{ position: 'relative' }}>
                    {videoUrl ? (
                      <video
                        src={videoUrl}
                        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                        muted
                      />
                    ) : frameUrl ? (
                      <Image
                        src={frameUrl}
                        alt={`镜头 ${shot.shot_number}`}
                        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                        preview={false}
                      />
                    ) : (
                      <div style={{ 
                        width: '100%', 
                        height: '100%', 
                        display: 'flex', 
                        alignItems: 'center', 
                        justifyContent: 'center',
                        background: '#242424'
                      }}>
                        <VideoCameraOutlined style={{ fontSize: 24, color: '#444' }} />
                      </div>
                    )}
                    
                    {video?.task?.status === 'processing' && (
                      <div style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        right: 0,
                        bottom: 0,
                        background: 'rgba(0,0,0,0.6)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center'
                      }}>
                        <Spin />
                      </div>
                    )}
                  </div>
                  <div className="timeline-item-info">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontWeight: 500 }}>镜头 {shot.shot_number}</span>
                      {getStatusTag(video)}
                    </div>
                    <div style={{ color: '#888', fontSize: 11 }}>
                      {Math.min(shot.duration || 5, 10)}秒
                    </div>
                  </div>
                </div>
              </Tooltip>
            )
          })}
        </div>
      )}

      <Modal
        title={`视频生成 - 镜头 ${selectedShot?.shot_number}`}
        open={isModalOpen}
        onCancel={() => setIsModalOpen(false)}
        footer={null}
        width={900}
      >
        {selectedShot && (
          <div style={{ display: 'flex', gap: 24 }}>
            <div style={{ width: 400 }}>
              <h4 style={{ marginBottom: 12 }}>首帧预览</h4>
              <div style={{ 
                aspectRatio: '16/9',
                background: '#1a1a1a',
                borderRadius: 8,
                overflow: 'hidden',
                marginBottom: 12
              }}>
                {(() => {
                  const frameUrl = getFrameUrl(selectedShot.id) || selectedShot.first_frame_url
                  return frameUrl ? (
                    <Image
                      src={frameUrl}
                      alt="首帧"
                      style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                    />
                  ) : (
                    <div style={{ 
                      width: '100%', 
                      height: '100%', 
                      display: 'flex', 
                      flexDirection: 'column',
                      alignItems: 'center', 
                      justifyContent: 'center',
                      color: '#666'
                    }}>
                      <VideoCameraOutlined style={{ fontSize: 48, color: '#444', marginBottom: 8 }} />
                      <span style={{ fontSize: 12 }}>请先生成首帧图</span>
                    </div>
                  )
                })()}
              </div>
              
              <h4 style={{ marginBottom: 12 }}>视频预览</h4>
              <div style={{ 
                aspectRatio: '16/9',
                background: '#1a1a1a',
                borderRadius: 8,
                overflow: 'hidden',
                marginBottom: 12
              }}>
                {selectedVideo?.video_url || selectedShot.video_url ? (
                  <video
                    src={selectedVideo?.video_url || selectedShot.video_url}
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                    controls
                  />
                ) : (
                  <div style={{ 
                    width: '100%', 
                    height: '100%', 
                    display: 'flex', 
                    flexDirection: 'column',
                    alignItems: 'center', 
                    justifyContent: 'center',
                    color: '#666'
                  }}>
                    <PlayCircleOutlined style={{ fontSize: 48, color: '#444', marginBottom: 8 }} />
                    <span style={{ fontSize: 12 }}>视频待生成</span>
                  </div>
                )}
              </div>
              
              {selectedVideo?.task?.status === 'processing' && (
                <Card size="small" style={{ marginBottom: 12 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <LoadingOutlined />
                    <span>视频正在生成中...</span>
                  </div>
                </Card>
              )}
            </div>

            <div style={{ flex: 1 }}>
              <Form form={form} layout="vertical">
                <Form.Item 
                  name="prompt" 
                  label="视频生成提示词"
                  rules={[{ required: true, message: '请输入提示词' }]}
                  extra="描述视频中的动作和镜头运动，根据分镜信息自动生成"
                >
                  <TextArea rows={6} />
                </Form.Item>
              </Form>
              
              <Divider />
              
              <Card size="small" title="分镜信息参考" style={{ background: '#1a1a1a', marginBottom: 16 }}>
                <div style={{ fontSize: 12, color: '#888' }}>
                  <p><strong>镜头设计：</strong>{selectedShot.shot_design || '未设置'}</p>
                  <p><strong>景别：</strong>{selectedShot.scene_type || '未设置'}</p>
                  <p><strong>角色：</strong>{selectedShot.characters?.join(', ') || '无'}</p>
                  <p><strong>动作：</strong>{selectedShot.character_action || '未设置'}</p>
                  <p><strong>情绪：</strong>{selectedShot.mood || '未设置'}</p>
                  <p style={{ marginBottom: 0 }}><strong>时长：</strong>{Math.min(selectedShot.duration || 5, 10)}秒</p>
                </div>
              </Card>
              
              {/* 音频上传占位 */}
              <Card size="small" title="音频配置（开发中）" style={{ background: '#1a1a1a', marginBottom: 16 }}>
                <div style={{ color: '#666', fontSize: 12, marginBottom: 12 }}>
                  后续版本将支持配音和音效上传
                </div>
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Upload disabled>
                    <Button icon={<SoundOutlined />} disabled>
                      上传配音音频
                    </Button>
                  </Upload>
                  <Upload disabled>
                    <Button icon={<UploadOutlined />} disabled>
                      上传背景音乐
                    </Button>
                  </Upload>
                </Space>
              </Card>
              
              {!(getFrameUrl(selectedShot.id) || selectedShot.first_frame_url) && (
                <div style={{ 
                  padding: 12, 
                  background: 'rgba(255, 165, 0, 0.1)', 
                  borderRadius: 8,
                  marginBottom: 12,
                  color: '#faad14'
                }}>
                  请先在"分镜首帧"页面生成该镜头的首帧图
                </div>
              )}
              
              <Button
                type="primary"
                icon={<ReloadOutlined />}
                onClick={generateSingleVideo}
                loading={singleGenerating}
                disabled={!(getFrameUrl(selectedShot.id) || selectedShot.first_frame_url)}
                block
              >
                {selectedVideo?.video_url ? '重新生成视频' : '生成视频'}
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* 设置弹窗 */}
      <Modal
        title="视频生成设置"
        open={settingsModalVisible}
        onCancel={() => setSettingsModalVisible(false)}
        footer={[
          <Button key="reset" onClick={() => {
            resetVideoSettings()
            message.success('已重置为系统默认设置')
          }}>
            重置为默认
          </Button>,
          <Button key="close" type="primary" onClick={() => setSettingsModalVisible(false)}>
            确定
          </Button>
        ]}
        width={600}
      >
        <div style={{ marginBottom: 16 }}>
          <div style={{ color: '#888', fontSize: 12, marginBottom: 16 }}>
            这里的设置会覆盖系统设置页面中的默认配置，仅对当前页面的视频生成生效。
          </div>
          
          <Row gutter={16}>
            <Col span={12}>
              <div style={{ marginBottom: 16 }}>
                <div style={{ marginBottom: 8, color: '#e0e0e0' }}>视频模型</div>
                <Select
                  style={{ width: '100%' }}
                  value={videoModel || systemVideoConfig.model}
                  onChange={(value) => {
                    setVideoModel(value)
                    // 切换模型时重置分辨率为该模型的默认值
                    const modelInfo = videoModels[value]
                    if (modelInfo?.default_size) {
                      setVideoSize(modelInfo.default_size)
                    }
                  }}
                >
                  {Object.entries(videoModels).map(([key, info]) => (
                    <Option key={key} value={key}>{info.name}</Option>
                  ))}
                </Select>
                {getCurrentModelInfo()?.description && (
                  <div style={{ fontSize: 11, color: '#666', marginTop: 4 }}>
                    {getCurrentModelInfo()?.description}
                  </div>
                )}
              </div>
            </Col>
            <Col span={12}>
              <div style={{ marginBottom: 16 }}>
                <div style={{ marginBottom: 8, color: '#e0e0e0' }}>视频分辨率</div>
                <Select
                  style={{ width: '100%' }}
                  value={videoSize || systemVideoConfig.size}
                  onChange={setVideoSize}
                >
                  {getCurrentModelSizes().map(size => (
                    <Option key={size.value} value={size.value}>{size.label}</Option>
                  ))}
                </Select>
              </div>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <div style={{ marginBottom: 16 }}>
                <div style={{ marginBottom: 8, color: '#e0e0e0' }}>生成组数</div>
                <InputNumber
                  style={{ width: '100%' }}
                  min={1}
                  max={10}
                  value={videoGroupCount}
                  onChange={(v) => setVideoGroupCount(v || 1)}
                />
                <div style={{ fontSize: 11, color: '#666', marginTop: 4 }}>
                  每个分镜生成的视频数量
                </div>
              </div>
            </Col>
            <Col span={12}>
              <div style={{ marginBottom: 16 }}>
                <div style={{ marginBottom: 8, color: '#e0e0e0' }}>随机种子</div>
                <InputNumber
                  style={{ width: '100%' }}
                  min={0}
                  value={videoSeed}
                  onChange={(v) => setVideoSeed(v)}
                  placeholder="留空为随机"
                />
              </div>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ color: '#e0e0e0' }}>智能改写</span>
                <Switch
                  checked={videoPromptExtend !== null ? videoPromptExtend : systemVideoConfig.prompt_extend}
                  onChange={setVideoPromptExtend}
                />
              </div>
              <div style={{ fontSize: 11, color: '#666', marginTop: 4 }}>
                自动优化和扩展提示词
              </div>
            </Col>
            <Col span={12}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ color: '#e0e0e0' }}>添加水印</span>
                <Switch
                  checked={videoWatermark !== null ? videoWatermark : systemVideoConfig.watermark}
                  onChange={setVideoWatermark}
                />
              </div>
            </Col>
          </Row>
        </div>
      </Modal>
    </div>
  )
}

export default VideosPage
