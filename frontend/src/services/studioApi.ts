import { api } from './apiClient'
import type { GalleryImage } from './api'

export interface ReferenceItem {
  type: 'character' | 'scene' | 'prop' | 'gallery' | 'style'
  id: string
  name: string
  url?: string
}

export interface ColorPaletteItem {
  hex: string
  ratio: string
}

export interface StudioTaskImage {
  id: string
  group_index: number
  url?: string
  storage_source?: 'remote' | 'oss' | 'local_fallback' | 'local_expired'
  storage_warning?: string | null
  retry_count?: number
  last_retry_error?: string | null
  last_retry_at?: string | null
  next_retry_at?: string | null
  fallback_created_at?: string | null
  prompt_used?: string
  is_selected: boolean
  markers?: string[]  // star, flag, check, cross
  created_at: string
}

export interface StudioTask {
  id: string
  project_id: string
  name: string
  description: string
  model: string
  model_id?: string
  provider?: string
  task_kind?: 'text_to_image' | 'image_edit' | 'interactive_edit' | 'sequential_generation'
  prompt: string
  negative_prompt: string
  n: number  // 每次请求生成的图片数量
  group_count: number  // 并发请求数（总图片数 = n * group_count）
  // 高级生成参数（持久化保存）
  size?: string  // 输出尺寸
  prompt_extend?: boolean  // 智能改写
  watermark?: boolean  // 水印
  seed?: number  // 随机种子
  // wan2.6-image 专用参数
  enable_interleave?: boolean  // 图文混合模式
  max_images?: number  // 图文混合模式下最大生成图数
  // wan2.7 专用参数
  enable_sequential?: boolean
  thinking_mode?: boolean | null
  bbox_list?: number[][][]
  color_palette?: ColorPaletteItem[]
  size_mode?: 'preset' | 'custom' | null
  size_preset?: string | null
  custom_width?: number | null
  custom_height?: number | null
  output_format?: 'jpeg' | 'png' | null
  web_search?: boolean
  aspect_ratio?: string | null
  image_size?: string | null
  google_search_mode?: 'none' | 'web' | 'image' | 'web_and_image' | string
  thinking_level?: 'minimal' | 'high' | string | null
  // 追踪ID
  last_task_id?: string
  last_request_id?: string
  task_ids?: string[]
  request_ids?: string[]
  input_assets?: Record<string, any>
  normalized_params?: Record<string, any>
  provider_payload_snapshot?: Record<string, any> | null
  provider_result_meta?: Record<string, any>
  references: ReferenceItem[]
  images: StudioTaskImage[]
  status: 'pending' | 'generating' | 'completed' | 'failed'
  error_message?: string
  warnings?: string[]
  created_at: string
  updated_at: string
}

export interface StudioOSSRetrySummary {
  retried_task_count?: number
  retried_image_count: number
  success_count: number
  failed_count: number
  paused_count: number
  expired_count: number
}

