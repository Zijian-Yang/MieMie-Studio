/**
 * 模型注册中心 Store
 * 
 * 统一管理所有 AI 模型的配置信息，包括：
 * - 模型能力声明
 * - 参数定义
 * - 尺寸约束和预设尺寸
 * 
 * 这是模型配置的唯一数据源，所有页面都应该从这里获取模型信息。
 */

import { create } from 'zustand'
import { modelsApi, RegisteredModelInfo, SizeOption, SizeConstraints } from '../services/api'

// 模型类型
export type ModelCategory = 
  | 'llm'
  | 'text_to_image' 
  | 'image_to_image' 
  | 'text_to_video' 
  | 'image_to_video'
  | 'reference_to_video'
  | 'keyframe_to_video'

interface ValidationResult {
  valid: boolean
  message: string
}

interface ModelRegistryState {
  // 状态
  models: Record<string, RegisteredModelInfo>
  loading: boolean
  error: string | null
  lastUpdated: Date | null
  
  // Actions
  fetchModels: () => Promise<void>
  fetchImageModels: () => Promise<void>
  fetchVideoModels: () => Promise<void>
  
  // 查询方法
  getModel: (modelId: string) => RegisteredModelInfo | undefined
  getModelsByCategory: (category: ModelCategory) => RegisteredModelInfo[]
  getImageModels: () => RegisteredModelInfo[]
  getVideoModels: () => RegisteredModelInfo[]
  getTextToImageModels: () => RegisteredModelInfo[]
  getImageToImageModels: () => RegisteredModelInfo[]
  
  // 尺寸相关
  getSizeOptions: (modelId: string) => SizeOption[]
  getSizeConstraints: (modelId: string) => SizeConstraints | undefined
  validateSize: (modelId: string, width: number, height: number) => ValidationResult
}

export const useModelRegistryStore = create<ModelRegistryState>((set, get) => ({
  // 初始状态
  models: {},
  loading: false,
  error: null,
  lastUpdated: null,
  
  // 获取所有模型
  fetchModels: async () => {
    // 避免重复请求
    if (get().loading) return
    
    set({ loading: true, error: null })
    try {
      const response = await modelsApi.listAll()
      set({
        models: response.models,
        loading: false,
        lastUpdated: new Date(),
      })
    } catch (error) {
      set({
        loading: false,
        error: error instanceof Error ? error.message : '加载模型配置失败',
      })
    }
  },
  
  // 获取图像模型
  fetchImageModels: async () => {
    set({ loading: true, error: null })
    try {
      const response = await modelsApi.listImageModels()
      set((state) => ({
        models: { ...state.models, ...response.models },
        loading: false,
        lastUpdated: new Date(),
      }))
    } catch (error) {
      set({
        loading: false,
        error: error instanceof Error ? error.message : '加载图像模型失败',
      })
    }
  },
  
  // 获取视频模型
  fetchVideoModels: async () => {
    set({ loading: true, error: null })
    try {
      const response = await modelsApi.listVideoModels()
      set((state) => ({
        models: { ...state.models, ...response.models },
        loading: false,
        lastUpdated: new Date(),
      }))
    } catch (error) {
      set({
        loading: false,
        error: error instanceof Error ? error.message : '加载视频模型失败',
      })
    }
  },
  
  // 获取单个模型
  getModel: (modelId: string) => {
    return get().models[modelId]
  },
  
  // 按类型获取模型
  getModelsByCategory: (category: ModelCategory) => {
    const { models } = get()
    return Object.values(models).filter(m => m.type === category)
  },
  
  // 获取所有图像模型
  getImageModels: () => {
    const { models } = get()
    return Object.values(models).filter(m => 
      m.type === 'text_to_image' || m.type === 'image_to_image'
    )
  },
  
  // 获取所有视频模型
  getVideoModels: () => {
    const { models } = get()
    return Object.values(models).filter(m =>
      ['text_to_video', 'image_to_video', 'reference_to_video', 'keyframe_to_video'].includes(m.type)
    )
  },
  
  // 获取文生图模型
  getTextToImageModels: () => {
    const { models } = get()
    return Object.values(models).filter(m => m.type === 'text_to_image')
  },
  
  // 获取图生图模型
  getImageToImageModels: () => {
    const { models } = get()
    return Object.values(models).filter(m => m.type === 'image_to_image')
  },
  
  // 获取模型的尺寸选项
  getSizeOptions: (modelId: string) => {
    const model = get().models[modelId]
    return model?.common_sizes || []
  },
  
  // 获取模型的尺寸约束
  getSizeConstraints: (modelId: string) => {
    const model = get().models[modelId]
    return model?.size_constraints
  },
  
  // 验证尺寸
  validateSize: (modelId: string, width: number, height: number): ValidationResult => {
    const constraints = get().getSizeConstraints(modelId)
    if (!constraints) {
      return { valid: true, message: '' }
    }
    
    const totalPixels = width * height
    const ratio = height > 0 ? width / height : 0
    
    if (constraints.min_pixels && totalPixels < constraints.min_pixels) {
      return { 
        valid: false, 
        message: `总像素 ${totalPixels.toLocaleString()} 小于最小值 ${constraints.min_pixels.toLocaleString()}` 
      }
    }
    if (constraints.max_pixels && totalPixels > constraints.max_pixels) {
      return { 
        valid: false, 
        message: `总像素 ${totalPixels.toLocaleString()} 大于最大值 ${constraints.max_pixels.toLocaleString()}` 
      }
    }
    if (constraints.min_ratio && ratio < constraints.min_ratio) {
      return { 
        valid: false, 
        message: `宽高比 ${ratio.toFixed(2)} 小于最小值 ${constraints.min_ratio}` 
      }
    }
    if (constraints.max_ratio && ratio > constraints.max_ratio) {
      return { 
        valid: false, 
        message: `宽高比 ${ratio.toFixed(2)} 大于最大值 ${constraints.max_ratio}` 
      }
    }
    
    return { valid: true, message: '' }
  },
}))
