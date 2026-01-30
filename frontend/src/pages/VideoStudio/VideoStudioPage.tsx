import { useState, useEffect, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { Card, Button, List, Modal, Input, Select, InputNumber, Switch, message, Popconfirm, Space, Empty, Spin, Row, Col, Tabs, Tag, Form } from 'antd'
import { PlusOutlined, DeleteOutlined, PlayCircleOutlined, SaveOutlined, VideoCameraOutlined, EditOutlined, ReloadOutlined } from '@ant-design/icons'
import { videoStudioApi, galleryApi, audioApi, videoLibraryApi, settingsApi, VideoStudioTask, GalleryImage, AudioItem, VideoLibraryItem, VideoModelInfo, RefVideoModelInfo, TextToVideoModelInfo, KeyframeToVideoModelInfo } from '../../services/api'
import { useProjectStore } from '../../stores/projectStore'

const { TextArea } = Input
const { Option } = Select

// 参考素材项类型
interface ReferenceItem {
  id: string
  url: string
  type: 'video' | 'image'
  name: string
  thumbnail?: string
  duration?: number  // 视频时长
}

const VideoStudioPage = () => {
  const { projectId } = useParams<{ projectId: string }>()
  const { fetchProject } = useProjectStore()
  
  const [tasks, setTasks] = useState<VideoStudioTask[]>([])
  const [loading, setLoading] = useState(true)
  const [createModalVisible, setCreateModalVisible] = useState(false)
  const [detailModalVisible, setDetailModalVisible] = useState(false)
  const [editModalVisible, setEditModalVisible] = useState(false)
  const [selectedTask, setSelectedTask] = useState<VideoStudioTask | null>(null)
  const [editForm] = Form.useForm()
  const [saving, setSaving] = useState(false)
  const [regenerating, setRegenerating] = useState(false)
  
  // 图库、音频库和视频库
  const [galleryImages, setGalleryImages] = useState<GalleryImage[]>([])
  const [audioItems, setAudioItems] = useState<AudioItem[]>([])
  const [videoLibraryItems, setVideoLibraryItems] = useState<VideoLibraryItem[]>([])
  
  // 创建任务表单
  const [taskType, setTaskType] = useState<'image_to_video' | 'reference_to_video' | 'text_to_video' | 'keyframe_to_video'>('image_to_video')  // 任务类型
  const [taskName, setTaskName] = useState('')
  const [firstFrameUrl, setFirstFrameUrl] = useState('')
  const [lastFrameUrl, setLastFrameUrl] = useState('')  // 首尾帧生视频的尾帧图
  const [audioUrl, setAudioUrl] = useState('')
  const [referenceItems, setReferenceItems] = useState<ReferenceItem[]>([])  // 参考素材队列（视频+图片，有序）
  const [prompt, setPrompt] = useState('')
  const [negativePrompt, setNegativePrompt] = useState('')
  const [model, setModel] = useState('wan2.5-i2v-preview')
  const [resolution, setResolution] = useState('1080P')  // 默认1080P
  const [size, setSize] = useState('1920*1080')  // 参考生视频分辨率
  const [duration, setDuration] = useState(5)
  const [promptExtend, setPromptExtend] = useState(true)  // 智能改写
  const [watermark, setWatermark] = useState(false)  // 水印
  const [seed, setSeed] = useState<number | undefined>(undefined)  // 随机种子
  const [autoAudio, setAutoAudio] = useState(true)  // 自动配音（默认开启）
  const [shotType, setShotType] = useState('single')  // 镜头类型
  const [t2vPromptExtend, setT2vPromptExtend] = useState(true)  // 文生视频智能改写
  const [groupCount, setGroupCount] = useState(1)
  const [creating, setCreating] = useState(false)
  
  // 模型配置
  const [videoModels, setVideoModels] = useState<Record<string, VideoModelInfo>>({})
  const [refVideoModels, setRefVideoModels] = useState<Record<string, RefVideoModelInfo>>({})
  const [textToVideoModels, setTextToVideoModels] = useState<Record<string, TextToVideoModelInfo>>({})
  const [keyframeToVideoModels, setKeyframeToVideoModels] = useState<Record<string, KeyframeToVideoModelInfo>>({})
  
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
      const [tasksRes, galleryRes, audioRes, videoLibRes, settingsRes] = await Promise.all([
        videoStudioApi.list(projectId),
        galleryApi.list(projectId),
        audioApi.list(projectId),
        videoLibraryApi.list(projectId),
        settingsApi.getSettings()
      ])
      setTasks(tasksRes.tasks)
      setGalleryImages(galleryRes.images)
      setAudioItems(audioRes.audios)
      setVideoLibraryItems(videoLibRes.videos)
      setVideoModels(settingsRes.available_video_models)
      setRefVideoModels(settingsRes.available_ref_video_models || {})
      setTextToVideoModels(settingsRes.available_text_to_video_models || {})
      setKeyframeToVideoModels(settingsRes.available_keyframe_to_video_models || {})
      
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
    if (!projectId) return
    
    // 根据任务类型验证
    if (taskType === 'image_to_video' && !firstFrameUrl) {
      message.warning('请选择首帧图')
      return
    }
    if (taskType === 'reference_to_video' && referenceItems.length === 0) {
      message.warning('请选择参考素材（视频或图片）')
      return
    }
    if (taskType === 'text_to_video' && !prompt) {
      message.warning('文生视频任务需要提供提示词')
      return
    }
    if (taskType === 'keyframe_to_video') {
      if (!firstFrameUrl) {
        message.warning('请选择首帧图')
        return
      }
      if (!lastFrameUrl) {
        message.warning('请选择尾帧图')
        return
      }
    }
    
    setCreating(true)
    try {
      // 获取当前文生视频模型
      const t2vModel = taskType === 'text_to_video' ? (model || 'wan2.6-t2v') : undefined
      const t2vModelInfo = t2vModel ? textToVideoModels[t2vModel] : undefined
      
      // 确定使用的模型
      let taskModel = model
      if (taskType === 'reference_to_video') {
        taskModel = 'wan2.6-r2v'
      } else if (taskType === 'text_to_video') {
        taskModel = t2vModel || 'wan2.6-t2v'
      } else if (taskType === 'keyframe_to_video') {
        taskModel = model || 'wan2.2-kf2v-flash'
      }
      
      const result = await videoStudioApi.create({
        project_id: projectId,
        name: taskName || undefined,
        task_type: taskType,
        // 图生视频/首尾帧生视频参数
        first_frame_url: (taskType === 'image_to_video' || taskType === 'keyframe_to_video') ? firstFrameUrl : undefined,
        last_frame_url: taskType === 'keyframe_to_video' ? lastFrameUrl : undefined,
        audio_url: taskType === 'image_to_video' ? (audioUrl || undefined) : (taskType === 'text_to_video' ? (audioUrl || undefined) : undefined),
        // 参考生视频参数（按顺序传递所有参考素材URL）
        reference_video_urls: taskType === 'reference_to_video' ? referenceItems.map(item => item.url) : undefined,
        // 通用参数
        prompt,
        negative_prompt: negativePrompt,
        model: taskModel,
        duration,
        watermark,
        seed: seed || undefined,
        auto_audio: autoAudio,
        shot_type: shotType,
        // 图生视频/首尾帧生视频专用
        resolution: (taskType === 'image_to_video' || taskType === 'keyframe_to_video') ? resolution : undefined,
        prompt_extend: (taskType === 'image_to_video' || taskType === 'keyframe_to_video') ? promptExtend : undefined,
        // 参考生视频专用
        size: taskType === 'reference_to_video' ? size : (taskType === 'text_to_video' ? size : undefined),
        // 文生视频专用
        t2v_prompt_extend: taskType === 'text_to_video' ? t2vPromptExtend : undefined,
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
    setTaskType('image_to_video')
    setTaskName('')
    setFirstFrameUrl('')
    setLastFrameUrl('')  // 重置尾帧图
    setAudioUrl('')
    setReferenceItems([])
    setPrompt('')
    setNegativePrompt('')
    setModel('wan2.5-i2v-preview')
    setResolution('1080P')  // 默认1080P
    setSize('1920*1080')  // 默认参考生视频分辨率
    setDuration(5)
    setShotType('single')
    setPromptExtend(true)
    setT2vPromptExtend(true)  // 重置文生视频智能改写
    setWatermark(false)
    setSeed(undefined)
    setAutoAudio(true)  // 默认开启
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

  // 编辑表单的额外状态（不在 Form 中管理的值）
  const [editTaskType, setEditTaskType] = useState<'image_to_video' | 'reference_to_video' | 'text_to_video' | 'keyframe_to_video'>('image_to_video')
  const [editFirstFrameUrl, setEditFirstFrameUrl] = useState('')
  const [editLastFrameUrl, setEditLastFrameUrl] = useState('')  // 首尾帧生视频的尾帧图
  const [editAudioUrl, setEditAudioUrl] = useState('')
  const [editReferenceItems, setEditReferenceItems] = useState<ReferenceItem[]>([])  // 编辑弹窗中的参考素材队列
  const [editGroupCount, setEditGroupCount] = useState(1)
  const [editModel, setEditModel] = useState('wan2.5-i2v-preview')  // 编辑弹窗中的当前模型
  const [editT2vPromptExtend, setEditT2vPromptExtend] = useState(true)  // 编辑弹窗中的t2v智能改写

  // 获取编辑弹窗中当前模型的信息
  const getEditModelInfo = () => {
    if (editTaskType === 'reference_to_video') {
      return refVideoModels[editModel] || Object.values(refVideoModels)[0]
    }
    if (editTaskType === 'text_to_video') {
      return textToVideoModels[editModel] || Object.values(textToVideoModels)[0]
    }
    return videoModels[editModel]
  }

  // 打开编辑弹窗
  const openEditModal = (task: VideoStudioTask) => {
    setSelectedTask(task)
    // 设置非 Form 管理的值
    const taskTypeValue = (task.task_type || 'image_to_video') as 'image_to_video' | 'reference_to_video' | 'text_to_video' | 'keyframe_to_video'
    setEditTaskType(taskTypeValue)
    setEditFirstFrameUrl(task.first_frame_url || '')
    setEditLastFrameUrl(task.last_frame_url || '')  // 首尾帧生视频的尾帧图
    setEditAudioUrl(task.audio_url || '')
    // 将已有的 reference_video_urls 转换为 ReferenceItem 格式
    const existingUrls = task.reference_video_urls || []
    const items: ReferenceItem[] = existingUrls.map((url, index) => {
      // 尝试从视频库匹配
      const video = videoLibraryItems.find(v => v.url === url)
      if (video) {
        return {
          id: `ref-${Date.now()}-${index}`,
          url: video.url,
          type: 'video' as const,
          name: video.name,
          thumbnail: video.thumbnail_url,
          duration: video.duration
        }
      }
      // 尝试从图库匹配
      const image = galleryImages.find(img => img.url === url)
      if (image) {
        return {
          id: `ref-${Date.now()}-${index}`,
          url: image.url,
          type: 'image' as const,
          name: image.name,
          thumbnail: image.url
        }
      }
      // 未知来源，根据URL扩展名判断类型
      const isVideo = /\.(mp4|mov|avi|webm)$/i.test(url)
      return {
        id: `ref-${Date.now()}-${index}`,
        url,
        type: isVideo ? 'video' as const : 'image' as const,
        name: url.split('/').pop() || `素材${index + 1}`,
        thumbnail: isVideo ? undefined : url
      }
    })
    setEditReferenceItems(items)
    setEditGroupCount(task.group_count || 1)
    // 根据任务类型设置默认模型
    let defaultModel = 'wan2.5-i2v-preview'
    if (taskTypeValue === 'text_to_video') defaultModel = 'wan2.6-t2v'
    else if (taskTypeValue === 'keyframe_to_video') defaultModel = 'wan2.2-kf2v-flash'
    setEditModel(task.model || defaultModel)
    setEditT2vPromptExtend(task.prompt_extend !== false)  // 文生视频智能改写，默认true
    
    editForm.setFieldsValue({
      name: task.name,
      prompt: task.prompt,
      negative_prompt: task.negative_prompt,
      model: task.model,
      resolution: task.resolution,
      size: task.size,
      duration: task.duration,
      prompt_extend: task.prompt_extend,
      watermark: task.watermark,
      seed: task.seed,
      auto_audio: task.auto_audio,
      shot_type: task.shot_type || 'single',
    })
    setEditModalVisible(true)
  }

  // 保存编辑
  const handleSaveEdit = async () => {
    if (!selectedTask) return
    
    // 根据任务类型验证
    if (editTaskType === 'image_to_video' && !editFirstFrameUrl) {
      message.warning('请选择首帧图')
      return
    }
    if (editTaskType === 'reference_to_video' && editReferenceItems.length === 0) {
      message.warning('请选择参考素材（视频或图片）')
      return
    }
    if (editTaskType === 'text_to_video' && !editForm.getFieldValue('prompt')) {
      message.warning('文生视频任务需要提供提示词')
      return
    }
    if (editTaskType === 'keyframe_to_video') {
      if (!editFirstFrameUrl) {
        message.warning('请选择首帧图')
        return
      }
      if (!editLastFrameUrl) {
        message.warning('请选择尾帧图')
        return
      }
    }
    
    try {
      setSaving(true)
      const values = editForm.getFieldsValue()
      
      // 构建更新数据
      const updateData: any = {
        ...values,
        task_type: editTaskType,
        group_count: editGroupCount,
      }
      
      if (editTaskType === 'image_to_video') {
        updateData.first_frame_url = editFirstFrameUrl
        updateData.audio_url = editAudioUrl || undefined
      } else if (editTaskType === 'reference_to_video') {
        // 按顺序传递所有参考素材URL
        updateData.reference_video_urls = editReferenceItems.map(item => item.url)
        updateData.size = values.size
      } else if (editTaskType === 'text_to_video') {
        updateData.prompt_extend = editT2vPromptExtend
        updateData.size = values.size
        updateData.audio_url = editAudioUrl || undefined
      } else if (editTaskType === 'keyframe_to_video') {
        updateData.first_frame_url = editFirstFrameUrl
        updateData.last_frame_url = editLastFrameUrl
      }
      
      const updatedTask = await videoStudioApi.update(selectedTask.id, updateData)
      setTasks(prev => prev.map(t => t.id === selectedTask.id ? updatedTask : t))
      setSelectedTask(updatedTask)
      setEditModalVisible(false)
      message.success('任务已更新')
    } catch (error: any) {
      message.error(error.message || '更新失败')
    } finally {
      setSaving(false)
    }
  }

  // 重新生成
  const handleRegenerate = async (task: VideoStudioTask) => {
    try {
      setRegenerating(true)
      const { task: updatedTask, task_ids } = await videoStudioApi.regenerate(task.id)
      setTasks(prev => prev.map(t => t.id === task.id ? updatedTask : t))
      setSelectedTask(updatedTask)
      
      // 启动轮询
      task_ids.forEach(() => {
        startPolling(task.id)
      })
      
      message.success('已开始重新生成')
    } catch (error: any) {
      message.error(error.message || '重新生成失败')
    } finally {
      setRegenerating(false)
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

  const isWan25OrNewer = model.includes('wan2.5') || model.includes('wan2.6')
  const isWan26 = model.includes('wan2.6')
  const currentModelInfo = videoModels[model]
  const currentRefVideoModelInfo = refVideoModels['wan2.6-r2v']  // 目前只有一个参考生视频模型

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
        okButtonProps={{ 
          disabled: taskType === 'image_to_video' 
            ? !firstFrameUrl 
            : taskType === 'reference_to_video'
              ? referenceItems.length === 0  // 至少需要一个参考素材
              : taskType === 'keyframe_to_video'
                ? !firstFrameUrl || !lastFrameUrl  // 首尾帧都需要
                : !prompt  // text_to_video 需要提示词
        }}
        width={700}
      >
        <Tabs
          items={[
            {
              key: 'basic',
              label: '基本信息',
              children: (
                <div>
                  {/* 任务类型选择 */}
                  <div style={{ marginBottom: 16 }}>
                    <div style={{ marginBottom: 8 }}>任务类型</div>
                    <Select
                      style={{ width: '100%' }}
                      value={taskType}
                      onChange={(v) => {
                        setTaskType(v)
                        // 切换类型时重置相关字段
                        if (v === 'reference_to_video') {
                          setModel('wan2.6-r2v')
                          setFirstFrameUrl('')
                          setLastFrameUrl('')
                          setAudioUrl('')
                        } else if (v === 'text_to_video') {
                          setModel('wan2.6-t2v')
                          setFirstFrameUrl('')
                          setLastFrameUrl('')
                          setReferenceVideoUrls([])
                        } else if (v === 'keyframe_to_video') {
                          setModel('wan2.2-kf2v-flash')
                          setReferenceVideoUrls([])
                          setAudioUrl('')
                          setResolution('720P')  // 默认720P
                        } else {
                          setModel('wan2.5-i2v-preview')
                          setReferenceVideoUrls([])
                          setLastFrameUrl('')
                        }
                      }}
                    >
                      <Option value="image_to_video">
                        <Space>
                          <Tag color="blue">图生视频</Tag>
                          基于首帧图生成视频
                        </Space>
                      </Option>
                      <Option value="reference_to_video">
                        <Space>
                          <Tag color="green">参考生视频</Tag>
                          参考视频/图片中的角色生成新视频
                        </Space>
                      </Option>
                      <Option value="text_to_video">
                        <Space>
                          <Tag color="purple">文生视频</Tag>
                          基于文字描述生成视频
                        </Space>
                      </Option>
                      <Option value="keyframe_to_video">
                        <Space>
                          <Tag color="orange">首尾帧生视频</Tag>
                          基于首帧和尾帧图生成平滑过渡视频
                        </Space>
                      </Option>
                    </Select>
                  </div>
                  
                  <div style={{ marginBottom: 16 }}>
                    <div style={{ marginBottom: 8 }}>任务名称</div>
                    <Input
                      value={taskName}
                      onChange={(e) => setTaskName(e.target.value)}
                      placeholder="输入任务名称（可选）"
                    />
                  </div>
                  
                  {/* 图生视频：首帧图选择 */}
                  {taskType === 'image_to_video' && (
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
                  )}
                  
                  {/* 参考生视频：参考素材选择（视频+图片，总数≤5） */}
                  {taskType === 'reference_to_video' && (
                    <>
                      {/* 添加素材选择器 */}
                      <Row gutter={16}>
                        <Col span={12}>
                          <div style={{ marginBottom: 16 }}>
                            <div style={{ marginBottom: 8 }}>添加参考视频</div>
                            <Select
                              style={{ width: '100%' }}
                              value={undefined}
                              onChange={(url) => {
                                if (!url || referenceItems.length >= 5) return
                                const videoCount = referenceItems.filter(i => i.type === 'video').length
                                if (videoCount >= 3) {
                                  message.warning('视频最多3个')
                                  return
                                }
                                const video = videoLibraryItems.find(v => v.url === url)
                                if (video && !referenceItems.some(i => i.url === url)) {
                                  setReferenceItems([...referenceItems, {
                                    id: `ref-${Date.now()}`,
                                    url: video.url,
                                    type: 'video',
                                    name: video.name,
                                    thumbnail: video.thumbnail_url,
                                    duration: video.duration
                                  }])
                                }
                              }}
                              placeholder="选择视频添加到队列"
                              disabled={referenceItems.length >= 5 || referenceItems.filter(i => i.type === 'video').length >= 3}
                            >
                              {videoLibraryItems.filter(v => !referenceItems.some(i => i.url === v.url)).map(video => (
                                <Option key={video.id} value={video.url}>
                                  <Space>
                                    <VideoCameraOutlined />
                                    {video.name}
                                    {video.duration && <span style={{ color: '#888' }}>({video.duration}s)</span>}
                                  </Space>
                                </Option>
                              ))}
                            </Select>
                          </div>
                        </Col>
                        <Col span={12}>
                          <div style={{ marginBottom: 16 }}>
                            <div style={{ marginBottom: 8 }}>添加参考图片</div>
                            <Select
                              style={{ width: '100%' }}
                              value={undefined}
                              onChange={(url) => {
                                if (!url || referenceItems.length >= 5) return
                                const imageCount = referenceItems.filter(i => i.type === 'image').length
                                if (imageCount >= 5) {
                                  message.warning('图片最多5张')
                                  return
                                }
                                const image = galleryImages.find(img => img.url === url)
                                if (image && !referenceItems.some(i => i.url === url)) {
                                  setReferenceItems([...referenceItems, {
                                    id: `ref-${Date.now()}`,
                                    url: image.url,
                                    type: 'image',
                                    name: image.name,
                                    thumbnail: image.url
                                  }])
                                }
                              }}
                              placeholder="选择图片添加到队列"
                              disabled={referenceItems.length >= 5}
                            >
                              {galleryImages.filter(img => !referenceItems.some(i => i.url === img.url)).map(img => (
                                <Option key={img.id} value={img.url}>
                                  <Space>
                                    <img src={img.url} alt="" style={{ width: 24, height: 24, objectFit: 'cover', borderRadius: 2 }} />
                                    {img.name}
                                  </Space>
                                </Option>
                              ))}
                            </Select>
                          </div>
                        </Col>
                      </Row>
                      
                      {/* 已选素材队列 */}
                      <div style={{ 
                        padding: '12px', 
                        background: '#1a1a1a', 
                        borderRadius: 8,
                        marginBottom: 16 
                      }}>
                        <div style={{ marginBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontWeight: 500 }}>
                            已选素材队列
                            <span style={{ 
                              marginLeft: 8, 
                              color: referenceItems.length >= 5 ? '#ff4d4f' : '#52c41a',
                              fontSize: 12,
                              fontWeight: 'normal'
                            }}>
                              ({referenceItems.length}/5)
                            </span>
                          </span>
                          {referenceItems.length > 0 && (
                            <Button type="link" size="small" danger onClick={() => setReferenceItems([])}>
                              清空全部
                            </Button>
                          )}
                        </div>
                        
                        {referenceItems.length === 0 ? (
                          <div style={{ color: '#666', textAlign: 'center', padding: '20px 0' }}>
                            请从上方选择参考视频或图片
                          </div>
                        ) : (
                          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                            {referenceItems.map((item, index) => (
                              <div 
                                key={item.id}
                                style={{ 
                                  width: 110,
                                  background: '#2a2a2a',
                                  borderRadius: 8,
                                  overflow: 'hidden',
                                  position: 'relative'
                                }}
                              >
                                {/* 缩略图 */}
                                <div style={{ 
                                  width: '100%', 
                                  height: 70, 
                                  background: '#333',
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'center'
                                }}>
                                  {item.type === 'video' ? (
                                    item.thumbnail ? (
                                      <img src={item.thumbnail} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                                    ) : (
                                      <VideoCameraOutlined style={{ fontSize: 24, color: '#666' }} />
                                    )
                                  ) : (
                                    <img src={item.thumbnail || item.url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                                  )}
                                </div>
                                
                                {/* 类型标签 */}
                                <Tag 
                                  color={item.type === 'video' ? 'blue' : 'green'} 
                                  style={{ position: 'absolute', top: 4, left: 4, fontSize: 10 }}
                                >
                                  {item.type === 'video' ? '视频' : '图片'}
                                </Tag>
                                
                                {/* character 编号 */}
                                <div style={{
                                  position: 'absolute',
                                  top: 4,
                                  right: 4,
                                  background: 'rgba(0,0,0,0.7)',
                                  color: '#fff',
                                  padding: '2px 6px',
                                  borderRadius: 4,
                                  fontSize: 10,
                                  fontWeight: 500
                                }}>
                                  character{index + 1}
                                </div>
                                
                                {/* 信息和操作 */}
                                <div style={{ padding: '6px 8px' }}>
                                  <div style={{ 
                                    fontSize: 11, 
                                    color: '#ccc',
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                    whiteSpace: 'nowrap',
                                    marginBottom: 4
                                  }}>
                                    {item.name}
                                  </div>
                                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                    <Space size={4}>
                                      <Button 
                                        type="text" 
                                        size="small"
                                        disabled={index === 0}
                                        onClick={() => {
                                          if (index > 0) {
                                            const newItems = [...referenceItems]
                                            ;[newItems[index - 1], newItems[index]] = [newItems[index], newItems[index - 1]]
                                            setReferenceItems(newItems)
                                          }
                                        }}
                                        style={{ padding: '0 4px', fontSize: 12 }}
                                      >
                                        ↑
                                      </Button>
                                      <Button 
                                        type="text" 
                                        size="small"
                                        disabled={index === referenceItems.length - 1}
                                        onClick={() => {
                                          if (index < referenceItems.length - 1) {
                                            const newItems = [...referenceItems]
                                            ;[newItems[index], newItems[index + 1]] = [newItems[index + 1], newItems[index]]
                                            setReferenceItems(newItems)
                                          }
                                        }}
                                        style={{ padding: '0 4px', fontSize: 12 }}
                                      >
                                        ↓
                                      </Button>
                                    </Space>
                                    <Button 
                                      type="text" 
                                      size="small" 
                                      danger
                                      onClick={() => setReferenceItems(referenceItems.filter(i => i.id !== item.id))}
                                      style={{ padding: '0 4px' }}
                                    >
                                      <DeleteOutlined style={{ fontSize: 12 }} />
                                    </Button>
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                        
                        <div style={{ marginTop: 12, fontSize: 12, color: '#888' }}>
                          提示词中使用 <code style={{ background: '#333', padding: '0 4px', borderRadius: 2 }}>character1</code>, <code style={{ background: '#333', padding: '0 4px', borderRadius: 2 }}>character2</code>... 按上述顺序引用角色
                        </div>
                      </div>
                    </>
                  )}
                  
                  {/* 首尾帧生视频：首帧图和尾帧图选择 */}
                  {taskType === 'keyframe_to_video' && (
                    <>
                      <Row gutter={16}>
                        <Col span={12}>
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
                                <img src={firstFrameUrl} alt="首帧预览" style={{ maxWidth: 150, maxHeight: 100 }} />
                              </div>
                            )}
                          </div>
                        </Col>
                        <Col span={12}>
                          <div style={{ marginBottom: 16 }}>
                            <div style={{ marginBottom: 8 }}>尾帧图 *</div>
                            <Select
                              style={{ width: '100%' }}
                              value={lastFrameUrl || undefined}
                              onChange={setLastFrameUrl}
                              placeholder="从图库选择尾帧图"
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
                            {lastFrameUrl && (
                              <div style={{ marginTop: 8 }}>
                                <img src={lastFrameUrl} alt="尾帧预览" style={{ maxWidth: 150, maxHeight: 100 }} />
                              </div>
                            )}
                          </div>
                        </Col>
                      </Row>
                      <div style={{ fontSize: 12, color: '#888', marginBottom: 16 }}>
                        首尾帧图片要求：JPEG/JPG/PNG/BMP/WEBP格式，尺寸360-2000像素，最大10MB。输出视频宽高比以首帧为准。
                      </div>
                    </>
                  )}
                  
                  <div style={{ marginBottom: 16 }}>
                    <div style={{ marginBottom: 8 }}>提示词{taskType === 'text_to_video' ? ' *' : ''}</div>
                    <TextArea
                      value={prompt}
                      onChange={(e) => setPrompt(e.target.value)}
                      placeholder={taskType === 'reference_to_video' 
                        ? "描述视频内容，使用 character1/character2 指代参考视频中的主体" 
                        : "描述视频内容"
                      }
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
                  {/* 图生视频参数 */}
                  {taskType === 'image_to_video' && (
                    <>
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
                                // 处理默认时长
                                if (modelInfo?.default_duration) {
                                  setDuration(modelInfo.default_duration)
                                }
                                // 处理音频支持
                                if (modelInfo?.supports_audio) {
                                  setAutoAudio(modelInfo.default_audio !== false)
                                } else {
                                  setAutoAudio(false)
                                  setAudioUrl('')
                                }
                                // 处理镜头类型
                                if (modelInfo?.supports_shot_type) {
                                  setShotType(modelInfo.default_shot_type || 'single')
                                } else {
                                  setShotType('single')
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
                            <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                              分辨率直接影响费用：1080P {'>'} 720P {'>'} 480P
                            </div>
                          </div>
                        </Col>
                      </Row>
                      
                      <Row gutter={16}>
                        <Col span={12}>
                          <div style={{ marginBottom: 16 }}>
                            <div style={{ marginBottom: 8 }}>时长</div>
                            {/* 根据模型是否有 duration_range 来决定使用 InputNumber 还是 Select */}
                            {currentModelInfo?.duration_range ? (
                              <InputNumber
                                style={{ width: '100%' }}
                                min={currentModelInfo.duration_range[0]}
                                max={currentModelInfo.duration_range[1]}
                                value={duration}
                                onChange={(v) => setDuration(v || currentModelInfo.default_duration || 5)}
                                addonAfter="秒"
                              />
                            ) : (
                              <Select
                                style={{ width: '100%' }}
                                value={duration}
                                onChange={setDuration}
                              >
                                {(currentModelInfo?.durations || [5]).map(d => (
                                  <Option key={d} value={d}>{d} 秒</Option>
                                ))}
                              </Select>
                            )}
                            <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                              时长直接影响费用，按秒计费
                              {currentModelInfo?.duration_range && ` (${currentModelInfo.duration_range[0]}-${currentModelInfo.duration_range[1]}秒)`}
                            </div>
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
                      
                      <Row gutter={16}>
                        <Col span={8}>
                          <div style={{ marginBottom: 16 }}>
                            <Space>
                              <Switch
                                checked={promptExtend}
                                onChange={setPromptExtend}
                              />
                              <span>智能改写</span>
                            </Space>
                            <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                              使用大模型优化提示词
                            </div>
                          </div>
                        </Col>
                        <Col span={8}>
                          <div style={{ marginBottom: 16 }}>
                            <Space>
                              <Switch
                                checked={watermark}
                                onChange={setWatermark}
                              />
                              <span>添加水印</span>
                            </Space>
                            <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                              右下角"AI生成"标识
                            </div>
                          </div>
                        </Col>
                        <Col span={8}>
                          <div style={{ marginBottom: 16 }}>
                            <div style={{ marginBottom: 8 }}>随机种子</div>
                            <InputNumber
                              style={{ width: '100%' }}
                              min={0}
                              max={2147483647}
                              value={seed}
                              onChange={(v) => setSeed(v || undefined)}
                              placeholder="留空随机"
                            />
                          </div>
                        </Col>
                      </Row>
                      
                      {currentModelInfo?.supports_audio && (
                        <div style={{ 
                          padding: 12, 
                          background: '#1a1a1a', 
                          borderRadius: 8, 
                          marginTop: 8,
                          border: '1px solid #333'
                        }}>
                          <div style={{ marginBottom: 12, fontWeight: 500 }}>🔊 音频设置</div>
                          
                          <div style={{ marginBottom: 12 }}>
                            <div style={{ marginBottom: 8 }}>自定义音频</div>
                            <Select
                              style={{ width: '100%' }}
                              value={audioUrl || undefined}
                              onChange={(v) => {
                                setAudioUrl(v || '')
                                // 选择音频后，auto_audio 无效
                                if (v) setAutoAudio(false)
                              }}
                              placeholder="从音频库选择（可选）"
                              allowClear
                            >
                              {audioItems.map(audio => (
                                <Option key={audio.id} value={audio.url}>
                                  {audio.name}
                                </Option>
                              ))}
                            </Select>
                            <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                              传入音频后，视频将与音频内容对齐（如口型、节奏）
                            </div>
                          </div>
                          
                          {/* 有声/无声切换（仅支持 audio toggle 的模型显示，如 wan2.6-i2v-flash） */}
                          {currentModelInfo?.supports_audio_toggle ? (
                            <div>
                              <Space>
                                <Switch
                                  checked={autoAudio}
                                  onChange={setAutoAudio}
                                  disabled={!!audioUrl}
                                />
                                <span>有声视频</span>
                              </Space>
                              <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                                {audioUrl 
                                  ? '已选择自定义音频'
                                  : autoAudio 
                                    ? '模型将根据提示词和画面自动生成匹配的背景音'
                                    : '关闭后生成无声视频（费用更低）'
                                }
                              </div>
                            </div>
                          ) : (
                            <div>
                              <Space>
                                <Switch
                                  checked={autoAudio}
                                  onChange={setAutoAudio}
                                  disabled={!!audioUrl}
                                />
                                <span>自动生成音频</span>
                              </Space>
                              <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                                {audioUrl 
                                  ? '已选择自定义音频，此选项无效'
                                  : autoAudio 
                                    ? '模型将根据提示词和画面自动生成匹配的背景音'
                                    : '关闭后将使用静音视频'
                                }
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                      
                      {/* 镜头类型（支持 shot_type 的模型） */}
                      {currentModelInfo?.supports_shot_type && (
                        <div style={{ 
                          padding: 12, 
                          background: '#1a1a1a', 
                          borderRadius: 8, 
                          marginTop: 8,
                        }}>
                          <div style={{ marginBottom: 8, fontWeight: 500, color: '#e5a84b' }}>
                            🎬 镜头类型设置
                          </div>
                          <div>
                            <div style={{ marginBottom: 8 }}>镜头类型</div>
                            <Select
                              style={{ width: '100%' }}
                              value={shotType}
                              onChange={setShotType}
                            >
                              <Option value="single">单镜头 - 一个连续镜头</Option>
                              <Option value="multi">多镜头叙事 - 多个切换镜头</Option>
                            </Select>
                            <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                              {shotType === 'single' 
                                ? '输出一个连续的镜头画面' 
                                : '输出多个切换的镜头，适合故事叙述（需开启智能改写）'
                              }
                            </div>
                          </div>
                        </div>
                      )}
                    </>
                  )}
                  
                  {/* 参考生视频参数 */}
                  {taskType === 'reference_to_video' && (
                    <>
                      <Row gutter={16}>
                        <Col span={12}>
                          <div style={{ marginBottom: 16 }}>
                            <div style={{ marginBottom: 8 }}>模型</div>
                            <Select
                              style={{ width: '100%' }}
                              value="wan2.6-r2v"
                              disabled
                            >
                              <Option value="wan2.6-r2v">{currentRefVideoModelInfo?.name || '万相2.6 参考生视频'}</Option>
                            </Select>
                            <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                              {currentRefVideoModelInfo?.description || '参考视频/图像的角色形象生成新视频'}
                            </div>
                          </div>
                        </Col>
                        <Col span={12}>
                          <div style={{ marginBottom: 16 }}>
                            <div style={{ marginBottom: 8 }}>分辨率</div>
                            <Select
                              style={{ width: '100%' }}
                              value={size}
                              onChange={setSize}
                            >
                              <Select.OptGroup label="1080P 档位">
                                {currentRefVideoModelInfo?.resolutions_1080p?.map((res: any) => (
                                  <Option key={res.value} value={res.value}>{res.label}</Option>
                                ))}
                              </Select.OptGroup>
                              <Select.OptGroup label="720P 档位">
                                {currentRefVideoModelInfo?.resolutions_720p?.map((res: any) => (
                                  <Option key={res.value} value={res.value}>{res.label}</Option>
                                ))}
                              </Select.OptGroup>
                            </Select>
                            <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                              分辨率直接影响费用：1080P {'>'} 720P
                            </div>
                          </div>
                        </Col>
                      </Row>
                      
                      <Row gutter={16}>
                        <Col span={12}>
                          <div style={{ marginBottom: 16 }}>
                            <div style={{ marginBottom: 8 }}>时长 (2-10秒)</div>
                            <InputNumber
                              style={{ width: '100%' }}
                              min={currentRefVideoModelInfo?.min_duration || 2}
                              max={currentRefVideoModelInfo?.max_duration || 10}
                              value={duration}
                              onChange={(v) => setDuration(v || 5)}
                              addonAfter="秒"
                            />
                            <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                              时长直接影响费用，按秒计费
                            </div>
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
                      
                      <Row gutter={16}>
                        <Col span={12}>
                          <div style={{ marginBottom: 16 }}>
                            <div style={{ marginBottom: 8 }}>镜头类型</div>
                            <Select
                              style={{ width: '100%' }}
                              value={shotType}
                              onChange={setShotType}
                            >
                              <Option value="single">单镜头 - 一个连续镜头</Option>
                              <Option value="multi">多镜头叙事 - 多个切换镜头</Option>
                            </Select>
                            <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                              {shotType === 'single' 
                                ? '输出一个连续的镜头画面' 
                                : '输出多个切换的镜头，保持角色一致性'
                              }
                            </div>
                          </div>
                        </Col>
                        <Col span={12}>
                          <div style={{ fontSize: 12, color: '#888', paddingTop: 24 }}>
                            音频说明：参考视频时可自动提取音色，也可通过提示词描述声音效果
                          </div>
                        </Col>
                      </Row>
                      
                      <Row gutter={16}>
                        <Col span={12}>
                          <div style={{ marginBottom: 16 }}>
                            <Space>
                              <Switch
                                checked={watermark}
                                onChange={setWatermark}
                              />
                              <span>添加水印</span>
                            </Space>
                            <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                              右下角"AI生成"标识
                            </div>
                          </div>
                        </Col>
                        <Col span={12}>
                          <div style={{ marginBottom: 16 }}>
                            <div style={{ marginBottom: 8 }}>随机种子</div>
                            <InputNumber
                              style={{ width: '100%' }}
                              min={0}
                              max={2147483647}
                              value={seed}
                              onChange={(v) => setSeed(v || undefined)}
                              placeholder="留空随机"
                            />
                          </div>
                        </Col>
                      </Row>
                    </>
                  )}
                  
                  {/* 文生视频参数 */}
                  {taskType === 'text_to_video' && (
                    <>
                      <Row gutter={16}>
                        <Col span={12}>
                          <div style={{ marginBottom: 16 }}>
                            <div style={{ marginBottom: 8 }}>模型</div>
                            <Select
                              style={{ width: '100%' }}
                              value={model}
                              onChange={(v) => {
                                setModel(v)
                                const modelInfo = textToVideoModels[v]
                                if (modelInfo?.default_size) {
                                  setSize(modelInfo.default_size)
                                }
                                if (modelInfo?.default_duration) {
                                  setDuration(modelInfo.default_duration)
                                }
                              }}
                            >
                              {Object.entries(textToVideoModels).map(([key, info]) => (
                                <Option key={key} value={key}>{info.name}</Option>
                              ))}
                            </Select>
                            <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                              {textToVideoModels[model]?.description}
                            </div>
                          </div>
                        </Col>
                        <Col span={12}>
                          <div style={{ marginBottom: 16 }}>
                            <div style={{ marginBottom: 8 }}>分辨率</div>
                            <Select
                              style={{ width: '100%' }}
                              value={size}
                              onChange={setSize}
                            >
                              {textToVideoModels[model]?.resolutions_1080p && (
                                <Select.OptGroup label="1080P 档位">
                                  {textToVideoModels[model]?.resolutions_1080p?.map((res: any) => (
                                    <Option key={res.value} value={res.value}>{res.label}</Option>
                                  ))}
                                </Select.OptGroup>
                              )}
                              {textToVideoModels[model]?.resolutions_720p && (
                                <Select.OptGroup label="720P 档位">
                                  {textToVideoModels[model]?.resolutions_720p?.map((res: any) => (
                                    <Option key={res.value} value={res.value}>{res.label}</Option>
                                  ))}
                                </Select.OptGroup>
                              )}
                              {textToVideoModels[model]?.resolutions_480p && (
                                <Select.OptGroup label="480P 档位">
                                  {textToVideoModels[model]?.resolutions_480p?.map((res: any) => (
                                    <Option key={res.value} value={res.value}>{res.label}</Option>
                                  ))}
                                </Select.OptGroup>
                              )}
                            </Select>
                            <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                              分辨率直接影响费用：1080P {'>'} 720P {'>'} 480P
                            </div>
                          </div>
                        </Col>
                      </Row>
                      
                      <Row gutter={16}>
                        <Col span={12}>
                          <div style={{ marginBottom: 16 }}>
                            <div style={{ marginBottom: 8 }}>时长</div>
                            <Select
                              style={{ width: '100%' }}
                              value={duration}
                              onChange={setDuration}
                            >
                              {textToVideoModels[model]?.durations?.map((d: number) => (
                                <Option key={d} value={d}>{d} 秒</Option>
                              ))}
                            </Select>
                            <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                              时长直接影响费用，按秒计费
                            </div>
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
                      
                      <Row gutter={16}>
                        <Col span={12}>
                          <div style={{ marginBottom: 16 }}>
                            <div style={{ marginBottom: 8 }}>镜头类型</div>
                            <Select
                              style={{ width: '100%' }}
                              value={shotType}
                              onChange={setShotType}
                            >
                              <Option value="single">单镜头 - 一个连续镜头</Option>
                              <Option value="multi">多镜头叙事 - 多个切换镜头</Option>
                            </Select>
                            <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                              {shotType === 'single' 
                                ? '输出一个连续的镜头画面' 
                                : '输出多个切换的镜头，适合故事叙述（需开启智能改写）'
                              }
                            </div>
                          </div>
                        </Col>
                        <Col span={12}>
                          <div style={{ marginBottom: 16 }}>
                            <Space>
                              <Switch
                                checked={autoAudio}
                                onChange={setAutoAudio}
                                disabled={!!audioUrl}
                              />
                              <span>自动生成音频</span>
                            </Space>
                            <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                              {audioUrl 
                                ? '已选择自定义音频，此选项无效'
                                : autoAudio 
                                  ? '模型将根据提示词和画面自动生成匹配的背景音'
                                  : '关闭后生成无声视频'
                              }
                            </div>
                          </div>
                        </Col>
                      </Row>
                      
                      <Row gutter={16}>
                        <Col span={8}>
                          <div style={{ marginBottom: 16 }}>
                            <Space>
                              <Switch
                                checked={t2vPromptExtend}
                                onChange={setT2vPromptExtend}
                              />
                              <span>智能改写</span>
                            </Space>
                            <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                              使用大模型优化提示词
                            </div>
                          </div>
                        </Col>
                        <Col span={8}>
                          <div style={{ marginBottom: 16 }}>
                            <Space>
                              <Switch
                                checked={watermark}
                                onChange={setWatermark}
                              />
                              <span>添加水印</span>
                            </Space>
                            <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                              右下角"AI生成"标识
                            </div>
                          </div>
                        </Col>
                        <Col span={8}>
                          <div style={{ marginBottom: 16 }}>
                            <div style={{ marginBottom: 8 }}>随机种子</div>
                            <InputNumber
                              style={{ width: '100%' }}
                              min={0}
                              max={2147483647}
                              value={seed}
                              onChange={(v) => setSeed(v || undefined)}
                              placeholder="留空随机"
                            />
                          </div>
                        </Col>
                      </Row>
                      
                      {/* 音频设置 */}
                      <div style={{ 
                        padding: 12, 
                        background: '#1a1a1a', 
                        borderRadius: 8, 
                        marginTop: 8,
                        border: '1px solid #333'
                      }}>
                        <div style={{ marginBottom: 12, fontWeight: 500 }}>🔊 音频设置</div>
                        
                        <div style={{ marginBottom: 12 }}>
                          <div style={{ marginBottom: 8 }}>自定义音频</div>
                          <Select
                            style={{ width: '100%' }}
                            value={audioUrl || undefined}
                            onChange={(v) => {
                              setAudioUrl(v || '')
                              // 选择音频后，auto_audio 无效
                              if (v) setAutoAudio(false)
                            }}
                            placeholder="从音频库选择（可选）"
                            allowClear
                          >
                            {audioItems.map(audio => (
                              <Option key={audio.id} value={audio.url}>
                                {audio.name}
                              </Option>
                            ))}
                          </Select>
                          <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                            传入音频后，视频将与音频内容对齐（如口型、节奏）
                          </div>
                        </div>
                      </div>
                    </>
                  )}
                  
                  {/* 首尾帧生视频参数 */}
                  {taskType === 'keyframe_to_video' && (
                    <>
                      <Row gutter={16}>
                        <Col span={12}>
                          <div style={{ marginBottom: 16 }}>
                            <div style={{ marginBottom: 8 }}>模型</div>
                            <Select
                              style={{ width: '100%' }}
                              value={model}
                              onChange={(v) => {
                                setModel(v)
                                const modelInfo = keyframeToVideoModels[v]
                                if (modelInfo?.default_resolution) {
                                  setResolution(modelInfo.default_resolution)
                                }
                              }}
                            >
                              {Object.entries(keyframeToVideoModels).map(([key, info]) => (
                                <Option key={key} value={key}>{info.name}</Option>
                              ))}
                            </Select>
                            <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                              {keyframeToVideoModels[model]?.description}
                            </div>
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
                              {(keyframeToVideoModels[model]?.resolutions || ['480P', '720P', '1080P']).map((res: string) => (
                                <Option key={res} value={res}>{res}</Option>
                              ))}
                            </Select>
                            <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                              分辨率直接影响费用：1080P {'>'} 720P {'>'} 480P
                            </div>
                          </div>
                        </Col>
                      </Row>
                      
                      <Row gutter={16}>
                        <Col span={12}>
                          <div style={{ marginBottom: 16 }}>
                            <div style={{ marginBottom: 8 }}>时长</div>
                            <Input value="5 秒（固定）" disabled />
                            <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                              首尾帧生视频固定生成5秒视频
                            </div>
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
                      
                      <Row gutter={16}>
                        <Col span={8}>
                          <div style={{ marginBottom: 16 }}>
                            <Space>
                              <Switch
                                checked={promptExtend}
                                onChange={setPromptExtend}
                              />
                              <span>智能改写</span>
                            </Space>
                            <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                              使用大模型优化提示词
                            </div>
                          </div>
                        </Col>
                        <Col span={8}>
                          <div style={{ marginBottom: 16 }}>
                            <Space>
                              <Switch
                                checked={watermark}
                                onChange={setWatermark}
                              />
                              <span>添加水印</span>
                            </Space>
                            <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                              右下角"AI生成"标识
                            </div>
                          </div>
                        </Col>
                        <Col span={8}>
                          <div style={{ marginBottom: 16 }}>
                            <div style={{ marginBottom: 8 }}>随机种子</div>
                            <InputNumber
                              style={{ width: '100%' }}
                              min={0}
                              max={2147483647}
                              value={seed}
                              onChange={(v) => setSeed(v || undefined)}
                              placeholder="留空随机"
                            />
                          </div>
                        </Col>
                      </Row>
                      
                      <div style={{ 
                        padding: 12, 
                        background: '#1a1a1a', 
                        borderRadius: 8, 
                        marginTop: 8,
                        border: '1px solid #333'
                      }}>
                        <div style={{ fontWeight: 500, marginBottom: 8 }}>💡 使用提示</div>
                        <ul style={{ fontSize: 12, color: '#888', paddingLeft: 16, margin: 0 }}>
                          <li>首尾帧生视频会生成从首帧平滑过渡到尾帧的5秒视频</li>
                          <li>输出视频的宽高比将以首帧图像为准</li>
                          <li>提示词可选，用于描述中间过渡过程（如运镜、动作变化）</li>
                          <li>如果首尾帧主体/场景变化大，建议描写变化过程</li>
                          <li>生成的视频为无声视频</li>
                        </ul>
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
        title={
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingRight: 30 }}>
            <span>{selectedTask?.name || '任务详情'}</span>
            <Space>
              <Button 
                size="small" 
                icon={<EditOutlined />}
                onClick={() => selectedTask && openEditModal(selectedTask)}
              >
                编辑
              </Button>
              <Button 
                size="small" 
                icon={<ReloadOutlined />}
                loading={regenerating}
                onClick={() => selectedTask && handleRegenerate(selectedTask)}
                disabled={selectedTask?.status === 'processing'}
              >
                重新生成
              </Button>
            </Space>
          </div>
        }
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
            
            {/* 追踪ID显示 */}
            {(selectedTask.task_ids?.length > 0 || selectedTask.request_ids?.length > 0) && (
              <div style={{ 
                marginTop: 16, 
                padding: '8px 12px', 
                background: '#1a1a1a', 
                borderRadius: 6,
                fontSize: 11,
                color: '#666',
                fontFamily: 'monospace'
              }}>
                {selectedTask.task_ids?.length > 0 && (
                  <div>Task ID: {selectedTask.task_ids[selectedTask.task_ids.length - 1]}</div>
                )}
                {selectedTask.request_ids?.length > 0 && (
                  <div>Request ID: {selectedTask.request_ids[selectedTask.request_ids.length - 1]}</div>
                )}
              </div>
            )}
          </div>
        )}
      </Modal>

      {/* 编辑任务弹窗 */}
      <Modal
        title="编辑任务"
        open={editModalVisible}
        onOk={handleSaveEdit}
        onCancel={() => setEditModalVisible(false)}
        okText="保存"
        cancelText="取消"
        confirmLoading={saving}
        width={700}
        okButtonProps={{ 
          disabled: editTaskType === 'image_to_video' 
            ? !editFirstFrameUrl 
            : editTaskType === 'reference_to_video'
              ? editReferenceItems.length === 0  // 至少需要一个参考素材
              : editTaskType === 'keyframe_to_video'
                ? !editFirstFrameUrl || !editLastFrameUrl
                : false  // text_to_video 只需要提示词，在 handleSaveEdit 中验证
        }}
      >
        <Tabs
          items={[
            {
              key: 'basic',
              label: '基本信息',
              children: (
                <Form form={editForm} layout="vertical">
                  <Form.Item name="name" label="任务名称">
                    <Input placeholder="任务名称" />
                  </Form.Item>
                  
                  {/* 任务类型标识（只读） */}
                  <div style={{ marginBottom: 16, padding: '8px 12px', background: '#1f1f1f', borderRadius: 4 }}>
                    <Tag color={
                      editTaskType === 'image_to_video' ? 'blue' : 
                      editTaskType === 'reference_to_video' ? 'green' : 
                      editTaskType === 'keyframe_to_video' ? 'orange' : 
                      'purple'
                    }>
                      {editTaskType === 'image_to_video' ? '图生视频' : 
                       editTaskType === 'reference_to_video' ? '参考生视频' : 
                       editTaskType === 'keyframe_to_video' ? '首尾帧生视频' :
                       '文生视频'}
                    </Tag>
                  </div>
                  
                  {/* 图生视频：首帧图选择 */}
                  {editTaskType === 'image_to_video' && (
                    <div style={{ marginBottom: 16 }}>
                      <div style={{ marginBottom: 8 }}>首帧图 *</div>
                      <Select
                        style={{ width: '100%' }}
                        value={editFirstFrameUrl || undefined}
                        onChange={setEditFirstFrameUrl}
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
                      {editFirstFrameUrl && (
                        <div style={{ marginTop: 8 }}>
                          <img src={editFirstFrameUrl} alt="预览" style={{ maxWidth: 200, maxHeight: 150, borderRadius: 4 }} />
                        </div>
                      )}
                    </div>
                  )}
                  
                  {/* 参考生视频：参考素材选择（视频+图片，总数≤5） */}
                  {editTaskType === 'reference_to_video' && (
                    <>
                      {/* 添加素材选择器 */}
                      <Row gutter={16}>
                        <Col span={12}>
                          <div style={{ marginBottom: 16 }}>
                            <div style={{ marginBottom: 8 }}>添加参考视频</div>
                            <Select
                              style={{ width: '100%' }}
                              value={undefined}
                              onChange={(url) => {
                                if (!url || editReferenceItems.length >= 5) return
                                const videoCount = editReferenceItems.filter(i => i.type === 'video').length
                                if (videoCount >= 3) {
                                  message.warning('视频最多3个')
                                  return
                                }
                                const video = videoLibraryItems.find(v => v.url === url)
                                if (video && !editReferenceItems.some(i => i.url === url)) {
                                  setEditReferenceItems([...editReferenceItems, {
                                    id: `ref-${Date.now()}`,
                                    url: video.url,
                                    type: 'video',
                                    name: video.name,
                                    thumbnail: video.thumbnail_url,
                                    duration: video.duration
                                  }])
                                }
                              }}
                              placeholder="选择视频添加到队列"
                              disabled={editReferenceItems.length >= 5 || editReferenceItems.filter(i => i.type === 'video').length >= 3}
                            >
                              {videoLibraryItems.filter(v => !editReferenceItems.some(i => i.url === v.url)).map(video => (
                                <Option key={video.id} value={video.url}>
                                  <Space>
                                    <VideoCameraOutlined />
                                    {video.name}
                                    {video.duration && <span style={{ color: '#888' }}>({video.duration}s)</span>}
                                  </Space>
                                </Option>
                              ))}
                            </Select>
                          </div>
                        </Col>
                        <Col span={12}>
                          <div style={{ marginBottom: 16 }}>
                            <div style={{ marginBottom: 8 }}>添加参考图片</div>
                            <Select
                              style={{ width: '100%' }}
                              value={undefined}
                              onChange={(url) => {
                                if (!url || editReferenceItems.length >= 5) return
                                const imageCount = editReferenceItems.filter(i => i.type === 'image').length
                                if (imageCount >= 5) {
                                  message.warning('图片最多5张')
                                  return
                                }
                                const image = galleryImages.find(img => img.url === url)
                                if (image && !editReferenceItems.some(i => i.url === url)) {
                                  setEditReferenceItems([...editReferenceItems, {
                                    id: `ref-${Date.now()}`,
                                    url: image.url,
                                    type: 'image',
                                    name: image.name,
                                    thumbnail: image.url
                                  }])
                                }
                              }}
                              placeholder="选择图片添加到队列"
                              disabled={editReferenceItems.length >= 5}
                            >
                              {galleryImages.filter(img => !editReferenceItems.some(i => i.url === img.url)).map(img => (
                                <Option key={img.id} value={img.url}>
                                  <Space>
                                    <img src={img.url} alt="" style={{ width: 24, height: 24, objectFit: 'cover', borderRadius: 2 }} />
                                    {img.name}
                                  </Space>
                                </Option>
                              ))}
                            </Select>
                          </div>
                        </Col>
                      </Row>
                      
                      {/* 已选素材队列 */}
                      <div style={{ 
                        padding: '12px', 
                        background: '#1a1a1a', 
                        borderRadius: 8,
                        marginBottom: 16 
                      }}>
                        <div style={{ marginBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontWeight: 500 }}>
                            已选素材队列
                            <span style={{ 
                              marginLeft: 8, 
                              color: editReferenceItems.length >= 5 ? '#ff4d4f' : '#52c41a',
                              fontSize: 12,
                              fontWeight: 'normal'
                            }}>
                              ({editReferenceItems.length}/5)
                            </span>
                          </span>
                          {editReferenceItems.length > 0 && (
                            <Button type="link" size="small" danger onClick={() => setEditReferenceItems([])}>
                              清空全部
                            </Button>
                          )}
                        </div>
                        
                        {editReferenceItems.length === 0 ? (
                          <div style={{ color: '#666', textAlign: 'center', padding: '20px 0' }}>
                            请从上方选择参考视频或图片
                          </div>
                        ) : (
                          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                            {editReferenceItems.map((item, index) => (
                              <div 
                                key={item.id}
                                style={{ 
                                  width: 110,
                                  background: '#2a2a2a',
                                  borderRadius: 8,
                                  overflow: 'hidden',
                                  position: 'relative'
                                }}
                              >
                                {/* 缩略图 */}
                                <div style={{ 
                                  width: '100%', 
                                  height: 70, 
                                  background: '#333',
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'center'
                                }}>
                                  {item.type === 'video' ? (
                                    item.thumbnail ? (
                                      <img src={item.thumbnail} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                                    ) : (
                                      <VideoCameraOutlined style={{ fontSize: 24, color: '#666' }} />
                                    )
                                  ) : (
                                    <img src={item.thumbnail || item.url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                                  )}
                                </div>
                                
                                {/* 类型标签 */}
                                <Tag 
                                  color={item.type === 'video' ? 'blue' : 'green'} 
                                  style={{ position: 'absolute', top: 4, left: 4, fontSize: 10 }}
                                >
                                  {item.type === 'video' ? '视频' : '图片'}
                                </Tag>
                                
                                {/* character 编号 */}
                                <div style={{
                                  position: 'absolute',
                                  top: 4,
                                  right: 4,
                                  background: 'rgba(0,0,0,0.7)',
                                  color: '#fff',
                                  padding: '2px 6px',
                                  borderRadius: 4,
                                  fontSize: 10,
                                  fontWeight: 500
                                }}>
                                  character{index + 1}
                                </div>
                                
                                {/* 信息和操作 */}
                                <div style={{ padding: '6px 8px' }}>
                                  <div style={{ 
                                    fontSize: 11, 
                                    color: '#ccc',
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                    whiteSpace: 'nowrap',
                                    marginBottom: 4
                                  }}>
                                    {item.name}
                                  </div>
                                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                    <Space size={4}>
                                      <Button 
                                        type="text" 
                                        size="small"
                                        disabled={index === 0}
                                        onClick={() => {
                                          if (index > 0) {
                                            const newItems = [...editReferenceItems]
                                            ;[newItems[index - 1], newItems[index]] = [newItems[index], newItems[index - 1]]
                                            setEditReferenceItems(newItems)
                                          }
                                        }}
                                        style={{ padding: '0 4px', fontSize: 12 }}
                                      >
                                        ↑
                                      </Button>
                                      <Button 
                                        type="text" 
                                        size="small"
                                        disabled={index === editReferenceItems.length - 1}
                                        onClick={() => {
                                          if (index < editReferenceItems.length - 1) {
                                            const newItems = [...editReferenceItems]
                                            ;[newItems[index], newItems[index + 1]] = [newItems[index + 1], newItems[index]]
                                            setEditReferenceItems(newItems)
                                          }
                                        }}
                                        style={{ padding: '0 4px', fontSize: 12 }}
                                      >
                                        ↓
                                      </Button>
                                    </Space>
                                    <Button 
                                      type="text" 
                                      size="small" 
                                      danger
                                      onClick={() => setEditReferenceItems(editReferenceItems.filter(i => i.id !== item.id))}
                                      style={{ padding: '0 4px' }}
                                    >
                                      <DeleteOutlined style={{ fontSize: 12 }} />
                                    </Button>
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                        
                        <div style={{ marginTop: 12, fontSize: 12, color: '#888' }}>
                          提示词中使用 <code style={{ background: '#333', padding: '0 4px', borderRadius: 2 }}>character1</code>, <code style={{ background: '#333', padding: '0 4px', borderRadius: 2 }}>character2</code>... 按上述顺序引用角色
                        </div>
                      </div>
                    </>
                  )}
                  
                  {/* 首尾帧生视频：首帧图和尾帧图选择 */}
                  {editTaskType === 'keyframe_to_video' && (
                    <>
                      <Row gutter={16}>
                        <Col span={12}>
                          <div style={{ marginBottom: 16 }}>
                            <div style={{ marginBottom: 8 }}>首帧图 *</div>
                            <Select
                              style={{ width: '100%' }}
                              value={editFirstFrameUrl || undefined}
                              onChange={setEditFirstFrameUrl}
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
                            {editFirstFrameUrl && (
                              <div style={{ marginTop: 8 }}>
                                <img src={editFirstFrameUrl} alt="首帧预览" style={{ maxWidth: 120, maxHeight: 80, borderRadius: 4 }} />
                              </div>
                            )}
                          </div>
                        </Col>
                        <Col span={12}>
                          <div style={{ marginBottom: 16 }}>
                            <div style={{ marginBottom: 8 }}>尾帧图 *</div>
                            <Select
                              style={{ width: '100%' }}
                              value={editLastFrameUrl || undefined}
                              onChange={setEditLastFrameUrl}
                              placeholder="从图库选择尾帧图"
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
                            {editLastFrameUrl && (
                              <div style={{ marginTop: 8 }}>
                                <img src={editLastFrameUrl} alt="尾帧预览" style={{ maxWidth: 120, maxHeight: 80, borderRadius: 4 }} />
                              </div>
                            )}
                          </div>
                        </Col>
                      </Row>
                      <div style={{ fontSize: 12, color: '#888', marginBottom: 16 }}>
                        首尾帧图片要求：JPEG/JPG/PNG/BMP/WEBP格式，尺寸360-2000像素，最大10MB。
                      </div>
                    </>
                  )}
                  
                  <Form.Item name="prompt" label={editTaskType === 'keyframe_to_video' ? '提示词（可选）' : '提示词'}>
                    <TextArea rows={3} placeholder="描述想要生成的视频内容" />
                  </Form.Item>
                  
                  <Form.Item name="negative_prompt" label="负向提示词">
                    <TextArea rows={2} placeholder="不希望出现的内容" />
                  </Form.Item>
                </Form>
              )
            },
            {
              key: 'params',
              label: '生成参数',
              children: (
                <Form form={editForm} layout="vertical">
                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item name="model" label="模型">
                        {editTaskType === 'image_to_video' ? (
                          <Select
                            onChange={(v) => {
                              setEditModel(v)
                              const modelInfo = videoModels[v]
                              if (modelInfo?.default_resolution) {
                                editForm.setFieldValue('resolution', modelInfo.default_resolution)
                              }
                              if (modelInfo?.default_duration) {
                                editForm.setFieldValue('duration', modelInfo.default_duration)
                              }
                              // 处理镜头类型
                              if (modelInfo?.supports_shot_type) {
                                editForm.setFieldValue('shot_type', modelInfo.default_shot_type || 'single')
                              }
                            }}
                          >
                            {Object.entries(videoModels).map(([key, info]) => (
                              <Option key={key} value={key}>{info.name}</Option>
                            ))}
                          </Select>
                        ) : editTaskType === 'reference_to_video' ? (
                          <Select
                            onChange={(v) => {
                              setEditModel(v)
                              const modelInfo = refVideoModels[v]
                              if (modelInfo?.default_resolution) {
                                editForm.setFieldValue('size', modelInfo.default_resolution)
                              }
                            }}
                          >
                            {Object.entries(refVideoModels).map(([key, info]) => (
                              <Option key={key} value={key}>{info.name}</Option>
                            ))}
                          </Select>
                        ) : (
                          <Select
                            onChange={(v) => {
                              setEditModel(v)
                              const modelInfo = textToVideoModels[v]
                              if (modelInfo?.default_size) {
                                editForm.setFieldValue('size', modelInfo.default_size)
                              }
                              if (modelInfo?.default_duration) {
                                editForm.setFieldValue('duration', modelInfo.default_duration)
                              }
                            }}
                          >
                            {Object.entries(textToVideoModels).map(([key, info]) => (
                              <Option key={key} value={key}>{info.name}</Option>
                            ))}
                          </Select>
                        )}
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      {editTaskType === 'image_to_video' ? (
                        <Form.Item name="resolution" label="分辨率">
                          <Select>
                            {(getEditModelInfo()?.resolutions || [
                              { value: '480P', label: '480P (标清)' },
                              { value: '720P', label: '720P (高清)' },
                              { value: '1080P', label: '1080P (全高清)' }
                            ]).map((res: any) => (
                              <Option key={res.value} value={res.value}>{res.label}</Option>
                            ))}
                          </Select>
                        </Form.Item>
                      ) : editTaskType === 'reference_to_video' ? (
                        <Form.Item name="size" label="分辨率">
                          <Select>
                            <Select.OptGroup label="1080P 档位">
                              {(getEditModelInfo() as any)?.resolutions_1080p?.map((res: any) => (
                                <Option key={res.value} value={res.value}>{res.label}</Option>
                              ))}
                            </Select.OptGroup>
                            <Select.OptGroup label="720P 档位">
                              {(getEditModelInfo() as any)?.resolutions_720p?.map((res: any) => (
                                <Option key={res.value} value={res.value}>{res.label}</Option>
                              ))}
                            </Select.OptGroup>
                          </Select>
                        </Form.Item>
                      ) : (
                        <Form.Item name="size" label="分辨率">
                          <Select>
                            {(getEditModelInfo() as any)?.resolutions_1080p && (
                              <Select.OptGroup label="1080P 档位">
                                {(getEditModelInfo() as any)?.resolutions_1080p?.map((res: any) => (
                                  <Option key={res.value} value={res.value}>{res.label}</Option>
                                ))}
                              </Select.OptGroup>
                            )}
                            {(getEditModelInfo() as any)?.resolutions_720p && (
                              <Select.OptGroup label="720P 档位">
                                {(getEditModelInfo() as any)?.resolutions_720p?.map((res: any) => (
                                  <Option key={res.value} value={res.value}>{res.label}</Option>
                                ))}
                              </Select.OptGroup>
                            )}
                            {(getEditModelInfo() as any)?.resolutions_480p && (
                              <Select.OptGroup label="480P 档位">
                                {(getEditModelInfo() as any)?.resolutions_480p?.map((res: any) => (
                                  <Option key={res.value} value={res.value}>{res.label}</Option>
                                ))}
                              </Select.OptGroup>
                            )}
                          </Select>
                        </Form.Item>
                      )}
                    </Col>
                  </Row>
                  
                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item name="duration" label="视频时长">
                        {/* 根据模型是否有 duration_range 或 min/max_duration 来决定使用 InputNumber 还是 Select */}
                        {(getEditModelInfo() as VideoModelInfo)?.duration_range ? (
                          <InputNumber
                            style={{ width: '100%' }}
                            min={(getEditModelInfo() as VideoModelInfo)?.duration_range?.[0] || 2}
                            max={(getEditModelInfo() as VideoModelInfo)?.duration_range?.[1] || 15}
                            addonAfter="秒"
                          />
                        ) : editTaskType === 'reference_to_video' ? (
                          // 参考生视频支持2-10秒连续范围
                          <InputNumber
                            style={{ width: '100%' }}
                            min={(getEditModelInfo() as any)?.min_duration || 2}
                            max={(getEditModelInfo() as any)?.max_duration || 10}
                            addonAfter="秒"
                          />
                        ) : (
                          <Select>
                            {((getEditModelInfo() as VideoModelInfo)?.durations || [5, 10]).map((d: number) => (
                              <Option key={d} value={d}>{d} 秒</Option>
                            ))}
                          </Select>
                        )}
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <div style={{ marginBottom: 24 }}>
                        <div style={{ marginBottom: 8 }}>生成组数</div>
                        <InputNumber
                          style={{ width: '100%' }}
                          min={1}
                          max={5}
                          value={editGroupCount}
                          onChange={(v) => setEditGroupCount(v || 1)}
                        />
                      </div>
                    </Col>
                  </Row>
                  
                  <Row gutter={16}>
                    <Col span={8}>
                      {editTaskType === 'image_to_video' ? (
                        <Form.Item name="prompt_extend" label="智能改写" valuePropName="checked">
                          <Switch />
                        </Form.Item>
                      ) : editTaskType === 'reference_to_video' ? (
                        <div style={{ marginBottom: 24 }}>
                          <div style={{ marginBottom: 8 }}>镜头类型</div>
                          <Form.Item name="shot_type" noStyle>
                            <Select style={{ width: '100%' }}>
                              <Option value="single">单镜头</Option>
                              <Option value="multi">多镜头叙事</Option>
                            </Select>
                          </Form.Item>
                        </div>
                      ) : (
                        <div style={{ marginBottom: 24 }}>
                          <div style={{ marginBottom: 8 }}>智能改写</div>
                          <Space>
                            <Switch 
                              checked={editT2vPromptExtend} 
                              onChange={setEditT2vPromptExtend}
                            />
                            <span style={{ color: '#888', fontSize: 12 }}>使用大模型优化提示词</span>
                          </Space>
                        </div>
                      )}
                    </Col>
                    <Col span={8}>
                      <Form.Item name="watermark" label="添加水印" valuePropName="checked">
                        <Switch />
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item name="seed" label="随机种子" extra="留空为随机">
                        <InputNumber style={{ width: '100%' }} min={0} max={2147483647} placeholder="留空" />
                      </Form.Item>
                    </Col>
                  </Row>
                  
                  {/* 音频设置 - wan2.5/2.6 支持 */}
                  {(getEditModelInfo()?.supports_audio || editModel?.includes('wan2.5') || editModel?.includes('wan2.6')) && (
                    <div style={{ 
                      padding: 12, 
                      background: '#1a1a1a', 
                      borderRadius: 8, 
                      marginTop: 8,
                      border: '1px solid #333'
                    }}>
                      <div style={{ marginBottom: 12, fontWeight: 500 }}>🔊 音频设置（仅 wan2.5 支持）</div>
                      
                      <div style={{ marginBottom: 12 }}>
                        <div style={{ marginBottom: 8 }}>自定义音频</div>
                        <Select
                          style={{ width: '100%' }}
                          value={editAudioUrl || undefined}
                          onChange={(v) => {
                            setEditAudioUrl(v || '')
                            if (v) editForm.setFieldValue('auto_audio', false)
                          }}
                          placeholder="从音频库选择（可选）"
                          allowClear
                        >
                          {audioItems.map(audio => (
                            <Option key={audio.id} value={audio.url}>
                              {audio.name}
                            </Option>
                          ))}
                        </Select>
                        <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                          传入音频后，视频将与音频内容对齐
                        </div>
                      </div>
                      
                      <Form.Item name="auto_audio" valuePropName="checked" style={{ marginBottom: 0 }}>
                        <Space>
                          <Switch disabled={!!editAudioUrl} />
                          <span>自动生成音频</span>
                        </Space>
                      </Form.Item>
                      <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                        {editAudioUrl 
                          ? '已选择自定义音频，此选项无效'
                          : '开启后模型将自动生成匹配的背景音'
                        }
                      </div>
                    </div>
                  )}
                  
                  {/* 镜头类型 - 仅 wan2.6 支持 */}
                  {(getEditModelInfo()?.supports_shot_type || editModel?.includes('wan2.6')) && (
                    <div style={{ 
                      padding: 12, 
                      background: '#1a1a1a', 
                      borderRadius: 8, 
                      marginTop: 8,
                      border: '1px solid #e5a84b'
                    }}>
                      <div style={{ marginBottom: 12, fontWeight: 500, color: '#e5a84b' }}>🎬 镜头类型设置（仅 wan2.6 支持）</div>
                      <Form.Item name="shot_type" label="镜头类型" style={{ marginBottom: 0 }}>
                        <Select>
                          <Option value="single">单镜头 - 一个连续镜头</Option>
                          <Option value="multi">多镜头叙事 - 多个切换镜头</Option>
                        </Select>
                      </Form.Item>
                      <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                        单镜头输出连续画面，多镜头叙事输出多个切换镜头（需开启智能改写）
                      </div>
                    </div>
                  )}
                </Form>
              )
            }
          ]}
        />
      </Modal>
    </div>
  )
}

export default VideoStudioPage

