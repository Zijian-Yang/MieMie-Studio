import { api } from './apiClient'
import type { GalleryImage, HelpContent, ModelCapabilities, ModelParameterDef, VideoLibraryItem } from './api'

export type VideoTaskKind =
  | 'image_to_video'
  | 'reference_to_video'
  | 'text_to_video'
  | 'keyframe_to_video'
  | 'video_extension'
  | 'video_edit_global'
  | 'video_edit_local'
  | 'video_repainting'

export type VideoStudioTaskType =
  | 'image_to_video'
  | 'reference_to_video'
  | 'text_to_video'
  | 'keyframe_to_video'
  | 'video_extension'
  | 'video_repainting'
  | 'video_edit'
  | 'video_edit_global'

export type VideoInputRole =
  | 'first_frame'
  | 'last_frame'
  | 'first_clip'
  | 'reference_image'
  | 'reference_video'
  | 'base_video'
  | 'feature_video'
  | 'source_video'
  | 'mask_image'
  | 'audio'

export type VideoNarrativeMode =
  | 'single'
  | 'multi_shot_intelligence'
  | 'multi_shot_customize'

export interface VideoReferenceMediaItem {
  type: 'reference_image' | 'reference_video'
  url: string
  reference_voice?: string
}

export interface VideoStudioInputAssets {
  first_frame?: string[]
  last_frame?: string[]
  first_clip?: string[]
  audio?: string[]
  reference_images?: string[]
  reference_videos?: string[]
  reference_media?: VideoReferenceMediaItem[]
  source_video?: string[]
  base_video?: string[]
  mask_image?: string[]
  [key: string]: any
}

export interface VideoPromptLengthPolicy {
  mode: 'cjk_weighted' | string
  max_units: number
  cjk_unit?: number
  non_cjk_unit?: number
  cjk_equivalent_limit?: number
  non_cjk_equivalent_limit?: number
}

export type VideoReferenceTokenRole = 'reference_image' | 'reference_video'

export interface VideoReferenceTokenVariant {
  key: string
  label: string
  template: string
}

export interface VideoReferenceTokenTemplate {
  template: string
  variants?: VideoReferenceTokenVariant[]
}

export interface VideoReferenceTokenPolicy {
  mode: 'media_reference_tokens' | string
  index_base: number
  numbering_scope: 'by_type' | 'combined'
  reference_order?: VideoReferenceTokenRole[]
  tokens: Partial<Record<VideoReferenceTokenRole, VideoReferenceTokenTemplate>>
}

export interface VideoTaskProfile {
  task_kind: VideoTaskKind
  label: string
  description?: string
  input_roles: VideoInputRole[]
  parameters: ModelParameterDef[]
  ui_hints?: Record<string, any> & {
    asset_help?: Partial<Record<VideoInputRole, HelpContent | string>>
    prompt_help?: HelpContent | string
    prompt_length_policy?: VideoPromptLengthPolicy
    reference_token_policy?: VideoReferenceTokenPolicy
  }
  supported_narrative_modes: VideoNarrativeMode[]
  default_values?: Record<string, any>
  verification_profiles?: Record<string, string[]>
}

export interface VideoCapabilityModel {
  id: string
  name: string
  provider: string
  type: string
  description?: string
  doc_url?: string
  capabilities?: ModelCapabilities
  supported_task_kinds: VideoTaskKind[]
  task_profiles: Partial<Record<VideoTaskKind, VideoTaskProfile>>
  ui_hints?: Record<string, any>
}

export interface VideoTaskKindInfo {
  id: VideoTaskKind
  label: string
  description?: string
  legacy_task_types: string[]
  model_ids: string[]
  default_model_id?: string | null
}

export interface VideoStudioCapabilitiesResponse {
  task_kinds: VideoTaskKindInfo[]
  models: Record<string, VideoCapabilityModel>
  legacy_task_kind_map: Record<string, VideoTaskKind>
}

export interface VideoStudioTask {
  id: string
  project_id: string
  name: string

  // 任务类型: image_to_video / reference_to_video / text_to_video / keyframe_to_video / video_extension / video_repainting / video_edit
  task_type: VideoStudioTaskType
  task_kind: VideoTaskKind
  provider: string
  key_profile?: 'test' | 'production' | null
  model_id?: string
  narrative_mode?: VideoNarrativeMode
  input_assets?: VideoStudioInputAssets
  normalized_params?: Record<string, any>
  provider_payload_snapshot?: Record<string, any> | null
  provider_result_meta?: Record<string, any>

