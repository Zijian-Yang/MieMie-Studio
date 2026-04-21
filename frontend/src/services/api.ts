import axios from 'axios'

export interface ApiError extends Error {
  data?: any
  status?: number
}

// 创建 axios 实例
const api = axios.create({
  baseURL: '/api',
  timeout: 360000, // 6分钟超时，支持长时间图片生成任务
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器 - 自动添加认证 token
api.interceptors.request.use(
  (config) => {
    // 从 localStorage 获取 token
    const authStorage = localStorage.getItem('auth-storage')
    if (authStorage) {
      try {
        const { state } = JSON.parse(authStorage)
        if (state?.token) {
          config.headers.Authorization = `Bearer ${state.token}`
        }
      } catch (e) {
        // ignore
      }
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    // 401 未授权，清除本地认证状态
    if (error.response?.status === 401) {
      localStorage.removeItem('auth-storage')
      // 如果不在登录页，跳转到登录页
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    const message = error.response?.data?.detail || error.message || '请求失败'
    const enhancedError = new Error(
      typeof message === 'string' ? message : '请求失败'
    ) as ApiError
    enhancedError.data = error.response?.data
    enhancedError.status = error.response?.status
    return Promise.reject(enhancedError)
  }
)

// ============ 设置 API ============

export interface LLMModelInfo {
  name: string
  max_output_tokens: number
  supports_thinking: boolean
  supports_search: boolean
  supports_json_mode: boolean
}

export interface ImageModelSizeOption {
  width: number
  height: number
  label: string
}

export interface ImageModelInfo {
  name: string
  description?: string
  min_pixels: number
  max_pixels: number
  min_ratio: number
  max_ratio: number
  use_http?: boolean  // 是否使用 HTTP 同步调用
  is_async?: boolean  // 是否异步调用（需要轮询）
  max_n?: number  // 最多生成图片数量
  default_n?: number  // 默认生成数量
  supports_prompt_extend?: boolean
  supports_watermark?: boolean  // 是否支持水印
  supports_seed?: boolean
  supports_negative_prompt?: boolean
  supports_reference_images?: boolean  // wan2.6-image：支持参考图
  supports_interleave?: boolean  // wan2.6-image：支持图文混合输出
  max_reference_images?: number  // wan2.6-image：最大参考图数量 (enable_interleave=false)
  max_reference_images_interleave?: number  // wan2.6-image：图文混合模式最大参考图数量
  min_reference_images?: number  // 最少参考图数量
  supports_max_images?: boolean  // wan2.6-image：支持 max_images 参数
  max_images_range?: [number, number]  // max_images 参数范围
  default_max_images?: number  // max_images 默认值
  common_sizes: ImageModelSizeOption[]
  model_type?: string  // 模型类型：text_to_image / image_to_image
  // 图像尺寸限制
  image_min_dimension?: number  // 参考图最小边长
  image_max_dimension?: number  // 参考图最大边长
  image_max_size_mb?: number  // 参考图最大文件大小(MB)
  supported_formats?: string[]  // 支持的图片格式
}

export interface VideoResolutionOption {
  value: string
  label: string
}

export interface VideoModelInfo {
  id?: string
  name: string
  description?: string
  resolutions: VideoResolutionOption[]
  default_resolution: string
  durations?: number[]  // 支持的时长列表（固定选项）
  duration_range?: [number, number]  // 连续时长范围 [min, max]（如 wan2.6-i2v-flash 的 [2, 15]）
  default_duration?: number
  supports_prompt?: boolean  // 是否支持提示词（默认 true，wan2.2-s2v 为 false）
  supports_prompt_extend?: boolean
  supports_watermark?: boolean
  supports_seed?: boolean
  supports_negative_prompt?: boolean
  supports_audio?: boolean  // 是否支持音频参数
  supports_audio_toggle?: boolean  // 是否支持有声/无声切换（仅 wan2.6-i2v-flash）
  requires_audio?: boolean  // 音频是否为必填项（wan2.2-s2v）
  default_audio?: boolean  // 默认是否开启自动配音
  supports_shot_type?: boolean  // 是否支持镜头类型（仅wan2.6）
  default_shot_type?: string  // 默认镜头类型
  supports_duration?: boolean  // 是否支持时长设置（默认 true，wan2.2-s2v 为 false）
  image_param?: string
}

export interface RegionInfo {
  name: string
  base_url: string
}

export interface LLMConfig {
  model: string
  max_tokens: number
  top_p: number
  temperature: number
  enable_thinking: boolean
  thinking_budget: number
  result_format: string
  enable_search: boolean
}

export interface ImageConfig {
  model: string
  width: number
  height: number
  prompt_extend: boolean
  watermark: boolean  // 水印（仅 wan2.6-t2i 支持）
  seed: number | null
}

export interface ImageEditConfig {
  model: string
  width: number
  height: number
  prompt_extend: boolean
  watermark: boolean  // 水印（仅 qwen-image-edit-plus 支持）
  seed: number | null
}

export interface VideoConfig {
  model: string
  resolution: string  // 分辨率（wan2.5用480P/720P/1080P，wanx2.1用宽*高）
  prompt_extend: boolean
  watermark: boolean
  seed: number | null
  duration: number  // 视频时长（秒）
  audio: boolean    // 是否自动生成音频（仅wan2.5支持）
}

// 文生视频配置
export interface TextToVideoConfig {
  model: string
  size: string  // 分辨率（宽*高格式，如 1920*1080）
  duration: number  // 视频时长（秒）
  prompt_extend: boolean  // 智能改写
  shot_type: string  // 镜头类型，single/multi
  watermark: boolean  // 水印
  seed: number | null  // 随机种子
  audio: boolean  // 是否自动配音
}

// 参考生视频配置
export interface RefVideoConfig {
  model: string
  size: string  // 分辨率（宽*高格式，如 1920*1080），默认1080P 16:9
  duration: number  // 视频时长（2-10秒整数）
  shot_type: string  // 镜头类型，single/multi
  watermark: boolean  // 水印
  seed: number | null  // 随机种子
}

// 文生视频模型信息
export interface TextToVideoModelInfo {
  name: string
  description?: string
  resolutions?: VideoResolutionOption[]
  resolutions_480p?: VideoResolutionOption[]
  resolutions_720p?: VideoResolutionOption[]
  resolutions_1080p?: VideoResolutionOption[]
  default_size: string
  durations?: number[]  // 支持的时长列表（离散）
  duration_range?: number[]  // 连续时长范围 [min, max]
  default_duration: number
  prompt_max_length?: number  // 提示词最大长度
  negative_prompt_max_length?: number  // 反向提示词最大长度
  supports_prompt_extend: boolean
  supports_shot_type: boolean
  default_shot_type?: string
  supports_watermark: boolean
  supports_seed: boolean
  supports_negative_prompt: boolean
  supports_audio: boolean
  default_audio: boolean
  audio_formats?: string[]  // 支持的音频格式
  audio_duration_range?: string  // 音频时长范围
  audio_max_size_mb?: number  // 音频最大文件大小
}

// 首尾帧生视频模型信息
export interface KeyframeToVideoModelInfo {
  name: string
  description?: string
  resolutions: string[]  // 支持的分辨率档位列表 ["480P", "720P", "1080P"]
  default_resolution: string  // 默认分辨率档位
  duration: number  // 固定时长（秒）
  prompt_max_length?: number  // 提示词最大长度
  negative_prompt_max_length?: number  // 反向提示词最大长度
  supports_prompt_extend: boolean
  supports_watermark: boolean
  supports_seed: boolean
  supports_negative_prompt: boolean
  supports_audio: boolean  // 是否支持音频（wan2.2不支持）
}

// 参考生视频模型信息
export interface RefVideoModelInfo {
  name: string
  description?: string
  resolutions?: VideoResolutionOption[]
  resolutions_720p: VideoResolutionOption[]
  resolutions_1080p: VideoResolutionOption[]
  default_size: string
  default_resolution?: string
  min_duration?: number
  max_duration?: number
  default_duration: number
  supports_shot_type: boolean
  default_shot_type: string
  supports_watermark: boolean
  supports_seed: boolean
  supports_negative_prompt: boolean
  supports_audio: boolean
  supports_audio_toggle?: boolean
  default_audio: boolean
  // 参考素材限制
  max_reference_images?: number  // 最多支持的参考图片数量（5）
  max_reference_videos?: number  // 最多支持的参考视频数量（3）
  max_reference_total?: number  // 图片+视频总数限制（5）
  reference_video_duration: string  // 参考视频时长要求
  reference_video_max_size: string  // 单个视频最大大小
}

export interface VaceVideoRepaintingModelInfo {
  name: string
  description?: string
  prompt_max_length: number
  supports_prompt_extend: boolean
  supports_watermark: boolean
  supports_seed: boolean
  supported_control_conditions: string[]
  default_control_condition: string
  strength_range: [number, number]
  default_strength: number
  max_reference_images: number
  supported_image_formats: string[]
  image_min_dimension: number
  image_max_dimension: number
  image_max_size_mb: number
  supported_video_formats: string[]
  video_min_fps: number
  video_max_size_mb: number
  video_max_duration_sec: number
  output_max_pixels: number
  supports_audio: boolean
}

export interface VaceVideoEditModelInfo {
  name: string
  description?: string
  prompt_max_length: number
  supports_prompt_extend: boolean
  supports_watermark: boolean
  supports_seed: boolean
  supported_control_conditions: string[]
  supported_mask_types: string[]
  default_mask_type: string
  expand_ratio_range: [number, number]
  default_expand_ratio: number
  supported_expand_modes: string[]
  default_expand_mode: string
  sizes: VideoResolutionOption[]
  default_size: string
  mask_frame_id_min: number
  max_reference_images: number
  supported_image_formats: string[]
  image_min_dimension: number
  image_max_dimension: number
  image_max_size_mb: number
  mask_max_size_mb: number
  supported_video_formats: string[]
  video_min_fps: number
  video_max_size_mb: number
  video_max_duration_sec: number
  output_max_pixels: number
  supports_audio: boolean
}

// OSS 配置
export interface OSSConfig {
  enabled: boolean
  access_key_id: string
  access_key_secret: string
  bucket_name: string
  endpoint: string
  prefix: string
}

export interface OSSConfigResponse {
  enabled: boolean
  access_key_id_masked: string
  access_key_secret_masked: string
  is_configured: boolean
  bucket_name: string
  endpoint: string
  prefix: string
}

export interface ConfigResponse {
  api_key_masked: string
  is_api_key_set: boolean
  test_api_key_masked: string
  is_test_api_key_set: boolean
  production_api_key_masked: string
  is_production_api_key_set: boolean
  wan_key_profile: 'test' | 'production'
  kling_key_profile: 'test' | 'production'
  vidu_key_profile: 'test' | 'production'
  video_task_notifications_enabled: boolean
  image_task_notifications_enabled: boolean
  api_region: string
  base_url: string
  llm: LLMConfig
  image: ImageConfig
  image_edit: ImageEditConfig
  video: VideoConfig
  text_to_video: TextToVideoConfig  // 文生视频配置
  ref_video: RefVideoConfig  // 参考生视频配置
  oss: OSSConfigResponse
  available_regions: Record<string, RegionInfo>
  available_llm_models: Record<string, LLMModelInfo>
  available_image_models: Record<string, ImageModelInfo>
  available_image_edit_models: Record<string, ImageModelInfo>
  available_video_models: Record<string, VideoModelInfo>
  available_text_to_video_models: Record<string, TextToVideoModelInfo>  // 文生视频模型
  available_ref_video_models: Record<string, RefVideoModelInfo>  // 参考生视频模型
  available_keyframe_to_video_models: Record<string, KeyframeToVideoModelInfo>  // 首尾帧生视频模型
  available_video_repainting_models: Record<string, VaceVideoRepaintingModelInfo>  // 视频重绘模型
  available_video_edit_models: Record<string, VaceVideoEditModelInfo>  // 局部编辑模型
}

export interface ConfigUpdateRequest {
  api_key?: string
  test_api_key?: string
  production_api_key?: string
  wan_key_profile?: 'test' | 'production'
  kling_key_profile?: 'test' | 'production'
  vidu_key_profile?: 'test' | 'production'
  video_task_notifications_enabled?: boolean
  image_task_notifications_enabled?: boolean
  api_region?: string
  llm?: Partial<LLMConfig>
  image?: Partial<ImageConfig>
  image_edit?: Partial<ImageEditConfig>
  video?: Partial<VideoConfig>
  text_to_video?: Partial<TextToVideoConfig>  // 文生视频配置
  ref_video?: Partial<RefVideoConfig>  // 参考生视频配置
  oss?: Partial<OSSConfig>
}

export const settingsApi = {
  getSettings: () => api.get<any, ConfigResponse>('/settings'),
  updateSettings: (data: ConfigUpdateRequest) => api.put('/settings', data),
  setApiKey: (apiKey: string) => api.post('/settings/api-key', { api_key: apiKey }),
  deleteApiKey: () => api.delete('/settings/api-key'),
  testOSSConnection: () => api.post<any, { success: boolean; message: string }>('/settings/oss/test'),
}

// ============ 项目 API ============

// 项目级别的 LLM 配置
export interface ProjectLLMConfig {
  model?: string
  max_tokens?: number | null
  top_p?: number | null
  temperature?: number | null
  enable_thinking?: boolean | null
  thinking_budget?: number | null
  result_format?: string | null
  enable_search?: boolean | null
}

export interface Project {
  id: string
  name: string
  description: string
  script?: Script
  character_ids: string[]
  scene_ids: string[]
  prop_ids: string[]
  llm_configs?: Record<string, ProjectLLMConfig>  // key 为模型名称
  created_at: string
  updated_at: string
}

export interface Script {
  id: string
  title: string
  original_content: string
  processed_content: string
  model_used?: string
  prompt_used?: string
  custom_prompt?: string
  shots: Shot[]
  script_versions?: ScriptVersion[]
  prompt_versions?: PromptVersion[]
  created_at: string
  updated_at: string
}

export interface Shot {
  id: string
  shot_number: number
  shot_design: string
  scene_type: string
  voice_subject: string
  dialogue: string
  characters: string[]
  character_appearance: string
  character_action: string
  scene_setting: string
  lighting: string
  mood: string
  composition: string
  props: string[]
  sound_effects: string
  duration: number
  // 关联的素材ID
  character_ids: string[]
  scene_id?: string
  prop_ids: string[]
  // 生成的素材
  first_frame_url?: string
  video_url?: string
  selected_video_id?: string
  video_prompt?: string
  audio_url?: string
}

export const projectsApi = {
  list: () => api.get<any, { projects: Project[]; total: number }>('/projects'),
  get: (id: string) => api.get<any, Project>(`/projects/${id}`),
  create: (data: { name: string; description?: string }) => api.post<any, Project>('/projects', data),
  update: (id: string, data: { name?: string; description?: string }) => api.put<any, Project>(`/projects/${id}`, data),
  delete: (id: string) => api.delete(`/projects/${id}`),
  getSummary: (id: string) => api.get(`/projects/${id}/summary`),
  // 项目级 LLM 配置
  getLLMConfigs: (id: string) => api.get<any, { llm_configs: Record<string, ProjectLLMConfig> }>(`/projects/${id}/llm-configs`),
  getLLMConfig: (id: string, model: string) => api.get<any, { model: string; config: ProjectLLMConfig }>(`/projects/${id}/llm-configs/${model}`),
  updateLLMConfig: (id: string, model: string, config: ProjectLLMConfig) => api.put(`/projects/${id}/llm-configs/${model}`, config),
  deleteLLMConfig: (id: string, model: string) => api.delete(`/projects/${id}/llm-configs/${model}`),
}

// ============ 分镜脚本 API ============

export interface ShotCreateRequest {
  shot_design?: string
  scene_type?: string
  voice_subject?: string
  dialogue?: string
  characters?: string[]
  character_appearance?: string
  character_action?: string
  scene_setting?: string
  lighting?: string
  mood?: string
  composition?: string
  props?: string[]
  sound_effects?: string
  duration?: number
  insert_after_shot_id?: string
}

// 剧本版本接口
export interface ScriptVersion {
  id: string
  name: string
  description: string
  content: string
  original_content: string
  model_used?: string
  prompt_used?: string
  created_at: string
}

export interface PromptVersion {
  id: string
  name: string
  description: string
  prompt: string
  created_at: string
}

export const scriptsApi = {
  get: (projectId: string) => api.get<any, Script>(`/scripts/${projectId}`),
  upload: (projectId: string, file: File) => {
    const formData = new FormData()
    formData.append('project_id', projectId)
    formData.append('file', file)
    return api.post('/scripts/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  save: (data: {
    project_id: string
    content: string
    model_used?: string
    prompt_used?: string
  }) => api.post('/scripts/save', data),
  parseShots: (projectId: string) => api.post(`/scripts/${projectId}/parse-shots`),
  updateShots: (projectId: string, shots: Shot[]) => api.put(`/scripts/${projectId}/shots`, { shots }),
  updateShot: (projectId: string, shotId: string, data: Partial<Shot>) => 
    api.put<any, { shot: Shot }>(`/scripts/${projectId}/shots/${shotId}`, data),
  reorderShots: (projectId: string, shotIds: string[]) => 
    api.put<any, { shots: Shot[] }>(`/scripts/${projectId}/shots-reorder`, { shot_ids: shotIds }),
  createShot: (projectId: string, data: ShotCreateRequest) => 
    api.post<any, { shot: Shot; shots: Shot[] }>(`/scripts/${projectId}/shots`, data),
  deleteShot: (projectId: string, shotId: string) => 
    api.delete<any, { message: string; shots: Shot[] }>(`/scripts/${projectId}/shots/${shotId}`),
  getDefaultPrompt: () => api.get<any, { prompt: string }>('/scripts/prompts/default'),
  
  // 版本管理
  getScriptVersions: (projectId: string) => 
    api.get<any, { versions: ScriptVersion[] }>(`/scripts/${projectId}/script-versions`),
  createScriptVersion: (projectId: string, data: {
    name: string
    description?: string
    content: string
    original_content?: string
    model_used?: string
    prompt_used?: string
  }) => api.post<any, { version: ScriptVersion; versions: ScriptVersion[] }>(`/scripts/${projectId}/script-versions`, data),
  
  getPromptVersions: (projectId: string) => 
    api.get<any, { versions: PromptVersion[] }>(`/scripts/${projectId}/prompt-versions`),
  createPromptVersion: (projectId: string, data: {
    name: string
    description?: string
    prompt: string
  }) => api.post<any, { version: PromptVersion; versions: PromptVersion[] }>(`/scripts/${projectId}/prompt-versions`, data),
  
  saveCustomPrompt: (projectId: string, customPrompt: string) => 
    api.put(`/scripts/${projectId}/custom-prompt`, { custom_prompt: customPrompt }),
}

// 获取认证头（用于 fetch 请求）
const getAuthHeaders = (): Record<string, string> => {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json'
  }
  const authStorage = localStorage.getItem('auth-storage')
  if (authStorage) {
    try {
      const { state } = JSON.parse(authStorage)
      if (state?.token) {
        headers['Authorization'] = `Bearer ${state.token}`
      }
    } catch (e) {
      // ignore
    }
  }
  return headers
}

// SSE 流式生成
export const generateScriptStream = (
  projectId: string,
    content: string,
    model: string,
  prompt?: string,
  onMessage: (content: string) => void = () => {},
  onDone: () => void = () => {},
  onError: (error: string) => void = () => {}
) => {
  const controller = new AbortController()
  
  fetch('/api/scripts/generate', {
      method: 'POST',
      headers: getAuthHeaders(),
    body: JSON.stringify({ project_id: projectId, content, model, prompt }),
    signal: controller.signal,
  })
    .then(async (response) => {
      // 检查认证错误
      if (response.status === 401) {
        onError('未登录或登录已过期，请重新登录')
        return
      }
      
      if (!response.ok) {
        const errorText = await response.text()
        onError(`请求失败: ${response.status} - ${errorText}`)
        return
      }
      
      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      
      if (!reader) {
        onError('无法读取响应')
        return
      }

    while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const text = decoder.decode(value)
        const lines = text.split('\n')

      for (const line of lines) {
        if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              if (data.content) {
                onMessage(data.content)
              }
              if (data.done) {
                onDone()
              }
              if (data.error) {
                onError(data.error)
              }
            } catch {
              // 忽略解析错误
            }
          }
        }
      }
    })
    .catch((error) => {
      if (error.name !== 'AbortError') {
        onError(error.message)
      }
    })
  
  return () => controller.abort()
}

