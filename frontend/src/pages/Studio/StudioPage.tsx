import React, { useEffect, useState, useCallback, useRef, useMemo } from 'react'
import { useParams } from 'react-router-dom'
import { 
  Button, Modal, Form, Input, Empty, Spin, message, 
  Image, Space, Popconfirm, Tag, Select,
  InputNumber, Checkbox, Switch, theme, Alert, Collapse, Segmented
} from 'antd'
import { 
  PlusOutlined, DeleteOutlined, PictureOutlined,
  ExclamationCircleOutlined, ThunderboltOutlined, SaveOutlined,
  CheckCircleOutlined, CloseCircleOutlined, SyncOutlined,
  StarOutlined, StarFilled, FlagOutlined, FlagFilled, CheckOutlined, CloseOutlined,
  UpOutlined, DownOutlined
} from '@ant-design/icons'
import { 
  studioApi, galleryApi, charactersApi, scenesApi, propsApi, stylesApi, settingsApi,
  StudioTask, GalleryImage, Character, Scene, Prop, Style, HelpContent
} from '../../services/api'
import { useProjectStore } from '../../stores/projectStore'
import { useModelRegistry } from '../../hooks/useModelRegistry'
import HoverInfoPopover from '../../components/Help/HoverInfoPopover'
import BBoxEditor from './BBoxEditor'
import ColorPaletteEditor from './ColorPaletteEditor'
import {
  WAN27_MIN_RATIO,
  buildWan27QualityTemplateGroups,
  buildWan27SizeTemplates,
  getWan27CustomSizeLimits,
  matchWan27QualityTemplate,
  type ImageQualityLevel,
} from '../../utils/wan27Size'

const { TextArea } = Input

/**
 * 格式化图片尺寸显示，包含方向标签
 * @param size 尺寸字符串，如 "1920*1080" 或 { width, height, label }
 * @returns 格式化后的显示文本，如 "1920×1080 横向"
 */
const formatSizeLabel = (size: string | { width: number; height: number; label?: string }) => {
  if (typeof size === 'object' && size.label) {
    return size.label
  }
  
  let width: number, height: number
  if (typeof size === 'string') {
    const parts = size.split('*')
    width = parseInt(parts[0], 10)
    height = parseInt(parts[1], 10)
  } else {
    width = size.width
    height = size.height
  }
  
  const sizeStr = `${width}×${height}`
  if (width > height) {
    return `${sizeStr} 横向`
  } else if (width < height) {
    return `${sizeStr} 竖向`
  } else {
    return `${sizeStr} 正方形`
  }
}

const parseCustomSizeString = (size?: string | null) => {
  if (!size || !size.includes('*')) return null
  const [widthText, heightText] = size.split('*', 2)
  const width = Number(widthText)
  const height = Number(heightText)
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) return null
  return { width, height }
}

type ImageTaskKind = 'text_to_image' | 'image_edit' | 'interactive_edit' | 'sequential_generation'
type ImageSizeUiMode = 'preset_only' | 'preset_plus_custom_with_templates'
type ImageSizeTemplate = {
  ratio: string
  orientation: string
  width: number
  height: number
  label: string
}

const TASK_KIND_OPTIONS: Array<{ value: ImageTaskKind; label: string; help: string }> = [
  { value: 'text_to_image', label: '文生图', help: '只用提示词生成图片，不依赖输入图。' },
  { value: 'image_edit', label: '图像编辑', help: '基于 1 张或多张输入图做编辑、融合或参考生成。' },
  { value: 'interactive_edit', label: '交互式编辑', help: '为输入图框选目标区域，再用提示词指定替换或摆放。' },
  { value: 'sequential_generation', label: '组图生成', help: '生成同主题的连续组图，强调主体前后一致。' },
]

const WAN27_MODELS = new Set(['wan2.7-image-pro', 'wan2.7-image'])
const WAN27_MAX_CUSTOM_DIMENSION = 12000
const WAN25_T2I_MIN_TOTAL_PIXELS = 768 * 768
const WAN25_T2I_MAX_TOTAL_PIXELS = 1440 * 1440
const WAN25_I2I_MIN_TOTAL_PIXELS = 768 * 768
const WAN25_I2I_MAX_TOTAL_PIXELS = 1280 * 1280
const WAN25_MIN_RATIO = 1 / 4
const WAN25_MAX_RATIO = 4
const DEFAULT_MODEL_BY_TASK_KIND: Record<ImageTaskKind, string> = {
  text_to_image: 'wan2.7-image-pro',
  image_edit: 'wan2.7-image-pro',
  interactive_edit: 'wan2.7-image-pro',
  sequential_generation: 'wan2.7-image-pro',
}

const mergeHelpContent = (...helps: Array<HelpContent | string | null | undefined>): HelpContent | null => {
  const merged: HelpContent = {}
  for (const help of helps) {
    if (!help) continue
    const normalized: HelpContent = typeof help === 'string' ? { summary: help } : help
    if (normalized.summary) {
      merged.summary = merged.summary ? `${merged.summary} ${normalized.summary}` : normalized.summary
    }
    if (normalized.meaning) {
      merged.meaning = merged.meaning ? `${merged.meaning} ${normalized.meaning}` : normalized.meaning
    }
    ;(['limits', 'how_to_choose', 'examples', 'notes'] as const).forEach((key) => {
      const incoming = normalized[key]
      if (!incoming?.length) return
      const existing = merged[key] || []
      merged[key] = [...existing, ...incoming.filter(item => !existing.includes(item))]
    })
  }
  return Object.keys(merged).length ? merged : null
}

const getWan27DefaultN = (taskKind: ImageTaskKind) => (
  taskKind === 'sequential_generation' ? 12 : 4
)

const getImageCustomSizeLimits = (
  modelId: string,
  taskKind: ImageTaskKind,
  referenceCount: number,
) => {
  if (WAN27_MODELS.has(modelId)) {
    return getWan27CustomSizeLimits(modelId, taskKind, referenceCount)
  }
  if (modelId === 'wan2.5-t2i-preview') {
    return {
      minTotalPixels: WAN25_T2I_MIN_TOTAL_PIXELS,
      maxTotalPixels: WAN25_T2I_MAX_TOTAL_PIXELS,
      minRatio: WAN25_MIN_RATIO,
      maxRatio: WAN25_MAX_RATIO,
    }
  }
  if (modelId === 'wan2.5-i2i-preview') {
    return {
      minTotalPixels: WAN25_I2I_MIN_TOTAL_PIXELS,
      maxTotalPixels: WAN25_I2I_MAX_TOTAL_PIXELS,
      minRatio: WAN25_MIN_RATIO,
      maxRatio: WAN25_MAX_RATIO,
    }
  }
  return null
}


const normalizeBBoxList = (value: unknown): number[][][] => {
  if (!Array.isArray(value)) return []
  return value.map((imageBoxes) => {
    if (!Array.isArray(imageBoxes)) return []
    return imageBoxes
      .filter((box): box is number[] => Array.isArray(box) && box.length === 4)
      .map((box) => box.map((point) => Number(point)))
      .filter((box) => box.every((point) => Number.isFinite(point)))
  })
}

const bboxListHasBoxes = (value: unknown) => normalizeBBoxList(value).some((imageBoxes) => imageBoxes.length > 0)

const resolvePreferredBBoxList = (formValue: unknown, stateValue: unknown): number[][][] => {
  const normalizedForm = normalizeBBoxList(formValue)
  const normalizedState = normalizeBBoxList(stateValue)
  if (bboxListHasBoxes(normalizedForm)) return normalizedForm
  if (bboxListHasBoxes(normalizedState)) return normalizedState
  if (normalizedForm.length) return normalizedForm
  return normalizedState
}

const getTaskKindLabel = (taskKind?: string) => (
  TASK_KIND_OPTIONS.find(item => item.value === taskKind)?.label || '图像编辑'
)