  // 图生视频参数
  mode: 'first_frame' | 'first_last_frame'
  first_frame_url?: string
  last_frame_url?: string
  first_clip_url?: string
  audio_url?: string

  // 参考生视频参数（支持视频和图片，总数≤5）
  reference_video_urls?: string[]  // 参考素材URL列表（视频+图片）

  // VACE 视频编辑参数
  source_video_url?: string
  source_video_preview_url?: string
  reference_image_url?: string
  mask_image_url?: string
  mask_frame_id?: number

  // 通用参数
  prompt: string
  negative_prompt: string
  model: string
  duration: number
  watermark: boolean  // 水印
  seed?: number | null  // 随机种子
  shot_type?: string  // 镜头类型 single/multi
  auto_audio: boolean  // 自动配音

  // 图生视频专用
  resolution: string
  prompt_extend: boolean  // 智能改写
  ratio?: string
  audio_setting?: string

  // 参考生视频专用
  size?: string  // 分辨率（宽*高格式）
  r2v_prompt_extend?: boolean  // 参考生视频提示词改写（已废弃）

  // 文生视频专用
  t2v_prompt_extend?: boolean  // 文生视频智能改写

  // VACE 专用
  control_condition?: string
  strength?: number | null
  mask_type?: string
  expand_ratio?: number | null
  expand_mode?: string

  group_count: number
  video_urls: string[]
  selected_video_url?: string
  thumbnail_url?: string
  video_markers?: Record<string, string[]>  // {video_url: [marker_type, ...]}
  task_ids: string[]
  request_ids?: string[]  // 各组的请求ID（用于追踪）
  status: 'pending' | 'processing' | 'succeeded' | 'failed'
  error_message?: string
  created_at: string
  updated_at: string
}

