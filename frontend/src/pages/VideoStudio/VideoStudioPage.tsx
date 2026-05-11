import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { Card, Button, List, Modal, Input, Select, InputNumber, Switch, message, Popconfirm, Space, Empty, Spin, Row, Col, Tabs, Tag, Form, theme, Collapse } from 'antd'
import { PlusOutlined, DeleteOutlined, PlayCircleOutlined, SaveOutlined, VideoCameraOutlined, EditOutlined, ReloadOutlined, StarFilled, FlagOutlined, FlagFilled, CheckOutlined, CloseOutlined, StarOutlined, CameraOutlined } from '@ant-design/icons'
import { videoStudioApi, galleryApi, audioApi, videoLibraryApi, settingsApi, VideoStudioTask, GalleryImage, AudioItem, VideoLibraryItem, VideoModelInfo, RefVideoModelInfo, TextToVideoModelInfo, KeyframeToVideoModelInfo, VideoStudioTaskType, VaceVideoRepaintingModelInfo, VaceVideoEditModelInfo, VideoTaskKind } from '../../services/api'
import { useProjectStore } from '../../stores/projectStore'
import { useTaskPolling } from '../../hooks/useTaskPolling'
import MaskEditor, { type MaskEditorHandle, type MaskEditorTool } from './MaskEditor'
import CapabilityCreateModal from './CapabilityCreateModal'
import {
  TASK_CARD_META_ROW_STYLE,
  TASK_CARD_PROGRESS_STYLE,
  TASK_CARD_TAGS_STYLE,
} from './taskCardLayout'

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

interface SourceVideoMetadata {
  width: number
  height: number
  fps: number
  duration: number
  frame_count: number
  file_size: number
  format: string
  warnings: string[]
}

const VACE_MODEL_ID = 'wanx2.1-vace-plus'
const MASK_BRUSH_SIZES = [8, 16, 32, 64]
const LEGACY_TASK_KIND_MAP: Record<string, VideoTaskKind> = {
  image_to_video: 'image_to_video',
  reference_to_video: 'reference_to_video',
  text_to_video: 'text_to_video',
  keyframe_to_video: 'keyframe_to_video',
  video_extension: 'video_extension',
  video_repainting: 'video_repainting',
  video_edit: 'video_edit_local',
  video_edit_global: 'video_edit_global',
}
const TASK_KIND_META: Record<VideoTaskKind, { color: string; text: string }> = {
  image_to_video: { color: 'blue', text: '图生视频' },
  reference_to_video: { color: 'green', text: '参考生视频' },
  text_to_video: { color: 'purple', text: '文生视频' },
  keyframe_to_video: { color: 'orange', text: '首尾帧生视频' },
  video_extension: { color: 'gold', text: '视频续写' },
  video_repainting: { color: 'cyan', text: '视频重绘' },
  video_edit_local: { color: 'magenta', text: '局部编辑' },
  video_edit_global: { color: 'geekblue', text: '视频编辑' },
}
const PARAM_LABELS: Record<string, string> = {
  mode: '画质模式',
  aspect_ratio: '画面比例',
  duration: '时长',
  narrative_mode: '叙事模式',
  shot_type: '镜头类型',
  resolution: '分辨率',
  size: '输出尺寸',
  ratio: '画面比例',
  audio_setting: '声音设置',
  audio: '音频',
  watermark: '水印',
  prompt_extend: '智能改写',
  keep_original_sound: '保留原声',
  control_condition: '控制条件',
  strength: '重绘强度',
  mask_type: '蒙版模式',
  expand_ratio: '扩展比例',
  expand_mode: '包裹模式',
}