// ============ 角色 API ============

export interface CharacterImage {
  id: string
  group_index: number
  front_url?: string
  side_url?: string
  back_url?: string
  prompt_used?: string
  created_at: string
}

export interface Character {
  id: string
  project_id: string
  name: string
  description: string
  appearance: string
  personality: string
  common_prompt: string
  character_prompt: string
  negative_prompt: string  // 负向提示词
  image_groups: CharacterImage[]
  selected_group_index: number
  voice: {
    voice_id?: string
    custom_audio_url?: string
    test_text: string
  }
  // 追踪ID
  last_task_id?: string  // DashScope 任务ID
  last_request_id?: string  // DashScope 请求ID
  created_at: string
  updated_at: string
}

export const charactersApi = {
  list: (projectId: string) => api.get<any, { characters: Character[] }>('/characters', { params: { project_id: projectId } }),
  get: (id: string) => api.get<any, Character>(`/characters/${id}`),
  create: (data: {
    project_id: string
    name: string
    description?: string
    appearance?: string
    personality?: string
    common_prompt?: string
    character_prompt?: string
    negative_prompt?: string
  }) => api.post<any, { character: Character }>('/characters/create', data),
  extract: (projectId: string) => api.post<any, { characters: Character[] }>('/characters/extract', { project_id: projectId }),
  update: (id: string, data: Partial<Character>) => api.put<any, Character>(`/characters/${id}`, data),
  selectImages: (id: string, data: {
    image_urls: string[]
    group_index?: number
  }) => api.post<any, { character: Character }>(`/characters/${id}/select-images`, data),
  generate: (id: string, data: {
    group_index?: number
    common_prompt?: string
    character_prompt?: string
    negative_prompt?: string
    use_style?: boolean
    style_id?: string
    model?: string
    width?: number
    height?: number
    prompt_extend?: boolean
    watermark?: boolean
    seed?: number
  }) => api.post(`/characters/${id}/generate`, data),
  generateAll: (id: string, data: {
    common_prompt?: string
    character_prompt?: string
    negative_prompt?: string
    group_count?: number
    use_style?: boolean
    style_id?: string
    model?: string
    width?: number
    height?: number
    prompt_extend?: boolean
    watermark?: boolean
    seed?: number
  }) => api.post<any, { image_groups: CharacterImage[] }>(`/characters/${id}/generate-all`, data),
  delete: (id: string) => api.delete(`/characters/${id}`),
  deleteAll: (projectId: string) => api.delete(`/characters/project/${projectId}/all`),
}

