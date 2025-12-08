// 基础类型定义

export interface Project {
  id: string;
  name: string;
  description: string;
  script?: Script;
  characters: Character[];
  scenes: Scene[];
  props: Prop[];
  created_at: string;
  updated_at: string;
}

export interface Script {
  id: string;
  project_id: string;
  title: string;
  original_content: string;
  processed_content: string;
  scenes: ScriptScene[];
  created_at: string;
  updated_at: string;
}

export interface ScriptScene {
  id: string;
  scene_number: number;
  shot_design: string;
  shot_type: string;
  voice_subject: string;
  dialogue: string;
  characters: string[];
  character_appearance: string;
  character_action: string;
  scene_setting: string;
  lighting: string;
  mood: string;
  composition: string;
  props: string[];
  sound_effects: string;
  duration: number;
  first_frame_url?: string;
  video_url?: string;
  audio_url?: string;
}

export interface CharacterImageSet {
  id: string;
  front_url?: string;
  side_url?: string;
  back_url?: string;
  selected: boolean;
}

export interface Character {
  id: string;
  project_id: string;
  name: string;
  description: string;
  appearance: string;
  prompt: string;
  image_sets: CharacterImageSet[];
  selected_set_id?: string;
  voice_id?: string;
  voice_sample_url?: string;
  created_at: string;
  updated_at: string;
}

export interface SceneImage {
  id: string;
  url?: string;
  selected: boolean;
}

export interface Scene {
  id: string;
  project_id: string;
  name: string;
  description: string;
  prompt: string;
  images: SceneImage[];
  selected_image_id?: string;
  created_at: string;
  updated_at: string;
}

export interface PropImage {
  id: string;
  url?: string;
  selected: boolean;
}

export interface Prop {
  id: string;
  project_id: string;
  name: string;
  description: string;
  prompt: string;
  images: PropImage[];
  selected_image_id?: string;
  created_at: string;
  updated_at: string;
}

// API 请求/响应类型
export interface SettingsResponse {
  dashscope_api_key: string;
  has_api_key: boolean;
}

export interface ScriptGenerateRequest {
  content: string;
  model: string;
  prompt?: string;
}

export interface CharacterExtractRequest {
  project_id: string;
  script_content: string;
}

export interface CharacterGenerateRequest {
  character_id: string;
  set_index: number;
  common_prompt?: string;
  character_prompt?: string;
}

export interface VideoGenerateRequest {
  project_id: string;
  scene_id: string;
  first_frame_url: string;
  prompt?: string;
  duration: number;
}

export type TaskStatus = 'pending' | 'processing' | 'succeeded' | 'failed';

export interface VideoStatusResponse {
  task_id: string;
  status: TaskStatus;
  video_url?: string;
  error_message?: string;
}

// 文本模型选项
export const LLM_MODELS = [
  { code: 'qwen3-max', name: 'Qwen3-Max', description: '最大输出65,536，仅非思考模式' },
  { code: 'qwen-plus-latest', name: 'Qwen-Plus-Latest', description: '最大输出32,768，支持深度思考模式' },
];

