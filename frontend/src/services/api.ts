import axios from 'axios'

// 创建 axios 实例
const api = axios.create({
  baseURL: '/api',
  timeout: 360000, // 6分钟超时，支持长时间图片生成任务
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器
api.interceptors.request.use(
  (config) => {
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
    const message = error.response?.data?.detail || error.message || '请求失败'
    return Promise.reject(new Error(message))
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
  common_sizes: ImageModelSizeOption[]
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
  durations?: number[]  // 支持的时长列表
  default_duration?: number
  supports_prompt_extend?: boolean
  supports_watermark?: boolean
  supports_seed?: boolean
  supports_negative_prompt?: boolean
  supports_audio?: boolean  // 是否支持音频参数
  default_audio?: boolean  // 默认是否开启自动配音
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
  api_region: string
  base_url: string
  llm: LLMConfig
  image: ImageConfig
  image_edit: ImageEditConfig
  video: VideoConfig
  oss: OSSConfigResponse
  available_regions: Record<string, RegionInfo>
  available_llm_models: Record<string, LLMModelInfo>
  available_image_models: Record<string, ImageModelInfo>
  available_image_edit_models: Record<string, ImageModelInfo>
  available_video_models: Record<string, VideoModelInfo>
}

export interface ConfigUpdateRequest {
  api_key?: string
  api_region?: string
  llm?: Partial<LLMConfig>
  image?: Partial<ImageConfig>
  image_edit?: Partial<ImageEditConfig>
  video?: Partial<VideoConfig>
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
  shots: Shot[]
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
      headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_id: projectId, content, model, prompt }),
    signal: controller.signal,
  })
    .then(async (response) => {
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
  created_at: string
  updated_at: string
}

export const charactersApi = {
  list: (projectId: string) => api.get<any, { characters: Character[] }>('/characters', { params: { project_id: projectId } }),
  get: (id: string) => api.get<any, Character>(`/characters/${id}`),
  extract: (projectId: string) => api.post<any, { characters: Character[] }>('/characters/extract', { project_id: projectId }),
  update: (id: string, data: Partial<Character>) => api.put<any, Character>(`/characters/${id}`, data),
  generate: (id: string, data: {
    group_index?: number
    common_prompt?: string
    character_prompt?: string
    negative_prompt?: string
    use_style?: boolean
    style_id?: string
  }) => api.post(`/characters/${id}/generate`, data),
  generateAll: (id: string, data: {
    common_prompt?: string
    character_prompt?: string
    negative_prompt?: string
    group_count?: number
    use_style?: boolean
    style_id?: string
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
  created_at: string
  updated_at: string
}

export const scenesApi = {
  list: (projectId: string) => api.get<any, { scenes: Scene[] }>('/scenes', { params: { project_id: projectId } }),
  get: (id: string) => api.get<any, Scene>(`/scenes/${id}`),
  extract: (projectId: string) => api.post<any, { scenes: Scene[] }>('/scenes/extract', { project_id: projectId }),
  update: (id: string, data: Partial<Scene>) => api.put<any, Scene>(`/scenes/${id}`, data),
  generate: (id: string, data: {
    group_index?: number
    common_prompt?: string
    scene_prompt?: string
    negative_prompt?: string
    use_style?: boolean
    style_id?: string
  }) => api.post(`/scenes/${id}/generate`, data),
  generateAll: (id: string, data: {
    common_prompt?: string
    scene_prompt?: string
    negative_prompt?: string
    group_count?: number
    use_style?: boolean
    style_id?: string
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
  created_at: string
  updated_at: string
}

export const propsApi = {
  list: (projectId: string) => api.get<any, { props: Prop[] }>('/props', { params: { project_id: projectId } }),
  get: (id: string) => api.get<any, Prop>(`/props/${id}`),
  extract: (projectId: string) => api.post<any, { props: Prop[] }>('/props/extract', { project_id: projectId }),
  update: (id: string, data: Partial<Prop>) => api.put<any, Prop>(`/props/${id}`, data),
  generate: (id: string, data: {
    group_index?: number
    common_prompt?: string
    prop_prompt?: string
    negative_prompt?: string
    use_style?: boolean
    style_id?: string
  }) => api.post(`/props/${id}/generate`, data),
  generateAll: (id: string, data: {
    common_prompt?: string
    prop_prompt?: string
    negative_prompt?: string
    group_count?: number
    use_style?: boolean
    style_id?: string
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
  }) => api.post<any, { frame: Frame }>('/frames/generate', data),
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
}

// ============ 视频 API ============

export interface VideoTask {
  id: string
  task_id: string
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
    // 音频参数（仅wan2.5支持）
    audio_url?: string
    audio?: boolean
  }) => api.post<any, { video: Video; task_id: string }>('/videos/generate', data),
  generateBatch: (projectId: string, options?: {
    model?: string
    resolution?: string
    prompt_extend?: boolean
    watermark?: boolean
    seed?: number | null
    audio?: boolean
  }) => api.post<any, { videos: Video[]; errors: Array<{ shot_id: string; error: string }>; success_count: number; error_count: number }>('/videos/generate-batch', { project_id: projectId, ...options }),
  getStatus: (taskId: string) => api.get<any, { task_id: string; status: string; video_url?: string }>(`/videos/status/${taskId}`),
  delete: (id: string) => api.delete(`/videos/${id}`),
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
  type: 'character' | 'scene' | 'prop' | 'gallery'
  id: string
  name: string
  url?: string
}

export interface StudioTaskImage {
  id: string
  group_index: number
  url?: string
  prompt_used?: string
  is_selected: boolean
  created_at: string
}

export interface StudioTask {
  id: string
  project_id: string
  name: string
  description: string
  model: string
  prompt: string
  negative_prompt: string
  n: number  // 每次请求生成的图片数量
  group_count: number  // 并发请求数（总图片数 = n * group_count）
  references: ReferenceItem[]
  images: StudioTaskImage[]
  status: 'pending' | 'generating' | 'completed' | 'failed'
  error_message?: string
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
    n?: number  // 每次请求生成的图片数量
    group_count?: number  // 并发请求数
    references?: Array<{ type: string, id: string }>
  }) => api.post<any, StudioTask>('/studio', data),
  update: (id: string, data: Partial<StudioTask>) => api.put<any, StudioTask>(`/studio/${id}`, data),
  generate: (id: string, data?: {
    prompt?: string
    negative_prompt?: string
    n?: number  // 每次请求生成的图片数量
    group_count?: number  // 并发请求数（总图片数 = n * group_count）
    // qwen-image-edit-plus 专用参数
    size?: string  // 输出尺寸，仅当 n=1 时可用
    prompt_extend?: boolean  // 智能改写
    watermark?: boolean  // 水印
    seed?: number | null  // 随机种子
  }) => api.post<any, { task: StudioTask }>(`/studio/${id}/generate`, data || {}),
  saveToGallery: (id: string, imageIds: string[]) => api.post<any, { saved_images: GalleryImage[] }>(`/studio/${id}/save-to-gallery`, { image_ids: imageIds }),
  delete: (id: string) => api.delete(`/studio/${id}`),
  deleteAll: (projectId: string) => api.delete(`/studio/project/${projectId}/all`),
  // 获取可用模型列表（带详情）
  getAvailableModels: () => api.get<any, { 
    models: Record<string, {
      id: string
      name: string
      description?: string
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
export interface VideoStudioTask {
  id: string
  project_id: string
  name: string
  mode: 'first_frame' | 'first_last_frame'
  first_frame_url?: string
  last_frame_url?: string
  audio_url?: string
  prompt: string
  negative_prompt: string
  model: string
  resolution: string
  duration: number
  prompt_extend: boolean  // 智能改写
  watermark: boolean  // 水印
  seed?: number | null  // 随机种子
  auto_audio: boolean  // 自动配音
  group_count: number
  video_urls: string[]
  selected_video_url?: string
  task_ids: string[]
  status: 'pending' | 'processing' | 'succeeded' | 'failed'
  error_message?: string
  created_at: string
  updated_at: string
}

export const videoStudioApi = {
  list: (projectId: string) => api.get<any, { tasks: VideoStudioTask[] }>('/video-studio', { params: { project_id: projectId } }),
  get: (id: string) => api.get<any, VideoStudioTask>(`/video-studio/${id}`),
  getStatus: (id: string) => api.get<any, { task: VideoStudioTask }>(`/video-studio/${id}/status`),
  create: (data: {
    project_id: string
    name?: string
    mode?: string
    first_frame_url: string
    last_frame_url?: string
    audio_url?: string
    prompt?: string
    negative_prompt?: string
    model?: string
    resolution?: string
    duration?: number
    prompt_extend?: boolean  // 智能改写
    watermark?: boolean  // 水印
    seed?: number  // 随机种子
    auto_audio?: boolean  // 自动配音
    group_count?: number
  }) => api.post<any, { task: VideoStudioTask }>('/video-studio', data),
  update: (id: string, data: { name?: string; selected_video_url?: string }) => 
    api.put<any, VideoStudioTask>(`/video-studio/${id}`, data),
  saveToLibrary: (id: string, videoUrl: string, name?: string) => 
    api.post<any, { message: string; video: VideoLibraryItem }>(`/video-studio/${id}/save-to-library`, null, { params: { video_url: videoUrl, name } }),
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
}

// 模型信息
export interface RegisteredModelInfo {
  id: string
  name: string
  type: string  // llm, text_to_image, image_to_image, image_to_video, etc.
  description?: string
  capabilities?: ModelCapabilities
  parameters?: ModelParameterDef[]
  default_values?: Record<string, any>
  deprecated?: boolean
  deprecated_message?: string
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
  
  // 验证参数
  validateParams: (modelId: string, params: Record<string, any>) => 
    api.post<any, { valid: boolean; errors: string[] }>(`/models/${modelId}/validate`, params),
  
  // 获取可用的模型类型
  listTypes: () => 
    api.get<any, { types: ModelTypeInfo[] }>('/models/types/available'),
}

export default api