// ============ 场景 API ============

export interface SceneImage {
  id: string
  group_index: number
  url?: string
  prompt_used?: string
  created_at: string
}

export interface Scene {
  id: string
  project_id: string
  name: string
  description: string  // 说明用，不参与生图
  common_prompt: string
  scene_prompt: string  // 用于生图
  negative_prompt: string
  image_groups: SceneImage[]
  selected_group_index: number
  // 追踪ID
  last_task_id?: string  // DashScope 任务ID
  last_request_id?: string  // DashScope 请求ID
  created_at: string
  updated_at: string
}

export const scenesApi = {
  list: (projectId: string) => api.get<any, { scenes: Scene[] }>('/scenes', { params: { project_id: projectId } }),
  get: (id: string) => api.get<any, Scene>(`/scenes/${id}`),
  create: (data: {
    project_id: string
    name: string
    description?: string
    common_prompt?: string
    scene_prompt?: string
    negative_prompt?: string
  }) => api.post<any, { scene: Scene }>('/scenes/create', data),
  extract: (projectId: string) => api.post<any, { scenes: Scene[] }>('/scenes/extract', { project_id: projectId }),
  update: (id: string, data: Partial<Scene>) => api.put<any, Scene>(`/scenes/${id}`, data),
  selectImage: (id: string, data: {
    image_url: string
    group_index?: number
  }) => api.post<any, { scene: Scene }>(`/scenes/${id}/select-image`, data),
  generate: (id: string, data: {
    group_index?: number
    common_prompt?: string
    scene_prompt?: string
    negative_prompt?: string
    use_style?: boolean
    style_id?: string
    model?: string
    width?: number
    height?: number
    prompt_extend?: boolean
    watermark?: boolean
    seed?: number
  }) => api.post(`/scenes/${id}/generate`, data),
  generateAll: (id: string, data: {
    common_prompt?: string
    scene_prompt?: string
    negative_prompt?: string
    group_count?: number
    use_style?: boolean
    style_id?: string
    model?: string
    width?: number
    height?: number
    prompt_extend?: boolean
    watermark?: boolean
    seed?: number
  }) => api.post<any, { image_groups: SceneImage[] }>(`/scenes/${id}/generate-all`, data),
  delete: (id: string) => api.delete(`/scenes/${id}`),
  deleteAll: (projectId: string) => api.delete(`/scenes/project/${projectId}/all`),
}