const StudioPage = () => {
  const { token } = theme.useToken()
  const { projectId } = useParams<{ projectId: string }>()
  const { currentProject, fetchProject } = useProjectStore()
  
  const [tasks, setTasks] = useState<StudioTask[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedTask, setSelectedTask] = useState<StudioTask | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [selectedImages, setSelectedImages] = useState<Set<string>>(new Set())
  const [form] = Form.useForm()
  
  // 监听模型选择变化，用于动态显示对应模型的参数面板
  const watchedModel = Form.useWatch('model', form)
  const watchedTaskKind = Form.useWatch('task_kind', form)
  const watchedEnableInterleave = Form.useWatch('enable_interleave', form)
  const watchedReferences = Form.useWatch('references', form) || []
  const watchedEnableSequential = Form.useWatch('enable_sequential', form)
  const watchedPrompt = Form.useWatch('prompt', form)
  const watchedNegativePrompt = Form.useWatch('negative_prompt', form)
  const watchedSizeMode = Form.useWatch('size_mode', form)
  const watchedSizePreset = Form.useWatch('size_preset', form)
  const watchedCustomWidth = Form.useWatch('custom_width', form)
  const watchedCustomHeight = Form.useWatch('custom_height', form)
  const watchedN = Form.useWatch('n', form)
  const watchedGroupCount = Form.useWatch('group_count', form)
  const watchedPromptExtend = Form.useWatch('prompt_extend', form)
  const watchedWatermark = Form.useWatch('watermark', form)
  const watchedSeed = Form.useWatch('seed', form)
  const watchedMaxImages = Form.useWatch('max_images', form)
  const watchedStyleId = Form.useWatch('style_id', form)
  const watchedBBoxList = Form.useWatch('bbox_list', form) || []
  const watchedColorPalette = Form.useWatch('color_palette', form) || []
  
  // 自动保存防抖定时器
  const autoSaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const autoSavingRef = useRef(false)
  const previewTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // 轮询基础设施（参照 VideoStudioPage）
  const pollingRef = useRef<Set<string>>(new Set())
  const notifiedResultsRef = useRef<Set<string>>(new Set())
  
  // 素材选择
  const [characters, setCharacters] = useState<Character[]>([])
  const [scenes, setScenes] = useState<Scene[]>([])
  const [props, setProps] = useState<Prop[]>([])
  const [galleryImages, setGalleryImages] = useState<GalleryImage[]>([])
  const [styles, setStyles] = useState<Style[]>([])
  const [selectedStyleId, setSelectedStyleId] = useState<string | null>(null)
  const [imageTaskNotificationsEnabled, setImageTaskNotificationsEnabled] = useState(false)
  const [studioModelMeta, setStudioModelMeta] = useState<Record<string, any>>({})
  const [previewPayload, setPreviewPayload] = useState<{
    canonical_request: Record<string, any>
    provider_payload: Record<string, any>
    validation_warnings: string[]
  } | null>(null)
  const [wan27BBoxList, setWan27BBoxList] = useState<number[][][]>([])
  const [wan27SizeModeChoice, setWan27SizeModeChoice] = useState<'custom' | 'preset'>('custom')
  const [wan27RatioChoice, setWan27RatioChoice] = useState<string>('1:1')
  const [wan27QualityChoice, setWan27QualityChoice] = useState<ImageQualityLevel>('medium')
  
  // 使用统一的模型注册中心
  const { models: registryModels } = useModelRegistry()
  
  // 兼容旧代码：将 registryModels 格式化为旧的 availableModels 格式
  const availableModels = useMemo(() => {
    const result: Record<string, any> = {
      ...studioModelMeta,
    }
    Object.values(registryModels).forEach(model => {
      const current = result[model.id] || {}
      if (model.type === 'text_to_image' || model.type === 'image_to_image') {
        result[model.id] = {
          ...current,
          id: model.id,
          name: model.name,
          description: model.description,
          model_type: model.type,
          capabilities: model.capabilities,
          parameters: model.parameters,
          common_sizes: model.common_sizes || current.common_sizes || [],
          supported_task_kinds: current.supported_task_kinds,
          size_ui_mode: current.size_ui_mode,
        }
      }
    })
    return result
  }, [registryModels, studioModelMeta])
  
  const isMountedRef = useRef(true)

  const safeSetState = useCallback((setter: (v: any) => void, value: unknown) => {
    if (isMountedRef.current) {
      setter(value)
    }
  }, [])

  const getModelTaskKinds = useCallback((modelId?: string): ImageTaskKind[] => {
    if (!modelId) return ['text_to_image', 'image_edit']
    const declared = availableModels[modelId]?.supported_task_kinds
    if (declared?.length) return declared
    if (WAN27_MODELS.has(modelId)) {
      return ['text_to_image', 'image_edit', 'interactive_edit', 'sequential_generation']
    }
    if (modelId === 'wan2.6-image' || modelId === 'qwen-image-2.0-pro' || modelId === 'qwen-image-2.0') {
      return ['text_to_image', 'image_edit']
    }
    if (modelId === 'wan2.5-i2i-preview' || modelId.startsWith('qwen-image-edit')) {
      return ['image_edit']
    }
    return ['text_to_image']
  }, [availableModels])

  const getModelsForTaskKind = useCallback((taskKind?: ImageTaskKind) => {
    const kind = taskKind || 'text_to_image'
    return Object.values(availableModels).filter((model) => getModelTaskKinds(model.id).includes(kind))
  }, [availableModels, getModelTaskKinds])

  const getParamMeta = useCallback((modelId: string | undefined, paramName: string) => {
    if (!modelId) return null
    return availableModels[modelId]?.parameters?.find((param: any) => param.name === paramName) || null
  }, [availableModels])

  const renderFormLabel = useCallback((modelId: string | undefined, paramName: string, fallbackLabel: string, extraHelp?: any) => {
    const paramMeta = getParamMeta(modelId, paramName)
    return (
      <Space size={6}>
        <span>{paramMeta?.label || fallbackLabel}</span>
        <HoverInfoPopover
          title={paramMeta?.label || fallbackLabel}
          help={mergeHelpContent(paramMeta?.help || paramMeta?.description, extraHelp)}
        />
      </Space>
    )
  }, [getParamMeta])

  const selectedReferenceItems = useMemo(() => {
    return (watchedReferences as string[]).map((value: string) => {
      const [type, id] = value.split(':')
      const url = (() => {
        if (type === 'character') return characters.find(item => item.id === id)?.image_groups?.[characters.find(item => item.id === id)?.selected_group_index || 0]?.front_url
        if (type === 'scene') return scenes.find(item => item.id === id)?.image_groups?.[scenes.find(item => item.id === id)?.selected_group_index || 0]?.url
        if (type === 'prop') return props.find(item => item.id === id)?.image_groups?.[props.find(item => item.id === id)?.selected_group_index || 0]?.url
        if (type === 'gallery') return galleryImages.find(item => item.id === id)?.url
        if (type === 'style') return getStyleImageUrl(styles.find(item => item.id === id) as Style)
        return ''
      })()
      return { key: value, type, id, url: url || '' }
    })
  }, [characters, galleryImages, props, scenes, styles, watchedReferences])

  const activeModelId = (watchedModel || selectedTask?.model || '') as string
  const activeTaskKind = (watchedTaskKind || selectedTask?.task_kind || 'text_to_image') as ImageTaskKind
  const isWan27Model = WAN27_MODELS.has(activeModelId)
  const isWan25CustomSizeModel = activeModelId === 'wan2.5-t2i-preview' || activeModelId === 'wan2.5-i2i-preview'
  const activeSizeUiMode = (availableModels[activeModelId]?.size_ui_mode || (isWan27Model || isWan25CustomSizeModel ? 'preset_plus_custom_with_templates' : 'preset_only')) as ImageSizeUiMode
  const shouldShowReferences = activeTaskKind !== 'text_to_image'
  const shouldShowGroupCount = !isWan27Model
  const activeCustomSizeLimits = useMemo(
    () => getImageCustomSizeLimits(activeModelId, activeTaskKind, selectedReferenceItems.length),
    [activeModelId, activeTaskKind, selectedReferenceItems.length]
  )
  const sizeTemplateOptions = useMemo(
    () => activeSizeUiMode === 'preset_plus_custom_with_templates' ? buildWan27SizeTemplates(activeCustomSizeLimits) : [],
    [activeCustomSizeLimits, activeSizeUiMode]
  )
  const wan27PresetOptions = useMemo(() => {
    if (!isWan27Model) return []
    const allow4K = activeModelId === 'wan2.7-image-pro' && activeTaskKind === 'text_to_image' && selectedReferenceItems.length === 0
    const presets = allow4K ? ['1K', '2K', '4K'] : ['1K', '2K']
    const ratioLabel = selectedReferenceItems.length > 0 ? '跟随最后一张输入图比例' : '默认正方形'
    return presets.map((preset) => ({ value: preset, label: `${preset}（${ratioLabel}）` }))
  }, [activeModelId, activeTaskKind, isWan27Model, selectedReferenceItems.length])
  const wan27HasInputImages = isWan27Model && selectedReferenceItems.length > 0
  const wan27PreferredEntryMode = 'custom'
  const effectiveWan27EntryMode = isWan27Model
    ? wan27SizeModeChoice
    : ((watchedSizeMode as 'preset' | 'custom' | undefined) || wan27PreferredEntryMode)
  const wan27QualityGroups = useMemo(
    () => isWan27Model ? buildWan27QualityTemplateGroups(activeCustomSizeLimits) : [],
    [activeCustomSizeLimits, isWan27Model]
  )
  const activeWan27QualityGroup = useMemo(
    () => wan27QualityGroups.find((group) => group.ratio === wan27RatioChoice) || wan27QualityGroups[0] || null,
    [wan27QualityGroups, wan27RatioChoice]
  )
  const wan27SubmittedSize = useMemo(() => {
    if (!isWan27Model) return ''
    if (effectiveWan27EntryMode === 'custom') {
      const width = form.getFieldValue('custom_width')
      const height = form.getFieldValue('custom_height')
      return width && height ? `${width}*${height}` : '请填写宽高'
    }
    return form.getFieldValue('size_preset') || '2K'
  }, [effectiveWan27EntryMode, form, isWan27Model, watchedCustomHeight, watchedCustomWidth, watchedSizeMode, watchedSizePreset])
  const hasPreviousTaskRequest = useMemo(() => {
    if (!selectedTask) return false
    return (
      selectedTask.status !== 'pending' ||
      (selectedTask.images?.length || 0) > 0 ||
      (selectedTask.task_ids?.length || 0) > 0 ||
      (selectedTask.request_ids?.length || 0) > 0 ||
      !!selectedTask.last_task_id ||
      !!selectedTask.last_request_id ||
      Object.keys(selectedTask.provider_result_meta || {}).length > 0
    )
  }, [selectedTask])

  const validateCustomDimension = useCallback(async (_: any, _value: number | null | undefined) => {
    if (activeSizeUiMode !== 'preset_plus_custom_with_templates' || watchedSizeMode !== 'custom' || !activeCustomSizeLimits) return Promise.resolve()
    const width = Number(form.getFieldValue('custom_width') || 0)
    const height = Number(form.getFieldValue('custom_height') || 0)
    if (!width || !height) return Promise.resolve()
    const ratio = width / height
    const pixels = width * height
    const ratioText = activeCustomSizeLimits.minRatio === WAN27_MIN_RATIO ? '1:8 到 8:1' : '1:4 到 4:1'
    if (ratio < activeCustomSizeLimits.minRatio || ratio > activeCustomSizeLimits.maxRatio) {
      return Promise.reject(new Error(`自定义尺寸宽高比需在 ${ratioText} 之间`))
    }
    if (pixels < activeCustomSizeLimits.minTotalPixels || pixels > activeCustomSizeLimits.maxTotalPixels) {
      return Promise.reject(new Error(`当前模型和模式下，总像素需在 ${activeCustomSizeLimits.minTotalPixels} 到 ${activeCustomSizeLimits.maxTotalPixels} 之间`))
    }
    return Promise.resolve()
  }, [activeCustomSizeLimits, activeSizeUiMode, form, watchedSizeMode])

  const resolveWan27SizeDraft = useCallback((values: any) => {
    if (!WAN27_MODELS.has(values.model)) {
      return {
        sizeMode: values.size_mode,
        sizePreset: values.size_preset,
        customWidth: values.custom_width,
        customHeight: values.custom_height,
      }
    }
    const inferredSizeMode = values.size_mode || (
      values.custom_width && values.custom_height
        ? 'custom'
        : values.size_preset
          ? 'preset'
          : wan27SizeModeChoice
    )
    return {
      sizeMode: inferredSizeMode,
      sizePreset: inferredSizeMode === 'preset' ? (values.size_preset || '2K') : undefined,
      customWidth: inferredSizeMode === 'custom' ? values.custom_width : undefined,
      customHeight: inferredSizeMode === 'custom' ? values.custom_height : undefined,
    }
  }, [wan27SizeModeChoice])

  const computeEffectiveSize = useCallback((values: any) => {
    if (WAN27_MODELS.has(values.model)) {
      const resolved = resolveWan27SizeDraft(values)
      if (resolved.sizeMode === 'custom' && resolved.customWidth && resolved.customHeight) {
        return `${resolved.customWidth}*${resolved.customHeight}`
      }
      return resolved.sizePreset || '2K'
    }
    if (values.model === 'wan2.5-t2i-preview' || values.model === 'wan2.5-i2i-preview') {
      if (values.size_mode === 'custom' && values.custom_width && values.custom_height) {
        return `${values.custom_width}*${values.custom_height}`
      }
      return values.size_preset || values.size || '1024*1024'
    }
    return values.size
  }, [resolveWan27SizeDraft])

  const buildStudioRequestPayload = useCallback((values: any, options?: { prompt?: string; negativePrompt?: string }) => {
    const references = (values.references || []).map((ref: string) => {
      const [type, id] = ref.split(':')
      return { type, id }
    })
    const effectiveSize = computeEffectiveSize(values)
    const resolvedWan27Size = resolveWan27SizeDraft(values)
    const effectiveBBoxList = WAN27_MODELS.has(values.model)
      ? resolvePreferredBBoxList(values.bbox_list, wan27BBoxList)
      : normalizeBBoxList(values.bbox_list)
    return {
      name: values.name || '未命名任务',
      description: values.description,
      model: values.model,
      task_kind: values.task_kind,
      prompt: options?.prompt ?? values.prompt,
      negative_prompt: options?.negativePrompt ?? values.negative_prompt,
      n: values.n,
      group_count: WAN27_MODELS.has(values.model) ? 1 : values.group_count,
      size: WAN27_MODELS.has(values.model) ? null : (effectiveSize || undefined),
      prompt_extend: values.prompt_extend,
      watermark: values.watermark,
      seed: values.seed || undefined,
      enable_interleave: values.enable_interleave,
      max_images: values.max_images,
      enable_sequential: values.task_kind === 'sequential_generation',
      thinking_mode: values.thinking_mode ?? null,
      bbox_list: effectiveBBoxList,
      color_palette: values.color_palette || [],
      size_mode: resolvedWan27Size.sizeMode,
      size_preset: resolvedWan27Size.sizePreset,
      custom_width: resolvedWan27Size.customWidth,
      custom_height: resolvedWan27Size.customHeight,
      references,
    }
  }, [computeEffectiveSize, resolveWan27SizeDraft, wan27BBoxList])

  const requestPayloadPreview = useCallback(async () => {
    if (!projectId || !isModalOpen) return
    const values = form.getFieldsValue(true)
    let references = (values.references || []).map((ref: string) => {
      const [type, id] = ref.split(':')
      return { type, id }
    })
    let finalPrompt = values.prompt || ''
    let finalNegativePrompt = values.negative_prompt || ''
    const resolvedWan27Size = resolveWan27SizeDraft(values)
    const effectiveBBoxList = WAN27_MODELS.has(values.model)
      ? resolvePreferredBBoxList(values.bbox_list, wan27BBoxList)
      : normalizeBBoxList(values.bbox_list)
    const styleId = values.style_id || selectedStyleId
    if (styleId) {
      const style = styles.find(s => s.id === styleId)
      if (style) {
        if (style.style_type === 'image') {
          const styleImageUrl = getStyleImageUrl(style)
          if (styleImageUrl) {
            references = [...references, { type: 'style', id: style.id }]
            if (style.style_prompt) {
              finalPrompt = `${finalPrompt}。参考最后一张图的${style.name}风格，${style.style_prompt}`
            }
            if (style.negative_prompt) {
              finalNegativePrompt = finalNegativePrompt
                ? `${finalNegativePrompt}, ${style.negative_prompt}`
                : style.negative_prompt
            }
          }
        } else if (style.style_type === 'text' && style.text_style_content) {
          finalPrompt = `${finalPrompt}。风格要求：${style.text_style_content}`
        }
      }
    }
    try {
      const result = await studioApi.previewPayload({
        project_id: projectId,
        model: values.model,
        task_kind: values.task_kind,
        prompt: finalPrompt,
        negative_prompt: finalNegativePrompt,
        n: values.n,
        group_count: values.group_count,
        size: WAN27_MODELS.has(values.model) ? null : computeEffectiveSize(values),
        prompt_extend: values.prompt_extend,
        watermark: values.watermark,
        seed: values.seed ?? null,
        enable_interleave: values.enable_interleave,
        max_images: values.max_images,
        enable_sequential: values.enable_sequential,
        thinking_mode: values.thinking_mode,
        bbox_list: effectiveBBoxList,
        color_palette: values.color_palette,
        size_mode: resolvedWan27Size.sizeMode,
        size_preset: resolvedWan27Size.sizePreset,
        custom_width: resolvedWan27Size.customWidth,
        custom_height: resolvedWan27Size.customHeight,
        references,
      })
      if (isMountedRef.current) {
        setPreviewPayload(result)
      }
    } catch {
      if (isMountedRef.current) {
        setPreviewPayload(null)
      }
    }
  }, [computeEffectiveSize, form, isModalOpen, projectId, resolveWan27SizeDraft, selectedStyleId, styles, wan27BBoxList])

  useEffect(() => {
    isMountedRef.current = true
    return () => {
      isMountedRef.current = false
      pollingRef.current.clear()
    }
  }, [])

  const maybeNotifyTaskFinished = useCallback((task: StudioTask) => {
    if (!imageTaskNotificationsEnabled) return
    if (typeof window === 'undefined' || !('Notification' in window)) return
    if (Notification.permission !== 'granted') return
    const dedupeKey = `${task.id}:${task.status}`
    if (notifiedResultsRef.current.has(dedupeKey)) return
    notifiedResultsRef.current.add(dedupeKey)
    const title = task.status === 'completed' ? '图片任务已完成' : '图片任务失败'
    const body = task.status === 'completed'
      ? `${task.name || '未命名任务'} 已生成完成`
      : `${task.name || '未命名任务'} 失败：${task.error_message || '未知错误'}`
    try {
      const notification = new Notification(title, { body, tag: dedupeKey })
      notification.onclick = () => window.focus()
    } catch {
      // ignore
    }
  }, [imageTaskNotificationsEnabled])

  const startPolling = useCallback((taskId: string) => {
    if (pollingRef.current.has(taskId)) return
    pollingRef.current.add(taskId)

    const poll = async () => {
      if (!pollingRef.current.has(taskId) || !isMountedRef.current) return

      try {
        const updatedTask = await studioApi.get(taskId)
        if (!isMountedRef.current) return

        setTasks(prev => prev.map(t => t.id === taskId ? updatedTask : t))
        setSelectedTask(prev => prev?.id === taskId ? updatedTask : prev)

        if (updatedTask.status === 'completed' || updatedTask.status === 'failed') {
          pollingRef.current.delete(taskId)
          maybeNotifyTaskFinished(updatedTask)
          if (updatedTask.status === 'completed') {
            const validCount = updatedTask.images?.filter((img: any) => img.url).length || 0
            if (updatedTask.error_message) {
              message.warning(updatedTask.error_message)
            } else {
              message.success(`图片生成完成（${validCount} 张）`)
            }
          } else {
            message.error(`生成失败: ${updatedTask.error_message || '未知错误'}`)
          }
        } else {
          setTimeout(poll, 3000)
        }
      } catch {
        pollingRef.current.delete(taskId)
      }
    }

    setTimeout(poll, 2000)
  }, [maybeNotifyTaskFinished])

  useEffect(() => {
    const loadData = async () => {
      if (!projectId) return
      safeSetState(setLoading, true)
      try {
        fetchProject(projectId).catch(() => {})
        
        const [tasksRes, charactersRes, scenesRes, propsRes, galleryRes, stylesRes, settingsRes, modelsRes] = await Promise.all([
          studioApi.list(projectId),
          charactersApi.list(projectId),
          scenesApi.list(projectId),
          propsApi.list(projectId),
          galleryApi.list(projectId),
          stylesApi.list(projectId),
          settingsApi.getSettings(),
          studioApi.getAvailableModels(),
        ])
        
        safeSetState(setTasks, tasksRes.tasks)
        safeSetState(setCharacters, charactersRes.characters)
        safeSetState(setScenes, scenesRes.scenes)
        safeSetState(setProps, propsRes.props)
        safeSetState(setGalleryImages, galleryRes.images)
        safeSetState(setStyles, stylesRes.styles)
        safeSetState(setStudioModelMeta, modelsRes.models || {})
        setImageTaskNotificationsEnabled(!!settingsRes.image_task_notifications_enabled)

        // 恢复正在生成中的任务的轮询
        tasksRes.tasks.forEach((task: StudioTask) => {
          if (task.status === 'generating') {
            startPolling(task.id)
          }
        })
      } catch (error) {
        message.error('加载失败')
      } finally {
        safeSetState(setLoading, false)
      }
    }
    loadData()
  }, [projectId, fetchProject, safeSetState, startPolling])

  useEffect(() => {
    if (!isModalOpen) return
    if (previewTimerRef.current) {
      clearTimeout(previewTimerRef.current)
    }
    previewTimerRef.current = setTimeout(() => {
      requestPayloadPreview()
    }, 350)
    return () => {
      if (previewTimerRef.current) {
        clearTimeout(previewTimerRef.current)
      }
    }
  }, [
    isModalOpen,
    requestPayloadPreview,
    watchedModel,
    watchedTaskKind,
    watchedPrompt,
    watchedNegativePrompt,
    watchedN,
    watchedGroupCount,
    watchedPromptExtend,
    watchedWatermark,
    watchedSeed,
    watchedEnableInterleave,
    watchedMaxImages,
    watchedEnableSequential,
    watchedSizeMode,
    watchedSizePreset,
    watchedCustomWidth,
    watchedCustomHeight,
    watchedReferences,
    watchedStyleId,
    watchedBBoxList,
    watchedColorPalette,
  ])

  useEffect(() => {
    if (!isModalOpen) return
    const compatibleModels = getModelsForTaskKind(activeTaskKind)
    if (!compatibleModels.length) return
    const currentModel = form.getFieldValue('model')
    const isCompatible = compatibleModels.some(model => model.id === currentModel)
    if (isCompatible) return
    const preferredModel = compatibleModels.find(model => model.id === DEFAULT_MODEL_BY_TASK_KIND[activeTaskKind]) || compatibleModels[0]
    form.setFieldValue('model', preferredModel.id)
  }, [activeTaskKind, form, getModelsForTaskKind, isModalOpen])

  useEffect(() => {
    if (!isModalOpen) return
    if (activeTaskKind === 'text_to_image') {
      const refs = form.getFieldValue('references') || []
      if (refs.length) {
        form.setFieldValue('references', [])
      }
    }
  }, [activeTaskKind, form, isModalOpen])

  useEffect(() => {
    if (!isModalOpen) return
    if (!isWan27Model) {
      setWan27BBoxList([])
      const resetValues: Record<string, any> = {
        enable_sequential: false,
        thinking_mode: null,
        bbox_list: [],
        color_palette: [],
      }
      if (activeSizeUiMode !== 'preset_plus_custom_with_templates') {
        resetValues.size_mode = null
        resetValues.size_preset = null
        resetValues.custom_width = null
        resetValues.custom_height = null
      } else if (!form.getFieldValue('size_mode')) {
        resetValues.size_mode = 'preset'
        resetValues.size_preset = form.getFieldValue('size_preset') || '1024*1024'
      }
      form.setFieldsValue(resetValues)
      return
    }
    if (form.getFieldValue('group_count') !== 1) {
      form.setFieldValue('group_count', 1)
    }
    if (!form.getFieldValue('size_mode')) {
      form.setFieldsValue({ size_mode: wan27PreferredEntryMode, size: undefined })
      setWan27SizeModeChoice(wan27PreferredEntryMode)
    }
    if (form.getFieldValue('size_mode') === 'preset' && !form.getFieldValue('size_preset')) {
      form.setFieldValue('size_preset', '2K')
    }
    if (form.getFieldValue('size_mode') === 'custom') {
      const width = form.getFieldValue('custom_width')
      const height = form.getFieldValue('custom_height')
      if (!width || !height) {
        const preferredGroup = wan27QualityGroups.find((group) => group.ratio === '1:1') || wan27QualityGroups[0]
        const preferredOption = preferredGroup?.options.find((item) => item.quality === 'medium') || preferredGroup?.options[0]
        if (preferredOption) {
          form.setFieldsValue({
            custom_width: preferredOption.width,
            custom_height: preferredOption.height,
            size_preset: undefined,
          })
          setWan27RatioChoice(preferredGroup.ratio)
          setWan27QualityChoice(preferredOption.quality)
        }
      }
    }
    form.setFieldValue('enable_sequential', activeTaskKind === 'sequential_generation')
    if (activeTaskKind !== 'text_to_image' || selectedReferenceItems.length > 0) {
      form.setFieldValue('thinking_mode', null)
    } else if (form.getFieldValue('thinking_mode') === undefined) {
      form.setFieldValue('thinking_mode', true)
    }
    if (activeTaskKind !== 'interactive_edit') {
      if (wan27BBoxList.length > 0) {
        message.info('已清除交互式框选区域，因为当前任务类型不再是交互式编辑')
      }
      setWan27BBoxList([])
      form.setFieldValue('bbox_list', [])
    }
    if (activeTaskKind === 'sequential_generation') {
      form.setFieldValue('color_palette', [])
      if ((form.getFieldValue('n') || 0) > 12 || !form.getFieldValue('n')) {
        form.setFieldValue('n', getWan27DefaultN('sequential_generation'))
      }
    } else if ((form.getFieldValue('n') || 0) > 4 || !form.getFieldValue('n')) {
      form.setFieldValue('n', getWan27DefaultN(activeTaskKind))
    }
  }, [activeSizeUiMode, activeTaskKind, form, isModalOpen, isWan27Model, selectedReferenceItems.length, wan27BBoxList.length, wan27PreferredEntryMode, wan27QualityGroups])

  useEffect(() => {
    if (!isModalOpen || !isWan27Model || activeTaskKind !== 'interactive_edit') return
    const currentBoxes = wan27BBoxList
    const targetLength = selectedReferenceItems.length
    if (currentBoxes.length === targetLength) return
    const nextBoxes = Array.from({ length: targetLength }, (_, index) => currentBoxes[index] || [])
    if (currentBoxes.length > targetLength) {
      message.info('输入图片数量已变化，已移除超出范围的框选区域')
    }
    setWan27BBoxList(nextBoxes)
    form.setFieldValue('bbox_list', nextBoxes)
  }, [activeTaskKind, form, isModalOpen, isWan27Model, selectedReferenceItems.length, wan27BBoxList])

  useEffect(() => {
    if (!isModalOpen || !isWan27Model) return
    if (!wan27QualityGroups.length) return
    const currentMode = form.getFieldValue('size_mode')
    if (currentMode !== 'custom') {
      const firstGroup = wan27QualityGroups[0]
      if (firstGroup) {
        setWan27RatioChoice(firstGroup.ratio)
        setWan27QualityChoice(firstGroup.options.find((item) => item.quality === 'medium')?.quality || firstGroup.options[0].quality)
      }
      return
    }
    const width = Number(form.getFieldValue('custom_width') || 0)
    const height = Number(form.getFieldValue('custom_height') || 0)
    if (!width || !height) return
    const bestMatch = matchWan27QualityTemplate(wan27QualityGroups, width, height)
    if (bestMatch) {
      setWan27RatioChoice(bestMatch.ratio)
      setWan27QualityChoice(bestMatch.quality)
    }
  }, [form, isModalOpen, isWan27Model, wan27QualityGroups, watchedSizeMode])

  useEffect(() => {
    if (!isModalOpen) return
    if (!(activeModelId || '').startsWith('qwen-image-edit')) return
    if (Number(watchedN || 1) <= 1) return
    if (!form.getFieldValue('size')) return
    form.setFieldValue('size', '')
  }, [activeModelId, form, isModalOpen, watchedN])

  // 新建模式状态
  const [isCreating, setIsCreating] = useState(false)
  
  const openCreateModal = () => {
    // 直接使用统一的弹窗，设置为新建模式
    setIsCreating(true)
    setSelectedTask(null)
    setSelectedImages(new Set())
    setPreviewPayload(null)
    setWan27BBoxList([])
    setWan27SizeModeChoice('custom')
    form.resetFields()
    form.setFieldsValue({
      name: '',
      description: '',
      task_kind: 'text_to_image',
      model: 'wan2.7-image-pro',
      prompt: '',
      negative_prompt: '',
      n: getWan27DefaultN('text_to_image'),
      group_count: 1,
      prompt_extend: true,
      watermark: false,
      enable_interleave: false,
      max_images: 5,
      enable_sequential: false,
      thinking_mode: true,
      bbox_list: [],
      color_palette: [],
      size_mode: 'custom',
      size_preset: undefined,
      custom_width: undefined,
      custom_height: undefined,
      references: [],
      style_id: null,
    })
    setSelectedStyleId(null)
    setIsModalOpen(true)
  }

  const createAndGenerate = async () => {
    if (!projectId) return
    let createdTask: StudioTask | null = null
    try {
      await form.validateFields()
      const values = form.getFieldsValue(true)
      
      // 解析选中的素材
      let references = (values.references || []).map((ref: string) => {
        const [type, id] = ref.split(':')
        return { type, id }
      })
      
      // 处理风格选择
      let finalPrompt = values.prompt || ''
      let finalNegativePrompt = values.negative_prompt || ''
      
      const styleId = values.style_id || selectedStyleId
      if (styleId) {
        const style = styles.find(s => s.id === styleId)
        if (style) {
          if (style.style_type === 'image') {
            const styleImageUrl = getStyleImageUrl(style)
            if (styleImageUrl) {
              references = [...references, { type: 'style', id: style.id }]
              if (style.style_prompt) {
                finalPrompt = `${finalPrompt}。参考最后一张图的${style.name}风格，${style.style_prompt}`
              }
              if (style.negative_prompt) {
                finalNegativePrompt = finalNegativePrompt 
                  ? `${finalNegativePrompt}, ${style.negative_prompt}` 
                  : style.negative_prompt
              }
            }
          } else if (style.style_type === 'text') {
            if (style.text_style_content) {
              finalPrompt = `${finalPrompt}。风格要求：${style.text_style_content}`
            }
          }
        }
      }
      
      // 前端参考图验证
      const isTextToImage = values.task_kind === 'text_to_image'
      const isWan26Image = values.model === 'wan2.6-image'
      const isQwenEditModel = values.model?.startsWith('qwen-image-edit')
      const isQwenImage2 = values.model === 'qwen-image-2.0-pro' || values.model === 'qwen-image-2.0'
      const isWan27 = WAN27_MODELS.has(values.model)
      const refCount = references.length
      const effectiveBBoxList = isWan27
        ? resolvePreferredBBoxList(values.bbox_list, wan27BBoxList)
        : normalizeBBoxList(values.bbox_list)
      
      if (isQwenEditModel && refCount === 0) {
        message.warning('qwen-image-edit 系列模型需要 1-3 张参考图作为输入')
        return
      }
      const needsReferences = !isTextToImage && !isWan26Image && !isQwenEditModel && !isQwenImage2
      if (needsReferences && refCount === 0) {
        message.warning('请先添加参考素材')
        return
      }
      if (isWan26Image && !(values.enable_interleave || false) && refCount === 0) {
        message.warning('参考图模式下必须选择至少1张参考图，或开启图文混合模式')
        return
      }
      if (isWan27 && values.task_kind === 'interactive_edit') {
        if (refCount === 0) {
          message.warning('交互式编辑至少需要 1 张输入图片')
          return
        }
        if (!effectiveBBoxList || effectiveBBoxList.length !== refCount) {
          message.warning('请为交互式编辑中的每张输入图准备对应的框选区域')
          return
        }
      }
      
      // 1. 创建任务
      const basePayload = buildStudioRequestPayload(values, {
        prompt: finalPrompt,
        negativePrompt: finalNegativePrompt,
      })
      const task = await studioApi.create({
        project_id: projectId,
        ...basePayload,
      })
      safeSetState(setTasks, (prev: StudioTask[]) => [task, ...prev])
      createdTask = task
      setSelectedStyleId(null)
      setIsCreating(false)
      setSelectedTask(task)
      
      // 2. 启动后台生成（立即返回）
      const generateParams: any = {
        ...basePayload,
        prompt: finalPrompt,
        negative_prompt: finalNegativePrompt,
      }
      
      if (isTextToImage && !isWan27) {
        generateParams.prompt_extend = values.prompt_extend !== false
        generateParams.watermark = values.watermark || false
        if (values.seed) generateParams.seed = values.seed
        if (values.size) generateParams.size = values.size
      }
      if (isWan26Image) {
        const enableInterleave = values.enable_interleave || false
        generateParams.prompt_extend = enableInterleave ? false : (values.prompt_extend !== false)
        generateParams.watermark = values.watermark || false
        if (values.seed) generateParams.seed = values.seed
        if (values.size) generateParams.size = values.size
        generateParams.enable_interleave = enableInterleave
        if (enableInterleave) {
          generateParams.n = 1
          generateParams.max_images = values.max_images || 5
        }
      }
      if (isQwenEditModel) {
        if (values.size) generateParams.size = values.size
        generateParams.prompt_extend = values.prompt_extend !== false
        generateParams.watermark = values.watermark || false
        if (values.seed) generateParams.seed = values.seed
        if (values.negative_prompt) generateParams.negative_prompt = values.negative_prompt
      }
      if (isQwenImage2) {
        if (values.size) generateParams.size = values.size
        generateParams.prompt_extend = values.prompt_extend !== false
        generateParams.watermark = values.watermark || false
        if (values.seed) generateParams.seed = values.seed
        if (values.negative_prompt) generateParams.negative_prompt = values.negative_prompt
        generateParams.n = values.n || 1
      }
      
      const result = await studioApi.generate(task.id, generateParams)
      // 后端立即返回 generating 状态，启动轮询跟踪进度
      safeSetState(setTasks, (prev: StudioTask[]) => prev.map(t => t.id === result.task.id ? result.task : t))
      setSelectedTask(result.task)
      startPolling(task.id)
      message.info('已开始生成，可继续创建其他任务')
    } catch (error: any) {
      message.error(error?.message || '生成失败')
      if (createdTask) {
        try {
          const updatedTask = await studioApi.get(createdTask.id)
          safeSetState(setTasks, (prev: StudioTask[]) => prev.map(t => t.id === updatedTask.id ? updatedTask : t))
          setSelectedTask(updatedTask)
        } catch {}
      }
    }
  }

  const openTaskModal = (task: StudioTask) => {
    setIsCreating(false)  // 编辑模式
    setSelectedTask(task)
    setSelectedImages(new Set())
    setSelectedStyleId(null)
    setPreviewPayload(null)
    const restoredBBoxList = resolvePreferredBBoxList(task.bbox_list, task.provider_payload_snapshot?.parameters?.bbox_list)
    const restoredCustomSize = parseCustomSizeString(task.size)
    const restoredSizeMode = task.size_mode || (restoredCustomSize ? 'custom' : (task.size_preset || (task.size && !task.size.includes('*')) ? 'preset' : null))
    setWan27SizeModeChoice(restoredSizeMode === 'preset' ? 'preset' : 'custom')
    setWan27BBoxList(restoredBBoxList)
    form.setFieldsValue({
      name: task.name,
      description: task.description,
      task_kind: task.task_kind || getModelTaskKinds(task.model)[0],
      model: task.model,
      prompt: task.prompt,
      negative_prompt: task.negative_prompt,
      n: task.n || getWan27DefaultN((task.task_kind || getModelTaskKinds(task.model)[0]) as ImageTaskKind),
      group_count: task.group_count || 1,
      // 加载保存的高级参数（如果有），否则使用默认值
      size: task.size || '',
      prompt_extend: task.prompt_extend !== undefined ? task.prompt_extend : true,
      watermark: task.watermark !== undefined ? task.watermark : false,
      seed: task.seed || undefined,
      // wan2.6-image 专用参数
      enable_interleave: task.enable_interleave || false,
      max_images: task.max_images || 5,
      enable_sequential: task.enable_sequential || false,
      thinking_mode: task.thinking_mode ?? null,
      bbox_list: restoredBBoxList,
      color_palette: task.color_palette || [],
      size_mode: restoredSizeMode,
      size_preset: task.size_preset || (task.size && !task.size.includes('*') ? task.size : undefined),
      custom_width: task.custom_width || restoredCustomSize?.width || undefined,
      custom_height: task.custom_height || restoredCustomSize?.height || undefined,
      // 还原参考素材选择（编辑时显示）
      references: task.references?.map(ref => `${ref.type}:${ref.id}`) || [],
    })
    setIsModalOpen(true)
  }

  const autoSaveTask = useCallback(async () => {
    if (!selectedTask || isCreating || autoSavingRef.current) return
    autoSavingRef.current = true
    try {
      const values = form.getFieldsValue(true)
      const updated = await studioApi.update(selectedTask.id, buildStudioRequestPayload(values))
      safeSetState(setTasks, (prev: StudioTask[]) => prev.map(t => t.id === updated.id ? updated : t))
      setSelectedTask(updated)
    } catch {
      // 静默失败，不打扰用户
    } finally {
      autoSavingRef.current = false
    }
  }, [selectedTask, isCreating, form, safeSetState, buildStudioRequestPayload])

  const queueStudioAutoSave = useCallback(() => {
    if (isCreating || !selectedTask) return
    if (autoSaveTimerRef.current) {
      clearTimeout(autoSaveTimerRef.current)
    }
    autoSaveTimerRef.current = setTimeout(() => {
      autoSaveTask()
    }, 800)
  }, [autoSaveTask, isCreating, selectedTask])

  const applyCustomSizeTemplate = useCallback((template: ImageSizeTemplate) => {
    form.setFieldsValue({
      size_mode: 'custom',
      size_preset: undefined,
      custom_width: template.width,
      custom_height: template.height,
    })
    queueStudioAutoSave()
  }, [form, queueStudioAutoSave])

  const applyWan27QualityTemplate = useCallback((ratio: string, quality: ImageQualityLevel) => {
    const group = wan27QualityGroups.find((item) => item.ratio === ratio) || wan27QualityGroups[0]
    const option = group?.options.find((item) => item.quality === quality) || group?.options[group.options.length - 1]
    if (!option) return
    setWan27RatioChoice(group.ratio)
    setWan27QualityChoice(option.quality)
    applyCustomSizeTemplate(option)
  }, [applyCustomSizeTemplate, wan27QualityGroups])

  const switchWan27SizeMode = useCallback((mode: 'preset' | 'custom') => {
    setWan27SizeModeChoice(mode)
    if (mode === 'preset') {
      form.setFieldsValue({
        size_mode: 'preset',
        size_preset: form.getFieldValue('size_preset') || '2K',
        size: undefined,
        custom_width: undefined,
        custom_height: undefined,
      })
      queueStudioAutoSave()
      return
    }
    form.setFieldsValue({ size_mode: 'custom', size: undefined, size_preset: undefined })
    const preferredGroup = wan27QualityGroups.find((group) => group.ratio === wan27RatioChoice) || wan27QualityGroups[0]
    const preferredOption =
      preferredGroup?.options.find((item) => item.quality === wan27QualityChoice) ||
      preferredGroup?.options.find((item) => item.quality === 'medium') ||
      preferredGroup?.options[0]
    if (preferredGroup && preferredOption) {
      applyWan27QualityTemplate(preferredGroup.ratio, preferredOption.quality)
    } else {
      queueStudioAutoSave()
    }
  }, [applyWan27QualityTemplate, form, queueStudioAutoSave, wan27QualityChoice, wan27QualityGroups, wan27RatioChoice])

  const syncWan27BBoxList = useCallback((nextBoxes: number[][][]) => {
    setWan27BBoxList(nextBoxes)
    form.setFieldValue('bbox_list', nextBoxes)
    queueStudioAutoSave()
  }, [form, queueStudioAutoSave])

  const moveReference = useCallback((index: number, direction: -1 | 1) => {
    const current = [...(form.getFieldValue('references') || [])]
    const targetIndex = index + direction
    if (targetIndex < 0 || targetIndex >= current.length) return
    const [item] = current.splice(index, 1)
    current.splice(targetIndex, 0, item)
    form.setFieldValue('references', current)
    if (isWan27Model && activeTaskKind === 'interactive_edit') {
      const currentBoxes = [...wan27BBoxList]
      const [boxGroup] = currentBoxes.splice(index, 1)
      currentBoxes.splice(targetIndex, 0, boxGroup || [])
      syncWan27BBoxList(currentBoxes)
    } else {
      queueStudioAutoSave()
    }
  }, [activeTaskKind, form, isWan27Model, queueStudioAutoSave, syncWan27BBoxList, wan27BBoxList])
  
  const handleFormValuesChange = useCallback((changedValues: any) => {
    if (changedValues.task_kind) {
      const nextKind = changedValues.task_kind as ImageTaskKind
      const compatibleModels = getModelsForTaskKind(nextKind)
      const currentModel = form.getFieldValue('model')
      if (WAN27_MODELS.has(currentModel)) {
        const currentN = form.getFieldValue('n')
        if (nextKind === 'sequential_generation') {
          form.setFieldValue('n', getWan27DefaultN(nextKind))
        } else if (!currentN || currentN > 4 || currentN === 12) {
          form.setFieldValue('n', getWan27DefaultN(nextKind))
        }
      }
      if (!compatibleModels.some(model => model.id === currentModel)) {
        const preferredModel = compatibleModels.find(model => model.id === DEFAULT_MODEL_BY_TASK_KIND[nextKind]) || compatibleModels[0]
        if (preferredModel) {
          form.setFieldValue('model', preferredModel.id)
        }
      }
    }

    // 模型切换时自动调整关联参数
    if (changedValues.model) {
      const model = changedValues.model
      if (WAN27_MODELS.has(model)) {
        setWan27SizeModeChoice('custom')
        form.setFieldsValue({
          group_count: 1,
          size: undefined,
          size_mode: 'custom',
          size_preset: undefined,
          custom_width: form.getFieldValue('custom_width'),
          custom_height: form.getFieldValue('custom_height'),
          n: getWan27DefaultN(activeTaskKind),
          watermark: false,
        })
      } else if (model === 'qwen-image-max' || model === 'qwen-image-plus') {
        form.setFieldsValue({ n: 1, size: '1664*928', watermark: false })
      } else if (model === 'wan2.6-image') {
        form.setFieldsValue({ n: 4, size: '1280*1280', watermark: false })
      } else if (model === 'wan2.6-t2i') {
        form.setFieldsValue({ n: 4, size: '1280*1280', watermark: false })
      } else if (model === 'wan2.5-t2i-preview') {
        form.setFieldsValue({
          n: 1,
          size: undefined,
          size_mode: 'preset',
          size_preset: '1024*1024',
          custom_width: undefined,
          custom_height: undefined,
          watermark: false,
        })
      } else if (model === 'wan2.5-i2i-preview') {
        form.setFieldsValue({
          n: 1,
          size: undefined,
          size_mode: 'preset',
          size_preset: '1024*1024',
          custom_width: undefined,
          custom_height: undefined,
          watermark: false,
        })
      } else if (model?.startsWith('qwen-image-edit')) {
        form.setFieldsValue({
          n: 1,
          size: '',
          size_mode: undefined,
          size_preset: undefined,
          custom_width: undefined,
          custom_height: undefined,
          watermark: false,
        })
      } else if (model === 'qwen-image-2.0-pro' || model === 'qwen-image-2.0') {
        const currentTaskKind = form.getFieldValue('task_kind')
        const hasReferences = (form.getFieldValue('references') || []).length > 0
        form.setFieldsValue({
          n: 1,
          size: currentTaskKind === 'image_edit' || hasReferences ? '' : '1024*1024',
          size_mode: undefined,
          size_preset: undefined,
          custom_width: undefined,
          custom_height: undefined,
          watermark: false,
        })
      } else {
        form.setFieldsValue({
          size_mode: undefined,
          size_preset: undefined,
          custom_width: undefined,
          custom_height: undefined,
        })
      }
    }

    if (changedValues.references) {
      const refs = changedValues.references || []
      const currentBoxes = wan27BBoxList
      if (activeTaskKind === 'interactive_edit' && WAN27_MODELS.has(form.getFieldValue('model'))) {
        syncWan27BBoxList(Array.from({ length: refs.length }, (_, index) => currentBoxes[index] || []))
      } else {
        queueStudioAutoSave()
      }
    }

    if (changedValues.size_mode === 'preset') {
      form.setFieldsValue({ size: undefined, custom_width: undefined, custom_height: undefined })
    }
    if (changedValues.size_mode === 'custom') {
      form.setFieldsValue({ size: undefined, size_preset: undefined })
    }
    if ((changedValues.n !== undefined || changedValues.model) && (form.getFieldValue('model') || '').startsWith('qwen-image-edit')) {
      const nextN = Number(form.getFieldValue('n') || 1)
      if (nextN > 1 && form.getFieldValue('size')) {
        form.setFieldValue('size', '')
      }
    }
    
    if (isCreating || !selectedTask) return
    if (autoSaveTimerRef.current) {
      clearTimeout(autoSaveTimerRef.current)
    }
    autoSaveTimerRef.current = setTimeout(() => {
      autoSaveTask()
    }, 800)
  }, [activeTaskKind, autoSaveTask, form, getModelsForTaskKind, isCreating, queueStudioAutoSave, selectedTask, syncWan27BBoxList, wan27BBoxList])
  
  useEffect(() => {
    return () => {
      if (autoSaveTimerRef.current) {
        clearTimeout(autoSaveTimerRef.current)
      }
    }
  }, [])

  const generateImages = async () => {
    if (!selectedTask) return
    
    const values = form.getFieldsValue(true)
    const isTextToImage = values.task_kind === 'text_to_image'
    const isWan26Image = values.model === 'wan2.6-image'
    const isQwenEditModel = values.model?.startsWith('qwen-image-edit')
    const isQwenImage2 = values.model === 'qwen-image-2.0-pro' || values.model === 'qwen-image-2.0'
    const isWan27 = WAN27_MODELS.has(values.model)
    const effectiveBBoxList = isWan27
      ? resolvePreferredBBoxList(values.bbox_list, wan27BBoxList)
      : normalizeBBoxList(values.bbox_list)
    
    // 从表单中解析参考图
    const formReferences = (values.references || []).map((ref: string) => {
      const [type, id] = ref.split(':')
      return { type, id }
    })
    const refCount = formReferences.length
    
    // 图生图模型需要参考素材（wan2.6-image、qwen-edit、qwen-image-2.0 有各自的验证）
    const needsReferences = !isTextToImage && !isWan26Image && !isQwenEditModel && !isQwenImage2
    if (needsReferences && refCount === 0) {
      message.warning('请先添加参考素材')
      return
    }
    
    // 验证 wan2.6-image 的参考图数量
    if (isWan26Image) {
      const enableInterleave = values.enable_interleave || false
      if (enableInterleave) {
        // 图文混合模式：最多1张参考图
        if (refCount > 1) {
          message.warning('图文混合模式下最多只能添加1张参考图')
          return
        }
      } else {
        // 参考图模式：必须有1-4张参考图
        if (refCount === 0) {
          message.warning('参考图模式下必须选择至少1张参考图，或开启图文混合模式')
          return
        }
        if (refCount > 4) {
          message.warning('参考图模式下最多只能添加4张参考图')
          return
        }
      }
    }
    
    // 验证 qwen-image-edit 系列的参数
    if (isQwenEditModel) {
      if (refCount === 0) {
        message.warning('qwen-image-edit 系列模型需要 1-3 张参考图作为输入')
        return
      }
      if (refCount > 3) {
        message.warning('qwen-image-edit 系列最多支持3张输入图片')
        return
      }
    }

    // 验证 qwen-image-2.0 系列参考图数量
    if (isQwenImage2 && refCount > 3) {
      message.warning('千问图像 2.0 最多支持3张输入图片')
      return
    }
    if (isWan27 && values.task_kind === 'interactive_edit') {
      if (refCount === 0) {
        message.warning('交互式编辑至少需要 1 张输入图片')
        return
      }
      if (!effectiveBBoxList || effectiveBBoxList.length !== refCount) {
        message.warning('请为交互式编辑中的每张输入图准备对应的框选区域')
        return
      }
    }
    
    // 生成前确保最新表单数据已保存（取消待执行的自动保存，立即保存一次）
    if (autoSaveTimerRef.current) {
      clearTimeout(autoSaveTimerRef.current)
      autoSaveTimerRef.current = null
    }
    try {
      await studioApi.update(selectedTask.id, buildStudioRequestPayload(values))
      const updatedTask = {
        ...selectedTask,
        ...buildStudioRequestPayload(values),
        references: formReferences.map((ref: any) => ({ ...ref })),
      }
      safeSetState(setTasks, (prev: StudioTask[]) => prev.map(t => t.id === selectedTask.id ? updatedTask : t))
      setSelectedTask(updatedTask)
    } catch (error) {
      console.error('保存任务失败:', error)
    }
    
    try {
      const generateParams: any = buildStudioRequestPayload(values)
      
      if (isTextToImage && !isWan27) {
        generateParams.prompt_extend = values.prompt_extend !== false
        generateParams.watermark = values.watermark || false
        if (values.seed) generateParams.seed = values.seed
        if (values.size) generateParams.size = values.size
      }
      
      if (isWan26Image) {
        const enableInterleave = values.enable_interleave || false
        generateParams.prompt_extend = enableInterleave ? false : (values.prompt_extend !== false)
        generateParams.watermark = values.watermark || false
        if (values.seed) generateParams.seed = values.seed
        if (values.size) generateParams.size = values.size
        generateParams.enable_interleave = enableInterleave
        if (enableInterleave) {
          generateParams.n = 1
          generateParams.max_images = values.max_images || 5
        }
      }
      
      if (isQwenEditModel) {
        if (values.size) generateParams.size = values.size
        generateParams.prompt_extend = values.prompt_extend !== false
        generateParams.watermark = values.watermark || false
        if (values.seed) generateParams.seed = values.seed
        if (values.negative_prompt) generateParams.negative_prompt = values.negative_prompt
      }
      if (isQwenImage2) {
        if (values.size) generateParams.size = values.size
        generateParams.prompt_extend = values.prompt_extend !== false
        generateParams.watermark = values.watermark || false
        if (values.seed) generateParams.seed = values.seed
        if (values.negative_prompt) generateParams.negative_prompt = values.negative_prompt
        generateParams.n = values.n || 1
      }
      
      const result = await studioApi.generate(selectedTask.id, generateParams)
      safeSetState(setTasks, (prev: StudioTask[]) => prev.map(t => t.id === result.task.id ? result.task : t))
      setSelectedTask(result.task)
      startPolling(selectedTask.id)
      message.info('已开始生成')
    } catch (error: any) {
      message.error(error?.message || '图片生成失败')
      try {
        const updatedTask = await studioApi.get(selectedTask.id)
        safeSetState(setTasks, (prev: StudioTask[]) => prev.map(t => t.id === updatedTask.id ? updatedTask : t))
        setSelectedTask(updatedTask)
      } catch {}
    }
  }

  const toggleImageSelection = (imageId: string) => {
    setSelectedImages(prev => {
      const next = new Set(prev)
      if (next.has(imageId)) {
        next.delete(imageId)
      } else {
        next.add(imageId)
      }
      return next
    })
  }

  const handleToggleImageMarker = async (taskId: string, imageId: string, markerKey: string, currentMarkers: string[]) => {
    const newMarkers = currentMarkers.includes(markerKey)
      ? currentMarkers.filter(m => m !== markerKey)
      : [...currentMarkers, markerKey]
    try {
      await studioApi.updateImageMarkers(taskId, imageId, newMarkers)
      setTasks(prev => prev.map(t => {
        if (t.id !== taskId) return t
        return { ...t, images: t.images.map(img => img.id === imageId ? { ...img, markers: newMarkers } : img) }
      }))
      if (selectedTask?.id === taskId) {
        setSelectedTask(prev => prev ? {
          ...prev,
          images: prev.images.map(img => img.id === imageId ? { ...img, markers: newMarkers } : img)
        } : prev)
      }
    } catch {
      message.error('标记更新失败')
    }
  }

  const saveToGallery = async () => {
    if (!selectedTask || selectedImages.size === 0) {
      message.warning('请先选择要保存的图片')
      return
    }
    
    try {
      const result = await studioApi.saveToGallery(selectedTask.id, Array.from(selectedImages))
      
      // 更新图库列表
      const galleryRes = await galleryApi.list(selectedTask.project_id)
      safeSetState(setGalleryImages, galleryRes.images)
      
      // 更新任务
      const taskRes = await studioApi.get(selectedTask.id)
      safeSetState(setTasks, (prev: StudioTask[]) => prev.map(t => t.id === taskRes.id ? taskRes : t))
      setSelectedTask(taskRes)
      
      setSelectedImages(new Set())
      message.success(`已保存 ${result.saved_images.length} 张图片到图库`)
    } catch (error) {
      message.error('保存失败')
    }
  }

  const deleteTask = async (taskId: string) => {
    try {
      await studioApi.delete(taskId)
      safeSetState(setTasks, (prev: StudioTask[]) => prev.filter(t => t.id !== taskId))
      if (selectedTask?.id === taskId) {
        setIsModalOpen(false)
      }
      message.success('任务已删除')
    } catch (error) {
      message.error('删除失败')
    }
  }

  const deleteAllTasks = async () => {
    if (!projectId) return
    try {
      await studioApi.deleteAll(projectId)
      safeSetState(setTasks, [])
      message.success('已删除所有任务')
    } catch (error) {
      message.error('删除失败')
    }
  }

  // 获取风格图片URL
  const getStyleImageUrl = (style: Style) => {
    if (style.style_type === 'image' && style.image_groups?.[style.selected_group_index]?.url) {
      return style.image_groups[style.selected_group_index].url
    }
    return null
  }
  
  // 构建素材选择选项（不包含风格）
  const buildReferenceOptions = () => {
    const options: { label: string, options: { label: React.ReactNode, value: string }[] }[] = []
    
    if (characters.length > 0) {
      options.push({
        label: '角色',
        options: characters.map(c => ({
          label: (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {c.image_groups?.[c.selected_group_index]?.front_url ? (
                <img src={c.image_groups[c.selected_group_index].front_url} alt="" style={{ width: 24, height: 24, objectFit: 'cover', borderRadius: 4 }} />
              ) : (
                <div style={{ width: 24, height: 24, background: token.colorBorder, borderRadius: 4 }} />
              )}
              <span>{c.name}</span>
            </div>
          ),
          value: `character:${c.id}`
        }))
      })
    }
    
    if (scenes.length > 0) {
      options.push({
        label: '场景',
        options: scenes.map(s => ({
          label: (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {s.image_groups?.[s.selected_group_index]?.url ? (
                <img src={s.image_groups[s.selected_group_index].url} alt="" style={{ width: 24, height: 24, objectFit: 'cover', borderRadius: 4 }} />
              ) : (
                <div style={{ width: 24, height: 24, background: token.colorBorder, borderRadius: 4 }} />
              )}
              <span>{s.name}</span>
            </div>
          ),
          value: `scene:${s.id}`
        }))
      })
    }
    
    if (props.length > 0) {
      options.push({
        label: '道具',
        options: props.map(p => ({
          label: (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {p.image_groups?.[p.selected_group_index]?.url ? (
                <img src={p.image_groups[p.selected_group_index].url} alt="" style={{ width: 24, height: 24, objectFit: 'cover', borderRadius: 4 }} />
              ) : (
                <div style={{ width: 24, height: 24, background: token.colorBorder, borderRadius: 4 }} />
              )}
              <span>{p.name}</span>
            </div>
          ),
          value: `prop:${p.id}`
        }))
      })
    }
    
    if (galleryImages.length > 0) {
      options.push({
        label: '图库',
        options: galleryImages.map(i => ({
          label: (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <img src={i.url} alt="" style={{ width: 24, height: 24, objectFit: 'cover', borderRadius: 4 }} />
              <span>{i.name}</span>
            </div>
          ),
          value: `gallery:${i.id}`
        }))
      })
    }
    
    return options
  }
  
  // 构建风格选项
  const buildStyleOptions = () => {
    return [
      { label: '不使用风格', value: '' },
      ...styles.map(s => ({
        label: (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {s.style_type === 'image' && getStyleImageUrl(s) ? (
              <img src={getStyleImageUrl(s)!} alt="" style={{ width: 24, height: 24, objectFit: 'cover', borderRadius: 4 }} />
            ) : (
              <div style={{ width: 24, height: 24, background: token.colorBorder, borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10 }}>T</div>
            )}
            <span>{s.name}</span>
            <Tag color={s.style_type === 'image' ? 'blue' : 'green'} style={{ fontSize: 10 }}>
              {s.style_type === 'image' ? '图片' : '文本'}
            </Tag>
          </div>
        ),
        value: s.id
      }))
    ]
  }

  const renderReferenceOrderList = () => {
    if (!selectedReferenceItems.length) return null
    return (
      <div style={{ marginTop: 12, display: 'grid', gap: 8 }}>
        {selectedReferenceItems.map((item, index) => (
          <div
            key={item.key}
            style={{
              display: 'grid',
              gridTemplateColumns: '56px 1fr auto',
              gap: 12,
              alignItems: 'center',
              padding: 8,
              borderRadius: 8,
              border: `1px solid ${token.colorBorder}`,
              background: token.colorBgLayout,
            }}
          >
            {item.url ? (
              <img src={item.url} alt="" style={{ width: 56, height: 56, borderRadius: 6, objectFit: 'cover' }} />
            ) : (
              <div style={{ width: 56, height: 56, borderRadius: 6, background: token.colorBorderSecondary }} />
            )}
            <div>
              <div style={{ fontWeight: 500 }}>图 {index + 1}</div>
              <div style={{ fontSize: 12, color: token.colorTextSecondary }}>{item.type}:{item.id}</div>
            </div>
            <Space direction="vertical" size={4}>
              <Button size="small" icon={<UpOutlined />} disabled={index === 0} onClick={() => moveReference(index, -1)} />
              <Button size="small" icon={<DownOutlined />} disabled={index === selectedReferenceItems.length - 1} onClick={() => moveReference(index, 1)} />
            </Space>
          </div>
        ))}
      </div>
    )
  }

  const renderWan27InteractiveEditors = () => {
    if (!isWan27Model || activeTaskKind !== 'interactive_edit' || !selectedReferenceItems.length) return null
    return (
      <div style={{ marginTop: 16 }}>
        <div style={{ marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontWeight: 500 }}>
            {renderFormLabel(activeModelId, 'bbox_list', '交互式框选区域')}
          </span>
        </div>
        <Space direction="vertical" style={{ width: '100%' }} size={16}>
          {selectedReferenceItems.map((item, index) => (
            <div key={item.key} style={{ padding: 12, borderRadius: 8, border: `1px solid ${token.colorBorder}` }}>
              <div style={{ marginBottom: 8, fontWeight: 500 }}>图 {index + 1}</div>
              <BBoxEditor
                imageUrl={item.url}
                value={wan27BBoxList[index] || []}
                onChange={(boxes) => {
                  const current = [...wan27BBoxList]
                  current[index] = boxes
                  syncWan27BBoxList(current)
                }}
              />
            </div>
          ))}
        </Space>
      </div>
    )
  }

  const renderDeveloperMode = () => (
    <Collapse
      style={{ marginTop: 16 }}
      items={[
        {
          key: 'developer-mode',
          label: '开发者模式',
          children: (
            <div>
              <div style={{ marginBottom: 8, fontWeight: 500 }}>提交状态</div>
              <div style={{ marginBottom: 12, color: token.colorTextSecondary }}>
                {isCreating ? '尚未提交' : `任务 ID: ${selectedTask?.id || '未知'}`}
              </div>
              <div style={{ marginBottom: 8, fontWeight: 500 }}>预览下次请求体参数</div>
              {previewPayload?.validation_warnings?.length ? (
                <Alert
                  type="warning"
                  showIcon
                  style={{ marginBottom: 12 }}
                  message="参数提醒"
                  description={
                    <div>
                      {previewPayload.validation_warnings.map((warning, index) => (
                        <div key={index}>{warning}</div>
                      ))}
                    </div>
                  }
                />
              ) : null}
              <div style={{ marginBottom: 8, fontWeight: 500 }}>Canonical 请求体（预览）</div>
              <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: 12, padding: 12, borderRadius: 8, background: token.colorBgLayout, marginBottom: 12 }}>
                {JSON.stringify(previewPayload?.canonical_request || {}, null, 2)}
              </pre>
              <div style={{ marginBottom: 8, fontWeight: 500 }}>厂商请求体（预览）</div>
              <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: 12, padding: 12, borderRadius: 8, background: token.colorBgLayout, marginBottom: 12 }}>
                {JSON.stringify(previewPayload?.provider_payload || {}, null, 2)}
              </pre>
              {!isCreating && selectedTask && hasPreviousTaskRequest && (
                <>
                  <div style={{ marginBottom: 8, fontWeight: 500 }}>上一次任务请求体参数</div>
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
                </>
              )}
              {!isCreating && selectedTask && !hasPreviousTaskRequest && (
                <Alert
                  type="info"
                  showIcon
                  message="当前任务还未生成过"
                  description="现在只显示下一次提交时的预览请求体；生成一次后，这里会同时展示上一次任务请求体。"
                />
              )}
            </div>
          ),
        },
      ]}
    />
  )

  const getStatusTag = (status: string) => {
    switch (status) {
      case 'pending':
        return <Tag>待生成</Tag>
      case 'generating':
        return <Tag color="processing" icon={<SyncOutlined spin />}>生成中</Tag>
      case 'completed':
        return <Tag color="success" icon={<CheckCircleOutlined />}>已完成</Tag>
      case 'failed':
        return <Tag color="error" icon={<CloseCircleOutlined />}>失败</Tag>
      default:
        return <Tag>{status}</Tag>
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
          <h1 style={{ fontSize: 20, fontWeight: 600, margin: 0, color: token.colorText }}>
            图片工作室
          </h1>
          <p style={{ color: token.colorTextSecondary, margin: '4px 0 0', fontSize: 13 }}>
            {currentProject?.name} - 共 {tasks.length} 个任务
          </p>
        </div>
        <Space>
          {tasks.length > 0 && (
            <Popconfirm 
              title="确定删除所有任务？" 
              description="此操作不可恢复"
              icon={<ExclamationCircleOutlined style={{ color: token.colorError }} />}
              onConfirm={deleteAllTasks}
              okText="删除"
              cancelText="取消"
              okButtonProps={{ danger: true }}
            >
              <Button danger icon={<DeleteOutlined />}>删除所有</Button>
            </Popconfirm>
          )}
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
            新建任务
          </Button>
        </Space>
      </div>

      {tasks.length === 0 ? (
        <Empty 
          description="暂无任务，点击新建创建生图任务" 
          style={{ marginTop: 100 }}
        >
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
            新建任务
          </Button>
        </Empty>
      ) : (
        <div className="image-grid">
          {tasks.map((task) => {
            const thumbnailUrl = task.images?.[0]?.url
            return (
              <div 
                key={task.id} 
                className="asset-card"
                onClick={() => openTaskModal(task)}
              >
                <div className="asset-card-image" style={{ position: 'relative' }}>
                  {thumbnailUrl ? (
                    <Image
                      src={thumbnailUrl}
                      alt={task.name}
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
                      background: token.colorBgContainer
                    }}>
                      <PictureOutlined style={{ fontSize: 48, color: token.colorBorderSecondary }} />
                    </div>
                  )}
                  <div style={{ position: 'absolute', top: 8, left: 8 }}>
                    {getStatusTag(task.status)}
                  </div>
                  <div style={{ position: 'absolute', top: 8, right: 8 }}>
                    <Tag>{task.references.length} 个素材</Tag>
                  </div>
                </div>
                <div className="asset-card-info">
                  <div className="asset-card-name">{task.name}</div>
                  <div className="asset-card-desc">
                    {task.status === 'failed' && task.error_message
                      ? <span style={{ color: token.colorError }}>{task.error_message.length > 40 ? task.error_message.slice(0, 40) + '...' : task.error_message}</span>
                      : task.images.length > 0 ? `${task.images.length} 张图片` : '暂无图片'}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* 统一的新建/编辑弹窗 */}
      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span>{isCreating ? '新建生图任务' : `任务详情 - ${selectedTask?.name}`}</span>
            {!isCreating && selectedTask && getStatusTag(selectedTask.status)}
          </div>
        }
        open={isModalOpen}
        onCancel={() => { setIsModalOpen(false); setIsCreating(false); setSelectedStyleId(null); setPreviewPayload(null); }}
        footer={null}
        width={1100}
      >
        {(isCreating || selectedTask) && (
          <Form form={form} layout="vertical" onValuesChange={handleFormValuesChange}>
          <div style={{ display: 'flex', gap: 24 }}>
            {/* 左侧：生成结果或素材选择 */}
            <div style={{ width: 500 }}>
              {isCreating ? (
                <>
                  {/* 新建模式：显示素材选择 */}
                  {shouldShowReferences && (
                    <>
                      <h4 style={{ margin: '0 0 12px 0', display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span>{renderFormLabel(activeModelId, 'images', '输入图片')}</span>
                      </h4>
                      <Form.Item 
                        name="references"
                        extra={
                          <span style={{ color: token.colorTextSecondary, fontSize: 12 }}>
                            按顺序选择素材；下方可继续调整图1、图2、图3的顺序
                          </span>
                        }
                      >
                        <Select
                          mode="multiple"
                          placeholder="按顺序选择参考素材（可选）"
                          options={buildReferenceOptions()}
                          style={{ width: '100%' }}
                          optionFilterProp="children"
                        />
                      </Form.Item>
                      {renderReferenceOrderList()}
                      {renderWan27InteractiveEditors()}
                    </>
                  )}
                  
                  {/* 风格选择 */}
                  <h4 style={{ margin: '16px 0 12px 0' }}>风格选择</h4>
                  <Form.Item 
                    name="style_id"
                    extra={
                      <span style={{ color: token.colorTextSecondary, fontSize: 12 }}>
                        图片风格：作为最后一个参考图加入。文本风格：描述嵌入提示词尾部
                      </span>
                    }
                  >
                    <Select
                      placeholder="选择风格（可选）"
                      options={buildStyleOptions()}
                      style={{ width: '100%' }}
                      allowClear
                      onChange={(value) => setSelectedStyleId(value || null)}
                    />
                  </Form.Item>
                  
                  {/* 选中风格预览 */}
                  {selectedStyleId && (() => {
                    const style = styles.find(s => s.id === selectedStyleId)
                    if (!style) return null
                    return (
                      <div style={{ 
                        padding: 12, 
                        background: token.colorBgLayout, 
                        borderRadius: 8,
                        border: `1px solid ${token.colorBorder}`,
                        marginBottom: 16
                      }}>
                        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                          {style.style_type === 'image' && getStyleImageUrl(style) && (
                            <img 
                              src={getStyleImageUrl(style)!} 
                              alt={style.name}
                              style={{ width: 80, height: 80, objectFit: 'cover', borderRadius: 4 }}
                            />
                          )}
                          <div style={{ flex: 1 }}>
                            <div style={{ fontWeight: 500, marginBottom: 4 }}>{style.name}</div>
                            <Tag color={style.style_type === 'image' ? 'blue' : 'green'}>
                              {style.style_type === 'image' ? '图片风格' : '文本风格'}
                            </Tag>
                            {style.style_type === 'text' && style.text_style_content && (
                              <div style={{ marginTop: 8, fontSize: 12, color: token.colorTextSecondary }}>
                                {style.text_style_content.slice(0, 100)}...
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    )
                  })()}
                  
                  <div style={{ 
                    padding: 16, 
                    background: token.colorBgLayout, 
                    borderRadius: 8,
                    textAlign: 'center',
                    color: token.colorTextTertiary,
                    marginTop: 16
                  }}>
                    <PictureOutlined style={{ fontSize: 48, marginBottom: 12, color: token.colorBorderSecondary }} />
                    <div>填写右侧配置后点击创建任务</div>
                    <div style={{ fontSize: 12, marginTop: 4 }}>创建后可生成图片</div>
                  </div>
                </>
              ) : selectedTask && (
                <>
                  {/* 编辑模式：显示生成结果 */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                    <h4 style={{ margin: 0 }}>生成结果</h4>
                    <Space>
                      {selectedImages.size > 0 && (
                        <Button 
                          type="primary" 
                          icon={<SaveOutlined />} 
                          onClick={saveToGallery}
                        >
                          保存选中到图库 ({selectedImages.size})
                        </Button>
                      )}
                    </Space>
                  </div>
                  
                  {selectedTask.status === 'failed' && selectedTask.error_message && (
                    <div style={{
                      padding: 12,
                      background: 'rgba(255, 77, 79, 0.08)',
                      border: '1px solid rgba(255, 77, 79, 0.3)',
                      borderRadius: 8,
                      marginBottom: 12
                    }}>
                      <div style={{ color: token.colorError, fontWeight: 500, marginBottom: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
                        <CloseCircleOutlined /> 生成失败
                      </div>
                      <div style={{ color: token.colorError, fontSize: 13, wordBreak: 'break-all' }}>
                        {selectedTask.error_message}
                      </div>
                    </div>
                  )}
                  
                  {/* 参考素材选择 */}
                  {shouldShowReferences && (
                    <div style={{ marginBottom: 16 }}>
                      <Form.Item 
                        name="references"
                        label={renderFormLabel(activeModelId, 'images', '输入图片')}
                        extra={
                          <span style={{ color: token.colorTextSecondary, fontSize: 12 }}>
                            按顺序选择参考素材，可在提示词中使用“图1”“图2”等引用不同素材
                          </span>
                        }
                        style={{ marginBottom: 0 }}
                      >
                        <Select
                          mode="multiple"
                          placeholder="按顺序选择参考素材（可选）"
                          options={buildReferenceOptions()}
                          style={{ width: '100%' }}
                          optionFilterProp="children"
                        />
                      </Form.Item>
                      {renderReferenceOrderList()}
                      {renderWan27InteractiveEditors()}
                    </div>
                  )}
                  
                  {/* 生成的图片 */}
                  {selectedTask.images.length > 0 ? (
                    <Image.PreviewGroup
                      items={selectedTask.images.filter(img => img.url).map(img => img.url!)}
                    >
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 }}>
                        {selectedTask.images.map((image, idx) => (
                          <div key={image.id}>
                            <div 
                              style={{ 
                                position: 'relative',
                                aspectRatio: '1',
                                background: token.colorBgLayout,
                                borderRadius: 8,
                                overflow: 'hidden',
                                border: selectedImages.has(image.id) ? `2px solid ${token.colorPrimary}` : '2px solid transparent'
                              }}
                            >
                              {image.url ? (
                                <Image 
                                  src={image.url} 
                                  alt={`第 ${idx + 1} 组`} 
                                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                                  preview={{ mask: '点击预览' }}
                                />
                              ) : (
                                <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                  <PictureOutlined style={{ fontSize: 32, color: token.colorBorderSecondary }} />
                                </div>
                              )}
                              <div 
                                style={{ position: 'absolute', top: 8, left: 8, cursor: 'pointer', zIndex: 10 }}
                                onClick={(e) => { e.stopPropagation(); toggleImageSelection(image.id); }}
                              >
                                <Checkbox checked={selectedImages.has(image.id)} />
                              </div>
                              <div style={{ position: 'absolute', bottom: 8, right: 8, pointerEvents: 'none' }}>
                                <Tag>第 {idx + 1} 组</Tag>
                              </div>
                              {image.is_selected && (
                                <div style={{ position: 'absolute', top: 8, right: 8, pointerEvents: 'none' }}>
                                  <Tag color="green">已保存</Tag>
                                </div>
                              )}
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'center', gap: 4, marginTop: 4 }}>
                              {([
                                { key: 'star', icon: <StarOutlined />, activeIcon: <StarFilled />, color: token.colorWarning, title: '星标' },
                                { key: 'flag', icon: <FlagOutlined />, activeIcon: <FlagFilled />, color: token.colorError, title: '红旗' },
                                { key: 'check', icon: <CheckOutlined />, activeIcon: <CheckOutlined />, color: token.colorSuccess, title: '对号' },
                                { key: 'cross', icon: <CloseOutlined />, activeIcon: <CloseOutlined />, color: token.colorError, title: '红叉' },
                              ] as const).map(marker => {
                                const active = (image.markers || []).includes(marker.key)
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
                                    onClick={() => handleToggleImageMarker(selectedTask.id, image.id, marker.key, image.markers || [])}
                                  />
                                )
                              })}
                            </div>
                          </div>
                        ))}
                      </div>
                    </Image.PreviewGroup>
                  ) : (
                    <>
                      {selectedTask?.status === 'failed' && selectedTask?.error_message ? (
                        <div style={{
                          padding: 16,
                          background: 'rgba(255, 77, 79, 0.08)',
                          border: '1px solid rgba(255, 77, 79, 0.3)',
                          borderRadius: 8,
                          marginBottom: 12
                        }}>
                          <div style={{ color: token.colorError, fontWeight: 500, marginBottom: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
                            <CloseCircleOutlined /> 生成失败
                          </div>
                          <div style={{ color: token.colorError, fontSize: 13, wordBreak: 'break-all' }}>
                            {selectedTask.error_message}
                          </div>
                        </div>
                      ) : null}
                      <Empty 
                        description={selectedTask?.status === 'failed' ? '生成失败，请查看上方错误信息' : '暂无生成结果，点击右侧生成按钮开始'}
                        image={Empty.PRESENTED_IMAGE_SIMPLE}
                      />
                    </>
                  )}
                </>
              )}
            </div>

            {/* 右侧：配置和操作 */}
            <div style={{ flex: 1 }}>
                <Form.Item
                  name="task_kind"
                  label={
                    <Space size={6}>
                      <span>任务类型</span>
                      <HoverInfoPopover
                        title="任务类型"
                        help={{
                          summary: '先选要做什么，再选兼容模型。',
                          how_to_choose: TASK_KIND_OPTIONS.map(item => `${item.label}：${item.help}`),
                        }}
                      />
                    </Space>
                  }
                  initialValue="text_to_image"
                >
                  <Select
                    options={TASK_KIND_OPTIONS.map(item => ({ value: item.value, label: item.label }))}
                  />
                </Form.Item>
                <Form.Item name="name" label="任务名称" rules={[{ required: true }]}>
                  <Input />
                </Form.Item>
                <Form.Item name="description" label="任务描述">
                  <TextArea rows={2} />
                </Form.Item>
                <Form.Item 
                  name="model" 
                  label="生成模型"
                  extra={
                    availableModels[activeModelId || 'wan2.7-image-pro']?.description
                  }
                >
                  <Select 
                    options={getModelsForTaskKind(activeTaskKind).map(m => ({ 
                      label: `${m.name} ${m.id}`, 
                      value: m.id 
                    }))} 
                    onChange={() => form.setFieldsValue({})} // 触发重新渲染显示描述
                  />
                </Form.Item>
                <div style={{ display: 'grid', gridTemplateColumns: shouldShowGroupCount ? '1fr 1fr' : '1fr', gap: 16 }}>
                  <Form.Item 
                    name="n" 
                    label={renderFormLabel(activeModelId, 'n', activeTaskKind === 'sequential_generation' ? '最大组图数' : '生图数量')}
                    extra={(() => {
                      const model = activeModelId
                      if (WAN27_MODELS.has(model)) return activeTaskKind === 'sequential_generation' ? '组图模式下为最大组图数，范围 1-12，默认 12' : '普通模式下范围 1-4，默认 4'
                      if (model?.startsWith('qwen-image-edit')) return '最多6张'
                      if (model === 'qwen-image-2.0-pro' || model === 'qwen-image-2.0') return '最多6张'
                      if (model === 'qwen-image-max' || model === 'qwen-image-plus') return '固定1张，用并发组数控制总量'
                      if (model === 'wan2.5-i2i-preview') return '最多4张'
                      return ''
                    })()}
                  >
                    <InputNumber 
                      min={1} 
                      max={(() => {
                        const model = activeModelId
                        if (WAN27_MODELS.has(model)) return activeTaskKind === 'sequential_generation' ? 12 : 4
                        if (model === 'qwen-image-max' || model === 'qwen-image-plus') return 1
                        if (model?.startsWith('qwen-image-edit')) return 6
                        if (model === 'qwen-image-2.0-pro' || model === 'qwen-image-2.0') return 6
                        if (model === 'wan2.5-i2i-preview') return 4
                        return 4
                      })()}
                      disabled={(() => {
                        const model = activeModelId
                        return model === 'qwen-image-max' || model === 'qwen-image-plus'
                      })()}
                      style={{ width: '100%' }} 
                    />
                  </Form.Item>
                  {shouldShowGroupCount && (
                    <Form.Item 
                      name="group_count" 
                      label={renderFormLabel(activeModelId, 'group_count', '并发组数', {
                        summary: '并发请求数，总图片数 = 生图数量 × 并发组数。',
                        how_to_choose: ['万相 2.7 已经由模型自身的 n 控制输出，默认不再额外开放并发组数。'],
                      })}
                      extra={`总计: ${(form.getFieldValue('n') || 1) * (form.getFieldValue('group_count') || 1)} 张`}
                    >
                      <InputNumber 
                        min={1} 
                        max={10} 
                        style={{ width: '100%' }} 
                      />
                    </Form.Item>
                  )}
                </div>
                <Form.Item name="prompt" label={renderFormLabel(activeModelId, 'prompt', '生成提示词')} extra={
                  (() => {
                    const m = activeModelId
                    if (m?.startsWith('qwen-image-edit')) return '多图时用"图1"、"图2"、"图3"指代不同图片'
                    if (m === 'qwen-image-2.0-pro' || m === 'qwen-image-2.0') return '无参考图为文生图；有参考图为编辑模式，多图用"图1""图2"指代'
                    if (WAN27_MODELS.has(m)) return 'wan2.7 多图时按图1、图2…理解输入顺序；组图生成时建议明确写出每张图的场景。'
                    return ''
                  })()
                }>
                  <TextArea rows={4} />
                </Form.Item>
                {!isWan27Model && (
                <Form.Item name="negative_prompt" label={renderFormLabel(activeModelId, 'negative_prompt', '负向提示词')}>
                  <TextArea rows={2} />
                </Form.Item>
                )}
                
                {/* wan2.7 模型参数 */}
                {isWan27Model && (
                  <div style={{ marginBottom: 16 }}>
                    <div style={{ marginBottom: 8, color: token.colorTextSecondary, fontSize: 12 }}>
                      Wan 2.7 图像生成参数
                    </div>
                    <div style={{ marginBottom: 12, padding: 12, borderRadius: 8, background: token.colorBgLayout }}>
                      <div style={{ marginBottom: 8, color: token.colorTextSecondary }}>
                        当前能力：{getTaskKindLabel(activeTaskKind)}
                      </div>
                      <div style={{ color: token.colorTextTertiary, fontSize: 12 }}>
                        {activeTaskKind === 'text_to_image' && '纯文生图。自定义宽高会按指定比例出图；规格档位 1K/2K/4K 默认输出正方形。'}
                        {activeTaskKind === 'image_edit' && '图像编辑/多图参考生成。自定义宽高会按指定比例出图；规格档位 1K/2K 会跟随最后一张输入图比例。'}
                        {activeTaskKind === 'interactive_edit' && '交互式编辑。bbox_list 必须和输入图一一对应，不需要框选的图位也要保留空数组 []。'}
                        {activeTaskKind === 'sequential_generation' && '组图生成。enable_sequential 自动开启，n 代表最大组图数，模型可能少于该上限返回。'}
                      </div>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                      <div>
                        <div style={{ marginBottom: 8, color: token.colorTextSecondary, fontSize: 12 }}>
                          尺寸模式
                        </div>
                        <Segmented
                          block
                          value={effectiveWan27EntryMode}
                          options={[
                            { value: 'custom', label: '自定义宽高（指定比例）' },
                            { value: 'preset', label: `规格档位（${wan27HasInputImages ? '跟随输入图' : '默认正方形'}）` },
                          ]}
                          onChange={(value) => switchWan27SizeMode(value as 'custom' | 'preset')}
                        />
                        <div style={{ marginTop: 8, color: token.colorTextSecondary, fontSize: 12 }}>
                          本次实际发送 size：{wan27SubmittedSize}
                        </div>
                      </div>
                      <Form.Item
                        name="seed"
                        label={renderFormLabel(activeModelId, 'seed', '随机种子')}
                        style={{ marginBottom: 0 }}
                      >
                        <InputNumber min={0} max={2147483647} style={{ width: '100%' }} placeholder="随机" />
                      </Form.Item>
                    </div>

                    {effectiveWan27EntryMode !== 'custom' ? (
                      <>
                        <Form.Item
                          name="size_preset"
                          label={renderFormLabel(activeModelId, 'size', '输出规格', {
                            summary: wan27HasInputImages ? '规格档位只控制总像素级别，输出比例会跟随最后一张输入图。' : '规格档位只提交 1K / 2K / 4K，无输入图时默认输出正方形。',
                            notes: wan27HasInputImages ? ['如果要指定横竖比例，请切到“自定义宽高（指定比例）”。'] : ['如果要指定横竖比例，请切到“自定义宽高（指定比例）”。'],
                          })}
                          style={{ marginBottom: 12 }}
                        >
                          <Select options={wan27PresetOptions} />
                        </Form.Item>
                        <div style={{ marginBottom: 12, color: token.colorTextSecondary, fontSize: 12 }}>
                          {wan27HasInputImages ? '当前使用规格档位，输出比例将跟随最后一张输入图。' : '当前使用规格档位，默认按正方形输出。'}
                        </div>
                      </>
                    ) : (
                      <>
                        <div style={{ display: 'grid', gridTemplateColumns: '200px minmax(0, 1fr)', gap: 12, marginBottom: 12 }}>
                          <Form.Item
                            label={renderFormLabel(activeModelId, 'size', '画面比例', {
                              summary: '选择比例后，平台会填入对应的自定义宽高像素，并向模型提交 size=宽*高。',
                              notes: ['这是文档中的自定义像素方式，可显式指定输出比例。'],
                            })}
                            style={{ marginBottom: 0 }}
                          >
                            <Select
                              style={{ width: '100%' }}
                              popupMatchSelectWidth={260}
                              value={activeWan27QualityGroup?.ratio}
                              options={wan27QualityGroups.map((group) => ({
                                value: group.ratio,
                                label: `${group.ratio} ${group.orientation}`,
                              }))}
                              onChange={(value) => {
                                setWan27RatioChoice(value)
                                const nextGroup = wan27QualityGroups.find((group) => group.ratio === value)
                                const nextOption =
                                  nextGroup?.options.find((item) => item.quality === wan27QualityChoice) ||
                                  nextGroup?.options.find((item) => item.quality === 'medium') ||
                                  nextGroup?.options[0]
                                if (nextOption) {
                                  applyWan27QualityTemplate(value, nextOption.quality)
                                }
                              }}
                            />
                          </Form.Item>
                          <Form.Item
                            label={renderFormLabel(undefined, 'quality_preset', '清晰度', {
                              summary: '像素档位是同比例下的不同宽高模板，像素越高通常细节越多。',
                              notes: ['这是平台对自定义像素的快捷模板，不是模型原生质量参数。'],
                            })}
                            style={{ marginBottom: 0 }}
                          >
                            <Select
                              value={wan27QualityChoice}
                              style={{ width: '100%' }}
                              popupMatchSelectWidth={320}
                              options={(activeWan27QualityGroup?.options || []).map((option) => ({
                                value: option.quality,
                                label: `${option.qualityLabel} ${option.width}×${option.height}`,
                              }))}
                              onChange={(value) => applyWan27QualityTemplate(activeWan27QualityGroup?.ratio || wan27RatioChoice, value as ImageQualityLevel)}
                            />
                          </Form.Item>
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                          <Form.Item
                            name="custom_width"
                            label={renderFormLabel(activeModelId, 'size', '自定义宽度')}
                            style={{ marginBottom: 0 }}
                            rules={[{ validator: validateCustomDimension }]}
                          >
                            <InputNumber min={1} max={WAN27_MAX_CUSTOM_DIMENSION} style={{ width: '100%' }} />
                          </Form.Item>
                          <Form.Item
                            name="custom_height"
                            label={renderFormLabel(activeModelId, 'size', '自定义高度')}
                            style={{ marginBottom: 0 }}
                            rules={[{ validator: validateCustomDimension }]}
                          >
                            <InputNumber min={1} max={WAN27_MAX_CUSTOM_DIMENSION} style={{ width: '100%' }} />
                          </Form.Item>
                        </div>
                        {activeCustomSizeLimits && (
                          <div style={{ marginBottom: 12, color: token.colorTextSecondary, fontSize: 12 }}>
                            当前模式下总像素需在 {activeCustomSizeLimits.minTotalPixels} 到 {activeCustomSizeLimits.maxTotalPixels} 之间，宽高比需在 1:8 到 8:1 之间。
                          </div>
                        )}
                      </>
                    )}

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                      {activeTaskKind === 'text_to_image' && selectedReferenceItems.length === 0 && (
                        <Form.Item
                          name="thinking_mode"
                          label={renderFormLabel(activeModelId, 'thinking_mode', '思考模式')}
                          valuePropName="checked"
                          style={{ marginBottom: 0 }}
                        >
                          <Switch checkedChildren="开" unCheckedChildren="关" />
                        </Form.Item>
                      )}
                      <Form.Item
                        name="watermark"
                        label={renderFormLabel(activeModelId, 'watermark', '水印')}
                        valuePropName="checked"
                        style={{ marginBottom: 0 }}
                      >
                        <Switch checkedChildren="开" unCheckedChildren="关" />
                      </Form.Item>
                    </div>

                    {activeTaskKind !== 'sequential_generation' && (
                      <Form.Item
                        name="color_palette"
                        label={renderFormLabel(activeModelId, 'color_palette', '颜色主题')}
                        style={{ marginBottom: 0 }}
                      >
                        <ColorPaletteEditor />
                      </Form.Item>
                    )}
                  </div>
                )}

                {/* wan2.5 文生图参数 */}
                {(watchedModel || selectedTask?.model) === 'wan2.5-t2i-preview' && (
                  <div style={{ marginBottom: 16 }}>
                    <div style={{ marginBottom: 8, color: token.colorTextSecondary, fontSize: 12 }}>
                      Wan2.5 文生图参数
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                      <Form.Item
                        name="size_mode"
                        label={renderFormLabel(activeModelId, 'size', '尺寸模式', {
                          summary: '支持预设尺寸和自定义像素。常用比例模板只是快捷填充器，底层仍提交真实宽高。',
                          limits: ['总像素需在 768×768 到 1440×1440 之间。', '宽高比需在 1:4 到 4:1 之间。'],
                        })}
                        style={{ marginBottom: 0 }}
                      >
                        <Select
                          options={[
                            { value: 'preset', label: '预设尺寸' },
                            { value: 'custom', label: '自定义像素' },
                          ]}
                        />
                      </Form.Item>
                      <Form.Item
                        name="seed"
                        label={renderFormLabel(activeModelId, 'seed', '随机种子')}
                        style={{ marginBottom: 0 }}
                      >
                        <InputNumber min={0} max={2147483647} style={{ width: '100%' }} placeholder="随机" />
                      </Form.Item>
                    </div>
                    {watchedSizeMode !== 'custom' ? (
                      <Form.Item
                        name="size_preset"
                        label={renderFormLabel(activeModelId, 'size', '预设尺寸')}
                        style={{ marginBottom: 12 }}
                      >
                        <Select
                          options={availableModels[activeModelId]?.common_sizes?.map((size: any) => ({
                            value: size.value || (typeof size === 'string' ? size : `${size.width}*${size.height}`),
                            label: size.label || formatSizeLabel(size),
                          }))}
                        />
                      </Form.Item>
                    ) : (
                      <>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                          <Form.Item
                            name="custom_width"
                            label={renderFormLabel(activeModelId, 'size', '自定义宽度')}
                            style={{ marginBottom: 0 }}
                            rules={[{ validator: validateCustomDimension }]}
                          >
                            <InputNumber min={1} max={12000} style={{ width: '100%' }} />
                          </Form.Item>
                          <Form.Item
                            name="custom_height"
                            label={renderFormLabel(activeModelId, 'size', '自定义高度')}
                            style={{ marginBottom: 0 }}
                            rules={[{ validator: validateCustomDimension }]}
                          >
                            <InputNumber min={1} max={12000} style={{ width: '100%' }} />
                          </Form.Item>
                        </div>
                        <div style={{ marginBottom: 12 }}>
                          <div style={{ marginBottom: 8, color: token.colorTextSecondary, fontSize: 12 }}>常用比例模板</div>
                          <Space wrap>
                            {sizeTemplateOptions.map((template) => (
                              <Button key={template.label} size="small" onClick={() => applyCustomSizeTemplate(template)}>
                                {template.label}
                              </Button>
                            ))}
                          </Space>
                          {activeCustomSizeLimits && (
                            <div style={{ marginTop: 8, color: token.colorTextSecondary, fontSize: 12 }}>
                              当前模式下总像素需在 {activeCustomSizeLimits.minTotalPixels} 到 {activeCustomSizeLimits.maxTotalPixels} 之间，宽高比需在 1:4 到 4:1 之间。
                            </div>
                          )}
                        </div>
                      </>
                    )}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                      <Form.Item
                        name="prompt_extend"
                        label={renderFormLabel(activeModelId, 'prompt_extend', '智能改写')}
                        valuePropName="checked"
                        initialValue={true}
                        style={{ marginBottom: 0 }}
                      >
                        <Switch checkedChildren="开" unCheckedChildren="关" />
                      </Form.Item>
                      <Form.Item
                        name="watermark"
                        label={renderFormLabel(activeModelId, 'watermark', '水印')}
                        valuePropName="checked"
                        initialValue={false}
                        style={{ marginBottom: 0 }}
                      >
                        <Switch checkedChildren="开" unCheckedChildren="关" />
                      </Form.Item>
                    </div>
                  </div>
                )}

                {/* 文生图模型参数 */}
                {availableModels[watchedModel || selectedTask?.model || '']?.model_type === 'text_to_image' &&
                  (watchedModel || selectedTask?.model) !== 'wan2.5-t2i-preview' &&
                  (watchedModel || selectedTask?.model) !== 'qwen-image-2.0-pro' &&
                  (watchedModel || selectedTask?.model) !== 'qwen-image-2.0' &&
                  !isWan27Model && (
                  <div style={{ 
                    marginBottom: 16
                  }}>
                    <div style={{ marginBottom: 8, color: token.colorTextSecondary, fontSize: 12 }}>
                      文生图模型参数
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                      <Form.Item 
                        name="size" 
                        label={renderFormLabel(activeModelId, 'size', '输出尺寸')}
                        style={{ marginBottom: 0 }}
                      >
                        <Select
                          placeholder="默认尺寸"
                          allowClear
                          options={
                            availableModels[watchedModel || selectedTask?.model || '']?.common_sizes?.map((size: any) => ({
                              value: size.value || (typeof size === 'string' ? size : `${size.width}*${size.height}`),
                              label: size.label || formatSizeLabel(size)
                            })) || [
                              { value: '1280*1280', label: '1280×1280 正方形' },
                            ]
                          }
                        />
                      </Form.Item>
                      <Form.Item 
                        name="seed" 
                        label={renderFormLabel(activeModelId, 'seed', '随机种子')}
                        style={{ marginBottom: 0 }}
                      >
                        <InputNumber 
                          min={0} 
                          max={2147483647} 
                          style={{ width: '100%' }} 
                          placeholder="随机"
                        />
                      </Form.Item>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                      <Form.Item 
                        name="prompt_extend" 
                        label={renderFormLabel(activeModelId, 'prompt_extend', '智能改写')}
                        valuePropName="checked"
                        initialValue={true}
                        style={{ marginBottom: 0 }}
                      >
                        <Switch checkedChildren="开" unCheckedChildren="关" />
                      </Form.Item>
                      <Form.Item 
                        name="watermark" 
                        label={renderFormLabel(activeModelId, 'watermark', '水印')}
                        valuePropName="checked"
                        initialValue={false}
                        style={{ marginBottom: 0 }}
                      >
                        <Switch checkedChildren="开" unCheckedChildren="关" />
                      </Form.Item>
                    </div>
                    <div style={{ marginTop: 8, color: token.colorTextTertiary, fontSize: 11 }}>
                      提示：文生图模型不需要参考图片，只需要输入提示词
                    </div>
                  </div>
                )}

                {/* wan2.5 图生图参数 */}
                {(watchedModel || selectedTask?.model) === 'wan2.5-i2i-preview' && (
                  <div style={{ marginBottom: 16 }}>
                    <div style={{ marginBottom: 8, color: token.colorTextSecondary, fontSize: 12 }}>
                      Wan2.5 图生图参数
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                      <Form.Item
                        name="size_mode"
                        label={renderFormLabel(activeModelId, 'size', '尺寸模式', {
                          summary: '支持预设尺寸和自定义像素。多图参考时建议先用模板，再按构图微调。',
                          limits: ['总像素需在 768×768 到 1280×1280 之间。', '宽高比需在 1:4 到 4:1 之间。'],
                        })}
                        style={{ marginBottom: 0 }}
                      >
                        <Select
                          options={[
                            { value: 'preset', label: '预设尺寸' },
                            { value: 'custom', label: '自定义像素' },
                          ]}
                        />
                      </Form.Item>
                      <Form.Item
                        name="seed"
                        label={renderFormLabel(activeModelId, 'seed', '随机种子')}
                        style={{ marginBottom: 0 }}
                      >
                        <InputNumber min={0} max={2147483647} style={{ width: '100%' }} placeholder="随机" />
                      </Form.Item>
                    </div>
                    {watchedSizeMode !== 'custom' ? (
                      <Form.Item
                        name="size_preset"
                        label={renderFormLabel(activeModelId, 'size', '预设尺寸')}
                        style={{ marginBottom: 12 }}
                      >
                        <Select
                          options={availableModels[activeModelId]?.common_sizes?.map((size: any) => ({
                            value: size.value || (typeof size === 'string' ? size : `${size.width}*${size.height}`),
                            label: size.label || formatSizeLabel(size),
                          }))}
                        />
                      </Form.Item>
                    ) : (
                      <>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                          <Form.Item
                            name="custom_width"
                            label={renderFormLabel(activeModelId, 'size', '自定义宽度')}
                            style={{ marginBottom: 0 }}
                            rules={[{ validator: validateCustomDimension }]}
                          >
                            <InputNumber min={1} max={12000} style={{ width: '100%' }} />
                          </Form.Item>
                          <Form.Item
                            name="custom_height"
                            label={renderFormLabel(activeModelId, 'size', '自定义高度')}
                            style={{ marginBottom: 0 }}
                            rules={[{ validator: validateCustomDimension }]}
                          >
                            <InputNumber min={1} max={12000} style={{ width: '100%' }} />
                          </Form.Item>
                        </div>
                        <div style={{ marginBottom: 12 }}>
                          <div style={{ marginBottom: 8, color: token.colorTextSecondary, fontSize: 12 }}>常用比例模板</div>
                          <Space wrap>
                            {sizeTemplateOptions.map((template) => (
                              <Button key={template.label} size="small" onClick={() => applyCustomSizeTemplate(template)}>
                                {template.label}
                              </Button>
                            ))}
                          </Space>
                          {activeCustomSizeLimits && (
                            <div style={{ marginTop: 8, color: token.colorTextSecondary, fontSize: 12 }}>
                              当前模式下总像素需在 {activeCustomSizeLimits.minTotalPixels} 到 {activeCustomSizeLimits.maxTotalPixels} 之间，宽高比需在 1:4 到 4:1 之间。
                            </div>
                          )}
                        </div>
                      </>
                    )}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                      <Form.Item
                        name="prompt_extend"
                        label={renderFormLabel(activeModelId, 'prompt_extend', '智能改写')}
                        valuePropName="checked"
                        initialValue={true}
                        style={{ marginBottom: 0 }}
                      >
                        <Switch checkedChildren="开" unCheckedChildren="关" />
                      </Form.Item>
                      <Form.Item
                        name="watermark"
                        label={renderFormLabel(activeModelId, 'watermark', '水印')}
                        valuePropName="checked"
                        initialValue={false}
                        style={{ marginBottom: 0 }}
                      >
                        <Switch checkedChildren="开" unCheckedChildren="关" />
                      </Form.Item>
                    </div>
                  </div>
                )}

                {/* wan2.6-image 模型参数 */}
                {(watchedModel || selectedTask?.model) === 'wan2.6-image' && (
                  <div style={{ 
                    marginBottom: 16
                  }}>
                    <div style={{ marginBottom: 8, color: token.colorTextSecondary, fontSize: 12 }}>
                      Wan2.6 图像生成参数
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                      <Form.Item 
                        name="size" 
                        label={renderFormLabel(activeModelId, 'size', '输出尺寸')}
                        style={{ marginBottom: 0 }}
                      >
                        <Select
                          placeholder="默认尺寸"
                          allowClear
                          options={
                            availableModels['wan2.6-image']?.common_sizes?.map((size: any) => ({
                              value: size.value || (typeof size === 'string' ? size : `${size.width}*${size.height}`),
                              label: size.label || formatSizeLabel(size)
                            })) || [
                              { value: '1280*1280', label: '1280×1280 正方形' },
                            ]
                          }
                        />
                      </Form.Item>
                      <Form.Item 
                        name="enable_interleave" 
                        label={renderFormLabel(activeModelId, 'enable_interleave', '图文混合模式')}
                        valuePropName="checked"
                        initialValue={false}
                        style={{ marginBottom: 0 }}
                        tooltip="启用后生成图文并茂内容。限制：参考图最多1张，生图数量固定为1"
                      >
                        <Switch 
                          checkedChildren="开" 
                          unCheckedChildren="关"
                          onChange={(checked) => {
                            if (checked) {
                              form.setFieldValue('n', 1)
                            }
                          }}
                        />
                      </Form.Item>
                    </div>
                    {/* 图文混合模式专用参数 */}
                    {watchedEnableInterleave && (
                      <div style={{ marginBottom: 12 }}>
                        <Form.Item 
                          name="max_images" 
                          label={renderFormLabel(activeModelId, 'max_images', '最大图片数')}
                          style={{ marginBottom: 0 }}
                          initialValue={5}
                          tooltip="图文混合模式下，模型最多生成的图片数量(1-5)，实际生成数量可能更少"
                        >
                          <InputNumber 
                            min={1} 
                            max={5}
                            style={{ width: '100%' }} 
                            placeholder="默认5张"
                          />
                        </Form.Item>
                      </div>
                    )}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
                      <Form.Item 
                        name="prompt_extend" 
                        label={renderFormLabel(activeModelId, 'prompt_extend', '智能改写')}
                        valuePropName="checked"
                        initialValue={true}
                        style={{ marginBottom: 0 }}
                        tooltip="仅非图文混合模式生效，自动优化提示词"
                      >
                        <Switch 
                          checkedChildren="开" 
                          unCheckedChildren="关"
                          disabled={watchedEnableInterleave}
                        />
                      </Form.Item>
                      <Form.Item 
                        name="watermark" 
                        label={renderFormLabel(activeModelId, 'watermark', '水印')}
                        valuePropName="checked"
                        initialValue={false}
                        style={{ marginBottom: 0 }}
                        tooltip="在图片右下角添加'AI生成'水印"
                      >
                        <Switch checkedChildren="开" unCheckedChildren="关" />
                      </Form.Item>
                      <Form.Item 
                        name="seed" 
                        label={renderFormLabel(activeModelId, 'seed', '随机种子')}
                        style={{ marginBottom: 0 }}
                        tooltip="相同种子可获得相对稳定的生成结果"
                      >
                        <InputNumber 
                          min={0} 
                          max={2147483647} 
                          style={{ width: '100%' }} 
                          placeholder="随机"
                        />
                      </Form.Item>
                    </div>
                    <div style={{ marginTop: 8, padding: '8px', background: token.colorBgElevated, borderRadius: 4, fontSize: 11 }}>
                      <div style={{ color: token.colorTextSecondary, marginBottom: 4 }}>📝 模式说明：</div>
                      <div style={{ color: token.colorTextTertiary }}>
                        {watchedEnableInterleave ? (
                          <>• <strong>图文混合模式</strong>：根据提示词生成图文并茂的内容，支持0-1张参考图</>
                        ) : (
                          <>• <strong>参考图模式</strong>：基于1-4张参考图进行风格迁移、主体一致性生成</>
                        )}
                      </div>
                      {!watchedEnableInterleave && (
                        <div style={{ color: token.colorWarning, marginTop: 4 }}>
                          ⚠️ 参考图模式下必须选择至少1张参考图
                        </div>
                      )}
                      <div style={{ color: token.colorTextQuaternary, marginTop: 4 }}>
                        参考图要求：宽高 384-5000px，格式 JPEG/PNG/BMP/WEBP，≤10MB
                      </div>
                    </div>
                  </div>
                )}

                {/* qwen-image-edit 系列专用参数 */}
                {(watchedModel || selectedTask?.model)?.startsWith('qwen-image-edit') && (() => {
                  const currentQwenModel = watchedModel || selectedTask?.model || 'qwen-image-edit-max'
                  const qwenModelInfo = availableModels[currentQwenModel]
                  const qwenEditSizeDisabled = Number(watchedN || 1) > 1
                  return (
                    <div style={{ marginBottom: 16 }}>
                      <div style={{ marginBottom: 8, color: token.colorTextSecondary, fontSize: 12 }}>
                        {qwenModelInfo?.name || currentQwenModel} 参数
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                        <Form.Item 
                          name="size" 
                          label={renderFormLabel(activeModelId, 'size', '输出尺寸')}
                          extra={qwenEditSizeDisabled ? '当前 n > 1，该模型的 size 不生效，已自动禁用。' : undefined}
                          style={{ marginBottom: 0 }}
                        >
                          <Select
                            disabled={qwenEditSizeDisabled}
                            allowClear
                            placeholder="默认（保持原图比例）"
                            options={
                              [
                                { value: '', label: '默认（保持原图比例）' },
                                ...(qwenModelInfo?.common_sizes?.map((size: any) => ({
                                  value: size.value || (typeof size === 'string' ? size : `${size.width}*${size.height}`),
                                  label: size.label || formatSizeLabel(size)
                                })) || [
                                  { value: '1024*1024', label: '1024×1024 正方形' },
                                ])
                              ]
                            }
                          />
                        </Form.Item>
                        <Form.Item 
                          name="seed" 
                          label={renderFormLabel(activeModelId, 'seed', '随机种子')}
                          style={{ marginBottom: 0 }}
                        >
                          <InputNumber 
                            min={0} 
                            max={2147483647} 
                            style={{ width: '100%' }} 
                            placeholder="留空为随机"
                          />
                        </Form.Item>
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                        <Form.Item 
                          name="prompt_extend" 
                          label={renderFormLabel(activeModelId, 'prompt_extend', '智能改写')}
                          valuePropName="checked"
                          style={{ marginBottom: 0 }}
                          tooltip="开启后模型优化提示词，对简单描述效果更明显"
                        >
                          <Switch defaultChecked />
                        </Form.Item>
                        <Form.Item 
                          name="watermark" 
                          label={renderFormLabel(activeModelId, 'watermark', '添加水印')}
                          valuePropName="checked"
                          style={{ marginBottom: 0 }}
                        >
                          <Switch />
                        </Form.Item>
                      </div>
                      <div style={{ marginTop: 8, padding: '8px', background: token.colorBgElevated, borderRadius: 4, fontSize: 11 }}>
                        <div style={{ color: token.colorTextTertiary }}>
                          • 支持1-3张输入图片，1张为单图编辑，2-3张为多图融合
                        </div>
                        <div style={{ color: token.colorTextTertiary, marginTop: 2 }}>
                          • 多图时用"图1"、"图2"、"图3"指代不同图片，输出比例以最后一张为准
                        </div>
                        <div style={{ color: token.colorTextQuaternary, marginTop: 2 }}>
                          • 当 n &gt; 1 时，size 不生效，平台会按模型默认行为处理输出尺寸
                        </div>
                        <div style={{ color: token.colorTextQuaternary, marginTop: 2 }}>
                          输入图建议：384-3072px，格式 JPG/PNG/BMP/WEBP/TIFF，≤10MB
                        </div>
                      </div>
                    </div>
                  )
                })()}

                {/* qwen-image-2.0 系列参数（文生图+图像编辑融合） */}
                {(() => {
                  const m = watchedModel || selectedTask?.model
                  if (m !== 'qwen-image-2.0-pro' && m !== 'qwen-image-2.0') return null
                  const modelInfo = availableModels[m]
                  const qwen2HasInputImages = ((form.getFieldValue('references') || []).length > 0)
                  const qwen2SizeOptions = [
                    {
                      value: '',
                      label: qwen2HasInputImages
                        ? '不设置尺寸（跟随最后一张输入图分辨率）'
                        : '不设置尺寸（使用模型默认）',
                    },
                    ...(
                      modelInfo?.common_sizes?.map((size: any) => ({
                        value: size.value || (typeof size === 'string' ? size : `${size.width}*${size.height}`),
                        label: size.label || `${size.width}×${size.height}`,
                      })) || [
                        { value: '1024*1024', label: '1024×1024 正方形 1:1' },
                      ]
                    ),
                  ]
                  return (
                    <div style={{ marginBottom: 16 }}>
                      <div style={{ marginBottom: 8, color: token.colorTextSecondary, fontSize: 12 }}>
                        {modelInfo?.name || m} 参数
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                        <Form.Item 
                          name="size" 
                          label={renderFormLabel(activeModelId, 'size', '输出尺寸')}
                          style={{ marginBottom: 0 }}
                        >
                          <Select
                            placeholder={qwen2HasInputImages ? '不设置尺寸（跟随最后一张输入图分辨率）' : '1024×1024（默认）'}
                            allowClear
                            options={qwen2SizeOptions}
                          />
                        </Form.Item>
                        <Form.Item 
                          name="seed" 
                          label={renderFormLabel(activeModelId, 'seed', '随机种子')}
                          style={{ marginBottom: 0 }}
                        >
                          <InputNumber 
                            min={0} 
                            max={2147483647} 
                            style={{ width: '100%' }} 
                            placeholder="留空为随机"
                          />
                        </Form.Item>
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                        <Form.Item 
                          name="prompt_extend" 
                          label={renderFormLabel(activeModelId, 'prompt_extend', '智能改写')}
                          valuePropName="checked"
                          style={{ marginBottom: 0 }}
                          tooltip="开启后模型优化提示词，对简单描述效果更明显"
                        >
                          <Switch defaultChecked />
                        </Form.Item>
                        <Form.Item 
                          name="watermark" 
                          label={renderFormLabel(activeModelId, 'watermark', '添加水印')}
                          valuePropName="checked"
                          style={{ marginBottom: 0 }}
                        >
                          <Switch />
                        </Form.Item>
                      </div>
                      <div style={{ marginTop: 8, padding: '8px', background: token.colorBgElevated, borderRadius: 4, fontSize: 11 }}>
                        <div style={{ color: token.colorTextTertiary }}>
                          • 不添加参考图为文生图模式，添加1-3张参考图为图像编辑模式
                        </div>
                        <div style={{ color: token.colorTextTertiary, marginTop: 2 }}>
                          • 编辑模式下用"图1"、"图2"、"图3"指代不同图片，输出比例以最后一张为准
                        </div>
                        <div style={{ color: token.colorTextTertiary, marginTop: 2 }}>
                          • 单次请求最多生成6张，尺寸范围 512×512 至 2048×2048
                        </div>
                        <div style={{ color: token.colorTextQuaternary, marginTop: 2 }}>
                          输入图建议：384-3072px，格式 JPG/PNG/BMP/WEBP/TIFF/GIF，≤10MB
                        </div>
                      </div>
                    </div>
                  )
                })()}
              
              <Space style={{ width: '100%' }} direction="vertical">
                {isCreating ? (
                  <>
                    <Button 
                      type="primary" 
                      icon={<ThunderboltOutlined />} 
                      onClick={createAndGenerate}
                      block
                    >
                      开始生成
                    </Button>
                    <Button onClick={() => { setIsModalOpen(false); setIsCreating(false); setSelectedStyleId(null); setPreviewPayload(null); }} block>
                      取消
                    </Button>
                  </>
                ) : selectedTask && (
                  <>
                    <Button 
                      type="primary" 
                      icon={<ThunderboltOutlined />} 
                      onClick={generateImages}
                      loading={selectedTask.status === 'generating'}
                      disabled={selectedTask.status === 'generating'}
                      block
                    >
                      {selectedTask.status === 'generating' ? '生成中...' : (selectedTask.images.length > 0 ? '重新生成' : '开始生成')}
                    </Button>
                    <Popconfirm
                      title="确定删除此任务？"
                      onConfirm={() => deleteTask(selectedTask.id)}
                      okText="删除"
                      cancelText="取消"
                      okButtonProps={{ danger: true }}
                    >
                      <Button danger block icon={<DeleteOutlined />}>
                        删除任务
                      </Button>
                    </Popconfirm>
                  </>
                )}
              </Space>
              {renderDeveloperMode()}
            </div>
          </div>
          </Form>
        )}
      </Modal>
    </div>
  )
}

export default StudioPage