export const studioApi = {
  list: (projectId: string) => api.get<any, { tasks: StudioTask[] }>('/studio', { params: { project_id: projectId } }),
  get: (id: string) => api.get<any, StudioTask>(`/studio/${id}`),
  create: (data: {
    project_id: string
    name: string
    description?: string
    model?: string
    prompt?: string
    negative_prompt?: string
    n?: number
    group_count?: number
    size?: string
    prompt_extend?: boolean
    watermark?: boolean
    seed?: number
    enable_interleave?: boolean
    max_images?: number
    task_kind?: 'text_to_image' | 'image_edit' | 'interactive_edit' | 'sequential_generation'
    enable_sequential?: boolean
    thinking_mode?: boolean | null
    bbox_list?: number[][][]
    color_palette?: ColorPaletteItem[]
    size_mode?: 'preset' | 'custom'
    size_preset?: string
    custom_width?: number
    custom_height?: number
    output_format?: 'jpeg' | 'png' | null
    web_search?: boolean
    aspect_ratio?: string | null
    image_size?: string | null
    google_search_mode?: 'none' | 'web' | 'image' | 'web_and_image' | string
    thinking_level?: 'minimal' | 'high' | string | null
    references?: Array<{ type: string, id: string }>
  }) => api.post<any, StudioTask>('/studio', data),
  update: (id: string, data: Partial<StudioTask>) => api.put<any, StudioTask>(`/studio/${id}`, data),
  generate: (id: string, data?: {
    prompt?: string
    negative_prompt?: string
    n?: number  // 每次请求生成的图片数量
    group_count?: number  // 并发请求数（总图片数 = n * group_count）
    task_kind?: 'text_to_image' | 'image_edit' | 'interactive_edit' | 'sequential_generation'
    // 通用参数
    size?: string  // 输出尺寸
    prompt_extend?: boolean  // 智能改写
    watermark?: boolean  // 水印
    seed?: number | null  // 随机种子
    // wan2.6-image 专用参数
    enable_interleave?: boolean  // 图文混合模式
    max_images?: number  // 图文混合模式下最大图片数 (1-5)
    // wan2.7 专用参数
    enable_sequential?: boolean
    thinking_mode?: boolean | null
    bbox_list?: number[][][]
    color_palette?: ColorPaletteItem[]
    size_mode?: 'preset' | 'custom'
    size_preset?: string
    custom_width?: number
    custom_height?: number
    output_format?: 'jpeg' | 'png' | null
    web_search?: boolean
    aspect_ratio?: string | null
    image_size?: string | null
    google_search_mode?: 'none' | 'web' | 'image' | 'web_and_image' | string
    thinking_level?: 'minimal' | 'high' | string | null
  }) => api.post<any, { task: StudioTask }>(`/studio/${id}/generate`, data || {}),
  previewPayload: (data: {
    project_id: string
    model: string
    task_kind?: 'text_to_image' | 'image_edit' | 'interactive_edit' | 'sequential_generation'
    prompt?: string
    negative_prompt?: string
    n?: number
    group_count?: number
    size?: string
    prompt_extend?: boolean
    watermark?: boolean
    seed?: number | null
    enable_interleave?: boolean
    max_images?: number
    enable_sequential?: boolean
    thinking_mode?: boolean | null
    bbox_list?: number[][][]
    color_palette?: ColorPaletteItem[]
    size_mode?: 'preset' | 'custom'
    size_preset?: string
    custom_width?: number
    custom_height?: number
    output_format?: 'jpeg' | 'png' | null
    web_search?: boolean
    aspect_ratio?: string | null
    image_size?: string | null
    google_search_mode?: 'none' | 'web' | 'image' | 'web_and_image' | string
    thinking_level?: 'minimal' | 'high' | string | null
    references?: Array<{ type: string, id: string }>
  }, options?: { signal?: AbortSignal }) => api.post<any, {
    canonical_request: Record<string, any>
    provider_payload: Record<string, any>
    validation_warnings: string[]
  }>('/studio/preview-payload', data, { signal: options?.signal }),
  saveToGallery: (id: string, imageIds: string[]) => api.post<any, { saved_images: GalleryImage[] }>(`/studio/${id}/save-to-gallery`, { image_ids: imageIds }),
  updateImageMarkers: (taskId: string, imageId: string, markers: string[]) =>
    api.post<any, { success: boolean; markers: string[] }>(`/studio/${taskId}/markers`, { image_id: imageId, markers }),
  retryTaskOSS: (id: string) => api.post<any, { task: StudioTask; summary: StudioOSSRetrySummary }>(`/studio/${id}/retry-oss`),
  retryProjectOSS: (projectId: string) => api.post<any, { tasks: StudioTask[]; summary: StudioOSSRetrySummary }>(`/studio/project/${projectId}/retry-oss`),
  delete: (id: string) => api.delete(`/studio/${id}`),
  deleteAll: (projectId: string) => api.delete(`/studio/project/${projectId}/all`),
  // 获取可用模型列表（带详情）
  getAvailableModels: () => api.get<any, {
    models: Record<string, {
      id: string
      name: string
      provider?: string
      description?: string
      supported_task_kinds?: Array<'text_to_image' | 'image_edit' | 'interactive_edit' | 'sequential_generation'>
      size_ui_mode?: 'preset_only' | 'preset_plus_custom_with_templates'
      capabilities?: {
        supports_batch?: boolean
        supports_async?: boolean
        supports_negative_prompt?: boolean
        max_concurrent?: number | null
        api_mode?: 'sync' | 'async'
        submit_rate_limit?: { count: number; period_seconds: number }
        concurrency_scope?: 'model' | 'shared_pool' | 'unlimited' | 'unknown'
        concurrency_pool_id?: string
        rate_limit_note?: string
      }
      parameters?: Array<{
        name: string
        label: string
        type: string
        description?: string
        default?: any
        constraint?: {
          min_value?: number
          max_value?: number
          options?: Array<{ value: any; label: string }>
        }
      }>
    }>
  }>('/studio/models/available'),
}