// ============ 道具 API ============

export interface PropImage {
  id: string
  group_index: number
  url?: string
  prompt_used?: string
  created_at: string
}

export interface Prop {
  id: string
  project_id: string
  name: string
  description: string  // 说明用，不参与生图
  common_prompt: string
  prop_prompt: string  // 用于生图
  negative_prompt: string
  image_groups: PropImage[]
  selected_group_index: number
  // 追踪ID
  last_task_id?: string  // DashScope 任务ID
  last_request_id?: string  // DashScope 请求ID
  created_at: string
  updated_at: string
}

export const propsApi = {
  list: (projectId: string) => api.get<any, { props: Prop[] }>('/props', { params: { project_id: projectId } }),
  get: (id: string) => api.get<any, Prop>(`/props/${id}`),
  create: (data: {
    project_id: string
    name: string
    description?: string
    common_prompt?: string
    prop_prompt?: string
    negative_prompt?: string
  }) => api.post<any, { prop: Prop }>('/props/create', data),
  extract: (projectId: string) => api.post<any, { props: Prop[] }>('/props/extract', { project_id: projectId }),
  update: (id: string, data: Partial<Prop>) => api.put<any, Prop>(`/props/${id}`, data),
  selectImage: (id: string, data: {
    image_url: string
    group_index?: number
  }) => api.post<any, { prop: Prop }>(`/props/${id}/select-image`, data),
  generate: (id: string, data: {
    group_index?: number
    common_prompt?: string
    prop_prompt?: string
    negative_prompt?: string
    use_style?: boolean
    style_id?: string
    model?: string
    width?: number
    height?: number
    prompt_extend?: boolean
    watermark?: boolean
    seed?: number
  }) => api.post(`/props/${id}/generate`, data),
  generateAll: (id: string, data: {
    common_prompt?: string
    prop_prompt?: string
    negative_prompt?: string
    group_count?: number
    use_style?: boolean
    style_id?: string
    model?: string
    width?: number
    height?: number
    prompt_extend?: boolean
    watermark?: boolean
    seed?: number
  }) => api.post<any, { image_groups: PropImage[] }>(`/props/${id}/generate-all`, data),
  delete: (id: string) => api.delete(`/props/${id}`),
  deleteAll: (projectId: string) => api.delete(`/props/project/${projectId}/all`),
}

// ============ 分镜首帧 API ============

export interface FrameImage {
  id: string
  group_index: number
  url?: string
  prompt_used?: string
  created_at: string
}

export interface Frame {
  id: string
  project_id: string
  shot_id: string
  shot_number: number
  prompt: string
  image_groups: FrameImage[]
  selected_group_index: number
  // 追踪ID
  last_task_id?: string  // DashScope 任务ID
  last_request_id?: string  // DashScope 请求ID
  created_at: string
  updated_at: string
}

export const framesApi = {
  list: (projectId: string) => api.get<any, { frames: Frame[] }>('/frames', { params: { project_id: projectId } }),
  get: (id: string) => api.get<any, Frame>(`/frames/${id}`),
  generate: (data: {
    project_id: string
    shot_id: string
    shot_number?: number
    prompt: string
    negative_prompt?: string
    group_index?: number
    use_shot_references?: boolean
    reference_urls?: string[]
    // 模型和参数设置（和图片工作室一样）
    model?: string  // 模型选择，如 wan2.6-image, wan2.5-i2i-preview, qwen-image-edit-plus
    n?: number  // 每次请求生成的图片数量
    // 通用参数
    size?: string  // 输出尺寸
    prompt_extend?: boolean  // 智能改写
    watermark?: boolean  // 水印
    seed?: number | null  // 随机种子
    // wan2.6-image 专用参数
    enable_interleave?: boolean  // 图文混合模式
  }) => api.post<any, { frame: Frame; generated_count?: number }>('/frames/generate', data),
  generateBatch: (projectId: string) => api.post('/frames/generate-batch', { project_id: projectId }),
  update: (id: string, data: { prompt?: string; selected_group_index?: number }) => api.put(`/frames/${id}`, data),
  delete: (id: string) => api.delete(`/frames/${id}`),
  setFromGallery: (data: {
    project_id: string
    shot_id: string
    shot_number?: number
    gallery_image_id: string
    gallery_image_url: string
    group_index?: number
  }) => api.post<any, { frame: Frame; message: string }>('/frames/set-from-gallery', data),
  saveToGallery: (frameId: string, data: { name?: string; description?: string; group_index?: number }) => 
    api.post<any, { gallery_image: GalleryImage; message: string }>(`/frames/${frameId}/save-to-gallery`, data),
  setFromVideoLastFrame: (data: {
    project_id: string
    shot_id: string
    shot_number?: number
    video_url: string
    group_index?: number
  }) => api.post<any, { frame: Frame; gallery_image: GalleryImage; message: string }>('/frames/set-from-video-last-frame', data),
}

// ============ 视频 API ============

export interface VideoTask {
  id: string
  task_id: string
  request_id?: string  // DashScope 请求ID
  status: 'pending' | 'processing' | 'succeeded' | 'failed'
  progress: number
  error_message?: string
  created_at: string
  updated_at: string
}

export interface Video {
  id: string
  project_id: string
  shot_id: string
  shot_number: number
  first_frame_url?: string
  prompt: string
  duration: number
  task?: VideoTask
  video_url?: string
  created_at: string
  updated_at: string
}

export const videosApi = {
  list: (projectId: string) => api.get<any, { videos: Video[] }>('/videos', { params: { project_id: projectId } }),
  get: (id: string) => api.get<any, Video>(`/videos/${id}`),
  generate: (data: {
    project_id: string
    shot_id: string
    shot_number?: number
    first_frame_url?: string  // 可选，后端会自动从分镜获取
    prompt?: string  // 可选，后端会自动生成
    duration?: number
    // 视频生成参数（覆盖系统设置）
    model?: string
    resolution?: string  // 分辨率
    prompt_extend?: boolean
    watermark?: boolean
    seed?: number | null
    // 音频参数（仅wan2.5/2.6支持）
    audio_url?: string
    audio?: boolean
    // 镜头类型（仅wan2.6支持）
    shot_type?: string  // single/multi
  }) => api.post<any, { video: Video; task_id: string }>('/videos/generate', data),
  generateBatch: (projectId: string, options?: {
    model?: string
    resolution?: string
    prompt_extend?: boolean
    watermark?: boolean
    seed?: number | null
    audio?: boolean
    shot_type?: string
  }) => api.post<any, { videos: Video[]; errors: Array<{ shot_id: string; error: string }>; success_count: number; error_count: number }>('/videos/generate-batch', { project_id: projectId, ...options }),
  getStatus: (taskId: string) => api.get<any, { task_id: string; status: string; video_url?: string }>(`/videos/status/${taskId}`),
  delete: (id: string) => api.delete(`/videos/${id}`),
  select: (data: { project_id: string; shot_id: string; video_id: string }) => 
    api.post<any, { message: string; shot_id: string; video_url: string }>('/videos/select', data),
  selectFromLibrary: (data: { project_id: string; shot_id: string; video_library_id: string }) =>
    api.post<any, { message: string; shot_id: string; video_url: string; video_name: string }>('/videos/select-from-library', data),
  export: (data: { project_id: string; name?: string }) =>
    api.post<any, { message: string; video: any; url: string; shot_count: number; warning?: string }>('/videos/export', data),
}

// ============ 风格 API ============

export interface ImageStylePreset {
  name: string
  prompt: string
  negative_prompt: string
}

export interface TextStylePreset {
  name: string
  content: string
}

