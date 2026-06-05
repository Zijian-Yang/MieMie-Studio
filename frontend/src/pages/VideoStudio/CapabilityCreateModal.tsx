import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Button,
  Col,
  Collapse,
  Divider,
  Dropdown,
  Empty,
  Input,
  InputNumber,
  Modal,
  Row,
  Select,
  Space,
  Spin,
  Tabs,
  Tag,
  Tooltip,
  Typography,
  message,
  theme,
} from 'antd'
import { DeleteOutlined, DownOutlined, PlusOutlined, VideoCameraOutlined } from '@ant-design/icons'
import {
  AudioItem,
  GalleryImage,
  HelpContent,
  VideoCapabilityModel,
  VideoInputRole,
  VideoNarrativeMode,
  VideoReferenceTokenRole,
  VideoReferenceMediaItem,
  VideoStudioTask,
  VideoStudioCapabilitiesResponse,
  VideoStudioInputAssets,
  VideoTaskKind,
  VideoTaskProfile,
  VideoLibraryItem,
  videoStudioApi,
} from '../../services/api'
import DynamicModelForm from '../../components/ModelConfig/DynamicModelForm'
import DeveloperPreviewPanel, { type VideoStudioPreviewPayload } from './DeveloperPreviewPanel'
import type { MaskEditorHandle, MaskEditorTool } from './MaskEditor'
import MaskEditorPanel, { type SourceVideoMetadata } from './MaskEditorPanel'
import ReferenceCollectionsPanel, { type StructuredReferenceMediaItem } from './ReferenceCollectionsPanel'
import VideoFieldLabel from './VideoFieldLabel'
import {
  countPromptLengthUnits,
  formatPromptLengthLimit,
  getPromptLengthError,
} from './promptLengthPolicy'
import {
  buildReferenceTokenOptions,
  insertReferenceTokenAtSelection,
} from './referenceTokenPolicy'

const { Text, Paragraph } = Typography
const { TextArea } = Input
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

interface MultiShotSegment {
  id: string
  prompt: string
  duration: number
}

interface PromptSelection {
  start: number
  end: number
}

interface CapabilityCreateModalProps {
  open: boolean
  projectId: string
  galleryImages: GalleryImage[]
  audioItems: AudioItem[]
  videoLibraryItems: VideoLibraryItem[]
  mode?: 'create' | 'edit'
  task?: VideoStudioTask | null
  onCancel: () => void
  onSubmitted: (task: VideoStudioTask) => void
}

function buildProfileModel(profile: VideoTaskProfile, model: VideoCapabilityModel) {
  return {
    id: model.id,
    name: model.name,
    type: model.type,
    description: model.description,
    parameters: profile.parameters,
    default_values: profile.default_values || {},
    capabilities: {},
    deprecated: false,
  }
}

function reconcileProfileValues(
  prevValues: Record<string, any>,
  profile: VideoTaskProfile | undefined
) {
  const defaults = profile?.default_values || {}
  const next: Record<string, any> = { ...defaults }
  const paramNames = new Set((profile?.parameters || []).map((param) => param.name))
  let keptCount = 0
  let resetCount = 0

  Object.entries(prevValues || {}).forEach(([key, value]) => {
    if (paramNames.has(key) && value !== undefined) {
      next[key] = value
      keptCount += 1
    } else if (value !== undefined) {
      resetCount += 1
    }
  })

  return { next, keptCount, resetCount }
}

function isPromptRequired(taskKind: VideoTaskKind, provider: string) {
  return (
    taskKind === 'text_to_video' ||
    taskKind === 'reference_to_video' ||
    taskKind === 'video_edit_global' ||
    taskKind === 'video_edit_local' ||
    taskKind === 'video_repainting' ||
    (taskKind === 'keyframe_to_video' && provider === 'vidu')
  )
}

function resolveTaskKind(task: VideoStudioTask): VideoTaskKind {
  const rawTaskType = task.task_type || 'image_to_video'
  const rawTaskKind = task.task_kind
  if (rawTaskKind && !(rawTaskKind === 'image_to_video' && rawTaskType !== 'image_to_video')) {
    return rawTaskKind
  }
  return LEGACY_TASK_KIND_MAP[rawTaskType] || 'image_to_video'
}

function buildFallbackInputAssets(task: VideoStudioTask, taskKind: VideoTaskKind): VideoStudioInputAssets {
  const referenceImages = task.reference_image_url ? [task.reference_image_url] : []
  return {
    first_frame: task.first_frame_url ? [task.first_frame_url] : [],
    last_frame: task.last_frame_url ? [task.last_frame_url] : [],
    first_clip: task.first_clip_url ? [task.first_clip_url] : [],
    audio: task.audio_url ? [task.audio_url] : [],
    reference_images: [...referenceImages],
    reference_videos: task.reference_video_urls || [],
    source_video: task.source_video_url ? [task.source_video_url] : [],
    base_video: taskKind === 'video_edit_global' && task.source_video_url ? [task.source_video_url] : [],
    mask_image: task.mask_image_url ? [task.mask_image_url] : [],
  }
}

function buildFallbackNormalizedParams(task: VideoStudioTask) {
  const resolvedTaskKind = resolveTaskKind(task)
  const normalizedSize = resolvedTaskKind === 'video_edit_local' && task.size === '1920*1080'
    ? undefined
    : task.size
  return {
    resolution: task.resolution,
    size: normalizedSize,
    duration: task.duration,
    prompt_extend: task.task_type === 'text_to_video' ? task.t2v_prompt_extend : task.prompt_extend,
    watermark: task.watermark,
    seed: task.seed,
    audio: task.auto_audio,
    ratio: task.ratio,
    audio_setting: task.audio_setting,
    shot_type: task.shot_type,
    control_condition: task.control_condition,
    strength: task.strength,
    mask_type: task.mask_type,
    expand_ratio: task.expand_ratio,
    expand_mode: task.expand_mode,
    mask_frame_id: task.mask_frame_id,
  }
}

function buildStructuredReferenceMedia(
  items: Array<VideoReferenceMediaItem | StructuredReferenceMediaItem>
): StructuredReferenceMediaItem[] {
  return items
    .filter((item) => item?.url)
    .map((item, index) => ({
      id: `reference-media-${index}-${item.type}-${item.url}`,
      type: item.type,
      url: item.url,
      reference_voice: item.reference_voice,
    }))
}

function getProviderTagColor(provider: string) {
  if (provider === 'wan') return 'blue'
  if (provider === 'happyhorse') return 'cyan'
  if (provider === 'kling') return 'purple'
  if (provider === 'vidu') return 'green'
  return 'default'
}

