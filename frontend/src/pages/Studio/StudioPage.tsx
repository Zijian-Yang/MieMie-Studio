import React, { useEffect, useState, useCallback, useRef, useMemo } from 'react'
import { useParams } from 'react-router-dom'
import { 
  Button, Modal, Form, Input, Empty, Spin, message, 
  Image, Space, Popconfirm, Card, Tag, Tooltip, Select,
  InputNumber, Checkbox, Tabs, Radio, Progress, Switch
} from 'antd'
import { 
  PlusOutlined, DeleteOutlined, EditOutlined, PictureOutlined,
  ExclamationCircleOutlined, ThunderboltOutlined, SaveOutlined,
  CheckCircleOutlined, CloseCircleOutlined, SyncOutlined
} from '@ant-design/icons'
import { 
  studioApi, galleryApi, charactersApi, scenesApi, propsApi, stylesApi,
  StudioTask, GalleryImage, Character, Scene, Prop, ReferenceItem, Style
} from '../../services/api'
import { useProjectStore } from '../../stores/projectStore'
import { useModelRegistry } from '../../hooks/useModelRegistry'
import { ModelSelector, SizeSelector } from '../../components/ModelConfig'

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

const StudioPage = () => {
  const { projectId } = useParams<{ projectId: string }>()
  const { currentProject, fetchProject } = useProjectStore()
  
  const [tasks, setTasks] = useState<StudioTask[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedTask, setSelectedTask] = useState<StudioTask | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [isGenerating, setIsGenerating] = useState(false)
  const [selectedImages, setSelectedImages] = useState<Set<string>>(new Set())
  const [form] = Form.useForm()
  
  // 监听模型选择变化，用于动态显示对应模型的参数面板
  const watchedModel = Form.useWatch('model', form)
  const watchedEnableInterleave = Form.useWatch('enable_interleave', form)
  
  // 自动保存防抖定时器
  const autoSaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const autoSavingRef = useRef(false)
  
  // 素材选择
  const [characters, setCharacters] = useState<Character[]>([])
  const [scenes, setScenes] = useState<Scene[]>([])
  const [props, setProps] = useState<Prop[]>([])
  const [galleryImages, setGalleryImages] = useState<GalleryImage[]>([])
  const [styles, setStyles] = useState<Style[]>([])
  
  // 使用统一的模型注册中心
  const { models: registryModels, loading: modelsLoading, getImageModels, getSizeOptions } = useModelRegistry()
  
  // 兼容旧代码：将 registryModels 格式化为旧的 availableModels 格式
  const availableModels = useMemo(() => {
    const result: Record<string, any> = {}
    Object.values(registryModels).forEach(model => {
      if (model.type === 'text_to_image' || model.type === 'image_to_image') {
        result[model.id] = {
          id: model.id,
          name: model.name,
          description: model.description,
          model_type: model.type,
          capabilities: model.capabilities,
          parameters: model.parameters,
          common_sizes: model.common_sizes || []
        }
      }
    })
    return result
  }, [registryModels])
  
  const isMountedRef = useRef(true)

  const safeSetState = useCallback(<T,>(setter: React.Dispatch<React.SetStateAction<T>>, value: T | ((prev: T) => T)) => {
    if (isMountedRef.current) {
      setter(value as any)
    }
  }, [])

  useEffect(() => {
    isMountedRef.current = true
    return () => { isMountedRef.current = false }
  }, [])

  useEffect(() => {
    const loadData = async () => {
      if (!projectId) return
      safeSetState(setLoading, true)
      try {
        fetchProject(projectId).catch(() => {})
        
        const [tasksRes, charactersRes, scenesRes, propsRes, galleryRes, stylesRes] = await Promise.all([
          studioApi.list(projectId),
          charactersApi.list(projectId),
          scenesApi.list(projectId),
          propsApi.list(projectId),
          galleryApi.list(projectId),
          stylesApi.list(projectId),
        ])
        
        safeSetState(setTasks, tasksRes.tasks)
        safeSetState(setCharacters, charactersRes.characters)
        safeSetState(setScenes, scenesRes.scenes)
        safeSetState(setProps, propsRes.props)
        safeSetState(setGalleryImages, galleryRes.images)
        safeSetState(setStyles, stylesRes.styles)
        // 模型配置现在通过 useModelRegistry hook 自动获取
      } catch (error) {
        message.error('加载失败')
      } finally {
        safeSetState(setLoading, false)
      }
    }
    loadData()
  }, [projectId, fetchProject, safeSetState])

  // 新建模式状态
  const [isCreating, setIsCreating] = useState(false)
  
  const openCreateModal = () => {
    // 直接使用统一的弹窗，设置为新建模式
    setIsCreating(true)
    setSelectedTask(null)
    setSelectedImages(new Set())
    form.resetFields()
    form.setFieldsValue({
      name: '',
      description: '',
      model: 'wan2.6-image',  // 默认使用最新模型
      prompt: '',
      negative_prompt: '',
      n: 4,  // wan2.6-image 默认4张
      group_count: 3,  // 并发请求数
      prompt_extend: true,
      watermark: false,
      enable_interleave: false,
      max_images: 5,
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
      const values = await form.validateFields()
      
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
      const modelInfo = availableModels[values.model]
      const isTextToImage = modelInfo?.model_type === 'text_to_image'
      const isWan26Image = values.model === 'wan2.6-image'
      const isQwenModel = values.model?.startsWith('qwen-image-edit')
      const refCount = references.length
      
      const needsReferences = !isTextToImage && !isWan26Image && !isQwenModel
      if (needsReferences && refCount === 0) {
        message.warning('请先添加参考素材')
        return
      }
      if (isWan26Image && !(values.enable_interleave || false) && refCount === 0) {
        message.warning('参考图模式下必须选择至少1张参考图，或开启图文混合模式')
        return
      }
      
      safeSetState(setIsGenerating, true)
      
      // 1. 创建任务
      const task = await studioApi.create({
        project_id: projectId,
        name: values.name || '未命名任务',
        description: values.description,
        model: values.model,
        prompt: finalPrompt,
        negative_prompt: finalNegativePrompt,
        n: values.n || 4,
        group_count: values.group_count,
        references,
        size: values.size || undefined,
        prompt_extend: values.prompt_extend,
        watermark: values.watermark,
        seed: values.seed || undefined,
        enable_interleave: values.enable_interleave,
        max_images: values.max_images
      })
      safeSetState(setTasks, (prev: StudioTask[]) => [task, ...prev])
      createdTask = task
      setSelectedStyleId(null)
      setIsCreating(false)
      setSelectedTask(task)
      
      // 2. 立即开始生成
      const generateParams: any = {
        prompt: finalPrompt,
        negative_prompt: finalNegativePrompt,
        n: values.n || (isWan26Image ? 4 : 1),
        group_count: values.group_count || 3
      }
      
      if (isTextToImage) {
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
      if (isQwenModel) {
        if (values.size) generateParams.size = values.size
        generateParams.prompt_extend = values.prompt_extend !== false
        generateParams.watermark = values.watermark || false
        if (values.seed) generateParams.seed = values.seed
        if (values.negative_prompt) generateParams.negative_prompt = values.negative_prompt
      }
      
      const result = await studioApi.generate(task.id, generateParams)
      safeSetState(setTasks, (prev: StudioTask[]) => prev.map(t => t.id === result.task.id ? result.task : t))
      setSelectedTask(result.task)
      message.success('图片生成完成')
    } catch (error: any) {
      message.error(error?.message || '生成失败')
      // 重新获取任务数据以获取后端保存的失败状态和错误信息
      if (createdTask) {
        try {
          const updatedTask = await studioApi.get(createdTask.id)
          safeSetState(setTasks, (prev: StudioTask[]) => prev.map(t => t.id === updatedTask.id ? updatedTask : t))
          setSelectedTask(updatedTask)
        } catch {}
      }
    } finally {
      safeSetState(setIsGenerating, false)
    }
  }

  const openTaskModal = (task: StudioTask) => {
    setIsCreating(false)  // 编辑模式
    setSelectedTask(task)
    setSelectedImages(new Set())
    setSelectedStyleId(null)
    form.setFieldsValue({
      name: task.name,
      description: task.description,
      model: task.model,
      prompt: task.prompt,
      negative_prompt: task.negative_prompt,
      n: task.n || 4,
      group_count: task.group_count || 3,  // 默认3组并发
      // 加载保存的高级参数（如果有），否则使用默认值
      size: task.size || '',
      prompt_extend: task.prompt_extend !== undefined ? task.prompt_extend : true,
      watermark: task.watermark !== undefined ? task.watermark : false,
      seed: task.seed || undefined,
      // wan2.6-image 专用参数
      enable_interleave: task.enable_interleave || false,
      max_images: task.max_images || 5,
      // 还原参考素材选择（编辑时显示）
      references: task.references?.map(ref => `${ref.type}:${ref.id}`) || [],
    })
    setIsModalOpen(true)
  }

  const autoSaveTask = useCallback(async () => {
    if (!selectedTask || isCreating || autoSavingRef.current) return
    autoSavingRef.current = true
    try {
      const values = form.getFieldsValue()
      
      const references = (values.references || []).map((ref: string) => {
        const [type, id] = ref.split(':')
        return { type, id }
      })
      
      const updated = await studioApi.update(selectedTask.id, {
        name: values.name,
        description: values.description,
        model: values.model,
        prompt: values.prompt,
        negative_prompt: values.negative_prompt,
        n: values.n,
        group_count: values.group_count,
        size: values.size || undefined,
        prompt_extend: values.prompt_extend,
        watermark: values.watermark,
        seed: values.seed || undefined,
        enable_interleave: values.enable_interleave,
        max_images: values.max_images,
        references: references
      })
      safeSetState(setTasks, (prev: StudioTask[]) => prev.map(t => t.id === updated.id ? updated : t))
      setSelectedTask(updated)
    } catch {
      // 静默失败，不打扰用户
    } finally {
      autoSavingRef.current = false
    }
  }, [selectedTask, isCreating, form, safeSetState])
  
  const handleFormValuesChange = useCallback(() => {
    if (isCreating || !selectedTask) return
    if (autoSaveTimerRef.current) {
      clearTimeout(autoSaveTimerRef.current)
    }
    autoSaveTimerRef.current = setTimeout(() => {
      autoSaveTask()
    }, 800)
  }, [isCreating, selectedTask, autoSaveTask])
  
  useEffect(() => {
    return () => {
      if (autoSaveTimerRef.current) {
        clearTimeout(autoSaveTimerRef.current)
      }
    }
  }, [])

  const generateImages = async () => {
    if (!selectedTask) return
    
    const values = form.getFieldsValue()
    const modelInfo = availableModels[values.model]
    const isTextToImage = modelInfo?.model_type === 'text_to_image'
    const isWan26Image = values.model === 'wan2.6-image'
    const isQwenModel = values.model?.startsWith('qwen-image-edit')
    
    // 从表单中解析参考图
    const formReferences = (values.references || []).map((ref: string) => {
      const [type, id] = ref.split(':')
      return { type, id }
    })
    const refCount = formReferences.length
    
    // 图生图模型需要参考素材（wan2.6-image 支持无参考图模式）
    const needsReferences = !isTextToImage && !isWan26Image
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
    if (isQwenModel) {
      if (refCount > 3) {
        message.warning('qwen-image-edit 系列最多支持3张输入图片')
        return
      }
    }
    
    // 生成前确保最新表单数据已保存（取消待执行的自动保存，立即保存一次）
    if (autoSaveTimerRef.current) {
      clearTimeout(autoSaveTimerRef.current)
      autoSaveTimerRef.current = null
    }
    try {
      const references = formReferences.map((ref: any) => ({ ...ref }))
      await studioApi.update(selectedTask.id, {
        name: values.name,
        description: values.description,
        model: values.model,
        prompt: values.prompt,
        negative_prompt: values.negative_prompt,
        n: values.n,
        group_count: values.group_count,
        size: values.size || undefined,
        prompt_extend: values.prompt_extend,
        watermark: values.watermark,
        seed: values.seed || undefined,
        enable_interleave: values.enable_interleave,
        max_images: values.max_images,
        references
      })
      const updatedTask = { ...selectedTask, references }
      safeSetState(setTasks, (prev: StudioTask[]) => prev.map(t => t.id === selectedTask.id ? updatedTask : t))
      setSelectedTask(updatedTask)
    } catch (error) {
      console.error('保存任务失败:', error)
    }
    
    safeSetState(setIsGenerating, true)
    try {
      const generateParams: any = {
        prompt: values.prompt,
        negative_prompt: values.negative_prompt,
        n: values.n || (isWan26Image ? 4 : 1),  // wan2.6-image 默认4张
        group_count: values.group_count || 3  // 默认3组并发
      }
      
      // 文生图模型参数
      if (isTextToImage) {
        generateParams.prompt_extend = values.prompt_extend !== false  // 默认 true
        generateParams.watermark = values.watermark || false
        if (values.seed) generateParams.seed = values.seed
        if (values.size) generateParams.size = values.size
      }
      
      // wan2.6-image 模型参数
      if (isWan26Image) {
        const enableInterleave = values.enable_interleave || false
        generateParams.prompt_extend = enableInterleave ? false : (values.prompt_extend !== false)  // 图文混合模式下不生效
        generateParams.watermark = values.watermark || false
        if (values.seed) generateParams.seed = values.seed
        if (values.size) generateParams.size = values.size
        generateParams.enable_interleave = enableInterleave
        
        // 图文混合模式下固定n=1，并传递max_images
        if (enableInterleave) {
          generateParams.n = 1
          generateParams.max_images = values.max_images || 5
        }
      }
      
      // qwen-image-edit 系列专用参数
      if (isQwenModel) {
        if (values.size) generateParams.size = values.size
        generateParams.prompt_extend = values.prompt_extend !== false
        generateParams.watermark = values.watermark || false
        if (values.seed) generateParams.seed = values.seed
        if (values.negative_prompt) generateParams.negative_prompt = values.negative_prompt
      }
      
      const result = await studioApi.generate(selectedTask.id, generateParams)
      
      safeSetState(setTasks, (prev: StudioTask[]) => prev.map(t => t.id === result.task.id ? result.task : t))
      setSelectedTask(result.task)
      message.success('图片生成完成')
    } catch (error: any) {
      message.error(error?.message || '图片生成失败')
      // 重新获取任务数据以获取后端保存的失败状态和错误信息
      try {
        const updatedTask = await studioApi.get(selectedTask.id)
        safeSetState(setTasks, (prev: StudioTask[]) => prev.map(t => t.id === updatedTask.id ? updatedTask : t))
        setSelectedTask(updatedTask)
      } catch {}
    } finally {
      safeSetState(setIsGenerating, false)
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

  // 获取素材的显示图片
  const getItemImage = (type: string, id: string): string | undefined => {
    if (type === 'character') {
      const char = characters.find(c => c.id === id)
      if (char?.image_groups?.[char.selected_group_index]) {
        return char.image_groups[char.selected_group_index].front_url
      }
    } else if (type === 'scene') {
      const scene = scenes.find(s => s.id === id)
      if (scene?.image_groups?.[scene.selected_group_index]) {
        return scene.image_groups[scene.selected_group_index].url
      }
    } else if (type === 'prop') {
      const prop = props.find(p => p.id === id)
      if (prop?.image_groups?.[prop.selected_group_index]) {
        return prop.image_groups[prop.selected_group_index].url
      }
    } else if (type === 'gallery') {
      const img = galleryImages.find(i => i.id === id)
      return img?.url
    }
    return undefined
  }

  // 风格选择状态
  const [selectedStyleId, setSelectedStyleId] = useState<string | null>(null)
  
  // 获取风格图片URL
  const getStyleImageUrl = (style: Style) => {
    if (style.style_type === 'image' && style.image_groups?.[style.selected_group_index]?.url) {
      return style.image_groups[style.selected_group_index].url
    }
    return null
  }
  
  // 获取选中的风格
  const getSelectedStyle = () => {
    if (!selectedStyleId) return null
    return styles.find(s => s.id === selectedStyleId) || null
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
                <div style={{ width: 24, height: 24, background: '#333', borderRadius: 4 }} />
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
                <div style={{ width: 24, height: 24, background: '#333', borderRadius: 4 }} />
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
                <div style={{ width: 24, height: 24, background: '#333', borderRadius: 4 }} />
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
              <div style={{ width: 24, height: 24, background: '#333', borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10 }}>T</div>
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
          <h1 style={{ fontSize: 20, fontWeight: 600, margin: 0, color: '#e0e0e0' }}>
            图片工作室
          </h1>
          <p style={{ color: '#888', margin: '4px 0 0', fontSize: 13 }}>
            {currentProject?.name} - 共 {tasks.length} 个任务
          </p>
        </div>
        <Space>
          {tasks.length > 0 && (
            <Popconfirm 
              title="确定删除所有任务？" 
              description="此操作不可恢复"
              icon={<ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />}
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
                      background: '#242424'
                    }}>
                      <PictureOutlined style={{ fontSize: 48, color: '#444' }} />
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
                      ? <span style={{ color: '#ff4d4f' }}>{task.error_message.length > 40 ? task.error_message.slice(0, 40) + '...' : task.error_message}</span>
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
        onCancel={() => { setIsModalOpen(false); setIsCreating(false); setSelectedStyleId(null); }}
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
                  <h4 style={{ margin: '0 0 12px 0' }}>选择参考素材</h4>
                  <Form.Item 
                    name="references"
                    extra={
                      <span style={{ color: '#888', fontSize: 12 }}>
                        按顺序选择参考素材，可在提示词中使用"第一个图"、"第二个图"等引用不同素材
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
                  
                  {/* 风格选择 */}
                  <h4 style={{ margin: '16px 0 12px 0' }}>风格选择</h4>
                  <Form.Item 
                    name="style_id"
                    extra={
                      <span style={{ color: '#888', fontSize: 12 }}>
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
                        background: '#1a1a1a', 
                        borderRadius: 8,
                        border: '1px solid #333',
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
                              <div style={{ marginTop: 8, fontSize: 12, color: '#888' }}>
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
                    background: '#1a1a1a', 
                    borderRadius: 8,
                    textAlign: 'center',
                    color: '#666',
                    marginTop: 16
                  }}>
                    <PictureOutlined style={{ fontSize: 48, marginBottom: 12, color: '#444' }} />
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
                      <div style={{ color: '#ff4d4f', fontWeight: 500, marginBottom: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
                        <CloseCircleOutlined /> 生成失败
                      </div>
                      <div style={{ color: '#ff7875', fontSize: 13, wordBreak: 'break-all' }}>
                        {selectedTask.error_message}
                      </div>
                    </div>
                  )}
                  
                  {/* 参考素材选择 */}
                  <div style={{ marginBottom: 16 }}>
                    <Form.Item 
                      name="references"
                      label="参考素材"
                      extra={
                        <span style={{ color: '#888', fontSize: 12 }}>
                          按顺序选择参考素材，可在提示词中使用"第一个图"、"第二个图"等引用不同素材
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
                  </div>
                  
                  {/* 生成的图片 */}
                  {selectedTask.images.length > 0 ? (
                    <Image.PreviewGroup
                      items={selectedTask.images.filter(img => img.url).map(img => img.url!)}
                    >
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 }}>
                        {selectedTask.images.map((image, idx) => (
                          <div 
                            key={image.id}
                            style={{ 
                              position: 'relative',
                              aspectRatio: '1',
                              background: '#1a1a1a',
                              borderRadius: 8,
                              overflow: 'hidden',
                              border: selectedImages.has(image.id) ? '2px solid #1890ff' : '2px solid transparent'
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
                                <PictureOutlined style={{ fontSize: 32, color: '#444' }} />
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
                          <div style={{ color: '#ff4d4f', fontWeight: 500, marginBottom: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
                            <CloseCircleOutlined /> 生成失败
                          </div>
                          <div style={{ color: '#ff7875', fontSize: 13, wordBreak: 'break-all' }}>
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
                    availableModels[watchedModel || selectedTask?.model || 'wan2.6-image']?.description
                  }
                >
                  <Select 
                    options={Object.values(availableModels).map(m => ({ 
                      label: `${m.name} ${m.id}`, 
                      value: m.id 
                    }))} 
                    onChange={() => form.setFieldsValue({})} // 触发重新渲染显示描述
                  />
                </Form.Item>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                  <Form.Item 
                    name="n" 
                    label="生图数量" 
                    tooltip="每次请求生成的图片数量"
                    extra={(() => {
                      const model = watchedModel || selectedTask?.model
                      if (model?.startsWith('qwen-image-edit')) return '最多6张'
                      if (model === 'wan2.5-i2i-preview') return '最多4张'
                      return ''
                    })()}
                  >
                    <InputNumber 
                      min={1} 
                      max={(() => {
                        const model = watchedModel || selectedTask?.model
                        if (model?.startsWith('qwen-image-edit')) return 6
                        if (model === 'wan2.5-i2i-preview') return 4
                        return 4
                      })()}
                      style={{ width: '100%' }} 
                    />
                  </Form.Item>
                  <Form.Item 
                    name="group_count" 
                    label="并发组数" 
                    tooltip="并发请求数，总图片数 = 生图数量 × 并发组数"
                    extra={`总计: ${(form.getFieldValue('n') || 1) * (form.getFieldValue('group_count') || 1)} 张`}
                  >
                    <InputNumber 
                      min={1} 
                      max={10} 
                      style={{ width: '100%' }} 
                    />
                  </Form.Item>
                </div>
                <Form.Item name="prompt" label="生成提示词" extra={
                  (watchedModel || selectedTask?.model)?.startsWith('qwen-image-edit')
                    ? '多图时用"图1"、"图2"、"图3"指代不同图片'
                    : ''
                }>
                  <TextArea rows={4} />
                </Form.Item>
                <Form.Item name="negative_prompt" label="负向提示词">
                  <TextArea rows={2} />
                </Form.Item>
                
                {/* 文生图模型参数 */}
                {availableModels[watchedModel || selectedTask?.model || '']?.model_type === 'text_to_image' && (
                  <div style={{ 
                    marginBottom: 16
                  }}>
                    <div style={{ marginBottom: 8, color: '#888', fontSize: 12 }}>
                      文生图模型参数
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                      <Form.Item 
                        name="size" 
                        label="输出尺寸"
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
                        label="随机种子"
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
                        label="智能改写"
                        valuePropName="checked"
                        initialValue={true}
                        style={{ marginBottom: 0 }}
                      >
                        <Switch checkedChildren="开" unCheckedChildren="关" />
                      </Form.Item>
                      <Form.Item 
                        name="watermark" 
                        label="水印"
                        valuePropName="checked"
                        initialValue={false}
                        style={{ marginBottom: 0 }}
                      >
                        <Switch checkedChildren="开" unCheckedChildren="关" />
                      </Form.Item>
                    </div>
                    <div style={{ marginTop: 8, color: '#666', fontSize: 11 }}>
                      提示：文生图模型不需要参考图片，只需要输入提示词
                    </div>
                  </div>
                )}

                {/* wan2.6-image 模型参数 */}
                {(watchedModel || selectedTask?.model) === 'wan2.6-image' && (
                  <div style={{ 
                    marginBottom: 16
                  }}>
                    <div style={{ marginBottom: 8, color: '#888', fontSize: 12 }}>
                      Wan2.6 图像生成参数
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                      <Form.Item 
                        name="size" 
                        label="输出尺寸"
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
                        label="图文混合模式"
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
                          label="最大图片数"
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
                        label="智能改写"
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
                        label="水印"
                        valuePropName="checked"
                        initialValue={false}
                        style={{ marginBottom: 0 }}
                        tooltip="在图片右下角添加'AI生成'水印"
                      >
                        <Switch checkedChildren="开" unCheckedChildren="关" />
                      </Form.Item>
                      <Form.Item 
                        name="seed" 
                        label="随机种子"
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
                    <div style={{ marginTop: 8, padding: '8px', background: '#252525', borderRadius: 4, fontSize: 11 }}>
                      <div style={{ color: '#888', marginBottom: 4 }}>📝 模式说明：</div>
                      <div style={{ color: '#666' }}>
                        {watchedEnableInterleave ? (
                          <>• <strong>图文混合模式</strong>：根据提示词生成图文并茂的内容，支持0-1张参考图</>
                        ) : (
                          <>• <strong>参考图模式</strong>：基于1-4张参考图进行风格迁移、主体一致性生成</>
                        )}
                      </div>
                      {!watchedEnableInterleave && (
                        <div style={{ color: '#d89614', marginTop: 4 }}>
                          ⚠️ 参考图模式下必须选择至少1张参考图
                        </div>
                      )}
                      <div style={{ color: '#555', marginTop: 4 }}>
                        参考图要求：宽高 384-5000px，格式 JPEG/PNG/BMP/WEBP，≤10MB
                      </div>
                    </div>
                  </div>
                )}

                {/* qwen-image-edit 系列专用参数 */}
                {(watchedModel || selectedTask?.model)?.startsWith('qwen-image-edit') && (() => {
                  const currentQwenModel = watchedModel || selectedTask?.model || 'qwen-image-edit-max'
                  const qwenModelInfo = availableModels[currentQwenModel]
                  return (
                    <div style={{ marginBottom: 16 }}>
                      <div style={{ marginBottom: 8, color: '#888', fontSize: 12 }}>
                        {qwenModelInfo?.name || currentQwenModel} 参数
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                        <Form.Item 
                          name="size" 
                          label="输出尺寸"
                          style={{ marginBottom: 0 }}
                        >
                          <Select
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
                          label="随机种子"
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
                          label="智能改写"
                          valuePropName="checked"
                          style={{ marginBottom: 0 }}
                          tooltip="开启后模型优化提示词，对简单描述效果更明显"
                        >
                          <Switch defaultChecked />
                        </Form.Item>
                        <Form.Item 
                          name="watermark" 
                          label="添加水印"
                          valuePropName="checked"
                          style={{ marginBottom: 0 }}
                        >
                          <Switch />
                        </Form.Item>
                      </div>
                      <div style={{ marginTop: 8, padding: '8px', background: '#252525', borderRadius: 4, fontSize: 11 }}>
                        <div style={{ color: '#666' }}>
                          • 支持1-3张输入图片，1张为单图编辑，2-3张为多图融合
                        </div>
                        <div style={{ color: '#666', marginTop: 2 }}>
                          • 多图时用"图1"、"图2"、"图3"指代不同图片，输出比例以最后一张为准
                        </div>
                        <div style={{ color: '#555', marginTop: 2 }}>
                          输入图建议：384-3072px，格式 JPG/PNG/BMP/WEBP/TIFF，≤10MB
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
                      loading={isGenerating}
                      block
                    >
                      开始生成
                    </Button>
                    <Button onClick={() => { setIsModalOpen(false); setIsCreating(false); setSelectedStyleId(null); }} block>
                      取消
                    </Button>
                  </>
                ) : selectedTask && (
                  <>
                    <Button 
                      type="primary" 
                      icon={<ThunderboltOutlined />} 
                      onClick={generateImages}
                      loading={isGenerating}
                      block
                    >
                      {selectedTask.images.length > 0 ? '重新生成' : '开始生成'}
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
              
              {/* 追踪ID显示 */}
              {!isCreating && selectedTask && (selectedTask.last_task_id || selectedTask.last_request_id) && (
                <div style={{ 
                  marginTop: 16, 
                  padding: '8px 12px', 
                  background: '#1a1a1a', 
                  borderRadius: 6,
                  fontSize: 11,
                  color: '#666',
                  fontFamily: 'monospace'
                }}>
                  {selectedTask.last_task_id && (
                    <div>Task ID: {selectedTask.last_task_id}</div>
                  )}
                  {selectedTask.last_request_id && (
                    <div>Request ID: {selectedTask.last_request_id}</div>
                  )}
                </div>
              )}
            </div>
          </div>
          </Form>
        )}
      </Modal>
    </div>
  )
}

export default StudioPage