export interface StyleImage {
  id: string
  group_index: number
  url?: string
  prompt_used?: string
  created_at: string
}

export interface TextStyleVersion {
  id: string
  name: string
  content: string
  created_at: string
  modified_info: string
}

export interface Style {
  id: string
  project_id: string
  name: string
  description: string
  style_type: 'image' | 'text'
  // 图片风格字段
  style_prompt: string
  negative_prompt: string
  preset_name?: string
  image_groups: StyleImage[]
  selected_group_index: number
  // 文本风格字段
  text_style_content: string
  text_style_versions: TextStyleVersion[]
  text_preset_name?: string
  // 共用字段
  is_selected: boolean
  created_at: string
  updated_at: string
}

export const stylesApi = {
  getPresets: () => api.get<any, { 
    image_presets: Record<string, ImageStylePreset>,
    text_presets: Record<string, TextStylePreset> 
  }>('/styles/presets'),
  list: (projectId: string) => api.get<any, { styles: Style[] }>('/styles', { params: { project_id: projectId } }),
  get: (id: string) => api.get<any, Style>(`/styles/${id}`),
  create: (data: {
    project_id: string
    name: string
    style_type?: 'image' | 'text'
    style_prompt?: string
    negative_prompt?: string
    preset_name?: string
    text_style_content?: string
    text_preset_name?: string
  }) => api.post<any, Style>('/styles/create', data),
  update: (id: string, data: Partial<Style>) => api.put<any, Style>(`/styles/${id}`, data),
  generate: (id: string, data: {
    group_index?: number
    style_prompt?: string
    negative_prompt?: string
  }) => api.post(`/styles/${id}/generate`, data),
  generateAll: (id: string, data: {
    style_prompt?: string
    negative_prompt?: string
    group_count?: number
  }) => api.post<any, { image_groups: StyleImage[] }>(`/styles/${id}/generate-all`, data),
  select: (id: string, groupIndex: number) => api.post<any, Style>(`/styles/${id}/select`, null, { params: { group_index: groupIndex } }),
  saveTextVersion: (id: string, data: {
    version_name: string
    content: string
    modified_info?: string
  }) => api.post(`/styles/${id}/save-text-version`, data),
  loadTextVersion: (id: string, versionId: string) => api.post<any, { message: string, content: string }>(`/styles/${id}/load-text-version/${versionId}`),
  delete: (id: string) => api.delete(`/styles/${id}`),
  deleteAll: (projectId: string) => api.delete(`/styles/project/${projectId}/all`),
}

// ============ 图库 API ============

export interface GalleryImage {
  id: string
  project_id: string
  name: string
  description: string
  url: string
  prompt_used?: string
  source: string
  task_id?: string
  tags: string[]
  created_at: string
  updated_at: string
}

export const galleryApi = {
  list: (projectId: string) => api.get<any, { images: GalleryImage[] }>('/gallery', { params: { project_id: projectId } }),
  get: (id: string) => api.get<any, GalleryImage>(`/gallery/${id}`),
  create: (data: {
    project_id: string
    name: string
    description?: string
    url: string
    prompt_used?: string
    source?: string
    task_id?: string
    tags?: string[]
  }) => api.post<any, GalleryImage>('/gallery', data),
  batchCreate: (projectId: string, images: Array<{
    name: string
    description?: string
    url: string
    prompt_used?: string
    source?: string
    task_id?: string
    tags?: string[]
  }>) => api.post<any, { images: GalleryImage[] }>('/gallery/batch', { project_id: projectId, images }),
  update: (id: string, data: Partial<GalleryImage>) => api.put<any, GalleryImage>(`/gallery/${id}`, data),
  delete: (id: string) => api.delete(`/gallery/${id}`),
  deleteAll: (projectId: string) => api.delete(`/gallery/project/${projectId}/all`),
  // OSS状态
  getOSSStatus: () => api.get<any, { enabled: boolean; configured: boolean }>('/gallery/oss-status'),
  // 上传文件
  uploadFiles: (projectId: string, files: File[]) => {
    const formData = new FormData()
    formData.append('project_id', projectId)
    files.forEach(file => formData.append('files', file))
    return api.post<any, { 
      images: GalleryImage[]
      success_count: number
      error_count: number
      errors: Array<{ filename?: string; error: string }>
    }>('/gallery/upload-files', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  // 从URL上传
  uploadFromUrls: (projectId: string, urls: string[]) => 
    api.post<any, { 
      images: GalleryImage[]
      success_count: number
      error_count: number
      errors: Array<{ url?: string; error: string }>
    }>('/gallery/upload-urls', { project_id: projectId, urls }),
}

// ============ 图片工作室 API ============

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
  storage_source?: 'remote' | 'oss' | 'local_fallback'
  storage_warning?: string | null
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
    references?: Array<{ type: string, id: string }>
  }) => api.post<any, {
    canonical_request: Record<string, any>
    provider_payload: Record<string, any>
    validation_warnings: string[]
  }>('/studio/preview-payload', data),
  saveToGallery: (id: string, imageIds: string[]) => api.post<any, { saved_images: GalleryImage[] }>(`/studio/${id}/save-to-gallery`, { image_ids: imageIds }),
  updateImageMarkers: (taskId: string, imageId: string, markers: string[]) =>
    api.post<any, { success: boolean; markers: string[] }>(`/studio/${taskId}/markers`, { image_id: imageId, markers }),
  delete: (id: string) => api.delete(`/studio/${id}`),
  deleteAll: (projectId: string) => api.delete(`/studio/project/${projectId}/all`),
  // 获取可用模型列表（带详情）
  getAvailableModels: () => api.get<any, { 
    models: Record<string, {
      id: string
      name: string
      description?: string
      supported_task_kinds?: Array<'text_to_image' | 'image_edit' | 'interactive_edit' | 'sequential_generation'>
      size_ui_mode?: 'preset_only' | 'preset_plus_custom_with_templates'
      capabilities?: {
        supports_batch?: boolean
        supports_async?: boolean
        supports_negative_prompt?: boolean
        max_concurrent?: number
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

// ============ 图片测评 API ============

export type ImageBenchmarkTaskKind = 'text_to_image' | 'image_edit' | 'interactive_edit'
export type ImageBenchmarkSuiteStatus = 'draft' | 'running' | 'completed' | 'failed'
export type ImageBenchmarkRunStatus = 'pending' | 'running' | 'completed' | 'failed'
export type ImageBenchmarkCellStatus = 'pending' | 'running' | 'completed' | 'failed' | 'skipped' | 'unsupported'

export interface ImageBenchmarkDatasetImage {
  url: string
  name: string
  mime_type?: string | null
  width?: number | null
  height?: number | null
  source_label?: string | null
}

export interface ImageBenchmarkImageSlot {
  position: number
  image: ImageBenchmarkDatasetImage
}

export interface ImageBenchmarkDatasetItem {
  id: string
  name: string
  prompt: string
  negative_prompt: string
  sort_order: number
  tags: string[]
  image_slots: ImageBenchmarkImageSlot[]
  bbox_list: number[][][]
}

export interface ImageBenchmarkDataset {
  id: string
  project_id: string
  name: string
  description: string
  task_kind: ImageBenchmarkTaskKind
  schema_version: string
  max_image_slot_index: number
  items: ImageBenchmarkDatasetItem[]
  created_at: string
  updated_at: string
}

export interface ImageBenchmarkDatasetIssue {
  item_id: string
  item_name: string
  missing_positions: number[]
  message?: string
}

export interface ImageBenchmarkOutputImage {
  url?: string | null
  prompt_used?: string | null
}

export interface ImageBenchmarkCellResult {
  id: string
  case_id: string
  case_name: string
  model_id: string
  model_name: string
  status: ImageBenchmarkCellStatus
  output_images: ImageBenchmarkOutputImage[]
  error_message?: string | null
  request_ids: string[]
  task_ids: string[]
  validation_warnings: string[]
  effective_params: Record<string, any>
  canonical_request?: Record<string, any> | null
  provider_payload?: Record<string, any> | null
  provider_result_meta?: Record<string, any>
  attempt_count: number
  auto_retry_count: number
  created_at: string
  updated_at: string
}

export interface ImageBenchmarkSuite {
  id: string
  project_id: string
  name: string
  description: string
  dataset_id: string
  task_kind: ImageBenchmarkTaskKind
  selected_models: string[]
  baseline_params: Record<string, any>
  model_overrides: Record<string, Record<string, any>>
  status: ImageBenchmarkSuiteStatus
  latest_run_id?: string | null
  latest_run_snapshot?: Record<string, any> | null
  share_token?: string | null
  share_enabled?: boolean
  share_created_at?: string | null
  share_disabled_at?: string | null
  created_at: string
  updated_at: string
}

export interface ImageBenchmarkRun {
  id: string
  suite_id: string
  project_id: string
  dataset_id: string
  task_kind: ImageBenchmarkTaskKind
  status: ImageBenchmarkRunStatus
  dataset_snapshot: Record<string, any>
  model_snapshots: Array<Record<string, any>>
  baseline_params: Record<string, any>
  model_overrides: Record<string, Record<string, any>>
  cell_results: ImageBenchmarkCellResult[]
  retry_source_run_id?: string | null
  retry_targets?: Array<{ case_id: string; model_id: string }>
  stats: Record<string, any>
  created_at: string
  updated_at: string
  started_at?: string | null
  finished_at?: string | null
}

export interface ImageBenchmarkCapabilitiesResponse {
  task_kinds: Array<{ id: ImageBenchmarkTaskKind; label: string }>
  models: Record<string, {
    id: string
    name: string
    description?: string
    model_type?: string
    capabilities?: ModelCapabilities
    parameters?: ModelParameterDef[]
    configurable_parameters?: ModelParameterDef[]
    common_sizes?: SizeOption[]
    supported_task_kinds?: ImageBenchmarkTaskKind[]
    size_ui_mode?: string
  }>
}

export interface ImageBenchmarkPublicCellResult {
  id: string
  case_id: string
  case_name: string
  model_id: string
  model_name: string
  status: ImageBenchmarkCellStatus
  output_images: ImageBenchmarkOutputImage[]
  error_message?: string | null
  validation_warnings: string[]
  attempt_count: number
  auto_retry_count: number
  created_at: string
  updated_at: string
}

export interface ImageBenchmarkPublicRun {
  id: string
  suite_id: string
  project_id: string
  dataset_id: string
  task_kind: ImageBenchmarkTaskKind
  status: ImageBenchmarkRunStatus
  dataset_snapshot: Record<string, any>
  model_snapshots: Array<Record<string, any>>
  cell_results: ImageBenchmarkPublicCellResult[]
  stats: Record<string, any>
  created_at: string
  updated_at: string
  started_at?: string | null
  finished_at?: string | null
}

export interface ImageBenchmarkPublicShareResponse {
  suite: {
    id: string
    name: string
    description: string
    task_kind: ImageBenchmarkTaskKind
    status: ImageBenchmarkSuiteStatus
    latest_run_id?: string | null
    updated_at: string
  }
  run: ImageBenchmarkPublicRun
}

export interface ImageBenchmarkExportResponse {
  filename: string
  content: string
  embedded_image_count: number
  fallback_url_count: number
}

export interface ImageBenchmarkExportFileResponse {
  filename: string
  blob: Blob
  embedded_image_count: number
  fallback_url_count: number
}

const getFilenameFromContentDisposition = (value: string | null, fallback: string) => {
  if (!value) return fallback
  const utf8Match = value.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1])
    } catch {
      return utf8Match[1]
    }
  }
  const asciiMatch = value.match(/filename="?([^";]+)"?/i)
  return asciiMatch?.[1] || fallback
}