const VideoStudioPage = () => {
  const { token } = theme.useToken()
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
  const [taskType, setTaskType] = useState<VideoStudioTaskType>('image_to_video')  // 任务类型
  const [taskName, setTaskName] = useState('')
  const [firstFrameUrl, setFirstFrameUrl] = useState('')
  const [lastFrameUrl, setLastFrameUrl] = useState('')  // 首尾帧生视频的尾帧图
  const [audioUrl, setAudioUrl] = useState('')
  const [referenceItems, setReferenceItems] = useState<ReferenceItem[]>([])  // 参考素材队列（视频+图片，有序）
  const [sourceVideoUrl, setSourceVideoUrl] = useState('')
  const [sourceVideoPreviewUrl, setSourceVideoPreviewUrl] = useState('')
  const [sourceVideoPreviewDataUrl, setSourceVideoPreviewDataUrl] = useState('')
  const [sourceVideoMetadata, setSourceVideoMetadata] = useState<SourceVideoMetadata | null>(null)
  const [sourceVideoWarnings, setSourceVideoWarnings] = useState<string[]>([])
  const [sourceVideoPreparing, setSourceVideoPreparing] = useState(false)
  const [referenceImageUrl, setReferenceImageUrl] = useState('')
  const [maskTool, setMaskTool] = useState<MaskEditorTool>('brush')
  const [maskBrushSize, setMaskBrushSize] = useState(16)
  const [maskHasContent, setMaskHasContent] = useState(false)
  const [maskUploading, setMaskUploading] = useState(false)
  const [controlCondition, setControlCondition] = useState('')
  const [strength, setStrength] = useState(1)
  const [maskType, setMaskType] = useState<'tracking' | 'fixed'>('tracking')
  const [expandRatio, setExpandRatio] = useState(0.05)
  const [expandMode, setExpandMode] = useState('hull')
  const [prompt, setPrompt] = useState('')
  const [negativePrompt, setNegativePrompt] = useState('')
  const [model, setModel] = useState('wan2.5-i2v-preview')
  const [refModel, setRefModel] = useState('wan2.6-r2v-flash')  // 参考生视频模型
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
  const [videoRepaintingModels, setVideoRepaintingModels] = useState<Record<string, VaceVideoRepaintingModelInfo>>({})
  const [videoEditModels, setVideoEditModels] = useState<Record<string, VaceVideoEditModelInfo>>({})
  const [videoTaskNotificationsEnabled, setVideoTaskNotificationsEnabled] = useState(false)
  const isMountedRef = useRef(true)
  const maskEditorRef = useRef<MaskEditorHandle | null>(null)
  const notifiedResultsRef = useRef<Set<string>>(new Set())

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
        settingsApi.getSettings(),
      ])
      setTasks(tasksRes.tasks)
      setGalleryImages(galleryRes.images)
      setAudioItems(audioRes.audios)
      setVideoLibraryItems(videoLibRes.videos)
      setVideoTaskNotificationsEnabled(!!settingsRes.video_task_notifications_enabled)
      setVideoModels({})
      setRefVideoModels({})
      setTextToVideoModels({})
      setKeyframeToVideoModels({})
      setVideoRepaintingModels({})
      setVideoEditModels({})

      // 启动轮询
      tasksRes.tasks.forEach(task => {
        if (task.status === 'processing') {
          startTaskPolling(task.id)
        }
      })
    } catch (error) {
      message.error('加载失败')
    } finally {
      setLoading(false)
    }
  }

  const getResolvedTaskKind = (task: VideoStudioTask): VideoTaskKind => {
    const rawTaskType = task.task_type || 'image_to_video'
    const rawTaskKind = task.task_kind
    if (rawTaskKind && !(rawTaskKind === 'image_to_video' && rawTaskType !== 'image_to_video')) {
      return rawTaskKind
    }
    return LEGACY_TASK_KIND_MAP[rawTaskType] || 'image_to_video'
  }

  const getCanonicalTaskTag = (task: VideoStudioTask) => {
    const taskKind = getResolvedTaskKind(task)
    const item = TASK_KIND_META[taskKind]
    return <Tag color={item.color}>{item.text}</Tag>
  }

  const getTaskInputAssets = (task: VideoStudioTask) => {
    if (task.input_assets && Object.keys(task.input_assets).length > 0) {
      const inputAssets = { ...task.input_assets }
      const referenceMedia = Array.isArray(inputAssets.reference_media) ? inputAssets.reference_media : []
      if (referenceMedia.length > 0) {
        inputAssets.reference_images = referenceMedia.filter((item: any) => item?.type === 'reference_image').map((item: any) => item.url)
        inputAssets.reference_videos = referenceMedia.filter((item: any) => item?.type === 'reference_video').map((item: any) => item.url)
      }
      return inputAssets
    }
    const taskKind = getResolvedTaskKind(task)
    return {
      first_frame: task.first_frame_url ? [task.first_frame_url] : [],
      last_frame: task.last_frame_url ? [task.last_frame_url] : [],
      first_clip: task.first_clip_url ? [task.first_clip_url] : [],
      audio: task.audio_url ? [task.audio_url] : [],
      reference_images: task.reference_image_url ? [task.reference_image_url] : [],
      reference_videos: task.reference_video_urls || [],
      source_video: task.source_video_url ? [task.source_video_url] : [],
      base_video: taskKind === 'video_edit_global' && task.source_video_url ? [task.source_video_url] : [],
      mask_image: task.mask_image_url ? [task.mask_image_url] : [],
    }
  }

  const getTaskNormalizedParams = (task: VideoStudioTask) => {
    if (task.normalized_params && Object.keys(task.normalized_params).length > 0) {
      return task.normalized_params
    }
    return {
      resolution: task.resolution,
      size: task.size,
      duration: task.duration,
      prompt_extend: task.task_type === 'text_to_video' ? task.t2v_prompt_extend : task.prompt_extend,
      watermark: task.watermark,
      seed: task.seed,
      audio: task.auto_audio,
      ratio: task.ratio,
      audio_setting: task.audio_setting,
      shot_type: task.shot_type,
      narrative_mode: task.narrative_mode,
      control_condition: task.control_condition,
      strength: task.strength,
      mask_type: task.mask_type,
      expand_ratio: task.expand_ratio,
      expand_mode: task.expand_mode,
    }
  }

  const formatTaskParamValue = (key: string, value: any) => {
    if (value === undefined || value === null || value === '') return ''
    if (typeof value === 'boolean') return value ? '是' : '否'
    if (key === 'narrative_mode') {
      if (value === 'multi_shot_intelligence') return '多镜头 - 智能分镜'
      if (value === 'multi_shot_customize') return '多镜头 - 自定义分镜'
      return '单镜头'
    }
    if (key === 'audio') return value ? '开启' : '关闭'
    return String(value)
  }

  const getTaskSummaryLine = (task: VideoStudioTask) => {
    const params = getTaskNormalizedParams(task)
    const parts = [task.model_id || task.model]
    if (task.provider) parts.push(task.provider.toUpperCase())
    if (params.size) parts.push(String(params.size))
    else if (params.resolution) parts.push(String(params.resolution))
    if (task.duration) parts.push(`${task.duration}秒`)
    return parts.filter(Boolean).join(' · ')
  }

  const getTaskParameterEntries = (task: VideoStudioTask) => {
    const params = getTaskNormalizedParams(task)
    return Object.entries(params)
      .filter(([key, value]) => PARAM_LABELS[key] && value !== undefined && value !== null && value !== '')
      .map(([key, value]) => ({
        key,
        label: PARAM_LABELS[key],
        value: formatTaskParamValue(key, value),
      }))
  }

  const getTaskPreviewUrl = (task: VideoStudioTask) => {
    return task.thumbnail_url || task.first_frame_url || task.source_video_preview_url || ''
  }

  const resetVaceState = () => {
    setSourceVideoUrl('')
    setSourceVideoPreviewUrl('')
    setSourceVideoPreviewDataUrl('')
    setSourceVideoMetadata(null)
    setSourceVideoWarnings([])
    setSourceVideoPreparing(false)
    setReferenceImageUrl('')
    setMaskTool('brush')
    setMaskBrushSize(16)
    setMaskHasContent(false)
    setMaskUploading(false)
    setControlCondition('')
    setStrength(1)
    setMaskType('tracking')
    setExpandRatio(0.05)
    setExpandMode('hull')
  }

  const handlePrepareSourceVideo = async (videoUrl: string) => {
    if (!projectId || !videoUrl) return
    setSourceVideoUrl(videoUrl)
    setSourceVideoPreparing(true)
    setSourceVideoPreviewDataUrl('')
    setSourceVideoPreviewUrl('')
    setSourceVideoMetadata(null)
    setSourceVideoWarnings([])
    setMaskHasContent(false)
    try {
      const result = await videoStudioApi.prepareSourceVideo({
        project_id: projectId,
        video_url: videoUrl
      })
      setSourceVideoPreviewDataUrl(result.preview_image_data_url)
      setSourceVideoPreviewUrl(result.preview_image_url || '')
      setSourceVideoMetadata(result.metadata)
      setSourceVideoWarnings(result.warnings || [])
      if (taskType === 'video_edit') {
        setSize(videoEditModels[VACE_MODEL_ID]?.default_size || '1280*720')
      }
    } catch (error: any) {
      setSourceVideoPreviewDataUrl('')
      setSourceVideoPreviewUrl('')
      setSourceVideoMetadata(null)
      setSourceVideoWarnings([])
      message.error(error.message || '源视频准备失败')
    } finally {
      setSourceVideoPreparing(false)
    }
  }

  const getApproxVideoDuration = () => {
    if (!sourceVideoMetadata) return 5
    return Math.max(1, Math.round(Math.min(sourceVideoMetadata.duration, 5)))
  }

  const isCreateDisabled = () => {
    if (taskType === 'image_to_video') {
      return !firstFrameUrl || (!!currentModelInfo?.requires_audio && !audioUrl)
    }
    if (taskType === 'reference_to_video') {
      return referenceItems.length === 0
    }
    if (taskType === 'text_to_video') {
      return !prompt
    }
    if (taskType === 'keyframe_to_video') {
      return !firstFrameUrl || !lastFrameUrl
    }
    if (taskType === 'video_repainting') {
      return !sourceVideoUrl || !prompt || !controlCondition || sourceVideoPreparing
    }
    if (taskType === 'video_edit') {
      return !sourceVideoUrl || !prompt || !sourceVideoPreviewDataUrl || !maskHasContent || sourceVideoPreparing || maskUploading
    }
    return false
  }

  const maybeNotifyTaskFinished = (task: VideoStudioTask) => {
    if (!videoTaskNotificationsEnabled) return
    if (typeof window === 'undefined' || !('Notification' in window)) return
    if (Notification.permission !== 'granted') return
    const dedupeKey = `${task.id}:${task.status}`
    if (notifiedResultsRef.current.has(dedupeKey)) return
    notifiedResultsRef.current.add(dedupeKey)
    const title = task.status === 'succeeded' ? '视频任务已完成' : '视频任务失败'
    const body = task.status === 'succeeded'
      ? `${task.name || '未命名任务'} 已生成完成`
      : `${task.name || '未命名任务'} 失败：${task.error_message || '未知错误'}`
    try {
      const notification = new Notification(title, { body, tag: dedupeKey })
      notification.onclick = () => window.focus()
    } catch {
      // ignore notification failures
    }
  }

  const { startPolling } = useTaskPolling({
    intervalMs: 5000,
    errorIntervalMs: 10000,
    onError: (_taskId, error) => {
      console.error('轮询错误:', error)
    },
  })

  const startTaskPolling = useCallback((taskId: string) => {
    startPolling(taskId, async () => {
      const result = await videoStudioApi.getStatus(taskId)

      if (isMountedRef.current) {
        setTasks(prev => prev.map(t => t.id === taskId ? result.task : t))
        setSelectedTask(prev => {
          if (prev?.id === taskId) return result.task
          return prev
        })
      }

      if (result.task.status === 'succeeded' || result.task.status === 'failed') {
        maybeNotifyTaskFinished(result.task)
        if (result.task.status === 'succeeded') {
          message.success('视频生成完成')
        } else {
          message.error(`视频生成失败: ${result.task.error_message || '未知错误'}`)
        }
        return true
      }

      return false
    })
  }, [maybeNotifyTaskFinished, startPolling])

  const handleCreate = async () => {
    if (!projectId) return

    // 根据任务类型验证
    if (taskType === 'image_to_video' && !firstFrameUrl) {
      message.warning('请选择首帧图')
      return
    }
    if (taskType === 'image_to_video' && currentModelInfo?.requires_audio && !audioUrl) {
      message.warning('数字人模型需要选择音频')
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
    if (taskType === 'video_repainting') {
      if (!sourceVideoUrl) {
        message.warning('请选择源视频')
        return
      }
      if (!prompt) {
        message.warning('请输入提示词')
        return
      }
      if (!controlCondition) {
        message.warning('请选择控制条件')
        return
      }
    }
    if (taskType === 'video_edit') {
      if (!sourceVideoUrl) {
        message.warning('请选择源视频')
        return
      }
      if (!prompt) {
        message.warning('请输入提示词')
        return
      }
      if (!sourceVideoPreviewDataUrl || !sourceVideoMetadata) {
        message.warning('请先准备源视频首帧')
        return
      }
      if (!maskHasContent || !maskEditorRef.current?.hasMask()) {
        message.warning('请先涂抹需要编辑的区域')
        return
      }
    }

    setCreating(true)
    try {
      // 获取当前文生视频模型
      // 确定使用的模型
      let taskModel = model
      if (taskType === 'reference_to_video') {
        taskModel = refModel
      } else if (taskType === 'text_to_video') {
        taskModel = model || 'wan2.6-t2v'
      } else if (taskType === 'keyframe_to_video') {
        taskModel = model || 'wan2.2-kf2v-flash'
      } else if (taskType === 'video_repainting' || taskType === 'video_edit') {
        taskModel = VACE_MODEL_ID
      }

      let uploadedMaskUrl: string | undefined
      if (taskType === 'video_edit') {
        const maskBlob = await maskEditorRef.current?.exportMask()
        if (!maskBlob) {
          throw new Error('导出Mask失败')
        }
        setMaskUploading(true)
        const formData = new FormData()
        formData.append('project_id', projectId)
        formData.append('source_video_url', sourceVideoUrl)
        formData.append('mask_file', maskBlob, 'video-edit-mask.png')
        const uploadRes = await videoStudioApi.uploadMask(formData)
        uploadedMaskUrl = uploadRes.mask_image_url
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
        source_video_url: taskType === 'video_repainting' || taskType === 'video_edit' ? sourceVideoUrl : undefined,
        source_video_preview_url: taskType === 'video_repainting' || taskType === 'video_edit' ? (sourceVideoPreviewUrl || undefined) : undefined,
        reference_image_url: taskType === 'video_repainting' || taskType === 'video_edit' ? (referenceImageUrl || undefined) : undefined,
        mask_image_url: taskType === 'video_edit' ? uploadedMaskUrl : undefined,
        mask_frame_id: taskType === 'video_edit' ? 1 : undefined,
        // 通用参数
        prompt,
        negative_prompt: taskType === 'image_to_video' || taskType === 'reference_to_video' || taskType === 'text_to_video' || taskType === 'keyframe_to_video'
          ? negativePrompt
          : undefined,
        model: taskModel,
        duration: taskType === 'video_repainting' || taskType === 'video_edit' ? getApproxVideoDuration() : duration,
        watermark,
        seed: seed || undefined,
        auto_audio: taskType === 'video_repainting' || taskType === 'video_edit' ? false : autoAudio,
        shot_type: taskType === 'video_repainting' || taskType === 'video_edit' ? undefined : shotType,
        // 图生视频/首尾帧生视频专用
        resolution: (taskType === 'image_to_video' || taskType === 'keyframe_to_video') ? resolution : undefined,
        prompt_extend: (taskType === 'image_to_video' || taskType === 'keyframe_to_video' || taskType === 'video_repainting' || taskType === 'video_edit') ? promptExtend : undefined,
        // 参考生视频专用
        size: taskType === 'reference_to_video' ? size : (taskType === 'text_to_video' ? size : (taskType === 'video_edit' ? size : undefined)),
        // 文生视频专用
        t2v_prompt_extend: taskType === 'text_to_video' ? t2vPromptExtend : undefined,
        control_condition: taskType === 'video_repainting'
          ? controlCondition
          : (taskType === 'video_edit' ? (controlCondition || undefined) : undefined),
        strength: taskType === 'video_repainting' ? strength : undefined,
        mask_type: taskType === 'video_edit' ? maskType : undefined,
        expand_ratio: taskType === 'video_edit' && maskType === 'tracking' ? expandRatio : undefined,
        expand_mode: taskType === 'video_edit' && maskType === 'tracking' ? expandMode : undefined,
        group_count: groupCount
      })

      setTasks(prev => [result.task, ...prev])
      setCreateModalVisible(false)
      resetForm()

      // 启动轮询
      startTaskPolling(result.task.id)
      
      message.success('任务已创建')
    } catch (error: any) {
      message.error(error.message || '创建失败')
    } finally {
      setCreating(false)
      setMaskUploading(false)
    }
  }

  const resetForm = () => {
    setTaskType('image_to_video')
    setTaskName('')
    setFirstFrameUrl('')
    setLastFrameUrl('')  // 重置尾帧图
    setAudioUrl('')
    setReferenceItems([])
    resetVaceState()
    setPrompt('')
    setNegativePrompt('')
    setModel('wan2.5-i2v-preview')
    setRefModel('wan2.6-r2v-flash')
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
      startTaskPolling(task.id)
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

  const [extractingFrames, setExtractingFrames] = useState<Set<string>>(new Set())

  const handleExtractLastFrame = async (videoUrl: string) => {
    if (!selectedTask) return
    setExtractingFrames(prev => new Set([...prev, videoUrl]))
    try {
      await videoStudioApi.extractLastFrame(selectedTask.id, videoUrl)
      message.success('尾帧已保存到图库')
    } catch (error: any) {
      message.error(error.message || '提取尾帧失败')
    } finally {
      setExtractingFrames(prev => { const next = new Set(prev); next.delete(videoUrl); return next })
    }
  }

  const handleToggleVideoMarker = async (taskId: string, videoUrl: string, markerKey: string) => {
    const task = tasks.find(t => t.id === taskId)
    if (!task) return
    const currentMarkers = task.video_markers?.[videoUrl] || []
    const newMarkers = currentMarkers.includes(markerKey)
      ? currentMarkers.filter((m: string) => m !== markerKey)
      : [...currentMarkers, markerKey]
    try {
      const res = await videoStudioApi.updateVideoMarkers(taskId, videoUrl, newMarkers)
      const updatedVideoMarkers = res.video_markers
      setTasks(prev => prev.map(t => t.id === taskId ? { ...t, video_markers: updatedVideoMarkers } : t))
      if (selectedTask?.id === taskId) {
        setSelectedTask(prev => prev ? { ...prev, video_markers: updatedVideoMarkers } : prev)
      }
    } catch {
      message.error('标记更新失败')
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
  const [editTaskType] = useState<VideoStudioTaskType>('image_to_video')
  const [editFirstFrameUrl, setEditFirstFrameUrl] = useState('')
  const [editLastFrameUrl, setEditLastFrameUrl] = useState('')  // 首尾帧生视频的尾帧图
  const [editAudioUrl, setEditAudioUrl] = useState('')
  const [editReferenceItems, setEditReferenceItems] = useState<ReferenceItem[]>([])  // 编辑弹窗中的参考素材队列
  const [editGroupCount, setEditGroupCount] = useState(1)
  const [editModel, setEditModel] = useState('wan2.5-i2v-preview')  // 编辑弹窗中的当前模型
  const [editT2vPromptExtend, setEditT2vPromptExtend] = useState(true)  // 编辑弹窗中的t2v智能改写
  const [editSourceVideoUrl] = useState('')
  const [editSourceVideoPreviewUrl] = useState('')
  const [editReferenceImageUrl, setEditReferenceImageUrl] = useState('')
  const [editMaskImageUrl] = useState('')
  const [editControlCondition, setEditControlCondition] = useState('')
  const [editStrength, setEditStrength] = useState(1)
  const [editMaskType, setEditMaskType] = useState<'tracking' | 'fixed'>('tracking')
  const [editExpandRatio, setEditExpandRatio] = useState(0.05)
  const [editExpandMode, setEditExpandMode] = useState('hull')

  // 获取编辑弹窗中当前模型的信息
  const getEditModelInfo = () => {
    if (editTaskType === 'reference_to_video') {
      return refVideoModels[editModel] || Object.values(refVideoModels)[0]
    }
    if (editTaskType === 'text_to_video') {
      return textToVideoModels[editModel] || Object.values(textToVideoModels)[0]
    }
    if (editTaskType === 'video_repainting') {
      return videoRepaintingModels[editModel] || Object.values(videoRepaintingModels)[0]
    }
    if (editTaskType === 'video_edit') {
      return videoEditModels[editModel] || Object.values(videoEditModels)[0]
    }
    return videoModels[editModel]
  }

  // 打开编辑弹窗
  const openEditModal = (task: VideoStudioTask) => {
    setSelectedTask(task)
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
    if (editTaskType === 'video_repainting') {
      if (!editSourceVideoUrl) {
        message.warning('源视频缺失')
        return
      }
      if (!editForm.getFieldValue('prompt')) {
        message.warning('请输入提示词')
        return
      }
      if (!editControlCondition) {
        message.warning('请选择控制条件')
        return
      }
    }
    if (editTaskType === 'video_edit') {
      if (!editSourceVideoUrl) {
        message.warning('源视频缺失')
        return
      }
      if (!editMaskImageUrl) {
        message.warning('Mask缺失，请新建任务重新绘制')
        return
      }
      if (!editForm.getFieldValue('prompt')) {
        message.warning('请输入提示词')
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
      } else if (editTaskType === 'video_repainting') {
        updateData.source_video_url = editSourceVideoUrl
        updateData.source_video_preview_url = editSourceVideoPreviewUrl || null
        updateData.reference_image_url = editReferenceImageUrl || null
        updateData.control_condition = editControlCondition
        updateData.strength = editStrength
        updateData.prompt_extend = values.prompt_extend
        updateData.model = VACE_MODEL_ID
        updateData.auto_audio = false
      } else if (editTaskType === 'video_edit') {
        updateData.source_video_url = editSourceVideoUrl
        updateData.source_video_preview_url = editSourceVideoPreviewUrl || null
        updateData.reference_image_url = editReferenceImageUrl || null
        updateData.mask_image_url = editMaskImageUrl
        updateData.mask_frame_id = 1
        updateData.control_condition = editControlCondition || null
        updateData.mask_type = editMaskType
        updateData.expand_ratio = editMaskType === 'tracking' ? editExpandRatio : null
        updateData.expand_mode = editMaskType === 'tracking' ? editExpandMode : null
        updateData.size = values.size
        updateData.prompt_extend = values.prompt_extend
        updateData.model = VACE_MODEL_ID
        updateData.auto_audio = false
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
      const { task: updatedTask } = await videoStudioApi.regenerate(task.id)
      setTasks(prev => prev.map(t => t.id === task.id ? updatedTask : t))
      setSelectedTask(updatedTask)

      // 启动轮询（后台会异步提交 API 任务）
      startTaskPolling(task.id)
      
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

  const currentModelInfo = videoModels[model]
  const currentRefVideoModelInfo = refVideoModels[refModel] || Object.values(refVideoModels)[0]
  const currentVideoRepaintingModelInfo = videoRepaintingModels[VACE_MODEL_ID] || Object.values(videoRepaintingModels)[0]
  const currentVideoEditModelInfo = videoEditModels[VACE_MODEL_ID] || Object.values(videoEditModels)[0]

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
                  cover={
                    <div
                      style={{
                        height: 120,
                        background: token.colorBgLayout,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        cursor: 'pointer',
                        position: 'relative'
                      }}
                      onClick={() => handleViewDetail(task)}
                    >
                      {getTaskPreviewUrl(task) ? (
                        <img
                          src={getTaskPreviewUrl(task)}
                          alt="首帧"
                          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                        />
                      ) : (
                        <PlayCircleOutlined style={{ fontSize: 48, color: token.colorPrimary }} />
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
                  <div style={TASK_CARD_META_ROW_STYLE}>
                    <Space size={[4, 4]} wrap style={TASK_CARD_TAGS_STYLE}>
                      {getCanonicalTaskTag(task)}
                      {task.provider && <Tag>{task.provider.toUpperCase()}</Tag>}
                      {getStatusTag(task.status)}
                    </Space>
                    <span style={{ ...TASK_CARD_PROGRESS_STYLE, color: token.colorTextSecondary }}>
                      {task.video_urls.length}/{task.group_count}
                    </span>
                  </div>
                </Card>
              </List.Item>
            )}
          />
        )}
      </Card>

      {projectId && createModalVisible && (
        <CapabilityCreateModal
          open={createModalVisible}
          projectId={projectId}
          galleryImages={galleryImages}
          audioItems={audioItems}
          videoLibraryItems={videoLibraryItems}
          mode="create"
          onCancel={() => setCreateModalVisible(false)}
          onSubmitted={(task) => {
            setTasks((prev) => [task, ...prev.filter((item) => item.id !== task.id)])
            if (task.status === 'processing') {
              startTaskPolling(task.id)
            }
          }}
        />
      )}

      {projectId && editModalVisible && (
        <CapabilityCreateModal
          open={editModalVisible}
          projectId={projectId}
          galleryImages={galleryImages}
          audioItems={audioItems}
          videoLibraryItems={videoLibraryItems}
          mode="edit"
          task={selectedTask}
          onCancel={() => setEditModalVisible(false)}
          onSubmitted={(task) => {
            setTasks((prev) => prev.map((item) => item.id === task.id ? task : item))
            setSelectedTask(task)
            setEditModalVisible(false)
          }}
        />
      )}

      {/* 创建任务弹窗 */}
      {false && (
      <Modal
        title="新建视频生成任务"
        open={false}
        onCancel={() => {
          setCreateModalVisible(false)
          resetForm()
        }}
        onOk={handleCreate}
        confirmLoading={creating}
        okButtonProps={{ disabled: isCreateDisabled() }}
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
                        const nextType = v as VideoStudioTaskType
                        setTaskType(nextType)
                        // 切换类型时重置相关字段
                        resetVaceState()
                        if (nextType === 'reference_to_video') {
                          setFirstFrameUrl('')
                          setLastFrameUrl('')
                          setAudioUrl('')
                          setNegativePrompt('')
                        } else if (nextType === 'text_to_video') {
                          setModel('wan2.6-t2v')
                          setFirstFrameUrl('')
                          setLastFrameUrl('')
                          setReferenceItems([])
                        } else if (nextType === 'keyframe_to_video') {
                          setModel('wan2.2-kf2v-flash')
                          setReferenceItems([])
                          setAudioUrl('')
                          setResolution('720P')
                        } else if (nextType === 'video_repainting') {
                          setModel(VACE_MODEL_ID)
                          setFirstFrameUrl('')
                          setLastFrameUrl('')
                          setReferenceItems([])
                          setAudioUrl('')
                          setNegativePrompt('')
                          setPromptExtend(false)
                          setControlCondition(videoRepaintingModels[VACE_MODEL_ID]?.default_control_condition || 'depth')
                          setStrength(videoRepaintingModels[VACE_MODEL_ID]?.default_strength || 1)
                        } else if (nextType === 'video_edit') {
                          setModel(VACE_MODEL_ID)
                          setFirstFrameUrl('')
                          setLastFrameUrl('')
                          setReferenceItems([])
                          setAudioUrl('')
                          setNegativePrompt('')
                          setPromptExtend(false)
                          setControlCondition('')
                          setMaskType((videoEditModels[VACE_MODEL_ID]?.default_mask_type as 'tracking' | 'fixed') || 'tracking')
                          setExpandRatio(videoEditModels[VACE_MODEL_ID]?.default_expand_ratio || 0.05)
                          setExpandMode(videoEditModels[VACE_MODEL_ID]?.default_expand_mode || 'hull')
                          setSize(videoEditModels[VACE_MODEL_ID]?.default_size || '1280*720')
                        } else {
                          setModel('wan2.5-i2v-preview')
                          setReferenceItems([])
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
                      <Option value="video_repainting">
                        <Space>
                          <Tag color="cyan">视频重绘</Tag>
                          基于源视频动作与构图重绘新视频
                        </Space>
                      </Option>
                      <Option value="video_edit">
                        <Space>
                          <Tag color="magenta">局部编辑</Tag>
                          基于首帧Mask对视频局部区域做编辑
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
                                    {video.duration && <span style={{ color: token.colorTextSecondary }}>({video.duration}s)</span>}
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
                        background: token.colorBgLayout,
                        borderRadius: 8,
                        marginBottom: 16
                      }}>
                        <div style={{ marginBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontWeight: 500 }}>
                            已选素材队列
                            <span style={{
                              marginLeft: 8,
                              color: referenceItems.length >= 5 ? token.colorError : token.colorSuccess,
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
                          <div style={{ color: token.colorTextTertiary, textAlign: 'center', padding: '20px 0' }}>
                            请从上方选择参考视频或图片
                          </div>
                        ) : (
                          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                            {referenceItems.map((item, index) => (
                              <div
                                key={item.id}
                                style={{
                                  width: 110,
                                  background: token.colorBgElevated,
                                  borderRadius: 8,
                                  overflow: 'hidden',
                                  position: 'relative'
                                }}
                              >
                                {/* 缩略图 */}
                                <div style={{
                                  width: '100%',
                                  height: 70,
                                  background: token.colorBorder,
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'center'
                                }}>
                                  {item.type === 'video' ? (
                                    item.thumbnail ? (
                                      <img src={item.thumbnail} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                                    ) : (
                                      <VideoCameraOutlined style={{ fontSize: 24, color: token.colorTextTertiary }} />
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
                                  color: token.colorWhite,
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
                                    color: token.colorText,
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

                        <div style={{ marginTop: 12, fontSize: 12, color: token.colorTextSecondary }}>
                          提示词中使用 <code style={{ background: token.colorBorder, padding: '0 4px', borderRadius: 2 }}>[Image 1]</code>, <code style={{ background: token.colorBorder, padding: '0 4px', borderRadius: 2 }}>[Image 2]</code>... 按上述顺序引用参考图
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
                      <div style={{ fontSize: 12, color: token.colorTextSecondary, marginBottom: 16 }}>
                        首尾帧图片要求：JPEG/JPG/PNG/BMP/WEBP格式，尺寸360-2000像素，最大10MB。输出视频宽高比以首帧为准。
                      </div>
                    </>
                  )}

                  {(taskType === 'video_repainting' || taskType === 'video_edit') && (
                    <>
                      <div style={{ marginBottom: 16 }}>
                        <div style={{ marginBottom: 8 }}>源视频 *</div>
                        <Select
                          style={{ width: '100%' }}
                          value={sourceVideoUrl || undefined}
                          onChange={(url) => {
                            setSourceVideoUrl(url)
                            setSourceVideoPreviewDataUrl('')
                            setSourceVideoPreviewUrl('')
                            setSourceVideoMetadata(null)
                            setSourceVideoWarnings([])
                            setMaskHasContent(false)
                            if (url) {
                              void handlePrepareSourceVideo(url)
                            }
                          }}
                          placeholder="从视频库选择源视频"
                          optionLabelProp="label"
                        >
                          {videoLibraryItems.map(video => (
                            <Option key={video.id} value={video.url} label={video.name}>
                              <Space>
                                <VideoCameraOutlined />
                                {video.name}
                              </Space>
                            </Option>
                          ))}
                        </Select>
                        {sourceVideoPreparing && (
                          <div style={{ marginTop: 8 }}>
                            <Space size={8}>
                              <Spin size="small" />
                              <span style={{ color: token.colorTextSecondary }}>正在提取源视频首帧与元数据...</span>
                            </Space>
                          </div>
                        )}
                        {sourceVideoMetadata && (
                          <div style={{ marginTop: 8, fontSize: 12, color: token.colorTextSecondary }}>
                            {sourceVideoMetadata!.width} × {sourceVideoMetadata!.height} · {sourceVideoMetadata!.fps.toFixed(2)} FPS · {sourceVideoMetadata!.duration.toFixed(2)} 秒
                          </div>
                        )}
                        {sourceVideoWarnings.length > 0 && (
                          <div style={{ marginTop: 8, padding: 10, borderRadius: 8, background: token.colorWarningBg }}>
                            {sourceVideoWarnings.map((warning, index) => (
                              <div key={index} style={{ fontSize: 12, color: token.colorWarningText }}>{warning}</div>
                            ))}
                          </div>
                        )}
                      </div>

                      <div style={{ marginBottom: 16 }}>
                        <div style={{ marginBottom: 8 }}>参考图</div>
                        <Select
                          style={{ width: '100%' }}
                          value={referenceImageUrl || undefined}
                          onChange={(url) => setReferenceImageUrl(url || '')}
                          placeholder="从图库选择参考图（可选，最多1张）"
                          allowClear
                          optionLabelProp="label"
                        >
                          {galleryImages.map(img => (
                            <Option key={img.id} value={img.url} label={img.name}>
                              <Space>
                                <img src={img.url} alt="" style={{ width: 32, height: 32, objectFit: 'cover', borderRadius: 4 }} />
                                {img.name}
                              </Space>
                            </Option>
                          ))}
                        </Select>
                        {referenceImageUrl && (
                          <div style={{ marginTop: 8 }}>
                            <img src={referenceImageUrl} alt="参考图预览" style={{ maxWidth: 200, maxHeight: 140, borderRadius: 8 }} />
                          </div>
                        )}
                      </div>
                    </>
                  )}

                  {taskType === 'video_edit' && (
                    <div style={{ marginBottom: 16 }}>
                      <div style={{ marginBottom: 8 }}>局部编辑 Mask *</div>
                      <div style={{ marginBottom: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                        <Button
                          type={maskTool === 'brush' ? 'primary' : 'default'}
                          onClick={() => setMaskTool('brush')}
                        >
                          画笔
                        </Button>
                        <Button
                          type={maskTool === 'polygon' ? 'primary' : 'default'}
                          onClick={() => setMaskTool('polygon')}
                        >
                          多边形
                        </Button>
                        <Button
                          type={maskTool === 'eraser' ? 'primary' : 'default'}
                          onClick={() => setMaskTool('eraser')}
                        >
                          橡皮擦
                        </Button>
                        {MASK_BRUSH_SIZES.map(sizeValue => (
                          <Button
                            key={sizeValue}
                            type={maskBrushSize === sizeValue ? 'primary' : 'default'}
                            onClick={() => setMaskBrushSize(sizeValue)}
                            disabled={maskTool === 'polygon'}
                          >
                            {sizeValue}px
                          </Button>
                        ))}
                        <Button onClick={() => {
                          maskEditorRef.current?.clearMask()
                          setMaskHasContent(false)
                        }}>
                          清空蒙版
                        </Button>
                      </div>

                      {sourceVideoPreviewDataUrl && sourceVideoMetadata ? (
                        <MaskEditor
                          ref={maskEditorRef}
                          backgroundImageUrl={sourceVideoPreviewDataUrl}
                          width={sourceVideoMetadata!.width}
                          height={sourceVideoMetadata!.height}
                          tool={maskTool}
                          brushSize={maskBrushSize}
                          onMaskStateChange={setMaskHasContent}
                        />
                      ) : (
                        <div style={{
                          padding: 16,
                          borderRadius: 8,
                          background: token.colorBgLayout,
                          color: token.colorTextSecondary,
                        }}>
                          请选择源视频，系统会先提取首帧，再显示可涂抹的编辑区域。
                        </div>
                      )}
                      {sourceVideoPreviewDataUrl && sourceVideoMetadata && maskTool === 'polygon' && (
                        <div style={{ marginTop: 8, fontSize: 12, color: token.colorTextSecondary }}>
                          多边形模式：在画面上逐点点击连线，按 Enter 闭环填充，按 Esc 取消当前未闭合区域。
                        </div>
                      )}
                    </div>
                  )}

                  {!(taskType === 'image_to_video' && currentModelInfo?.supports_prompt === false) && (
                  <>
                  <div style={{ marginBottom: 16 }}>
                    <div style={{ marginBottom: 8 }}>提示词{taskType === 'text_to_video' || taskType === 'video_repainting' || taskType === 'video_edit' ? ' *' : ''}</div>
                    <TextArea
                      value={prompt}
                      onChange={(e) => setPrompt(e.target.value)}
                      placeholder={taskType === 'reference_to_video'
                        ? "描述视频内容，使用 [Image 1]/[Image 2] 指代参考图中的主体"
                        : taskType === 'video_repainting'
                          ? "描述重绘后的视频内容、风格与主体变化"
                          : taskType === 'video_edit'
                            ? "描述需要替换或新增的局部内容"
                        : "描述视频内容"
                      }
                      rows={3}
                    />
                  </div>

                  {(taskType === 'image_to_video' || taskType === 'reference_to_video' || taskType === 'text_to_video' || taskType === 'keyframe_to_video') && (
                    <div>
                      <div style={{ marginBottom: 8 }}>负面提示词</div>
                      <TextArea
                        value={negativePrompt}
                        onChange={(e) => setNegativePrompt(e.target.value)}
                        placeholder="不希望出现的内容"
                        rows={2}
                      />
                    </div>
                  )}
                  </>
                  )}
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
                                if (modelInfo?.default_duration) {
                                  setDuration(modelInfo.default_duration)
                                }
                                if (modelInfo?.supports_audio) {
                                  setAutoAudio(modelInfo.default_audio !== false)
                                } else {
                                  setAutoAudio(false)
                                  setAudioUrl('')
                                }
                                if (modelInfo?.supports_shot_type) {
                                  setShotType(modelInfo.default_shot_type || 'single')
                                } else {
                                  setShotType('single')
                                }
                                if (modelInfo?.requires_audio) {
                                  setAutoAudio(false)
                                  setPrompt('')
                                  setNegativePrompt('')
                                  setSeed(undefined)
                                }
                              }}
                            >
                              {Object.entries(videoModels).map(([key, info]) => (
                                <Option key={key} value={key}>{info.name} {key}</Option>
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
                            <div style={{ fontSize: 12, color: token.colorTextSecondary, marginTop: 4 }}>
                              分辨率直接影响费用：1080P {'>'} 720P {'>'} 480P
                            </div>
                          </div>
                        </Col>
                      </Row>

                      {currentModelInfo?.supports_duration !== false && (
                      <Row gutter={16}>
                        <Col span={12}>
                          <div style={{ marginBottom: 16 }}>
                            <div style={{ marginBottom: 8 }}>时长</div>
                            {currentModelInfo?.duration_range ? (
                              <InputNumber
                                style={{ width: '100%' }}
                                min={currentModelInfo.duration_range?.[0] || 1}
                                max={currentModelInfo.duration_range?.[1] || 15}
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
                            <div style={{ fontSize: 12, color: token.colorTextSecondary, marginTop: 4 }}>
                              时长直接影响费用，按秒计费
                              {currentModelInfo?.duration_range && ` (${currentModelInfo.duration_range?.[0]}-${currentModelInfo.duration_range?.[1]}秒)`}
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
                      )}

                      {currentModelInfo?.requires_audio && (
                        <div style={{
                          padding: 12,
                          background: token.colorBgLayout,
                          borderRadius: 8,
                          marginBottom: 16,
                          border: `1px solid ${token.colorBorder}`
                        }}>
                          <div style={{ marginBottom: 12, fontWeight: 500 }}>🎤 驱动音频（必选）</div>
                          <Select
                            style={{ width: '100%' }}
                            value={audioUrl || undefined}
                            onChange={(v) => setAudioUrl(v || '')}
                            placeholder="从音频库选择"
                            allowClear
                            status={!audioUrl ? 'warning' : undefined}
                          >
                            {audioItems.map(audio => (
                              <Option key={audio.id} value={audio.url}>
                                {audio.name}
                              </Option>
                            ))}
                          </Select>
                          <div style={{ fontSize: 12, color: token.colorTextSecondary, marginTop: 4 }}>
                            音频将驱动人物口型、表情和动作（wav/mp3，小于15MB，时长不超过20秒，需清晰人声）
                          </div>
                        </div>
                      )}

                      {(currentModelInfo?.supports_prompt_extend || currentModelInfo?.supports_watermark || currentModelInfo?.supports_seed) && (
                      <Row gutter={16}>
                        {currentModelInfo?.supports_prompt_extend && (
                        <Col span={8}>
                          <div style={{ marginBottom: 16 }}>
                            <Space>
                              <Switch
                                checked={promptExtend}
                                onChange={setPromptExtend}
                              />
                              <span>智能改写</span>
                            </Space>
                            <div style={{ fontSize: 12, color: token.colorTextSecondary, marginTop: 4 }}>
                              使用大模型优化提示词
                            </div>
                          </div>
                        </Col>
                        )}
                        {currentModelInfo?.supports_watermark && (
                        <Col span={8}>
                          <div style={{ marginBottom: 16 }}>
                            <Space>
                              <Switch
                                checked={watermark}
                                onChange={setWatermark}
                              />
                              <span>添加水印</span>
                            </Space>
                            <div style={{ fontSize: 12, color: token.colorTextSecondary, marginTop: 4 }}>
                              右下角"AI生成"标识
                            </div>
                          </div>
                        </Col>
                        )}
                        {currentModelInfo?.supports_seed && (
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
                        )}
                      </Row>
                      )}

                      {currentModelInfo?.supports_audio && !currentModelInfo?.requires_audio && (
                        <div style={{
                          padding: 12,
                          background: token.colorBgLayout,
                          borderRadius: 8,
                          marginTop: 8,
                          border: `1px solid ${token.colorBorder}`
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
                            <div style={{ fontSize: 12, color: token.colorTextSecondary, marginTop: 4 }}>
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
                              <div style={{ fontSize: 12, color: token.colorTextSecondary, marginTop: 4 }}>
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
                              <div style={{ fontSize: 12, color: token.colorTextSecondary, marginTop: 4 }}>
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
                          background: token.colorBgLayout,
                          borderRadius: 8,
                          marginTop: 8,
                        }}>
                          <div style={{ marginBottom: 8, fontWeight: 500, color: token.colorPrimary }}>
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
                            <div style={{ fontSize: 12, color: token.colorTextSecondary, marginTop: 4 }}>
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
                              value={refModel}
                              onChange={(v) => {
                                setRefModel(v)
                                const modelInfo = refVideoModels[v]
                                if (modelInfo?.default_size) {
                                  setSize(modelInfo.default_size)
                                }
                                if (modelInfo?.default_duration) {
                                  setDuration(modelInfo.default_duration)
                                }
                                if (modelInfo?.supports_audio_toggle) {
                                  setAutoAudio(modelInfo.default_audio !== false)
                                }
                              }}
                            >
                              {Object.entries(refVideoModels).map(([key, info]) => (
                                <Option key={key} value={key}>{info.name}</Option>
                              ))}
                            </Select>
                            <div style={{ fontSize: 12, color: token.colorTextSecondary, marginTop: 4 }}>
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
                            <div style={{ fontSize: 12, color: token.colorTextSecondary, marginTop: 4 }}>
                              分辨率直接影响费用：1080P {'>'} 720P
                            </div>
                          </div>
                        </Col>
                      </Row>

                      <Row gutter={16}>
                        <Col span={12}>
                          <div style={{ marginBottom: 16 }}>
                            <div style={{ marginBottom: 8 }}>时长 ({currentRefVideoModelInfo?.min_duration || 2}-{currentRefVideoModelInfo?.max_duration || 10}秒)</div>
                            <InputNumber
                              style={{ width: '100%' }}
                              min={currentRefVideoModelInfo?.min_duration || 2}
                              max={currentRefVideoModelInfo?.max_duration || 10}
                              value={duration}
                              onChange={(v) => setDuration(v || 5)}
                              addonAfter="秒"
                            />
                            <div style={{ fontSize: 12, color: token.colorTextSecondary, marginTop: 4 }}>
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
                            <div style={{ fontSize: 12, color: token.colorTextSecondary, marginTop: 4 }}>
                              {shotType === 'single'
                                ? '输出一个连续的镜头画面'
                                : '输出多个切换的镜头，保持角色一致性'
                              }
                            </div>
                          </div>
                        </Col>
                        <Col span={12}>
                          {currentRefVideoModelInfo?.supports_audio_toggle ? (
                            <div style={{ marginBottom: 16 }}>
                              <Space>
                                <Switch
                                  checked={autoAudio}
                                  onChange={setAutoAudio}
                                />
                                <span>有声视频</span>
                              </Space>
                              <div style={{ fontSize: 12, color: token.colorTextSecondary, marginTop: 4 }}>
                                {autoAudio ? '生成有声视频（从参考视频提取音色）' : '生成无声视频（费用更低）'}
                              </div>
                            </div>
                          ) : (
                            <div style={{ fontSize: 12, color: token.colorTextSecondary, paddingTop: 24 }}>
                              音频说明：参考视频时自动提取音色生成有声视频
                            </div>
                          )}
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
                            <div style={{ fontSize: 12, color: token.colorTextSecondary, marginTop: 4 }}>
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
                                <Option key={key} value={key}>{info.name} {key}</Option>
                              ))}
                            </Select>
                            <div style={{ fontSize: 12, color: token.colorTextSecondary, marginTop: 4 }}>
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
                            <div style={{ fontSize: 12, color: token.colorTextSecondary, marginTop: 4 }}>
                              分辨率直接影响费用：1080P {'>'} 720P {'>'} 480P
                            </div>
                          </div>
                        </Col>
                      </Row>

                      <Row gutter={16}>
                        <Col span={12}>
                          <div style={{ marginBottom: 16 }}>
                            <div style={{ marginBottom: 8 }}>时长</div>
                            {textToVideoModels[model]?.duration_range ? (
                              <InputNumber
                                style={{ width: '100%' }}
                                min={textToVideoModels[model].duration_range![0]}
                                max={textToVideoModels[model].duration_range![1]}
                                value={duration}
                                onChange={(v) => setDuration(v || textToVideoModels[model]?.default_duration || 5)}
                                addonAfter="秒"
                              />
                            ) : (
                              <Select
                                style={{ width: '100%' }}
                                value={duration}
                                onChange={setDuration}
                              >
                                {textToVideoModels[model]?.durations?.map((d: number) => (
                                  <Option key={d} value={d}>{d} 秒</Option>
                                ))}
                              </Select>
                            )}
                            <div style={{ fontSize: 12, color: token.colorTextSecondary, marginTop: 4 }}>
                              时长直接影响费用，按秒计费
                              {textToVideoModels[model]?.duration_range && ` (${textToVideoModels[model].duration_range![0]}-${textToVideoModels[model].duration_range![1]}秒)`}
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
                            <div style={{ fontSize: 12, color: token.colorTextSecondary, marginTop: 4 }}>
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
                            <div style={{ fontSize: 12, color: token.colorTextSecondary, marginTop: 4 }}>
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
                            <div style={{ fontSize: 12, color: token.colorTextSecondary, marginTop: 4 }}>
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
                            <div style={{ fontSize: 12, color: token.colorTextSecondary, marginTop: 4 }}>
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
                        background: token.colorBgLayout,
                        borderRadius: 8,
                        marginTop: 8,
                        border: `1px solid ${token.colorBorder}`
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
                          <div style={{ fontSize: 12, color: token.colorTextSecondary, marginTop: 4 }}>
                            传入音频后，视频将与音频内容对齐（如口型、节奏）
                          </div>
                        </div>
                      </div>
                    </>
                  )}

                  {/* 首尾帧生视频参数 */}
                  {taskType === 'video_repainting' && (
                    <>
                      <Row gutter={16}>
                        <Col span={12}>
                          <div style={{ marginBottom: 16 }}>
                            <div style={{ marginBottom: 8 }}>模型</div>
                            <Select style={{ width: '100%' }} value={VACE_MODEL_ID} disabled>
                              <Option value={VACE_MODEL_ID}>
                                {currentVideoRepaintingModelInfo?.name || `视频重绘 ${VACE_MODEL_ID}`}
                              </Option>
                            </Select>
                            <div style={{ fontSize: 12, color: token.colorTextSecondary, marginTop: 4 }}>
                              {currentVideoRepaintingModelInfo?.description}
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
                            <div style={{ marginBottom: 8 }}>控制条件 *</div>
                            <Select
                              style={{ width: '100%' }}
                              value={controlCondition || undefined}
                              onChange={(value) => setControlCondition(value)}
                            >
                              {currentVideoRepaintingModelInfo?.supported_control_conditions?.map((value) => (
                                <Option key={value} value={value}>{value}</Option>
                              ))}
                            </Select>
                          </div>
                        </Col>
                        <Col span={12}>
                          <div style={{ marginBottom: 16 }}>
                            <div style={{ marginBottom: 8 }}>控制强度</div>
                            <InputNumber
                              style={{ width: '100%' }}
                              min={currentVideoRepaintingModelInfo?.strength_range?.[0] ?? 0}
                              max={currentVideoRepaintingModelInfo?.strength_range?.[1] ?? 1}
                              step={0.05}
                              value={strength}
                              onChange={(value) => setStrength(Number(value ?? 1))}
                            />
                          </div>
                        </Col>
                      </Row>

                      <Row gutter={16}>
                        <Col span={8}>
                          <div style={{ marginBottom: 16 }}>
                            <Space>
                              <Switch checked={promptExtend} onChange={setPromptExtend} />
                              <span>智能改写</span>
                            </Space>
                          </div>
                        </Col>
                        <Col span={8}>
                          <div style={{ marginBottom: 16 }}>
                            <Space>
                              <Switch checked={watermark} onChange={setWatermark} />
                              <span>添加水印</span>
                            </Space>
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
                              onChange={(value) => setSeed(value || undefined)}
                              placeholder="留空随机"
                            />
                          </div>
                        </Col>
                      </Row>
                    </>
                  )}

                  {taskType === 'video_edit' && (
                    <>
                      <Row gutter={16}>
                        <Col span={12}>
                          <div style={{ marginBottom: 16 }}>
                            <div style={{ marginBottom: 8 }}>模型</div>
                            <Select style={{ width: '100%' }} value={VACE_MODEL_ID} disabled>
                              <Option value={VACE_MODEL_ID}>
                                {currentVideoEditModelInfo?.name || `局部编辑 ${VACE_MODEL_ID}`}
                              </Option>
                            </Select>
                            <div style={{ fontSize: 12, color: token.colorTextSecondary, marginTop: 4 }}>
                              {currentVideoEditModelInfo?.description}
                            </div>
                          </div>
                        </Col>
                        <Col span={12}>
                          <div style={{ marginBottom: 16 }}>
                            <div style={{ marginBottom: 8 }}>输出分辨率</div>
                            <Select
                              style={{ width: '100%' }}
                              value={size}
                              onChange={setSize}
                            >
                              {currentVideoEditModelInfo?.sizes?.map((item) => (
                                <Option key={item.value} value={item.value}>{item.label}</Option>
                              ))}
                            </Select>
                          </div>
                        </Col>
                      </Row>

                      <Row gutter={16}>
                        <Col span={12}>
                          <div style={{ marginBottom: 16 }}>
                            <div style={{ marginBottom: 8 }}>控制条件</div>
                            <Select
                              style={{ width: '100%' }}
                              value={controlCondition || '__none__'}
                              onChange={(value) => setControlCondition(value === '__none__' ? '' : value)}
                            >
                              <Option value="__none__">不提取</Option>
                              {currentVideoEditModelInfo?.supported_control_conditions?.map((value) => (
                                <Option key={value} value={value}>{value}</Option>
                              ))}
                            </Select>
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
                            <div style={{ marginBottom: 8 }}>Mask 模式</div>
                            <Select
                              style={{ width: '100%' }}
                              value={maskType}
                              onChange={(value) => setMaskType(value)}
                            >
                              <Option value="tracking">tracking</Option>
                              <Option value="fixed">fixed</Option>
                            </Select>
                          </div>
                        </Col>
                        {maskType === 'tracking' && (
                          <Col span={12}>
                            <div style={{ marginBottom: 16 }}>
                              <div style={{ marginBottom: 8 }}>扩展比例</div>
                              <InputNumber
                                style={{ width: '100%' }}
                                min={currentVideoEditModelInfo?.expand_ratio_range?.[0] ?? 0}
                                max={currentVideoEditModelInfo?.expand_ratio_range?.[1] ?? 1}
                                step={0.01}
                                value={expandRatio}
                                onChange={(value) => setExpandRatio(Number(value ?? 0.05))}
                              />
                            </div>
                          </Col>
                        )}
                      </Row>

                      {maskType === 'tracking' && (
                        <Row gutter={16}>
                          <Col span={12}>
                            <div style={{ marginBottom: 16 }}>
                              <div style={{ marginBottom: 8 }}>包裹模式</div>
                              <Select
                                style={{ width: '100%' }}
                                value={expandMode}
                                onChange={setExpandMode}
                              >
                                {currentVideoEditModelInfo?.supported_expand_modes?.map((value) => (
                                  <Option key={value} value={value}>{value}</Option>
                                ))}
                              </Select>
                            </div>
                          </Col>
                        </Row>
                      )}

                      <Row gutter={16}>
                        <Col span={8}>
                          <div style={{ marginBottom: 16 }}>
                            <Space>
                              <Switch checked={promptExtend} onChange={setPromptExtend} />
                              <span>智能改写</span>
                            </Space>
                          </div>
                        </Col>
                        <Col span={8}>
                          <div style={{ marginBottom: 16 }}>
                            <Space>
                              <Switch checked={watermark} onChange={setWatermark} />
                              <span>添加水印</span>
                            </Space>
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
                              onChange={(value) => setSeed(value || undefined)}
                              placeholder="留空随机"
                            />
                          </div>
                        </Col>
                      </Row>
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
                                <Option key={key} value={key}>{info.name} {key}</Option>
                              ))}
                            </Select>
                            <div style={{ fontSize: 12, color: token.colorTextSecondary, marginTop: 4 }}>
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
                            <div style={{ fontSize: 12, color: token.colorTextSecondary, marginTop: 4 }}>
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
                            <div style={{ fontSize: 12, color: token.colorTextSecondary, marginTop: 4 }}>
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
                            <div style={{ fontSize: 12, color: token.colorTextSecondary, marginTop: 4 }}>
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
                            <div style={{ fontSize: 12, color: token.colorTextSecondary, marginTop: 4 }}>
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
                        background: token.colorBgLayout,
                        borderRadius: 8,
                        marginTop: 8,
                        border: `1px solid ${token.colorBorder}`
                      }}>
                        <div style={{ fontWeight: 500, marginBottom: 8 }}>💡 使用提示</div>
                        <ul style={{ fontSize: 12, color: token.colorTextSecondary, paddingLeft: 16, margin: 0 }}>
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
      )}

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
            {(() => {
              const inputAssets = getTaskInputAssets(selectedTask)
              const paramEntries = getTaskParameterEntries(selectedTask)
              const sourceVideos = [...(inputAssets.source_video || [])]
              const baseVideos = [...(inputAssets.base_video || [])]
              const firstClips = [...(inputAssets.first_clip || [])]
              const firstFrames = [...(inputAssets.first_frame || [])]
              const lastFrames = [...(inputAssets.last_frame || [])]
              const audioAssets = [...(inputAssets.audio || [])]
              const referenceMedia = [...(inputAssets.reference_media || [])]
              const referenceImages = [...(inputAssets.reference_images || [])]
              const referenceVideos = [...(inputAssets.reference_videos || [])]
              const maskImages = [...(inputAssets.mask_image || [])]

              return (
                <>
            <div style={{ marginBottom: 16 }}>
              <Space>
                {getCanonicalTaskTag(selectedTask)}
                {selectedTask.provider && <Tag>{selectedTask.provider.toUpperCase()}</Tag>}
                {getStatusTag(selectedTask.status)}
                <span style={{ color: token.colorTextSecondary }}>
                  {getTaskSummaryLine(selectedTask)}
                </span>
              </Space>
            </div>

            {(sourceVideos.length > 0 || baseVideos.length > 0 || firstClips.length > 0 || firstFrames.length > 0 || lastFrames.length > 0 || referenceImages.length > 0 || referenceVideos.length > 0 || maskImages.length > 0 || audioAssets.length > 0) && (
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

            {selectedTask.status === 'processing' && (
              <div style={{ textAlign: 'center', padding: 40 }}>
                <Spin size="large" />
                <div style={{ marginTop: 16, color: token.colorTextSecondary }}>
                  正在生成视频... ({selectedTask.video_urls.length}/{selectedTask.group_count})
                </div>
              </div>
            )}

            {selectedTask.status === 'failed' && (
              <div style={{ padding: 20, background: token.colorErrorBg, borderRadius: 8, color: token.colorError }}>
                生成失败: {selectedTask.error_message || '未知错误'}
              </div>
            )}

            {selectedTask.video_urls.length > 0 && (
              <div>
                <div style={{ marginBottom: 16, fontWeight: 500 }}>生成结果</div>
                <Row gutter={16}>
                  {selectedTask.video_urls.map((url, index) => {
                    const videoMarkers = selectedTask.video_markers?.[url] || []
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
                                  onClick={() => handleToggleVideoMarker(selectedTask.id, url, marker.key)}
                                />
                              )
                            })}
                          </div>
                          <div style={{ marginTop: 6, textAlign: 'center', display: 'flex', justifyContent: 'center', gap: 8 }}>
                            <Button
                              type="primary"
                              size="small"
                              icon={<SaveOutlined />}
                              onClick={() => handleSaveToLibrary(url)}
                            >
                              保存到视频库
                            </Button>
                            <Button
                              size="small"
                              icon={<CameraOutlined />}
                              loading={extractingFrames.has(url)}
                              onClick={() => handleExtractLastFrame(url)}
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

            {selectedTask.prompt && (
              <div style={{ marginTop: 16 }}>
                <div style={{ fontWeight: 500, marginBottom: 8 }}>提示词</div>
                <div style={{ background: token.colorBgContainer, padding: 12, borderRadius: 8 }}>
                  {selectedTask.prompt}
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
                        {JSON.stringify(selectedTask.task_ids || [], null, 2)}
                      </pre>
                      <div style={{ marginBottom: 8, fontWeight: 500 }}>Request IDs</div>
                      <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: 12, padding: 12, borderRadius: 8, background: token.colorBgLayout, marginBottom: 12 }}>
                        {JSON.stringify(selectedTask.request_ids || [], null, 2)}
                      </pre>
                      <div style={{ marginBottom: 8, fontWeight: 500 }}>厂商请求体快照</div>
                      <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: 12, padding: 12, borderRadius: 8, background: token.colorBgLayout, marginBottom: 12 }}>
                        {JSON.stringify(selectedTask.provider_payload_snapshot || {}, null, 2)}
                      </pre>
                      <div style={{ marginBottom: 8, fontWeight: 500 }}>厂商结果元信息</div>
                      <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: 12, padding: 12, borderRadius: 8, background: token.colorBgLayout }}>
                        {JSON.stringify(selectedTask.provider_result_meta || {}, null, 2)}
                      </pre>
                    </div>
                  ),
                },
              ]}
            />
                </>
              )
            })()}
          </div>
        )}
      </Modal>

      {/* 编辑任务弹窗 */}
      {false && (
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
              : editTaskType === 'video_repainting'
                ? !editSourceVideoUrl || !editControlCondition
                : editTaskType === 'video_edit'
                  ? !editSourceVideoUrl || !editMaskImageUrl
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
                  <div style={{ marginBottom: 16, padding: '8px 12px', background: token.colorBgLayout, borderRadius: 4 }}>
                    <Tag color={
                      editTaskType === 'image_to_video' ? 'blue' :
                      editTaskType === 'reference_to_video' ? 'green' :
                      editTaskType === 'video_repainting' ? 'cyan' :
                      editTaskType === 'video_edit' ? 'magenta' :
                      editTaskType === 'keyframe_to_video' ? 'orange' :
                      'purple'
                    }>
                      {editTaskType === 'image_to_video' ? '图生视频' :
                       editTaskType === 'reference_to_video' ? '参考生视频' :
                       editTaskType === 'video_repainting' ? '视频重绘' :
                       editTaskType === 'video_edit' ? '局部编辑' :
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
                                    {video.duration && <span style={{ color: token.colorTextSecondary }}>({video.duration}s)</span>}
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
                        background: token.colorBgLayout,
                        borderRadius: 8,
                        marginBottom: 16
                      }}>
                        <div style={{ marginBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontWeight: 500 }}>
                            已选素材队列
                            <span style={{
                              marginLeft: 8,
                              color: editReferenceItems.length >= 5 ? token.colorError : token.colorSuccess,
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
                          <div style={{ color: token.colorTextTertiary, textAlign: 'center', padding: '20px 0' }}>
                            请从上方选择参考视频或图片
                          </div>
                        ) : (
                          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                            {editReferenceItems.map((item, index) => (
                              <div
                                key={item.id}
                                style={{
                                  width: 110,
                                  background: token.colorBgElevated,
                                  borderRadius: 8,
                                  overflow: 'hidden',
                                  position: 'relative'
                                }}
                              >
                                {/* 缩略图 */}
                                <div style={{
                                  width: '100%',
                                  height: 70,
                                  background: token.colorBorder,
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'center'
                                }}>
                                  {item.type === 'video' ? (
                                    item.thumbnail ? (
                                      <img src={item.thumbnail} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                                    ) : (
                                      <VideoCameraOutlined style={{ fontSize: 24, color: token.colorTextTertiary }} />
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
                                  color: token.colorWhite,
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
                                    color: token.colorText,
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

                        <div style={{ marginTop: 12, fontSize: 12, color: token.colorTextSecondary }}>
                          提示词中使用 <code style={{ background: token.colorBorder, padding: '0 4px', borderRadius: 2 }}>[Image 1]</code>, <code style={{ background: token.colorBorder, padding: '0 4px', borderRadius: 2 }}>[Image 2]</code>... 按上述顺序引用参考图
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
                      <div style={{ fontSize: 12, color: token.colorTextSecondary, marginBottom: 16 }}>
                        首尾帧图片要求：JPEG/JPG/PNG/BMP/WEBP格式，尺寸360-2000像素，最大10MB。
                      </div>
                    </>
                  )}

                  {(editTaskType === 'video_repainting' || editTaskType === 'video_edit') && (
                    <>
                      <div style={{ marginBottom: 16 }}>
                        <div style={{ marginBottom: 8 }}>源视频</div>
                        <Input value={editSourceVideoUrl} disabled />
                        {editSourceVideoPreviewUrl && (
                          <div style={{ marginTop: 8 }}>
                            <img
                              src={editSourceVideoPreviewUrl}
                              alt="源视频首帧"
                              style={{ maxWidth: 220, maxHeight: 140, borderRadius: 8 }}
                            />
                          </div>
                        )}
                      </div>

                      <div style={{ marginBottom: 16 }}>
                        <div style={{ marginBottom: 8 }}>参考图</div>
                        <Select
                          style={{ width: '100%' }}
                          value={editReferenceImageUrl || undefined}
                          onChange={(url) => setEditReferenceImageUrl(url || '')}
                          placeholder="从图库选择参考图（可选）"
                          allowClear
                          optionLabelProp="label"
                        >
                          {galleryImages.map(img => (
                            <Option key={img.id} value={img.url} label={img.name}>
                              <Space>
                                <img src={img.url} alt="" style={{ width: 32, height: 32, objectFit: 'cover', borderRadius: 4 }} />
                                {img.name}
                              </Space>
                            </Option>
                          ))}
                        </Select>
                      </div>

                      {editTaskType === 'video_edit' && editMaskImageUrl && (
                        <div style={{ marginBottom: 16 }}>
                          <div style={{ marginBottom: 8 }}>当前 Mask</div>
                          <img
                            src={editMaskImageUrl}
                            alt="当前Mask"
                            style={{ maxWidth: 220, maxHeight: 140, borderRadius: 8, background: token.colorBgLayout }}
                          />
                          <div style={{ marginTop: 6, fontSize: 12, color: token.colorTextSecondary }}>
                            当前编辑弹窗支持复用已有Mask；如需重新绘制，请新建任务。
                          </div>
                        </div>
                      )}
                    </>
                  )}

                  {!(editTaskType === 'image_to_video' && (getEditModelInfo() as VideoModelInfo)?.supports_prompt === false) && (
                  <>
                  <Form.Item name="prompt" label={editTaskType === 'keyframe_to_video' ? '提示词（可选）' : '提示词'}>
                    <TextArea rows={3} placeholder="描述想要生成的视频内容" />
                  </Form.Item>

                  {(editTaskType === 'image_to_video' || editTaskType === 'reference_to_video' || editTaskType === 'text_to_video' || editTaskType === 'keyframe_to_video') && (
                    <Form.Item name="negative_prompt" label="负向提示词">
                      <TextArea rows={2} placeholder="不希望出现的内容" />
                    </Form.Item>
                  )}
                  </>
                  )}
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
                              <Option key={key} value={key}>{info.name} {key}</Option>
                            ))}
                          </Select>
                        ) : editTaskType === 'reference_to_video' ? (
                          <Select
                            onChange={(v) => {
                              setEditModel(v)
                              const modelInfo = refVideoModels[v]
                              if (modelInfo?.default_size) {
                                editForm.setFieldValue('size', modelInfo.default_size)
                              }
                              if (modelInfo?.default_duration) {
                                editForm.setFieldValue('duration', modelInfo.default_duration)
                              }
                            }}
                          >
                            {Object.entries(refVideoModels).map(([key, info]) => (
                              <Option key={key} value={key}>{info.name}</Option>
                            ))}
                          </Select>
                        ) : editTaskType === 'video_repainting' || editTaskType === 'video_edit' ? (
                          <Select disabled value={VACE_MODEL_ID}>
                            <Option value={VACE_MODEL_ID}>{VACE_MODEL_ID}</Option>
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
                              <Option key={key} value={key}>{info.name} {key}</Option>
                            ))}
                          </Select>
                        )}
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      {editTaskType === 'image_to_video' ? (
                        <Form.Item name="resolution" label="分辨率">
                          <Select>
                            {(((getEditModelInfo() as VideoModelInfo | undefined)?.resolutions) || [
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
                      ) : editTaskType === 'video_edit' ? (
                        <Form.Item name="size" label="分辨率">
                          <Select>
                            {(getEditModelInfo() as VaceVideoEditModelInfo | undefined)?.sizes?.map((item) => (
                              <Option key={item.value} value={item.value}>{item.label}</Option>
                            ))}
                          </Select>
                        </Form.Item>
                      ) : editTaskType === 'video_repainting' ? (
                        <Form.Item label="输出规则">
                          <Input value="跟随源视频，超720P自动等比缩放" disabled />
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

                  {editTaskType !== 'video_repainting' && editTaskType !== 'video_edit' && (getEditModelInfo() as VideoModelInfo)?.supports_duration !== false && (
                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item name="duration" label="视频时长">
                        {(getEditModelInfo() as VideoModelInfo)?.duration_range ? (
                          <InputNumber
                            style={{ width: '100%' }}
                            min={(getEditModelInfo() as VideoModelInfo)?.duration_range?.[0] || 2}
                            max={(getEditModelInfo() as VideoModelInfo)?.duration_range?.[1] || 15}
                            addonAfter="秒"
                          />
                        ) : editTaskType === 'reference_to_video' ? (
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
                  )}

                  {editTaskType === 'video_repainting' && (
                    <>
                      <Row gutter={16}>
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
                        <Col span={12}>
                          <div style={{ marginBottom: 24 }}>
                            <div style={{ marginBottom: 8 }}>控制条件</div>
                            <Select value={editControlCondition} onChange={setEditControlCondition}>
                              {currentVideoRepaintingModelInfo?.supported_control_conditions?.map((value) => (
                                <Option key={value} value={value}>{value}</Option>
                              ))}
                            </Select>
                          </div>
                        </Col>
                      </Row>
                      <Row gutter={16}>
                        <Col span={12}>
                          <div style={{ marginBottom: 24 }}>
                            <div style={{ marginBottom: 8 }}>控制强度</div>
                            <InputNumber
                              style={{ width: '100%' }}
                              min={0}
                              max={1}
                              step={0.05}
                              value={editStrength}
                              onChange={(v) => setEditStrength(Number(v ?? 1))}
                            />
                          </div>
                        </Col>
                      </Row>
                    </>
                  )}

                  {editTaskType === 'video_edit' && (
                    <>
                      <Row gutter={16}>
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
                        <Col span={12}>
                          <div style={{ marginBottom: 24 }}>
                            <div style={{ marginBottom: 8 }}>控制条件</div>
                            <Select
                              value={editControlCondition || '__none__'}
                              onChange={(value) => setEditControlCondition(value === '__none__' ? '' : value)}
                            >
                              <Option value="__none__">不提取</Option>
                              {currentVideoEditModelInfo?.supported_control_conditions?.map((value) => (
                                <Option key={value} value={value}>{value}</Option>
                              ))}
                            </Select>
                          </div>
                        </Col>
                      </Row>
                      <Row gutter={16}>
                        <Col span={12}>
                          <div style={{ marginBottom: 24 }}>
                            <div style={{ marginBottom: 8 }}>Mask 模式</div>
                            <Select value={editMaskType} onChange={setEditMaskType}>
                              <Option value="tracking">tracking</Option>
                              <Option value="fixed">fixed</Option>
                            </Select>
                          </div>
                        </Col>
                        {editMaskType === 'tracking' && (
                          <Col span={12}>
                            <div style={{ marginBottom: 24 }}>
                              <div style={{ marginBottom: 8 }}>扩展比例</div>
                              <InputNumber
                                style={{ width: '100%' }}
                                min={0}
                                max={1}
                                step={0.01}
                                value={editExpandRatio}
                                onChange={(v) => setEditExpandRatio(Number(v ?? 0.05))}
                              />
                            </div>
                          </Col>
                        )}
                      </Row>
                      {editMaskType === 'tracking' && (
                        <Row gutter={16}>
                          <Col span={12}>
                            <div style={{ marginBottom: 24 }}>
                              <div style={{ marginBottom: 8 }}>包裹模式</div>
                              <Select value={editExpandMode} onChange={setEditExpandMode}>
                                {currentVideoEditModelInfo?.supported_expand_modes?.map((value) => (
                                  <Option key={value} value={value}>{value}</Option>
                                ))}
                              </Select>
                            </div>
                          </Col>
                        </Row>
                      )}
                    </>
                  )}

                  {(getEditModelInfo() as VideoModelInfo)?.requires_audio && (
                    <div style={{
                      padding: 12,
                      background: token.colorBgLayout,
                      borderRadius: 8,
                      marginBottom: 16,
                      border: `1px solid ${token.colorBorder}`
                    }}>
                      <div style={{ marginBottom: 12, fontWeight: 500 }}>🎤 驱动音频（必选）</div>
                      <Select
                        style={{ width: '100%' }}
                        value={editAudioUrl || undefined}
                        onChange={(v) => setEditAudioUrl(v || '')}
                        placeholder="从音频库选择"
                        allowClear
                        status={!editAudioUrl ? 'warning' : undefined}
                      >
                        {audioItems.map(audio => (
                          <Option key={audio.id} value={audio.url}>
                            {audio.name}
                          </Option>
                        ))}
                      </Select>
                      <div style={{ fontSize: 12, color: token.colorTextSecondary, marginTop: 4 }}>
                        音频将驱动人物口型、表情和动作（wav/mp3，小于15MB，时长不超过20秒，需清晰人声）
                      </div>
                    </div>
                  )}

                  {!((getEditModelInfo() as VideoModelInfo)?.requires_audio) && (
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
                      ) : editTaskType === 'text_to_video' ? (
                        <div style={{ marginBottom: 24 }}>
                          <div style={{ marginBottom: 8 }}>智能改写</div>
                          <Space>
                            <Switch
                              checked={editT2vPromptExtend}
                              onChange={setEditT2vPromptExtend}
                            />
                            <span style={{ color: token.colorTextSecondary, fontSize: 12 }}>使用大模型优化提示词</span>
                          </Space>
                        </div>
                      ) : (
                        <Form.Item name="prompt_extend" label="智能改写" valuePropName="checked">
                          <Switch />
                        </Form.Item>
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
                  )}

                  {editTaskType !== 'video_repainting' && editTaskType !== 'video_edit' && (getEditModelInfo()?.supports_audio || editModel?.includes('wan2.5') || editModel?.includes('wan2.6')) && !(getEditModelInfo() as VideoModelInfo)?.requires_audio && (
                    <div style={{
                      padding: 12,
                      background: token.colorBgLayout,
                      borderRadius: 8,
                      marginTop: 8,
                      border: `1px solid ${token.colorBorder}`
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
                        <div style={{ fontSize: 12, color: token.colorTextSecondary, marginTop: 4 }}>
                          传入音频后，视频将与音频内容对齐
                        </div>
                      </div>

                      <Form.Item name="auto_audio" valuePropName="checked" style={{ marginBottom: 0 }}>
                        <Space>
                          <Switch disabled={!!editAudioUrl} />
                          <span>自动生成音频</span>
                        </Space>
                      </Form.Item>
                      <div style={{ fontSize: 12, color: token.colorTextSecondary, marginTop: 4 }}>
                        {editAudioUrl
                          ? '已选择自定义音频，此选项无效'
                          : '开启后模型将自动生成匹配的背景音'
                        }
                      </div>
                    </div>
                  )}

                  {/* 镜头类型 - 仅 wan2.6 支持 */}
                  {editTaskType !== 'video_repainting' && editTaskType !== 'video_edit' && (((getEditModelInfo() as VideoModelInfo | RefVideoModelInfo | TextToVideoModelInfo | undefined)?.supports_shot_type) || editModel?.includes('wan2.6')) && (
                    <div style={{
                      padding: 12,
                      background: token.colorBgLayout,
                      borderRadius: 8,
                      marginTop: 8,
                      border: `1px solid ${token.colorPrimary}`
                    }}>
                      <div style={{ marginBottom: 12, fontWeight: 500, color: token.colorPrimary }}>🎬 镜头类型设置（仅 wan2.6 支持）</div>
                      <Form.Item name="shot_type" label="镜头类型" style={{ marginBottom: 0 }}>
                        <Select>
                          <Option value="single">单镜头 - 一个连续镜头</Option>
                          <Option value="multi">多镜头叙事 - 多个切换镜头</Option>
                        </Select>
                      </Form.Item>
                      <div style={{ fontSize: 12, color: token.colorTextSecondary, marginTop: 4 }}>
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
      )}
    </div>
  )
}

export default VideoStudioPage