const CapabilityCreateModal = ({
  open,
  projectId,
  galleryImages,
  audioItems,
  videoLibraryItems,
  mode = 'create',
  task,
  onCancel,
  onSubmitted,
}: CapabilityCreateModalProps) => {
  const { token } = theme.useToken()
  const isEditMode = mode === 'edit'
  const [capabilities, setCapabilities] = useState<VideoStudioCapabilitiesResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [creating, setCreating] = useState(false)
  const [taskKind, setTaskKind] = useState<VideoTaskKind>('text_to_video')
  const [modelId, setModelId] = useState('')
  const [taskName, setTaskName] = useState('')
  const [prompt, setPrompt] = useState('')
  const [negativePrompt, setNegativePrompt] = useState('')
  const [groupCount, setGroupCount] = useState(1)
  const [dynamicValues, setDynamicValues] = useState<Record<string, any>>({})
  const [firstFrameUrl, setFirstFrameUrl] = useState('')
  const [lastFrameUrl, setLastFrameUrl] = useState('')
  const [referenceFirstFrameUrl, setReferenceFirstFrameUrl] = useState('')
  const [audioUrl, setAudioUrl] = useState('')
  const [firstClipUrl, setFirstClipUrl] = useState('')
  const [baseVideoUrl, setBaseVideoUrl] = useState('')
  const [sourceVideoUrl, setSourceVideoUrl] = useState('')
  const [referenceImageUrls, setReferenceImageUrls] = useState<string[]>([])
  const [referenceVideoUrls, setReferenceVideoUrls] = useState<string[]>([])
  const [referenceMediaItems, setReferenceMediaItems] = useState<StructuredReferenceMediaItem[]>([])
  const [sourceVideoPreviewDataUrl, setSourceVideoPreviewDataUrl] = useState('')
  const [sourceVideoPreviewUrl, setSourceVideoPreviewUrl] = useState('')
  const [sourceVideoMetadata, setSourceVideoMetadata] = useState<SourceVideoMetadata | null>(null)
  const [sourceVideoWarnings, setSourceVideoWarnings] = useState<string[]>([])
  const [sourceVideoPreparing, setSourceVideoPreparing] = useState(false)
  const [maskTool, setMaskTool] = useState<MaskEditorTool>('brush')
  const [maskBrushSize, setMaskBrushSize] = useState(16)
  const [maskHasContent, setMaskHasContent] = useState(false)
  const [maskUploading, setMaskUploading] = useState(false)
  const [multiShotSegments, setMultiShotSegments] = useState<MultiShotSegment[]>([
    { id: 'segment-1', prompt: '', duration: 5 },
  ])
  const [previewPayload, setPreviewPayload] = useState<VideoStudioPreviewPayload | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const maskEditorRef = useRef<MaskEditorHandle | null>(null)
  const promptTextAreaRef = useRef<any>(null)
  const promptSelectionRef = useRef<PromptSelection | null>(null)

  const resetLocalState = (defaults: Record<string, any> = {}) => {
    setTaskName('')
    setPrompt('')
    promptSelectionRef.current = null
    setNegativePrompt('')
    setGroupCount(1)
    setDynamicValues(defaults)
    setFirstFrameUrl('')
    setLastFrameUrl('')
    setReferenceFirstFrameUrl('')
    setAudioUrl('')
    setFirstClipUrl('')
    setBaseVideoUrl('')
    setSourceVideoUrl('')
    setReferenceImageUrls([])
    setReferenceVideoUrls([])
    setReferenceMediaItems([])
    setSourceVideoPreviewDataUrl('')
    setSourceVideoPreviewUrl('')
    setSourceVideoMetadata(null)
    setSourceVideoWarnings([])
    setSourceVideoPreparing(false)
    setMaskTool('brush')
    setMaskBrushSize(16)
    setMaskHasContent(false)
    setMaskUploading(false)
    setMultiShotSegments([{ id: `segment-${Date.now()}`, prompt: '', duration: 5 }])
    setPreviewPayload(null)
    setPreviewLoading(false)
  }

  const populateFromTask = (response: VideoStudioCapabilitiesResponse, currentTask: VideoStudioTask) => {
    const resolvedTaskKind = resolveTaskKind(currentTask)
    const taskInfo = response.task_kinds.find((item) => item.id === resolvedTaskKind)
    const resolvedModelId = currentTask.model_id || currentTask.model || taskInfo?.default_model_id || taskInfo?.model_ids[0] || ''
    const resolvedModel = response.models[resolvedModelId]
    const profile = resolvedModel?.task_profiles?.[resolvedTaskKind] as VideoTaskProfile | undefined
    const assets = currentTask.input_assets && Object.keys(currentTask.input_assets).length > 0
      ? currentTask.input_assets
      : buildFallbackInputAssets(currentTask, resolvedTaskKind)
    const fallbackParams = buildFallbackNormalizedParams(currentTask)
    const baseParams = currentTask.normalized_params && Object.keys(currentTask.normalized_params).length > 0
      ? currentTask.normalized_params
      : fallbackParams
    const nextDynamicValues: Record<string, any> = {
      ...(profile?.default_values || {}),
      ...fallbackParams,
      ...baseParams,
    }
    if (profile?.parameters.some((param) => param.name === 'narrative_mode') && currentTask.narrative_mode) {
      nextDynamicValues.narrative_mode = currentTask.narrative_mode
    }

    setTaskKind(resolvedTaskKind)
    setModelId(resolvedModelId)
    setTaskName(currentTask.name || '')
    setPrompt(currentTask.prompt || '')
    setNegativePrompt(currentTask.negative_prompt || '')
    setGroupCount(currentTask.group_count || 1)
    setDynamicValues(nextDynamicValues)
    setFirstFrameUrl((assets.first_frame || [])[0] || '')
    setLastFrameUrl((assets.last_frame || [])[0] || '')
    setReferenceFirstFrameUrl(resolvedTaskKind === 'reference_to_video' ? ((assets.first_frame || [])[0] || '') : '')
    setAudioUrl((assets.audio || [])[0] || '')
    setFirstClipUrl((assets.first_clip || [])[0] || currentTask.first_clip_url || '')
    setBaseVideoUrl((assets.base_video || [])[0] || '')
    setSourceVideoUrl((assets.source_video || [])[0] || '')
    setReferenceImageUrls([...(assets.reference_images || [])])
    setReferenceVideoUrls([...(assets.reference_videos || [])])
    setReferenceMediaItems(
      Array.isArray(assets.reference_media) && assets.reference_media.length > 0
        ? buildStructuredReferenceMedia(assets.reference_media)
        : buildStructuredReferenceMedia([
            ...(assets.reference_images || []).map((url: string) => ({ type: 'reference_image' as const, url })),
            ...(assets.reference_videos || []).map((url: string) => ({ type: 'reference_video' as const, url })),
          ])
    )
    setSourceVideoPreviewDataUrl('')
    setSourceVideoPreviewUrl(currentTask.source_video_preview_url || '')
    setSourceVideoMetadata(null)
    setSourceVideoWarnings([])
    setSourceVideoPreparing(false)
    setMaskTool('brush')
    setMaskBrushSize(16)
    setMaskHasContent(Boolean((assets.mask_image || [])[0] || currentTask.mask_image_url))
    setMaskUploading(false)
    setMultiShotSegments(
      Array.isArray(nextDynamicValues.multi_prompt_segments) && nextDynamicValues.multi_prompt_segments.length > 0
        ? nextDynamicValues.multi_prompt_segments.map((segment: any, index: number) => ({
            id: `segment-${index}-${Date.now()}`,
            prompt: segment.prompt || '',
            duration: segment.duration || 5,
          }))
        : [{ id: `segment-${Date.now()}`, prompt: '', duration: 5 }]
    )
  }

  useEffect(() => {
    if (!open) return
    setLoading(true)
    videoStudioApi.getCapabilities()
      .then((response) => {
        setCapabilities(response)
        if (isEditMode && task) {
          populateFromTask(response, task)
        } else {
          const defaultTaskKind = response.task_kinds[0]?.id || 'text_to_video'
          const defaultModelId = response.task_kinds[0]?.default_model_id || ''
          const defaultProfile = response.models[defaultModelId]?.task_profiles?.[defaultTaskKind] as VideoTaskProfile | undefined
          setTaskKind(defaultTaskKind)
          setModelId(defaultModelId)
          resetLocalState(defaultProfile?.default_values || {})
        }
      })
      .catch((error: any) => {
        message.error(error.message || '加载视频能力失败')
      })
      .finally(() => setLoading(false))
  }, [open, isEditMode, task])

  const currentTaskInfo = useMemo(
    () => capabilities?.task_kinds.find((item) => item.id === taskKind) || null,
    [capabilities, taskKind]
  )
  const currentModel = useMemo(
    () => (modelId ? capabilities?.models[modelId] : undefined),
    [capabilities, modelId]
  )
  const currentProfile = useMemo(
    () => (currentModel?.task_profiles?.[taskKind] as VideoTaskProfile | undefined),
    [currentModel, taskKind]
  )

  useEffect(() => {
    if (taskKind !== 'reference_to_video' || modelId !== 'wan2.7-r2v') return
    if (referenceMediaItems.length > 0) return
    if (referenceImageUrls.length === 0 && referenceVideoUrls.length === 0) return
    setReferenceMediaItems(buildStructuredReferenceMedia([
      ...referenceImageUrls.map((url) => ({ type: 'reference_image' as const, url })),
      ...referenceVideoUrls.map((url) => ({ type: 'reference_video' as const, url })),
    ]))
  }, [taskKind, modelId, referenceMediaItems, referenceImageUrls, referenceVideoUrls])

  useEffect(() => {
    if (taskKind !== 'reference_to_video' || modelId !== 'wan2.7-r2v') return
    setReferenceImageUrls(referenceMediaItems.filter((item) => item.type === 'reference_image').map((item) => item.url))
    setReferenceVideoUrls(referenceMediaItems.filter((item) => item.type === 'reference_video').map((item) => item.url))
  }, [taskKind, modelId, referenceMediaItems])

  const getAssetHelp = (role: VideoInputRole): HelpContent | string | undefined => {
    const profileHelp = currentProfile?.ui_hints?.asset_help?.[role]
    if (profileHelp) return profileHelp

    if (currentProvider === 'vidu' && role === 'first_frame') {
      return {
        summary: 'Vidu 首帧图会作为视频的视觉起点。',
        limits: ['格式支持 JPG / PNG / WEBP', '宽高比需在 1:4 到 4:1 之间', '文件大小不超过 50MB'],
        how_to_choose: ['主体尽量清晰完整', '画面边缘避免裁切关键主体'],
        examples: ['例如：角色站立全身图、产品正面图、场景起始镜头图'],
      }
    }
    if (currentProvider === 'vidu' && role === 'last_frame') {
      return {
        summary: 'Vidu 尾帧图用于定义视频的结束画面。',
        limits: ['尾帧图与首帧图建议保持相近分辨率', '两者总像素比值需在 0.8 到 1.25 之间'],
        how_to_choose: ['适合做镜头运动、姿态变化、开合动作的终点状态'],
      }
    }
    if (currentProvider === 'vidu' && role === 'reference_video') {
      return {
        summary: 'Vidu 参考视频用于提供运动节奏、镜头动态或动作趋势。',
        limits: ['格式支持 MP4 / AVI / MOV', '时长需在 1 到 5 秒之间', '宽高比需在 1:4 到 4:1 之间'],
        how_to_choose: ['优先选择运动清晰、节奏稳定的短视频', '避免过快剪辑和过于复杂的镜头切换'],
      }
    }
    if (currentProvider === 'vidu' && role === 'reference_image') {
      return {
        summary: 'Vidu 参考图用于传递角色、物体或风格线索。',
        limits: ['格式支持 JPG / PNG / WEBP', '宽高比需在 1:4 到 4:1 之间', '文件大小不超过 50MB'],
        how_to_choose: ['角色参考图尽量单主体', '背景参考图尽量少混入无关元素'],
      }
    }
    if (currentProvider === 'kling' && role === 'base_video') {
      return {
        summary: 'Kling 视频编辑的 base video 是被编辑的原视频。',
        limits: ['格式支持 MP4 / MOV', '时长需在 3 到 10 秒之间', '帧率需在 24 到 60 FPS 之间', '宽高需在 720 到 2160 像素之间'],
        how_to_choose: ['优先使用单镜头、主体清晰的视频', '复杂剪辑视频更容易触发模型限制或编辑失真'],
        examples: ['例如：10 秒以内的机械臂操作视频、人物走动镜头、产品展示镜头'],
      }
    }
    if (currentProvider === 'wan' && role === 'first_clip') {
      return {
        summary: 'Wan2.7 视频续写会把首段视频作为前情片段，继续生成后续内容。',
        limits: ['格式支持 MP4 / MOV', '时长需在 2 到 10 秒之间', '宽高需在 240 到 4096 像素之间', '宽高比需在 1:8 到 8:1 之间', '文件大小不超过 100MB'],
        how_to_choose: ['优先使用单镜头、动作连续、节奏明确的视频片段', '如果还想指定结尾画面，可额外提供尾帧图'],
        examples: ['例如：一段 4 秒的机械臂起手动作视频，续写后生成完整开柜门过程'],
      }
    }
    if (currentProvider === 'wan' && role === 'base_video') {
      return {
        summary: 'Wan2.7 视频编辑的待编辑视频是被改造的原视频。',
        limits: ['格式支持 MP4 / MOV', '时长需在 2 到 10 秒之间', '宽高需在 240 到 4096 像素之间', '宽高比需在 1:8 到 8:1 之间', '文件大小不超过 100MB'],
        how_to_choose: ['优先使用单镜头、主体明确的视频', '如果只做风格迁移，可以不传参考图'],
        examples: ['例如：人物走动镜头、机械臂操作镜头、产品展示镜头'],
      }
    }
    if (currentProvider === 'wan' && role === 'reference_image' && taskKind === 'video_edit_global') {
      return {
        summary: 'Wan2.7 视频编辑可选参考图，用于做服饰、物体或风格引导。',
        limits: ['最多 3 张参考图', '格式支持 JPEG / JPG / PNG / BMP / WEBP', '不支持透明通道 PNG', '宽高需在 240 到 8000 像素之间', '宽高比需在 1:8 到 8:1 之间', '文件大小不超过 20MB'],
        how_to_choose: ['不传参考图时更像整体风格修改', '传参考图时更适合做主体外观、服饰或材质替换'],
      }
    }
    if (currentProvider === 'kling' && role === 'reference_video') {
      return {
        summary: 'Kling 参考视频用于提供动作、构图或节奏参考。',
        limits: ['格式支持 MP4 / MOV', '时长需在 3 到 10 秒之间', '帧率需在 24 到 60 FPS 之间', '宽高需在 720 到 2160 像素之间'],
        how_to_choose: ['参考视频适合传递动作风格，不适合做像素级替换', '复杂剪辑视频建议拆成更短、更单一的动作段落'],
      }
    }
    if (currentProvider === 'kling' && role === 'reference_image') {
      return {
        summary: 'Kling 参考图用于引导主体造型、服饰或风格。',
        limits: ['格式支持 JPG / JPEG / PNG', '宽高需在 300 到 8000 像素之间', 'PNG 不能带透明通道'],
        how_to_choose: ['角色/物体参考图建议主体突出', '避免透明底、拼贴图和过多无关背景'],
      }
    }
    if (currentProvider === 'wan' && role === 'source_video') {
      return {
        summary: 'Wan 局部编辑和视频重绘都会先读取源视频结构与运动信息。',
        limits: ['格式必须为 MP4', '帧率至少 16 FPS', '大小不超过 50MB', '超过 5 秒会被截到前 5 秒'],
        how_to_choose: ['源视频越稳定，局部编辑越容易保持原动作', '建议先用单镜头短视频验证效果'],
      }
    }
    if (currentProvider === 'wan' && role === 'mask_image') {
      return {
        summary: 'Mask 白色区域会被编辑，黑色区域保持不变。',
        limits: ['Mask 分辨率必须与源视频首帧完全一致', '白色必须是纯白，黑色必须是纯黑'],
        how_to_choose: ['运动主体优先用 tracking', '静止主体优先用 fixed', '接触边缘可适当多包一点，避免切边'],
        examples: ['例如：机械臂整体替换时，Mask 需覆盖机械臂主体与关键接触部位'],
      }
    }
    return undefined
  }

  const promptHelp = currentProfile?.ui_hints?.prompt_help as HelpContent | string | undefined

  useEffect(() => {
    if (!capabilities || !currentTaskInfo) return
    if (!currentTaskInfo.model_ids.includes(modelId)) {
      const nextModelId = currentTaskInfo.default_model_id || currentTaskInfo.model_ids[0] || ''
      setModelId(nextModelId)
      const nextProfile = nextModelId
        ? capabilities?.models[nextModelId]?.task_profiles?.[taskKind] as VideoTaskProfile | undefined
        : undefined
      setDynamicValues(nextProfile?.default_values || {})
    }
  }, [capabilities, currentTaskInfo, modelId])

  useEffect(() => {
    if (!currentModel || currentModel.provider !== 'vidu' || !currentProfile) return
    const sizeOptionsByResolution = currentProfile.ui_hints?.size_options_by_resolution || {}
    const resolution = dynamicValues.resolution
    const options = sizeOptionsByResolution[resolution] || []
    if (options.length === 0) return
    if (!options.some((item: { value: string }) => item.value === dynamicValues.size)) {
      setDynamicValues((prev) => ({ ...prev, size: options[0].value }))
    }
  }, [currentModel, currentProfile, dynamicValues.resolution, dynamicValues.size])

  const handleTaskKindChange = (nextTaskKind: string) => {
    const typedTaskKind = nextTaskKind as VideoTaskKind
    setTaskKind(typedTaskKind)
    const nextTaskInfo = capabilities?.task_kinds.find((item) => item.id === typedTaskKind)
    const nextModelId = nextTaskInfo?.default_model_id || nextTaskInfo?.model_ids[0] || ''
    const nextProfile = nextModelId ? capabilities?.models[nextModelId]?.task_profiles?.[typedTaskKind] as VideoTaskProfile | undefined : undefined
    if (nextTaskInfo) {
      setModelId(nextModelId)
    }
    resetLocalState(nextProfile?.default_values || {})
  }

  const handleModelChange = (nextModelId: string) => {
    setModelId(nextModelId)
    const nextProfile = capabilities?.models[nextModelId]?.task_profiles?.[taskKind] as VideoTaskProfile | undefined
    if (!nextProfile) {
      setDynamicValues({})
      return
    }
    setDynamicValues((prev) => {
      const { next, keptCount, resetCount } = reconcileProfileValues(prev, nextProfile)
      if (keptCount > 0 || resetCount > 0) {
        message.info({
          key: 'video-model-profile-change',
          content: `已保留 ${keptCount} 个兼容参数，重置 ${resetCount} 个当前模型不支持的参数`,
        })
      }
      return next
    })
  }

  const getEffectiveProfile = () => {
    if (!currentProfile || !currentModel) return null
    const params = currentProfile.parameters.filter((param) => {
      if (param.name === 'keep_original_sound') {
        if (taskKind === 'video_edit_global') return Boolean(baseVideoUrl)
        if (taskKind === 'reference_to_video') return referenceVideoUrls.length > 0
      }
      return true
    })
    return { ...currentProfile, parameters: params }
  }

  const handlePrepareSourceVideo = async (videoUrl: string) => {
    if (!videoUrl) return
    setSourceVideoPreparing(true)
    setSourceVideoPreviewDataUrl('')
    setSourceVideoPreviewUrl('')
    setSourceVideoMetadata(null)
    setSourceVideoWarnings([])
    setMaskHasContent(false)
    try {
      const result = await videoStudioApi.prepareSourceVideo({
        project_id: projectId,
        video_url: videoUrl,
      })
      setSourceVideoPreviewDataUrl(result.preview_image_data_url)
      setSourceVideoPreviewUrl(result.preview_image_url || '')
      setSourceVideoMetadata(result.metadata)
      setSourceVideoWarnings(result.warnings || [])
    } catch (error: any) {
      message.error(error.message || '源视频准备失败')
    } finally {
      setSourceVideoPreparing(false)
    }
  }

  const addUnique = (items: string[], value: string) => items.includes(value) ? items : [...items, value]
  const currentProvider = currentModel?.provider || 'wan'
  const currentRateLimitCapabilities = currentModel?.capabilities || {}
  const groupCountMax = typeof currentRateLimitCapabilities.max_concurrent === 'number'
    ? currentRateLimitCapabilities.max_concurrent
    : undefined
  const submitRate = currentRateLimitCapabilities.submit_rate_limit
  const groupCountHelp = [
    groupCountMax ? `并发上限 ${groupCountMax} 组` : null,
    submitRate ? `提交频率 ${submitRate.count} 次/${submitRate.period_seconds === 1 ? '秒' : `${submitRate.period_seconds} 秒`}` : null,
  ].filter(Boolean).join('；')
  const isWan27ReferenceModel = taskKind === 'reference_to_video' && modelId === 'wan2.7-r2v'
  const promptRequired = isPromptRequired(taskKind, currentProvider)
  const promptLengthPolicy = currentProfile?.ui_hints?.prompt_length_policy
  const promptLengthUnits = countPromptLengthUnits(prompt.trim(), promptLengthPolicy)
  const promptLengthError = getPromptLengthError(prompt.trim(), promptLengthPolicy)
  const promptLengthLimitLabel = formatPromptLengthLimit(promptLengthPolicy)
  const narrativeMode = ((dynamicValues.narrative_mode as VideoNarrativeMode | undefined) || dynamicValues.shot_type || task?.narrative_mode || 'single') as VideoNarrativeMode
  const supportsMultiShot = currentProfile?.supported_narrative_modes?.some((mode) => mode !== 'single') || false

  const getPromptTextAreaElement = () => (
    promptTextAreaRef.current?.resizableTextArea?.textArea as HTMLTextAreaElement | undefined
  )
  const updatePromptSelection = (target: HTMLTextAreaElement) => {
    promptSelectionRef.current = {
      start: target.selectionStart,
      end: target.selectionEnd,
    }
  }
  const insertReferenceToken = (tokenText: string) => {
    const textArea = getPromptTextAreaElement()
    const liveSelection = promptSelectionRef.current || (
      textArea && document.activeElement === textArea
        ? { start: textArea.selectionStart, end: textArea.selectionEnd }
        : null
    )
    const next = insertReferenceTokenAtSelection(prompt, tokenText, liveSelection?.start, liveSelection?.end)
    setPrompt(next.value)
    promptSelectionRef.current = { start: next.cursor, end: next.cursor }
    window.requestAnimationFrame(() => {
      const nextTextArea = getPromptTextAreaElement()
      if (!nextTextArea) return
      nextTextArea.focus()
      nextTextArea.setSelectionRange(next.cursor, next.cursor)
    })
  }
  const renderReferenceTokenButton = (
    role: VideoReferenceTokenRole,
    roleIndex: number,
    roleCounts: Partial<Record<VideoReferenceTokenRole, number>>,
  ) => {
    const options = buildReferenceTokenOptions({
      role,
      roleIndex,
      roleCounts,
      policy: currentProfile?.ui_hints?.reference_token_policy,
    })
    const [primary, ...variants] = options
    if (!primary) return null

    const primaryButton = (
      <Tooltip title={`插入指代词 ${primary.token}`}>
        <Button
          size="small"
          type="text"
          aria-label={`插入指代词 ${primary.token}`}
          onClick={() => insertReferenceToken(primary.token)}
        >
          @
        </Button>
      </Tooltip>
    )

    if (variants.length === 0) return primaryButton

    return (
      <Space.Compact size="small">
        {primaryButton}
        <Dropdown
          trigger={['click']}
          menu={{
            items: variants.map((option) => ({
              key: option.key,
              label: option.label,
            })),
            onClick: ({ key }) => {
              const option = variants.find((item) => item.key === key)
              if (option) insertReferenceToken(option.token)
            },
          }}
        >
          <Button
            size="small"
            type="text"
            icon={<DownOutlined />}
            aria-label="选择指代词格式"
          />
        </Dropdown>
      </Space.Compact>
    )
  }

  useEffect(() => {
    if (!groupCountMax || groupCount <= groupCountMax) return
    setGroupCount(groupCountMax)
  }, [groupCount, groupCountMax])

  const removeReferenceImage = (url: string) => setReferenceImageUrls((prev) => prev.filter((item) => item !== url))
  const removeReferenceVideo = (url: string) => setReferenceVideoUrls((prev) => prev.filter((item) => item !== url))
  const addReferenceMediaItem = (type: 'reference_image' | 'reference_video', url: string) => {
    if (!url) return
    setReferenceMediaItems((prev) => {
      if (prev.some((item) => item.type === type && item.url === url)) return prev
      return [
        ...prev,
        {
          id: `reference-media-${Date.now()}-${Math.random()}`,
          type,
          url,
        },
      ]
    })
  }
  const removeReferenceMediaItem = (id: string) => {
    setReferenceMediaItems((prev) => prev.filter((item) => item.id !== id))
  }
  const moveReferenceMediaItem = (id: string, direction: -1 | 1) => {
    setReferenceMediaItems((prev) => {
      const index = prev.findIndex((item) => item.id === id)
      const targetIndex = index + direction
      if (index < 0 || targetIndex < 0 || targetIndex >= prev.length) return prev
      const next = [...prev]
      const [moved] = next.splice(index, 1)
      next.splice(targetIndex, 0, moved)
      return next
    })
  }
  const updateReferenceMediaVoice = (id: string, referenceVoice?: string) => {
    setReferenceMediaItems((prev) => prev.map((item) => item.id === id ? { ...item, reference_voice: referenceVoice || undefined } : item))
  }
  const existingMaskImageUrl = (task?.input_assets?.mask_image || [])[0] || task?.mask_image_url || ''

  const buildInputAssets = async () => {
    const inputAssets: Record<string, any> = {}
    if (firstFrameUrl) inputAssets.first_frame = [firstFrameUrl]
    if (lastFrameUrl) inputAssets.last_frame = [lastFrameUrl]
    if (firstClipUrl) inputAssets.first_clip = [firstClipUrl]
    if (audioUrl) inputAssets.audio = [audioUrl]
    if (isWan27ReferenceModel) {
      if (referenceMediaItems.length > 0) {
        inputAssets.reference_media = referenceMediaItems.map((item) => ({
          type: item.type,
          url: item.url,
          reference_voice: item.reference_voice,
        }))
      }
    } else {
      if (referenceImageUrls.length > 0) inputAssets.reference_images = referenceImageUrls
      if (referenceVideoUrls.length > 0) inputAssets.reference_videos = referenceVideoUrls
    }
    if (referenceFirstFrameUrl) inputAssets.first_frame = [referenceFirstFrameUrl]
    if (baseVideoUrl) inputAssets.base_video = [baseVideoUrl]
    if (sourceVideoUrl) inputAssets.source_video = [sourceVideoUrl]

    if (taskKind === 'video_edit_local') {
      if (isEditMode) {
        if (!existingMaskImageUrl) {
          throw new Error('当前任务没有可复用的蒙版，请重新创建局部编辑任务')
        }
        inputAssets.mask_image = [existingMaskImageUrl]
      } else {
        if (!maskHasContent || !sourceVideoMetadata) {
          throw new Error('请先绘制局部编辑蒙版')
        }
        const maskBlob = await maskEditorRef.current?.exportMask()
        if (!maskBlob) {
          throw new Error('蒙版导出失败')
        }
        const formData = new FormData()
        formData.append('project_id', projectId)
        formData.append('source_video_url', sourceVideoUrl)
        formData.append('mask_file', maskBlob, 'mask.png')
        setMaskUploading(true)
        try {
          const maskResult = await videoStudioApi.uploadMask(formData)
          inputAssets.mask_image = [maskResult.mask_image_url]
        } finally {
          setMaskUploading(false)
        }
      }
    }
    return inputAssets
  }

  const buildPreviewDraft = async () => {
    const effectiveProfile = getEffectiveProfile()
    if (!currentModel || !effectiveProfile) return null
    const normalizedParams = { ...dynamicValues }
    if (currentProvider === 'kling' && taskKind === 'text_to_video' && narrativeMode === 'multi_shot_customize') {
      normalizedParams.multi_prompt_segments = multiShotSegments.map((segment) => ({
        prompt: segment.prompt,
        duration: segment.duration,
      }))
    }
    const inputAssets = await (async () => {
      const assets: Record<string, any> = {}
      if (firstFrameUrl) assets.first_frame = [firstFrameUrl]
      if (lastFrameUrl) assets.last_frame = [lastFrameUrl]
      if (firstClipUrl) assets.first_clip = [firstClipUrl]
      if (audioUrl) assets.audio = [audioUrl]
      if (isWan27ReferenceModel) {
        if (referenceMediaItems.length > 0) {
          assets.reference_media = referenceMediaItems.map((item) => ({
            type: item.type,
            url: item.url,
            reference_voice: item.reference_voice,
          }))
        }
      } else {
        if (referenceImageUrls.length > 0) assets.reference_images = referenceImageUrls
        if (referenceVideoUrls.length > 0) assets.reference_videos = referenceVideoUrls
      }
      if (referenceFirstFrameUrl) assets.first_frame = [referenceFirstFrameUrl]
      if (baseVideoUrl) assets.base_video = [baseVideoUrl]
      if (sourceVideoUrl) assets.source_video = [sourceVideoUrl]
      if (taskKind === 'video_edit_local') {
        const maskUrl = isEditMode ? existingMaskImageUrl : undefined
        if (maskUrl) assets.mask_image = [maskUrl]
      }
      return assets
    })()
    return {
      project_id: projectId,
      name: taskName || undefined,
      task_kind: taskKind,
      task_type: (taskKind === 'video_edit_local' ? 'video_edit' : taskKind) as any,
      provider: currentProvider,
      model_id: modelId,
      model: modelId,
      narrative_mode: narrativeMode,
      input_assets: inputAssets,
      normalized_params: normalizedParams,
      prompt: prompt.trim(),
      negative_prompt: negativePrompt.trim(),
      group_count: groupCount,
      source_video_preview_url: sourceVideoPreviewUrl || undefined,
    }
  }

  useEffect(() => {
    if (!open || !currentModel || !currentProfile) return
    let cancelled = false
    const timer = window.setTimeout(async () => {
      try {
        setPreviewLoading(true)
        const draft = await buildPreviewDraft()
        if (!draft) return
        const result = await videoStudioApi.previewPayload(draft)
        if (!cancelled) {
          setPreviewPayload(result)
        }
      } catch {
        if (!cancelled) {
          setPreviewPayload(null)
        }
      } finally {
        if (!cancelled) {
          setPreviewLoading(false)
        }
      }
    }, 250)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [
    open,
    projectId,
    currentModel,
    currentProfile,
    currentProvider,
    taskKind,
    modelId,
    taskName,
    prompt,
    negativePrompt,
    groupCount,
    JSON.stringify(dynamicValues),
    firstFrameUrl,
    lastFrameUrl,
    referenceFirstFrameUrl,
    audioUrl,
    firstClipUrl,
    baseVideoUrl,
    sourceVideoUrl,
    sourceVideoPreviewUrl,
    existingMaskImageUrl,
    referenceImageUrls.join('|'),
    referenceVideoUrls.join('|'),
    referenceMediaItems.map((item) => `${item.type}:${item.url}:${item.reference_voice || ''}`).join('|'),
    narrativeMode,
    multiShotSegments.map((s) => `${s.prompt}-${s.duration}`).join('|'),
  ])

  const validateBeforeSubmit = () => {
    if (!currentModel || !currentProfile) {
      throw new Error('请选择模型')
    }
    if (taskKind === 'image_to_video' && !firstFrameUrl) {
      throw new Error('请选择首帧图')
    }
    if (taskKind === 'keyframe_to_video' && (!firstFrameUrl || !lastFrameUrl)) {
      throw new Error('请选择首帧图和尾帧图')
    }
    if (taskKind === 'video_extension' && !firstClipUrl) {
      throw new Error('请选择首段视频')
    }
    if (taskKind === 'reference_to_video' && isWan27ReferenceModel && referenceMediaItems.length === 0) {
      throw new Error('请至少添加一项参考素材')
    }
    if (taskKind === 'reference_to_video' && !isWan27ReferenceModel && referenceImageUrls.length === 0 && referenceVideoUrls.length === 0) {
      throw new Error('请至少添加一项参考素材')
    }
    if (taskKind === 'video_edit_global' && !baseVideoUrl) {
      throw new Error('请选择待编辑视频')
    }
    if ((taskKind === 'video_edit_local' || taskKind === 'video_repainting') && !sourceVideoUrl) {
      throw new Error('请选择源视频')
    }
    if (isEditMode && taskKind === 'video_edit_local' && !existingMaskImageUrl) {
      throw new Error('当前任务没有可复用的蒙版，请重新创建局部编辑任务')
    }
    if (promptRequired && !prompt.trim()) {
      throw new Error('请输入提示词')
    }
    const lengthError = getPromptLengthError(prompt.trim(), currentProfile?.ui_hints?.prompt_length_policy)
    if (lengthError) {
      throw new Error(lengthError)
    }
    if (currentProvider === 'kling' && taskKind === 'reference_to_video' && referenceFirstFrameUrl && referenceVideoUrls.length === 0) {
      throw new Error('可灵首帧参考模式需要同时选择参考视频')
    }
    if (currentProvider === 'kling' && taskKind === 'text_to_video' && narrativeMode === 'multi_shot_customize') {
      if (multiShotSegments.length === 0 || multiShotSegments.some((segment) => !segment.prompt.trim())) {
        throw new Error('请完整填写自定义分镜内容')
      }
    }
  }

  const handleSubmit = async () => {
    try {
      validateBeforeSubmit()
      setCreating(true)
      const inputAssets = await buildInputAssets()
      const normalizedParams = { ...dynamicValues }
      if (currentProvider === 'kling' && taskKind === 'text_to_video' && narrativeMode === 'multi_shot_customize') {
        normalizedParams.multi_prompt_segments = multiShotSegments.map((segment) => ({
          prompt: segment.prompt,
          duration: segment.duration,
        }))
      }

      const commonPayload = {
        name: taskName || undefined,
        task_kind: taskKind,
        task_type: taskKind === 'video_edit_local' ? 'video_edit' : (taskKind as any),
        provider: currentProvider,
        model_id: modelId,
        model: modelId,
        narrative_mode: narrativeMode,
        input_assets: inputAssets,
        normalized_params: normalizedParams,
        prompt: prompt.trim(),
        negative_prompt: negativePrompt.trim(),
        group_count: groupCount,
        source_video_preview_url: sourceVideoPreviewUrl || undefined,
      }
      const savedTask = isEditMode && task
        ? await videoStudioApi.update(task.id, commonPayload)
        : (await videoStudioApi.create({
            project_id: projectId,
            ...commonPayload,
          })).task
      message.success(isEditMode ? '任务已更新' : '任务已创建')
      if (!isEditMode) {
        resetLocalState(currentProfile?.default_values || {})
      }
      onSubmitted(savedTask)
      onCancel()
    } catch (error: any) {
      message.error(error.message || (isEditMode ? '更新任务失败' : '创建任务失败'))
    } finally {
      setCreating(false)
    }
  }

  const renderAssetSelector = (role: VideoInputRole) => {
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
              if (taskKind === 'reference_to_video') setReferenceFirstFrameUrl(value || '')
              else setFirstFrameUrl(value || '')
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
            onChange={(value) => setLastFrameUrl(value || '')}
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
            onChange={(value) => setAudioUrl(value || '')}
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
            onChange={(value) => setFirstClipUrl(value || '')}
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
                setBaseVideoUrl(value || '')
              } else {
                setSourceVideoUrl(value || '')
                if (value) {
                  void handlePrepareSourceVideo(value)
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

  const renderReferenceCollections = () => {
    return (
      <ReferenceCollectionsPanel
        taskKind={taskKind}
        currentProfile={currentProfile}
        isWan27ReferenceModel={isWan27ReferenceModel}
        galleryImages={galleryImages}
        videoLibraryItems={videoLibraryItems}
        audioItems={audioItems}
        referenceImageUrls={referenceImageUrls}
        referenceVideoUrls={referenceVideoUrls}
        referenceMediaItems={referenceMediaItems}
        getAssetHelp={getAssetHelp}
        onAddReferenceImage={(url) => setReferenceImageUrls((prev) => addUnique(prev, url))}
        onAddReferenceVideo={(url) => setReferenceVideoUrls((prev) => addUnique(prev, url))}
        onRemoveReferenceImage={removeReferenceImage}
        onRemoveReferenceVideo={removeReferenceVideo}
        onAddReferenceMediaItem={addReferenceMediaItem}
        onRemoveReferenceMediaItem={removeReferenceMediaItem}
        onMoveReferenceMediaItem={moveReferenceMediaItem}
        onUpdateReferenceMediaVoice={updateReferenceMediaVoice}
        renderReferenceTokenButton={renderReferenceTokenButton}
      />
    )
  }

  const renderMaskEditor = () => {
    if (taskKind !== 'video_edit_local') return null

    return (
      <MaskEditorPanel
        isEditMode={isEditMode}
        existingMaskImageUrl={existingMaskImageUrl}
        sourceVideoWarnings={sourceVideoWarnings}
        sourceVideoPreviewDataUrl={sourceVideoPreviewDataUrl}
        sourceVideoMetadata={sourceVideoMetadata}
        maskTool={maskTool}
        maskBrushSize={maskBrushSize}
        maskEditorRef={maskEditorRef}
        maskHelp={getAssetHelp('mask_image')}
        onMaskToolChange={setMaskTool}
        onMaskBrushSizeChange={setMaskBrushSize}
        onMaskContentChange={setMaskHasContent}
      />
    )
  }

  return (
    <Modal
      open={open}
      onCancel={() => {
        resetLocalState(currentProfile?.default_values || {})
        onCancel()
      }}
      onOk={handleSubmit}
      confirmLoading={creating || maskUploading}
      okText={isEditMode ? '保存修改' : '创建任务'}
      cancelText="取消"
      width={980}
      title={isEditMode ? '编辑视频任务' : '新建视频任务'}
      destroyOnClose
    >
      {loading || !capabilities || !currentTaskInfo || !currentModel || !currentProfile ? (
        <div style={{ padding: '48px 0', textAlign: 'center' }}>
          <Spin />
        </div>
      ) : (
        <>
          <Tabs
            activeKey={taskKind}
            onChange={isEditMode ? undefined : handleTaskKindChange}
            items={capabilities.task_kinds.map((item) => ({
              key: item.id,
              label: item.label,
              disabled: isEditMode && item.id !== taskKind,
            }))}
          />

          <Row gutter={16}>
            <Col span={12}>
              <div style={{ marginBottom: 16 }}>
                <div style={{ marginBottom: 8 }}>任务名称</div>
                <Input value={taskName} onChange={(event) => setTaskName(event.target.value)} placeholder="留空自动生成" />
              </div>
            </Col>
            <Col span={12}>
              <div style={{ marginBottom: 16 }}>
                <div style={{ marginBottom: 8 }}>模型</div>
                <Select
                  style={{ width: '100%' }}
                  value={modelId}
                  onChange={handleModelChange}
                >
                  {currentTaskInfo.model_ids.map((id) => {
                    const model = capabilities.models[id]
                    return (
                      <Select.Option key={id} value={id}>
                        {model.name} {id}
                      </Select.Option>
                    )
                  })}
                </Select>
                <div style={{ marginTop: 8, fontSize: 12 }}>
                  <Tag color={getProviderTagColor(currentProvider)}>
                    {currentProvider.toUpperCase()}
                  </Tag>
                </div>
              </div>
            </Col>
          </Row>

          <div style={{ marginBottom: 16, padding: 12, borderRadius: 8, background: token.colorBgLayout }}>
            <Paragraph style={{ marginBottom: 4 }}>{currentTaskInfo.description}</Paragraph>
            {currentModel.description && <Text type="secondary">{currentModel.description}</Text>}
          </div>

          {currentProfile.input_roles.map((role) => (
            <div key={role}>{renderAssetSelector(role)}</div>
          ))}

          {renderReferenceCollections()}
          {renderMaskEditor()}

          <div style={{ marginBottom: 16 }}>
            <div style={{ marginBottom: 8 }}><VideoFieldLabel label="提示词" help={promptHelp} required={promptRequired} /></div>
            <TextArea
              ref={promptTextAreaRef}
              value={prompt}
              onChange={(event) => {
                setPrompt(event.target.value)
                updatePromptSelection(event.currentTarget)
              }}
              onClick={(event) => updatePromptSelection(event.currentTarget)}
              onKeyUp={(event) => updatePromptSelection(event.currentTarget)}
              onSelect={(event) => updatePromptSelection(event.currentTarget)}
              rows={3}
              placeholder={taskKind === 'video_edit_local'
                ? '描述需要替换或新增的局部内容'
                : taskKind === 'video_repainting'
                  ? '描述重绘后的画面和风格'
                  : '描述想要生成的视频内容'}
            />
            {promptLengthPolicy?.max_units && (
              <div
                style={{
                  marginTop: 6,
                  fontSize: 12,
                  color: promptLengthError ? token.colorError : token.colorTextSecondary,
                }}
              >
                {promptLengthUnits}/{promptLengthPolicy.max_units} 单位；上限 {promptLengthLimitLabel}
              </div>
            )}
          </div>

          {['wan'].includes(currentProvider) && !['video_edit_local', 'video_repainting'].includes(taskKind) && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ marginBottom: 8 }}>负面提示词</div>
              <TextArea
                value={negativePrompt}
                onChange={(event) => setNegativePrompt(event.target.value)}
                rows={2}
                placeholder="不希望出现的内容"
              />
            </div>
          )}

          {supportsMultiShot && currentProvider === 'kling' && taskKind === 'text_to_video' && (
            <>
              <Divider orientation="left">分镜模式</Divider>
              <div style={{ marginBottom: 16, padding: 12, borderRadius: 8, background: token.colorBgLayout }}>
                <Text type="secondary">多镜头能力由模型参数面板中的“叙事模式”控制。</Text>
              </div>
            </>
          )}

          {narrativeMode === 'multi_shot_customize' && currentProvider === 'kling' && taskKind === 'text_to_video' && (
            <div style={{ marginBottom: 16, padding: 12, borderRadius: 8, border: `1px solid ${token.colorBorder}` }}>
              <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontWeight: 500 }}>自定义分镜</span>
                <Button
                  icon={<PlusOutlined />}
                  disabled={multiShotSegments.length >= 6}
                  onClick={() => setMultiShotSegments((prev) => [
                    ...prev,
                    { id: `segment-${Date.now()}`, prompt: '', duration: 5 },
                  ])}
                >
                  添加分镜
                </Button>
              </div>
              <Space direction="vertical" style={{ width: '100%' }}>
                {multiShotSegments.map((segment, index) => (
                  <div key={segment.id} style={{ padding: 12, borderRadius: 8, background: token.colorBgLayout }}>
                    <div style={{ marginBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span>片段 {index + 1}</span>
                      <Button
                        type="text"
                        danger
                        disabled={multiShotSegments.length === 1}
                        icon={<DeleteOutlined />}
                        onClick={() => setMultiShotSegments((prev) => prev.filter((item) => item.id !== segment.id))}
                      />
                    </div>
                    <TextArea
                      value={segment.prompt}
                      rows={2}
                      onChange={(event) => setMultiShotSegments((prev) => prev.map((item) => item.id === segment.id ? { ...item, prompt: event.target.value } : item))}
                      placeholder="描述该分镜内容"
                    />
                    <InputNumber
                      style={{ width: '100%', marginTop: 8 }}
                      min={1}
                      max={16}
                      value={segment.duration}
                      addonAfter="秒"
                      onChange={(value) => setMultiShotSegments((prev) => prev.map((item) => item.id === segment.id ? { ...item, duration: value || 5 } : item))}
                    />
                  </div>
                ))}
              </Space>
            </div>
          )}

          <Divider orientation="left">模型参数</Divider>
          <DynamicModelForm
            modelInfo={buildProfileModel(getEffectiveProfile() || currentProfile, currentModel)}
            value={dynamicValues}
            onChange={setDynamicValues}
            columns={2}
          />

          <Row gutter={16}>
            <Col span={12}>
              <div style={{ marginTop: 16 }}>
                <div style={{ marginBottom: 8 }}>生成组数</div>
                <InputNumber style={{ width: '100%' }} min={1} max={groupCountMax} value={groupCount} onChange={(value) => setGroupCount(value || 1)} />
                {groupCountHelp && (
                  <div style={{ marginTop: 4, color: token.colorTextSecondary, fontSize: 12 }}>
                    {groupCountHelp}
                  </div>
                )}
              </div>
            </Col>
          </Row>

          {currentProvider === 'kling' && (
            <div style={{ marginTop: 16, padding: 12, borderRadius: 8, background: token.colorBgLayout }}>
              <Text type="secondary">
                可灵参考图和参考视频属于参考生成，不是像素级粘贴。复杂参考组合和主体 ID 属于高级能力，当前版本优先提供稳定的普通工作流。
              </Text>
            </div>
          )}

          {!currentTaskInfo.model_ids.length && (
            <Empty description="当前能力暂无可用模型" />
          )}

          <Collapse
            style={{ marginTop: 16 }}
            items={[
              {
                key: 'developer-mode',
                label: '开发者模式',
                children: (
                  <DeveloperPreviewPanel
                    isEditMode={isEditMode}
                    taskId={task?.id}
                    previewLoading={previewLoading}
                    previewPayload={previewPayload}
                  />
                ),
              },
            ]}
          />
        </>
      )}
    </Modal>
  )
}

export default CapabilityCreateModal