const downloadImageBenchmarkExportFile = async (
  id: string,
  format: 'md' | 'html',
  data?: { inline_images?: boolean },
): Promise<ImageBenchmarkExportFileResponse> => {
  const endpoint = format === 'md' ? 'export-md-file' : 'export-html-file'
  const response = await fetch(`/api/image-benchmark/runs/${id}/${endpoint}`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(data ?? {}),
  })
  if (response.status === 401) {
    localStorage.removeItem('auth-storage')
    if (window.location.pathname !== '/login') {
      window.location.href = '/login'
    }
    throw new Error('未登录或登录已过期，请重新登录')
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(payload?.detail || `导出失败: HTTP ${response.status}`)
  }
  const fallbackFilename = `image_benchmark_${id}.${format}`
  return {
    filename: getFilenameFromContentDisposition(response.headers.get('content-disposition'), fallbackFilename),
    blob: await response.blob(),
    embedded_image_count: Number(response.headers.get('x-embedded-image-count') || 0),
    fallback_url_count: Number(response.headers.get('x-fallback-url-count') || 0),
  }
}

export const imageBenchmarkApi = {
  getCapabilities: () => api.get<any, ImageBenchmarkCapabilitiesResponse>('/image-benchmark/capabilities'),
  listDatasets: (projectId: string) => api.get<any, { datasets: ImageBenchmarkDataset[] }>('/image-benchmark/datasets', { params: { project_id: projectId } }),
  getDataset: (id: string) => api.get<any, { dataset: ImageBenchmarkDataset; warnings: ImageBenchmarkDatasetIssue[]; blocking_issues: ImageBenchmarkDatasetIssue[] }>(`/image-benchmark/datasets/${id}`),
  createDataset: (data: {
    project_id: string
    name: string
    description?: string
    task_kind: ImageBenchmarkTaskKind
    max_image_slot_index?: number
    items?: Array<{
      id?: string
      name: string
      prompt: string
      negative_prompt: string
      tags: string[]
      image_slots: ImageBenchmarkImageSlot[]
    }>
  }) => api.post<any, { dataset: ImageBenchmarkDataset; warnings: ImageBenchmarkDatasetIssue[]; blocking_issues: ImageBenchmarkDatasetIssue[] }>('/image-benchmark/datasets', data),
  updateDataset: (id: string, data: {
    name?: string
    description?: string
    max_image_slot_index?: number
    items?: Array<{
      id?: string
      name: string
      prompt: string
      negative_prompt: string
      tags: string[]
      image_slots: ImageBenchmarkImageSlot[]
    }>
  }) => api.put<any, { dataset: ImageBenchmarkDataset; warnings: ImageBenchmarkDatasetIssue[]; blocking_issues: ImageBenchmarkDatasetIssue[] }>(`/image-benchmark/datasets/${id}`, data),
  validateDataset: (id: string) => api.post<any, { warnings: ImageBenchmarkDatasetIssue[]; blocking_issues: ImageBenchmarkDatasetIssue[] }>(`/image-benchmark/datasets/${id}/validate`),
  deleteDataset: (id: string) => api.delete(`/image-benchmark/datasets/${id}`),
  importDataset: (data: { project_id: string; data: Record<string, any>; name?: string; description?: string; migrate_images_to_oss?: boolean }) =>
    api.post<any, {
      dataset: ImageBenchmarkDataset
      warnings: ImageBenchmarkDatasetIssue[]
      blocking_issues: ImageBenchmarkDatasetIssue[]
      migration_report?: {
        enabled: boolean
        attempted: number
        succeeded: number
        failed: number
        skipped: number
        errors: Array<{ item_id?: string; item_name?: string; position?: number; url?: string; error: string }>
      }
    }>('/image-benchmark/datasets/import', data),
  exportDataset: (id: string) => api.get<any, Record<string, any>>(`/image-benchmark/datasets/${id}/export`),
  listSuites: (projectId: string) => api.get<any, { suites: ImageBenchmarkSuite[] }>('/image-benchmark/suites', { params: { project_id: projectId } }),
  getSuite: (id: string) => api.get<any, { suite: ImageBenchmarkSuite }>(`/image-benchmark/suites/${id}`),
  createSuite: (data: {
    project_id: string
    name: string
    description?: string
    dataset_id: string
    selected_models?: string[]
    baseline_params?: Record<string, any>
    model_overrides?: Record<string, Record<string, any>>
  }) => api.post<any, { suite: ImageBenchmarkSuite }>('/image-benchmark/suites', data),
  updateSuite: (id: string, data: {
    name?: string
    description?: string
    dataset_id?: string
    selected_models?: string[]
    baseline_params?: Record<string, any>
    model_overrides?: Record<string, Record<string, any>>
  }) => api.put<any, { suite: ImageBenchmarkSuite }>(`/image-benchmark/suites/${id}`, data),
  deleteSuite: (id: string) => api.delete(`/image-benchmark/suites/${id}`),
  enableSuiteShare: (id: string) => api.post<any, { suite: ImageBenchmarkSuite; share_url: string; public_api_url: string }>(`/image-benchmark/suites/${id}/share`),
  disableSuiteShare: (id: string) => api.delete<any, { suite: ImageBenchmarkSuite }>(`/image-benchmark/suites/${id}/share`),
  runSuite: (id: string) => api.post<any, { run: ImageBenchmarkRun; suite: ImageBenchmarkSuite }>(`/image-benchmark/suites/${id}/run`),
  getRun: (id: string) => api.get<any, { run: ImageBenchmarkRun }>(`/image-benchmark/runs/${id}`),
  retryFailedRun: (id: string) => api.post<any, { run: ImageBenchmarkRun; suite: ImageBenchmarkSuite }>(`/image-benchmark/runs/${id}/retry-failures`),
  exportRunMarkdown: (id: string, data?: { inline_images?: boolean }) => api.post<any, ImageBenchmarkExportResponse>(`/image-benchmark/runs/${id}/export-md`, data ?? {}),
  exportRunHtml: (id: string, data?: { inline_images?: boolean }) => api.post<any, ImageBenchmarkExportResponse>(`/image-benchmark/runs/${id}/export-html`, data ?? {}),
  downloadRunMarkdown: (id: string, data?: { inline_images?: boolean }) => downloadImageBenchmarkExportFile(id, 'md', data),
  downloadRunHtml: (id: string, data?: { inline_images?: boolean }) => downloadImageBenchmarkExportFile(id, 'html', data),
  previewCell: (data: {
    project_id: string
    task_kind: ImageBenchmarkTaskKind
    model_id: string
    case_data: {
      id?: string
      name: string
      prompt: string
      negative_prompt: string
      tags?: string[]
      image_slots: ImageBenchmarkImageSlot[]
      bbox_list?: number[][][]
    }
    baseline_params?: Record<string, any>
    override_params?: Record<string, any>
  }) => api.post<any, {
    effective_params: Record<string, any>
    canonical_request: Record<string, any>
    provider_payload: Record<string, any>
    validation_warnings: string[]
  }>('/image-benchmark/preview-cell', data),
}

