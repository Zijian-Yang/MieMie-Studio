import type { VideoStudioTask, VideoTaskKind } from '../../services/api'

export const TASK_KIND_META: Record<VideoTaskKind, { color: string; text: string }> = {
  image_to_video: { color: 'blue', text: '图生视频' },
  reference_to_video: { color: 'green', text: '参考生视频' },
  text_to_video: { color: 'purple', text: '文生视频' },
  keyframe_to_video: { color: 'orange', text: '首尾帧生视频' },
  video_extension: { color: 'gold', text: '视频续写' },
  video_repainting: { color: 'cyan', text: '视频重绘' },
  video_edit_local: { color: 'magenta', text: '局部编辑' },
  video_edit_global: { color: 'geekblue', text: '视频编辑' },
}

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

export const getResolvedTaskKind = (task: VideoStudioTask): VideoTaskKind => {
  const rawTaskType = task.task_type || 'image_to_video'
  const rawTaskKind = task.task_kind
  if (rawTaskKind && !(rawTaskKind === 'image_to_video' && rawTaskType !== 'image_to_video')) {
    return rawTaskKind
  }
  return LEGACY_TASK_KIND_MAP[rawTaskType] || 'image_to_video'
}

export const getTaskInputAssets = (task: VideoStudioTask) => {
  if (task.input_assets && Object.keys(task.input_assets).length > 0) {
    const inputAssets = { ...task.input_assets }
    const referenceMedia = Array.isArray(inputAssets.reference_media) ? inputAssets.reference_media : []
    if (referenceMedia.length > 0) {
      inputAssets.reference_images = referenceMedia
        .filter((item: any) => item?.type === 'reference_image')
        .map((item: any) => item.url)
      inputAssets.reference_videos = referenceMedia
        .filter((item: any) => item?.type === 'reference_video')
        .map((item: any) => item.url)
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

export const getTaskNormalizedParams = (task: VideoStudioTask) => {
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

export const getTaskSummaryLine = (task: VideoStudioTask) => {
  const params = getTaskNormalizedParams(task)
  const parts = [task.model_id || task.model]
  if (task.provider) parts.push(task.provider.toUpperCase())
  if (params.size) parts.push(String(params.size))
  else if (params.resolution) parts.push(String(params.resolution))
  if (task.duration) parts.push(`${task.duration}秒`)
  return parts.filter(Boolean).join(' · ')
}

export const getTaskParameterEntries = (task: VideoStudioTask) => {
  const params = getTaskNormalizedParams(task)
  return Object.entries(params)
    .filter(([key, value]) => PARAM_LABELS[key] && value !== undefined && value !== null && value !== '')
    .map(([key, value]) => ({
      key,
      label: PARAM_LABELS[key],
      value: formatTaskParamValue(key, value),
    }))
}

export const getTaskPreviewUrl = (task: VideoStudioTask) => (
  task.thumbnail_url || task.first_frame_url || task.source_video_preview_url || ''
)
