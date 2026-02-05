/**
 * useModelRegistry Hook
 * 
 * 提供统一的模型配置访问接口。
 * 在组件首次使用时自动加载模型配置，并缓存在全局 store 中。
 * 
 * 使用示例：
 * ```tsx
 * function MyComponent() {
 *   const { 
 *     models, 
 *     loading, 
 *     getImageModels, 
 *     getSizeOptions,
 *     validateSize 
 *   } = useModelRegistry()
 *   
 *   if (loading) return <Spin />
 *   
 *   const imageModels = getImageModels()
 *   const sizes = getSizeOptions('wan2.6-t2i')
 *   
 *   return <ModelSelector models={imageModels} />
 * }
 * ```
 */

import { useEffect } from 'react'
import { useModelRegistryStore, ModelCategory } from '../stores/modelRegistryStore'

interface UseModelRegistryOptions {
  /** 是否只加载图像模型 */
  imageOnly?: boolean
  /** 是否只加载视频模型 */
  videoOnly?: boolean
  /** 是否禁用自动加载 */
  disableAutoFetch?: boolean
}

export function useModelRegistry(options: UseModelRegistryOptions = {}) {
  const store = useModelRegistryStore()
  
  const { imageOnly, videoOnly, disableAutoFetch } = options
  
  // 首次加载时自动获取模型
  useEffect(() => {
    if (disableAutoFetch) return
    
    const hasModels = Object.keys(store.models).length > 0
    
    // 如果已有数据且未在加载中，不重复请求
    if (hasModels || store.loading) return
    
    // 根据选项决定加载哪些模型
    if (imageOnly) {
      store.fetchImageModels()
    } else if (videoOnly) {
      store.fetchVideoModels()
    } else {
      store.fetchModels()
    }
  }, [disableAutoFetch, imageOnly, videoOnly])
  
  return store
}

/**
 * 仅获取图像模型的简化 Hook
 */
export function useImageModels() {
  const store = useModelRegistry({ imageOnly: true })
  return {
    models: store.getImageModels(),
    textToImageModels: store.getTextToImageModels(),
    imageToImageModels: store.getImageToImageModels(),
    loading: store.loading,
    error: store.error,
    getSizeOptions: store.getSizeOptions,
    validateSize: store.validateSize,
  }
}

/**
 * 仅获取视频模型的简化 Hook
 */
export function useVideoModels() {
  const store = useModelRegistry({ videoOnly: true })
  return {
    models: store.getVideoModels(),
    loading: store.loading,
    error: store.error,
    getSizeOptions: store.getSizeOptions,
  }
}

export default useModelRegistry