export const videoStudioApi = {
  list: (projectId: string) => api.get<any, { tasks: VideoStudioTask[] }>('/video-studio', { params: { project_id: projectId } }),
  getCapabilities: () => api.get<any, VideoStudioCapabilitiesResponse>('/video-studio/capabilities'),
  get: (id: string) => api.get<any, VideoStudioTask>(`/video-studio/${id}`),
  getStatus: (id: string) => api.get<any, { task: VideoStudioTask }>(`/video-studio/${id}/status`),
  previewPayload: (data: {
    project_id: string
    name?: string
    task_type?: VideoStudioTaskType
    task_kind?: VideoTaskKind
    provider?: string
    model_id?: string
    narrative_mode?: VideoNarrativeMode
    input_assets?: VideoStudioInputAssets
    normalized_params?: Record<string, any>
    prompt?: string
    negative_prompt?: string
    group_count?: number
    source_video_preview_url?: string
    model?: string
    duration?: number
    resolution?: string
    size?: string
    watermark?: boolean
    auto_audio?: boolean
    shot_type?: string
    prompt_extend?: boolean
    t2v_prompt_extend?: boolean
    seed?: number
    first_frame_url?: string
    last_frame_url?: string
    first_clip_url?: string
    audio_url?: string
    reference_video_urls?: string[]
    source_video_url?: string
    reference_image_url?: string
    mask_image_url?: string
    mask_frame_id?: number
    control_condition?: string
    strength?: number
    mask_type?: string
    expand_ratio?: number
    expand_mode?: string
    ratio?: string
    audio_setting?: string
  }) => api.post<any, {
    canonical_request: Record<string, any>
    provider_payload: Record<string, any> | null
    validation_warnings: string[]
  }>('/video-studio/preview-payload', data),
  prepareSourceVideo: (data: { project_id: string; video_url: string }) =>
    api.post<any, {
      preview_image_data_url: string
      preview_image_url?: string | null
      metadata: {
        width: number
        height: number
        fps: number
        duration: number
        frame_count: number
        file_size: number
        format: string
        warnings: string[]
      }
      warnings: string[]
    }>('/video-studio/prepare-source-video', data),
  uploadMask: (formData: FormData) =>
    api.post<any, { mask_image_url: string; width: number; height: number }>(
      '/video-studio/upload-mask',
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    ),
  create: (data: {
    project_id: string
    name?: string
    task_type?: VideoStudioTaskType
    task_kind?: VideoTaskKind
    provider?: string
    model_id?: string
    narrative_mode?: VideoNarrativeMode
    input_assets?: VideoStudioInputAssets
    normalized_params?: Record<string, any>
    mode?: string
    first_frame_url?: string  // 图生视频需要
    last_frame_url?: string
    first_clip_url?: string
    audio_url?: string  // 自定义音频URL（图生视频/文生视频支持）
    // 参考生视频参数
    reference_video_urls?: string[]  // 参考生视频的参考素材（视频+图片）
    // VACE 参数
    source_video_url?: string
    source_video_preview_url?: string
    reference_image_url?: string
    mask_image_url?: string
    mask_frame_id?: number
    // 通用参数
    prompt?: string
    negative_prompt?: string
    model?: string
    duration?: number
    watermark?: boolean  // 水印
    seed?: number  // 随机种子
    shot_type?: string  // 镜头类型
    auto_audio?: boolean  // 自动配音
    // 图生视频专用
    resolution?: string
    prompt_extend?: boolean  // 智能改写
    ratio?: string
    audio_setting?: string
    // 参考生视频专用
    size?: string  // 分辨率（宽*高格式）
    r2v_prompt_extend?: boolean  // 参考生视频提示词改写（已废弃）
    // 文生视频专用
    t2v_prompt_extend?: boolean  // 文生视频智能改写
    // VACE 专用
    control_condition?: string
    strength?: number
    mask_type?: string
    expand_ratio?: number
    expand_mode?: string
    group_count?: number
  }) => api.post<any, { task: VideoStudioTask }>('/video-studio', data),
  update: (id: string, data: {
    name?: string
    selected_video_url?: string
    task_type?: VideoStudioTaskType
    task_kind?: VideoTaskKind
    provider?: string
    model_id?: string
    narrative_mode?: VideoNarrativeMode
    input_assets?: VideoStudioInputAssets
    normalized_params?: Record<string, any>
    prompt?: string
    negative_prompt?: string
    model?: string
    resolution?: string
    duration?: number
    prompt_extend?: boolean
    watermark?: boolean
    seed?: number
    auto_audio?: boolean
    shot_type?: string  // 镜头类型
    first_frame_url?: string
    last_frame_url?: string
    first_clip_url?: string
    audio_url?: string
    reference_video_urls?: string[]  // 参考素材URL列表（视频+图片）
    size?: string  // 分辨率（宽*高格式）
    ratio?: string
    audio_setting?: string
    r2v_prompt_extend?: boolean  // 参考生视频提示词改写（已废弃）
    t2v_prompt_extend?: boolean  // 文生视频智能改写
    group_count?: number
    source_video_url?: string
    source_video_preview_url?: string
    reference_image_url?: string
    mask_image_url?: string
    mask_frame_id?: number
    control_condition?: string
    strength?: number
    mask_type?: string
    expand_ratio?: number
    expand_mode?: string
  }) =>
    api.put<any, VideoStudioTask>(`/video-studio/${id}`, data),
  regenerate: (id: string) =>
    api.post<any, { task: VideoStudioTask; task_ids: string[] }>(`/video-studio/${id}/regenerate`),
  saveToLibrary: (id: string, videoUrl: string, name?: string) =>
    api.post<any, { message: string; video: VideoLibraryItem }>(`/video-studio/${id}/save-to-library`, null, { params: { video_url: videoUrl, name } }),
  updateVideoMarkers: (taskId: string, videoUrl: string, markers: string[]) =>
    api.post<any, { success: boolean; video_markers: Record<string, string[]> }>(`/video-studio/${taskId}/markers`, { video_url: videoUrl, markers }),
  extractLastFrame: (taskId: string, videoUrl: string, name?: string) =>
    api.post<any, { message: string; image: GalleryImage }>(`/video-studio/${taskId}/extract-last-frame`, { video_url: videoUrl, name }),
  delete: (id: string) => api.delete(`/video-studio/${id}`),
  deleteAll: (projectId: string) => api.delete(`/video-studio?project_id=${projectId}`),
}