const getPublicJson = async <T>(url: string): Promise<T> => {
  const response = await fetch(url, { headers: { Accept: 'application/json' } })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(data?.detail || '请求失败')
  }
  return data as T
}

export const imageBenchmarkPublicApi = {
  getShare: (token: string) => getPublicJson<ImageBenchmarkPublicShareResponse>(`/api/image-benchmark/public/shares/${encodeURIComponent(token)}`),
  getShareMarkdown: (token: string) => getPublicJson<{ filename: string; content: string }>(`/api/image-benchmark/public/shares/${encodeURIComponent(token)}/markdown`),
}

// ============ 音频库 API ============
export interface AudioItem {
  id: string
  project_id: string
  name: string
  description: string
  url: string
  file_type: string
  file_size: number
  duration?: number
  sample_rate?: number
  channels?: number
  created_at: string
  updated_at: string
}

export const audioApi = {
  list: (projectId: string) => api.get<any, { audios: AudioItem[] }>('/audio', { params: { project_id: projectId } }),
  get: (id: string) => api.get<any, AudioItem>(`/audio/${id}`),
  uploadFiles: (projectId: string, files: File[]) => {
    const formData = new FormData()
    files.forEach(file => formData.append('files', file))
    return api.post<any, { audios: AudioItem[]; errors: any[]; success_count: number; error_count: number }>(
      `/audio/upload-files?project_id=${projectId}`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    )
  },
  uploadUrls: (projectId: string, urls: string[], names?: string[]) => 
    api.post<any, { audios: AudioItem[]; errors: any[]; success_count: number; error_count: number }>(
      '/audio/upload-urls',
      { project_id: projectId, urls, names }
    ),
  update: (id: string, data: { name?: string; description?: string }) => api.put<any, AudioItem>(`/audio/${id}`, data),
  delete: (id: string) => api.delete(`/audio/${id}`),
  deleteAll: (projectId: string) => api.delete(`/audio?project_id=${projectId}`),
}

// ============ 视频库 API ============
export interface VideoLibraryItem {
  id: string
  project_id: string
  name: string
  description: string
  url: string
  file_type: string
  file_size: number
  duration?: number
  width?: number
  height?: number
  fps?: number
  thumbnail_url?: string
  created_at: string
  updated_at: string
}

export const videoLibraryApi = {
  list: (projectId: string) => api.get<any, { videos: VideoLibraryItem[] }>('/video-library', { params: { project_id: projectId } }),
  get: (id: string) => api.get<any, VideoLibraryItem>(`/video-library/${id}`),
  uploadFiles: (projectId: string, files: File[]) => {
    const formData = new FormData()
    files.forEach(file => formData.append('files', file))
    return api.post<any, { videos: VideoLibraryItem[]; errors: any[]; success_count: number; error_count: number }>(
      `/video-library/upload-files?project_id=${projectId}`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    )
  },
  uploadUrls: (projectId: string, urls: string[], names?: string[]) => 
    api.post<any, { videos: VideoLibraryItem[]; errors: any[]; success_count: number; error_count: number }>(
      '/video-library/upload-urls',
      { project_id: projectId, urls, names }
    ),
  update: (id: string, data: { name?: string; description?: string }) => api.put<any, VideoLibraryItem>(`/video-library/${id}`, data),
  delete: (id: string) => api.delete(`/video-library/${id}`),
  deleteAll: (projectId: string) => api.delete(`/video-library?project_id=${projectId}`),
  extractLastFrame: (id: string, name?: string) => 
    api.post<any, { message: string; image: GalleryImage }>(`/video-library/${id}/extract-last-frame`, null, { params: { name } }),
}

// ============ 文本库 API ============
export interface TextItemVersion {
  id: string
  content: string
  created_at: string
  description: string
}

export interface TextLibraryItem {
  id: string
  project_id: string
  name: string
  content: string
  category: string
  versions: TextItemVersion[]
  created_at: string
  updated_at: string
}

export const textLibraryApi = {
  list: (projectId: string, category?: string) => 
    api.get<any, { texts: TextLibraryItem[] }>('/text-library', { params: { project_id: projectId, category } }),
  get: (id: string) => api.get<any, TextLibraryItem>(`/text-library/${id}`),
  create: (data: { project_id: string; name: string; content: string; category?: string; description?: string }) => 
    api.post<any, TextLibraryItem>('/text-library', data),
  update: (id: string, data: { name?: string; content?: string; category?: string; save_version?: boolean; version_description?: string }) => 
    api.put<any, TextLibraryItem>(`/text-library/${id}`, data),
  saveVersion: (id: string, description?: string) => 
    api.post<any, { message: string; version: TextItemVersion }>(`/text-library/${id}/versions`, null, { params: { description } }),
  listVersions: (id: string) => api.get<any, { versions: TextItemVersion[] }>(`/text-library/${id}/versions`),
  restoreVersion: (id: string, versionId: string) => 
    api.post<any, { message: string; text: TextLibraryItem }>(`/text-library/${id}/restore`, { version_id: versionId }),
  deleteVersion: (id: string, versionId: string) => api.delete(`/text-library/${id}/versions/${versionId}`),
  delete: (id: string) => api.delete(`/text-library/${id}`),
  deleteAll: (projectId: string, category?: string) => 
    api.delete(`/text-library?project_id=${projectId}${category ? `&category=${category}` : ''}`),
}

// ============ 视频工作室 API ============
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

