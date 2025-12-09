import { useState, useEffect, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { Card, Button, List, Modal, Input, Select, InputNumber, Switch, message, Popconfirm, Space, Empty, Spin, Row, Col, Tabs, Tag } from 'antd'
import { PlusOutlined, DeleteOutlined, PlayCircleOutlined, SaveOutlined, VideoCameraOutlined } from '@ant-design/icons'
import { videoStudioApi, galleryApi, audioApi, settingsApi, VideoStudioTask, GalleryImage, AudioItem, VideoModelInfo } from '../../services/api'
import { useProjectStore } from '../../stores/projectStore'

const { TextArea } = Input
const { Option } = Select

const VideoStudioPage = () => {
  const { projectId } = useParams<{ projectId: string }>()
  const { fetchProject } = useProjectStore()
  
  const [tasks, setTasks] = useState<VideoStudioTask[]>([])
  const [loading, setLoading] = useState(true)
  const [createModalVisible, setCreateModalVisible] = useState(false)
  const [detailModalVisible, setDetailModalVisible] = useState(false)
  const [selectedTask, setSelectedTask] = useState<VideoStudioTask | null>(null)
  
  // 图库和音频库
  const [galleryImages, setGalleryImages] = useState<GalleryImage[]>([])
  const [audioItems, setAudioItems] = useState<AudioItem[]>([])
  
  // 创建任务表单
  const [taskName, setTaskName] = useState('')
  const [firstFrameUrl, setFirstFrameUrl] = useState('')
  const [audioUrl, setAudioUrl] = useState('')
  const [prompt, setPrompt] = useState('')
  const [negativePrompt, setNegativePrompt] = useState('')
  const [model, setModel] = useState('wan2.5-i2v-preview')
  const [resolution, setResolution] = useState('720P')
  const [duration, setDuration] = useState(5)
  const [autoAudio, setAutoAudio] = useState(false)
  const [groupCount, setGroupCount] = useState(1)
  const [creating, setCreating] = useState(false)
  
  // 模型配置
  const [videoModels, setVideoModels] = useState<Record<string, VideoModelInfo>>({})
  
  // 轮询
  const pollingRef = useRef<Set<string>>(new Set())
  const isMountedRef = useRef(true)

  useEffect(() => {
    isMountedRef.current = true
    if (projectId) {
      fetchProject(projectId)
      loadData()
    }
    return () => {
      isMountedRef.current = false
    }
  }, [projectId, fetchProject])

  const loadData = async () => {
    if (!projectId) return
    setLoading(true)
    try {
      const [tasksRes, galleryRes, audioRes, settingsRes] = await Promise.all([
        videoStudioApi.list(projectId),
        galleryApi.list(projectId),
        audioApi.list(projectId),
        settingsApi.getSettings()
      ])
      setTasks(tasksRes.tasks)
      setGalleryImages(galleryRes.images)
      setAudioItems(audioRes.audios)
      setVideoModels(settingsRes.available_video_models)
      
      // 启动轮询
      tasksRes.tasks.forEach(task => {
        if (task.status === 'processing') {
          startPolling(task.id)
        }
      })
    } catch (error) {
      message.error('加载失败')
    } finally {
      setLoading(false)
    }
  }

  const startPolling = (taskId: string) => {
    if (pollingRef.current.has(taskId)) return
    pollingRef.current.add(taskId)
    
    const poll = async () => {
      if (!pollingRef.current.has(taskId) || !isMountedRef.current) return
      
      try {
        const result = await videoStudioApi.getStatus(taskId)
        
        if (isMountedRef.current) {
          setTasks(prev => prev.map(t => t.id === taskId ? result.task : t))
          
          // 更新详情弹窗中的任务
          setSelectedTask(prev => {
            if (prev?.id === taskId) return result.task
            return prev
          })
        }
        
        if (result.task.status === 'succeeded' || result.task.status === 'failed') {
          pollingRef.current.delete(taskId)
          if (result.task.status === 'succeeded') {
            message.success('视频生成完成')
          } else {
            message.error(`视频生成失败: ${result.task.error_message || '未知错误'}`)
          }
        } else {
          setTimeout(poll, 5000)
        }
      } catch (error) {
        pollingRef.current.delete(taskId)
        console.error('轮询错误:', error)
      }
    }
    
    poll()
  }

  const handleCreate = async () => {
    if (!projectId || !firstFrameUrl) {
      message.warning('请选择首帧图')
      return
    }
    
    setCreating(true)
    try {
      const result = await videoStudioApi.create({
        project_id: projectId,
        name: taskName || undefined,
        first_frame_url: firstFrameUrl,
        audio_url: audioUrl || undefined,
        prompt,
        negative_prompt: negativePrompt,
        model,
        resolution,
        duration,
        auto_audio: autoAudio,
        group_count: groupCount
      })
      
      setTasks(prev => [result.task, ...prev])
      setCreateModalVisible(false)
      resetForm()
      
      // 启动轮询
      startPolling(result.task.id)
      
      message.success('任务已创建')
    } catch (error: any) {
      message.error(error.message || '创建失败')
    } finally {
      setCreating(false)
    }
  }

  const resetForm = () => {
    setTaskName('')
    setFirstFrameUrl('')
    setAudioUrl('')
    setPrompt('')
    setNegativePrompt('')
    setModel('wan2.5-i2v-preview')
    setResolution('720P')
    setDuration(5)
    setAutoAudio(false)
    setGroupCount(1)
  }

  const handleViewDetail = (task: VideoStudioTask) => {
    setSelectedTask(task)
    setDetailModalVisible(true)
    
    // 如果正在处理，启动轮询
    if (task.status === 'processing') {
      startPolling(task.id)
    }
  }

  const handleSaveToLibrary = async (videoUrl: string) => {
    if (!selectedTask) return
    
    try {
      await videoStudioApi.saveToLibrary(selectedTask.id, videoUrl)
      message.success('已保存到视频库')
    } catch (error: any) {
      message.error(error.message || '保存失败')
    }
  }

  const handleDelete = async (task: VideoStudioTask) => {
    try {
      await videoStudioApi.delete(task.id)
      setTasks(prev => prev.filter(t => t.id !== task.id))
      message.success('删除成功')
    } catch (error: any) {
      message.error(error.message || '删除失败')
    }
  }

  const handleDeleteAll = async () => {
    if (!projectId) return
    try {
      await videoStudioApi.deleteAll(projectId)
      setTasks([])
      message.success('全部删除成功')
    } catch (error: any) {
      message.error(error.message || '删除失败')
    }
  }

  const getStatusTag = (status: string) => {
    const statusMap: Record<string, { color: string; text: string }> = {
      pending: { color: 'default', text: '等待中' },
      processing: { color: 'processing', text: '生成中' },
      succeeded: { color: 'success', text: '已完成' },
      failed: { color: 'error', text: '失败' }
    }
    const s = statusMap[status] || { color: 'default', text: status }
    return <Tag color={s.color}>{s.text}</Tag>
  }

  const getCurrentModelResolutions = () => {
    const modelInfo = videoModels[model]
    return modelInfo?.resolutions || []
  }

  const isWan25 = model.includes('wan2.5')

  return (
    <div style={{ padding: 24 }}>
      <Card
        title={
          <Space>
            <VideoCameraOutlined />
            视频工作室
          </Space>
        }
        extra={
          <Space>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setCreateModalVisible(true)}
            >
              新建任务
            </Button>
            {tasks.length > 0 && (
              <Popconfirm
                title="确定删除所有任务？"
                onConfirm={handleDeleteAll}
              >
                <Button danger icon={<DeleteOutlined />}>
                  全部删除
                </Button>
              </Popconfirm>
            )}
          </Space>
        }
        style={{ background: '#1a1a1a', borderColor: '#333' }}
      >
        {tasks.length === 0 ? (
          <Empty description="暂无任务" />
        ) : (
          <List
            grid={{ gutter: 16, column: 4 }}
            dataSource={tasks}
            loading={loading}
            renderItem={(task) => (
              <List.Item>
                <Card
                  size="small"
                  style={{ background: '#242424', borderColor: '#333' }}
                  cover={
                    <div 
                      style={{ 
                        height: 120, 
                        background: '#1a1a1a', 
                        display: 'flex', 
                        alignItems: 'center', 
                        justifyContent: 'center',
                        cursor: 'pointer',
                        position: 'relative'
                      }}
                      onClick={() => handleViewDetail(task)}
                    >
                      {task.first_frame_url ? (
                        <img 
                          src={task.first_frame_url} 
                          alt="首帧" 
                          style={{ width: '100%', height: '100%', objectFit: 'cover' }} 
                        />
                      ) : (
                        <PlayCircleOutlined style={{ fontSize: 48, color: '#1890ff' }} />
                      )}
                      {task.status === 'processing' && (
                        <div style={{ 
                          position: 'absolute', 
                          top: 0, 
                          left: 0, 
                          right: 0, 
                          bottom: 0, 
                          background: 'rgba(0,0,0,0.5)', 
                          display: 'flex', 
                          alignItems: 'center', 
                          justifyContent: 'center' 
                        }}>
                          <Spin />
                        </div>
                      )}
                    </div>
                  }
                  actions={[
                    <Button type="link" size="small" onClick={() => handleViewDetail(task)}>查看</Button>,
                    <Popconfirm title="确定删除？" onConfirm={() => handleDelete(task)}>
                      <Button type="link" size="small" danger>删除</Button>
                    </Popconfirm>
                  ]}
                >
                  <div style={{ fontWeight: 500, marginBottom: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {task.name}
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    {getStatusTag(task.status)}
                    <span style={{ fontSize: 12, color: '#888' }}>
                      {task.video_urls.length}/{task.group_count}
                    </span>
                  </div>
                </Card>
              </List.Item>
            )}
          />
        )}
      </Card>

      {/* 创建任务弹窗 */}
      <Modal
        title="新建视频生成任务"
        open={createModalVisible}
        onCancel={() => {
          setCreateModalVisible(false)
          resetForm()
        }}
        onOk={handleCreate}
        confirmLoading={creating}
        okButtonProps={{ disabled: !firstFrameUrl }}
        width={700}
      >
        <Tabs
          items={[
            {
              key: 'basic',
              label: '基本信息',
              children: (
                <div>
                  <div style={{ marginBottom: 16 }}>
                    <div style={{ marginBottom: 8 }}>任务名称</div>
                    <Input
                      value={taskName}
                      onChange={(e) => setTaskName(e.target.value)}
                      placeholder="输入任务名称（可选）"
                    />
                  </div>
                  
                  <div style={{ marginBottom: 16 }}>
                    <div style={{ marginBottom: 8 }}>首帧图 *</div>
                    <Select
                      style={{ width: '100%' }}
                      value={firstFrameUrl || undefined}
                      onChange={setFirstFrameUrl}
                      placeholder="从图库选择首帧图"
                      optionLabelProp="label"
                    >
                      {galleryImages.map(img => (
                        <Option key={img.id} value={img.url} label={img.name}>
                          <Space>
                            <img src={img.url} alt="" style={{ width: 40, height: 40, objectFit: 'cover' }} />
                            {img.name}
                          </Space>
                        </Option>
                      ))}
                    </Select>
                    {firstFrameUrl && (
                      <div style={{ marginTop: 8 }}>
                        <img src={firstFrameUrl} alt="预览" style={{ maxWidth: 200, maxHeight: 150 }} />
                      </div>
                    )}
                  </div>
                  
                  <div style={{ marginBottom: 16 }}>
                    <div style={{ marginBottom: 8 }}>提示词</div>
                    <TextArea
                      value={prompt}
                      onChange={(e) => setPrompt(e.target.value)}
                      placeholder="描述视频内容"
                      rows={3}
                    />
                  </div>
                  
                  <div>
                    <div style={{ marginBottom: 8 }}>负面提示词</div>
                    <TextArea
                      value={negativePrompt}
                      onChange={(e) => setNegativePrompt(e.target.value)}
                      placeholder="不希望出现的内容"
                      rows={2}
                    />
                  </div>
                </div>
              )
            },
            {
              key: 'params',
              label: '生成参数',
              children: (
                <div>
                  <Row gutter={16}>
                    <Col span={12}>
                      <div style={{ marginBottom: 16 }}>
                        <div style={{ marginBottom: 8 }}>模型</div>
                        <Select
                          style={{ width: '100%' }}
                          value={model}
                          onChange={(v) => {
                            setModel(v)
                            const modelInfo = videoModels[v]
                            if (modelInfo?.default_resolution) {
                              setResolution(modelInfo.default_resolution)
                            }
                          }}
                        >
                          {Object.entries(videoModels).map(([key, info]) => (
                            <Option key={key} value={key}>{info.name}</Option>
                          ))}
                        </Select>
                      </div>
                    </Col>
                    <Col span={12}>
                      <div style={{ marginBottom: 16 }}>
                        <div style={{ marginBottom: 8 }}>分辨率</div>
                        <Select
                          style={{ width: '100%' }}
                          value={resolution}
                          onChange={setResolution}
                        >
                          {getCurrentModelResolutions().map(res => (
                            <Option key={res.value} value={res.value}>{res.label}</Option>
                          ))}
                        </Select>
                      </div>
                    </Col>
                  </Row>
                  
                  <Row gutter={16}>
                    <Col span={12}>
                      <div style={{ marginBottom: 16 }}>
                        <div style={{ marginBottom: 8 }}>时长（秒）</div>
                        <InputNumber
                          style={{ width: '100%' }}
                          min={5}
                          max={10}
                          value={duration}
                          onChange={(v) => setDuration(v || 5)}
                        />
                      </div>
                    </Col>
                    <Col span={12}>
                      <div style={{ marginBottom: 16 }}>
                        <div style={{ marginBottom: 8 }}>生成组数</div>
                        <InputNumber
                          style={{ width: '100%' }}
                          min={1}
                          max={5}
                          value={groupCount}
                          onChange={(v) => setGroupCount(v || 1)}
                        />
                      </div>
                    </Col>
                  </Row>
                  
                  {isWan25 && (
                    <>
                      <div style={{ marginBottom: 16 }}>
                        <div style={{ marginBottom: 8 }}>音频设置</div>
                        <Select
                          style={{ width: '100%' }}
                          value={audioUrl || undefined}
                          onChange={setAudioUrl}
                          placeholder="从音频库选择（可选）"
                          allowClear
                        >
                          {audioItems.map(audio => (
                            <Option key={audio.id} value={audio.url}>
                              {audio.name}
                            </Option>
                          ))}
                        </Select>
                      </div>
                      
                      <div>
                        <Space>
                          <Switch
                            checked={autoAudio}
                            onChange={setAutoAudio}
                            disabled={!!audioUrl}
                          />
                          <span>自动生成音频</span>
                          {audioUrl && <span style={{ color: '#888' }}>（已选择音频，自动生成已禁用）</span>}
                        </Space>
                      </div>
                    </>
                  )}
                </div>
              )
            }
          ]}
        />
      </Modal>

      {/* 详情弹窗 */}
      <Modal
        title={selectedTask?.name || '任务详情'}
        open={detailModalVisible}
        onCancel={() => setDetailModalVisible(false)}
        footer={null}
        width={800}
      >
        {selectedTask && (
          <div>
            <div style={{ marginBottom: 16 }}>
              <Space>
                {getStatusTag(selectedTask.status)}
                <span style={{ color: '#888' }}>
                  {selectedTask.model} · {selectedTask.resolution} · {selectedTask.duration}秒
                </span>
              </Space>
            </div>
            
            {selectedTask.status === 'processing' && (
              <div style={{ textAlign: 'center', padding: 40 }}>
                <Spin size="large" />
                <div style={{ marginTop: 16, color: '#888' }}>
                  正在生成视频... ({selectedTask.video_urls.length}/{selectedTask.group_count})
                </div>
              </div>
            )}
            
            {selectedTask.status === 'failed' && (
              <div style={{ padding: 20, background: '#2a1818', borderRadius: 8, color: '#ff4d4f' }}>
                生成失败: {selectedTask.error_message || '未知错误'}
              </div>
            )}
            
            {selectedTask.video_urls.length > 0 && (
              <div>
                <div style={{ marginBottom: 16, fontWeight: 500 }}>生成结果</div>
                <Row gutter={16}>
                  {selectedTask.video_urls.map((url, index) => (
                    <Col key={index} span={12}>
                      <Card size="small" style={{ marginBottom: 16 }}>
                        <video
                          controls
                          style={{ width: '100%' }}
                          src={url}
                        />
                        <div style={{ marginTop: 8, textAlign: 'center' }}>
                          <Button
                            type="primary"
                            size="small"
                            icon={<SaveOutlined />}
                            onClick={() => handleSaveToLibrary(url)}
                          >
                            保存到视频库
                          </Button>
                        </div>
                      </Card>
                    </Col>
                  ))}
                </Row>
              </div>
            )}
            
            {selectedTask.prompt && (
              <div style={{ marginTop: 16 }}>
                <div style={{ fontWeight: 500, marginBottom: 8 }}>提示词</div>
                <div style={{ background: '#242424', padding: 12, borderRadius: 8 }}>
                  {selectedTask.prompt}
                </div>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  )
}

export default VideoStudioPage

