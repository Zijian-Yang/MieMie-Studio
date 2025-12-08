import { useEffect, useState, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { 
  Card, Button, Modal, Form, Input, Empty, Spin, message, 
  Image, Progress, Tag, Tooltip, Divider, Upload, Space
} from 'antd'
import { 
  PlayCircleOutlined, ReloadOutlined, VideoCameraOutlined,
  LoadingOutlined, CheckCircleOutlined, CloseCircleOutlined,
  SoundOutlined, UploadOutlined
} from '@ant-design/icons'
import { videosApi, framesApi, Video, Shot, Frame } from '../../services/api'
import { useProjectStore } from '../../stores/projectStore'

const { TextArea } = Input

const VideosPage = () => {
  const { projectId } = useParams<{ projectId: string }>()
  const { currentProject, fetchProject } = useProjectStore()
  
  const [videos, setVideos] = useState<Video[]>([])
  const [frames, setFrames] = useState<Frame[]>([])
  const [shots, setShots] = useState<Shot[]>([])
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [selectedShot, setSelectedShot] = useState<Shot | null>(null)
  const [selectedVideo, setSelectedVideo] = useState<Video | null>(null)
  const [selectedFrame, setSelectedFrame] = useState<Frame | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [singleGenerating, setSingleGenerating] = useState(false)
  const [form] = Form.useForm()
  
  // 轮询状态更新
  const pollingRef = useRef<Set<string>>(new Set())

  useEffect(() => {
    const loadData = async () => {
      if (!projectId) return
      
      setLoading(true)
      try {
        // 不阻塞加载
        fetchProject(projectId).catch(() => {})
        const [videosRes, framesRes] = await Promise.all([
          videosApi.list(projectId),
          framesApi.list(projectId),
        ])
        setVideos(videosRes.videos)
        setFrames(framesRes.frames)
        
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
      // 清理轮询
      pollingRef.current.clear()
    }
  }, [projectId, fetchProject])

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
      if (!pollingRef.current.has(taskId)) return
      
      try {
        const result = await videosApi.getStatus(taskId)
        
        if (result.status === 'SUCCEEDED' || result.status === 'FAILED') {
          pollingRef.current.delete(taskId)
          
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
          
          if (result.status === 'SUCCEEDED') {
            message.success('视频生成完成')
          }
        } else {
          // 继续轮询
          setTimeout(poll, 5000)
        }
      } catch {
        pollingRef.current.delete(taskId)
      }
    }
    
    poll()
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
      const result = await videosApi.generateBatch(projectId)
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
    const video = videos.find(v => v.shot_id === shot.id)
    setSelectedVideo(video || null)
    
    const frame = frames.find(f => f.shot_id === shot.id)
    setSelectedFrame(frame || null)
    
    // 使用改进的提示词生成
    form.setFieldsValue({
      prompt: video?.prompt || buildVideoPrompt(shot)
    })
    
    setIsModalOpen(true)
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
    
    setSingleGenerating(true)
    try {
      const result = await videosApi.generate({
        project_id: projectId,
        shot_id: selectedShot.id,
        shot_number: selectedShot.shot_number,
        first_frame_url: frameUrl,
        prompt: values.prompt,
        duration: Math.min(selectedShot.duration || 5, 10) // 确保不超过10秒
      })
      
      setVideos(prev => {
        const exists = prev.find(v => v.shot_id === selectedShot.id)
        if (exists) {
          return prev.map(v => v.shot_id === selectedShot.id ? result.video : v)
        }
        return [...prev, result.video]
      })
      
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
  const getStatusTag = (video?: Video) => {
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
        <Button
          type="primary"
          icon={<PlayCircleOutlined />}
          onClick={generateAllVideos}
          loading={generating}
          disabled={shots.length === 0}
        >
          批量生成视频
        </Button>
      </div>

      {shots.length === 0 ? (
        <Empty 
          description="请先在分镜脚本页面解析分镜" 
          style={{ marginTop: 100 }} 
        />
      ) : (
        <div className="timeline" style={{ flexWrap: 'wrap' }}>
          {shots.map((shot) => {
            const video = videos.find(v => v.shot_id === shot.id)
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
    </div>
  )
}

export default VideosPage