export interface VideoTaskProfile {
  task_kind: VideoTaskKind
  label: string
  description?: string
  input_roles: VideoInputRole[]
  parameters: ModelParameterDef[]
  ui_hints?: Record<string, any> & {
    asset_help?: Partial<Record<VideoInputRole, HelpContent | string>>
    prompt_help?: HelpContent | string
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

// ============ 模型注册系统 API ============

// 参数类型
export type ModelParameterType =
  | 'string'
  | 'integer'
  | 'float'
  | 'boolean'
  | 'select'
  | 'multi_select'
  | 'tags'
  | 'text'
  | 'image_url'
  | 'image_urls'
  | 'audio_url'
  | 'video_url'
  | 'file'

// 参数选项
export interface ModelSelectOption {
  value: any
  label: string
  description?: string
}

export interface HelpContent {
  summary?: string
  meaning?: string
  limits?: string[]
  how_to_choose?: string[]
  examples?: string[]
  notes?: string[]
}

// 参数约束
export interface ModelParameterConstraint {
  min_value?: number
  max_value?: number
  min_length?: number
  max_length?: number
  pattern?: string
  options?: ModelSelectOption[]
  depends_on?: string
  depends_value?: any
}

// 参数定义
export interface ModelParameterDef {
  name: string
  label: string
  type: ModelParameterType
  description?: string
  help?: HelpContent
  required?: boolean
  default?: any
  constraint?: ModelParameterConstraint
  group?: string
  advanced?: boolean
  order?: number
}

// 模型能力
export interface ModelCapabilities {
  supports_streaming?: boolean
  supports_batch?: boolean
  supports_async?: boolean
  supports_thinking?: boolean
  supports_search?: boolean
  supports_json_mode?: boolean
  supports_tools?: boolean
  max_context_length?: number
  supports_negative_prompt?: boolean
  supports_seed?: boolean
  supports_prompt_extend?: boolean
  supports_watermark?: boolean
  supports_audio?: boolean
  max_concurrent?: number
  // 图像特有能力
  supports_reference_images?: boolean
  max_reference_images?: number
  supports_interleave?: boolean  // 图文混合模式
}

// 尺寸选项
export interface SizeOption {
  width: number
  height: number
  label: string
  aspect_ratio?: string
  value: string  // "width*height"
}

// 尺寸约束
export interface SizeConstraints {
  min_pixels?: number
  max_pixels?: number
  min_ratio?: number
  max_ratio?: number
  min_width?: number
  max_width?: number
  min_height?: number
  max_height?: number
}

// 模型信息
export interface RegisteredModelInfo {
  id: string
  name: string
  type: string  // llm, text_to_image, image_to_image, image_to_video, text_to_video, reference_to_video, etc.
  description?: string
  version?: string
  capabilities?: ModelCapabilities
  parameters?: ModelParameterDef[]
  default_values?: Record<string, any>
  // 尺寸相关
  size_constraints?: SizeConstraints
  common_sizes?: SizeOption[]
  // 状态
  deprecated?: boolean
  deprecated_message?: string
  recommended?: boolean  // 推荐模型
  doc_url?: string
}

// 模型类型信息
export interface ModelTypeInfo {
  type: string
  label: string
  count: number
}

export const modelsApi = {
  // 获取所有模型
  listAll: () => api.get<any, { models: Record<string, RegisteredModelInfo> }>('/models'),
  
  // 获取图像生成模型（文生图 + 图生图）
  listImageModels: () => 
    api.get<any, { models: Record<string, RegisteredModelInfo> }>('/models/image'),
  
  // 获取视频生成模型
  listVideoModels: () => 
    api.get<any, { models: Record<string, RegisteredModelInfo> }>('/models/video'),
  
  // 按类型获取模型
  listByType: (modelType: string) => 
    api.get<any, { models: Record<string, RegisteredModelInfo> }>(`/models/by-type/${modelType}`),
  
  // 获取单个模型详情
  getModel: (modelId: string) => 
    api.get<any, RegisteredModelInfo>(`/models/${modelId}`),
  
  // 获取模型参数定义
  getParameters: (modelId: string, group?: string) => 
    api.get<any, { model_id: string; parameters: ModelParameterDef[] }>(
      `/models/${modelId}/parameters`,
      { params: group ? { group } : {} }
    ),
  
  // 获取模型支持的尺寸选项
  getSizes: (modelId: string) => 
    api.get<any, { 
      model_id: string
      common_sizes: SizeOption[]
      size_constraints: SizeConstraints | null 
    }>(`/models/${modelId}/sizes`),
  
  // 验证尺寸
  validateSize: (modelId: string, width: number, height: number) => 
    api.post<any, { 
      valid: boolean
      message: string
      width: number
      height: number
      total_pixels: number 
    }>(`/models/${modelId}/validate-size`, null, { params: { width, height } }),
  
  // 验证参数
  validateParams: (modelId: string, params: Record<string, any>) => 
    api.post<any, { valid: boolean; errors: string[] }>(`/models/${modelId}/validate`, params),
  
  // 获取可用的模型类型
  listTypes: () => 
    api.get<any, { types: ModelTypeInfo[] }>('/models/types/available'),
}

// ============ 认证 API ============

export interface UserInfo {
  id: string
  username: string
  display_name: string
  created_at: string
  last_login?: string
}

export interface LoginResponse {
  token: string
  user: UserInfo
}

export const authApi = {
  // 登录
  login: (username: string, password: string) => 
    api.post<any, LoginResponse>('/auth/login', { username, password }),
  
  // 注册
  register: (username: string, password: string, display_name?: string) => 
    api.post<any, LoginResponse>('/auth/register', { username, password, display_name }),
  
  // 登出
  logout: () => api.post<any, { success: boolean }>('/auth/logout'),
  
  // 获取当前用户
  me: () => api.get<any, UserInfo>('/auth/me'),
  
  // 修改密码
  changePassword: (oldPassword: string, newPassword: string) => 
    api.post<any, { success: boolean; message: string }>('/auth/change-password', {
      old_password: oldPassword,
      new_password: newPassword
    }),
}

// ============ 音频工作室 API ============

export interface AudioStudioTask {
  id: string
  project_id: string
  task_type: 'tts' | 'voice_clone' | 'voice_design'
  name: string
  // TTS
  text: string
  voice: string
  format: string
  volume: number
  speech_rate: number
  pitch_rate: number
  seed?: number | null
  language_hints?: string | null
  instruction?: string | null
  enable_ssml: boolean
  // Voice Clone
  audio_url?: string | null
  prefix: string
  clone_language_hints?: string | null
  // Voice Design
  voice_prompt?: string | null
  preview_text?: string | null
  design_sample_rate: number
  design_response_format: string
  // Results
  result_audio_url?: string | null
  result_voice_id?: string | null
  audio_duration?: number | null
  saved_to_library: boolean
  markers?: string[]  // star, flag, check, cross
  // Status
  status: 'pending' | 'processing' | 'succeeded' | 'failed'
  error_message?: string | null
  request_id?: string | null
  created_at: string
  updated_at: string
}

export interface VoiceProfile {
  id: string
  project_id: string
  voice_id: string
  name: string
  source: 'clone' | 'design'
  target_model: string
  prefix: string
  status: 'deploying' | 'ok' | 'undeployed'
  voice_prompt?: string | null
  preview_text?: string | null
  preview_audio_url?: string | null
  audio_url?: string | null
  created_at: string
  updated_at: string
}

export const audioStudioApi = {
  list: (projectId: string) =>
    api.get<any, { tasks: AudioStudioTask[] }>('/audio-studio', { params: { project_id: projectId } }),

  get: (id: string) =>
    api.get<any, { task: AudioStudioTask }>(`/audio-studio/${id}`),

  delete: (id: string) =>
    api.delete(`/audio-studio/${id}`),

  createTTS: (data: {
    project_id: string
    name?: string
    text: string
    voice: string
    format?: string
    volume?: number
    speech_rate?: number
    pitch_rate?: number
    seed?: number | null
    language_hints?: string | null
    instruction?: string | null
    enable_ssml?: boolean
  }) => api.post<any, { task: AudioStudioTask }>('/audio-studio/tts', data),

  createVoiceClone: (data: {
    project_id: string
    name?: string
    audio_url: string
    prefix: string
    language_hints?: string | null
  }) => api.post<any, { task: AudioStudioTask }>('/audio-studio/voice-clone', data),

  createVoiceDesign: (data: {
    project_id: string
    name?: string
    voice_prompt: string
    preview_text: string
    prefix: string
    sample_rate?: number
    response_format?: string
  }) => api.post<any, { task: AudioStudioTask }>('/audio-studio/voice-design', data),

  saveToLibrary: (taskId: string) =>
    api.post<any, { success: boolean }>(`/audio-studio/${taskId}/save-to-library`),
  updateMarkers: (taskId: string, markers: string[]) =>
    api.post<any, { success: boolean; markers: string[] }>(`/audio-studio/${taskId}/markers`, { markers }),

  listVoices: (projectId: string) =>
    api.get<any, { voices: VoiceProfile[] }>('/audio-studio/voices', { params: { project_id: projectId } }),

  deleteVoice: (profileId: string) =>
    api.delete(`/audio-studio/voices/${profileId}`),
}

export default api
