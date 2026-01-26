import { useEffect, useState, useCallback, useRef } from 'react'
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

const { TextArea } = Input

const StudioPage = () => {
  const { projectId } = useParams<{ projectId: string }>()
  const { currentProject, fetchProject } = useProjectStore()
  
  const [tasks, setTasks] = useState<StudioTask[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedTask, setSelectedTask] = useState<StudioTask | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)
  const [isGenerating, setIsGenerating] = useState(false)
  const [selectedImages, setSelectedImages] = useState<Set<string>>(new Set())
  const [form] = Form.useForm()
  const [createForm] = Form.useForm()
  
  // 素材选择
  const [characters, setCharacters] = useState<Character[]>([])
  const [scenes, setScenes] = useState<Scene[]>([])
  const [props, setProps] = useState<Prop[]>([])
  const [galleryImages, setGalleryImages] = useState<GalleryImage[]>([])
  const [styles, setStyles] = useState<Style[]>([])
  const [availableModels, setAvailableModels] = useState<Record<string, {
    id: string
    name: string
    description?: string
    model_type?: 'text_to_image' | 'image_to_image' | 'image_generation'
    capabilities?: {
      supports_batch?: boolean
      supports_async?: boolean
      supports_negative_prompt?: boolean
      supports_prompt_extend?: boolean
      supports_watermark?: boolean
      supports_seed?: boolean
      max_n?: number
      supports_reference_images?: boolean
      supports_interleave?: boolean
      max_reference_images?: number
    }
    parameters?: any[]
    common_sizes?: string[]
  }>>({})
  
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
        
        const [tasksRes, charactersRes, scenesRes, propsRes, galleryRes, stylesRes, modelsRes] = await Promise.all([
          studioApi.list(projectId),
          charactersApi.list(projectId),
          scenesApi.list(projectId),
          propsApi.list(projectId),
          galleryApi.list(projectId),
          stylesApi.list(projectId),
          studioApi.getAvailableModels().catch(() => ({ 
            models: {
              'wan2.5-i2i-preview': {
                id: 'wan2.5-i2i-preview',
                name: '图生图 wan2.5-i2i-preview',
                description: '风格迁移和多图融合'
              }
            }
          }))
        ])
        
        safeSetState(setTasks, tasksRes.tasks)
        safeSetState(setCharacters, charactersRes.characters)
        safeSetState(setScenes, scenesRes.scenes)
        safeSetState(setProps, propsRes.props)
        safeSetState(setGalleryImages, galleryRes.images)
        safeSetState(setStyles, stylesRes.styles)
        safeSetState(setAvailableModels, modelsRes.models || {})
      } catch (error) {
        message.error('加载失败')
      } finally {
        safeSetState(setLoading, false)
      }
    }
    loadData()
  }, [projectId, fetchProject, safeSetState])

  const openCreateModal = () => {
    createForm.resetFields()
    createForm.setFieldsValue({
      model: 'wan2.5-i2i-preview',
      n: 1,  // 每次请求生成的图片数量
      group_count: 3  // 并发请求数
    })
    setIsCreateModalOpen(true)
  }

  const createTask = async () => {
    if (!projectId) return
    try {
      const values = await createForm.validateFields()
      
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
            // 图片风格：作为最后一个参考图片加入
            const styleImageUrl = getStyleImageUrl(style)
            if (styleImageUrl) {
              references = [...references, { type: 'style', id: style.id }]
              // 在提示词中添加风格参考说明
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
            // 文本风格：嵌入提示词尾部
            if (style.text_style_content) {
              finalPrompt = `${finalPrompt}。风格要求：${style.text_style_content}`
            }
          }
        }
      }
      
      const task = await studioApi.create({
        project_id: projectId,
        name: values.name,
        description: values.description,
        model: values.model,
        prompt: finalPrompt,
        negative_prompt: finalNegativePrompt,
        n: values.n || 1,
        group_count: values.group_count,
        references
      })
      
      safeSetState(setTasks, (prev: StudioTask[]) => [task, ...prev])
      setIsCreateModalOpen(false)
      setSelectedStyleId(null)
      message.success('任务已创建')
      
      // 自动打开编辑弹窗
      openTaskModal(task)
    } catch (error) {
      message.error('创建失败')
    }
  }

  const openTaskModal = (task: StudioTask) => {
    setSelectedTask(task)
    setSelectedImages(new Set())
    form.setFieldsValue({
      name: task.name,
      description: task.description,
      model: task.model,
      prompt: task.prompt,
      negative_prompt: task.negative_prompt,
      n: task.n || 1,
      group_count: task.group_count || 3,  // 默认3组并发
      // 加载保存的高级参数（如果有），否则使用默认值
      size: task.size || '',
      prompt_extend: task.prompt_extend !== undefined ? task.prompt_extend : true,
      watermark: task.watermark !== undefined ? task.watermark : false,
      seed: task.seed || undefined,
      // wan2.6-image 专用参数
      enable_interleave: task.enable_interleave || false,
      max_images: task.max_images || 5
    })
    setIsModalOpen(true)
  }

  const saveTask = async () => {
    if (!selectedTask) return
    try {
      const values = await form.validateFields()
      const updated = await studioApi.update(selectedTask.id, {
        name: values.name,
        description: values.description,
        model: values.model,
        prompt: values.prompt,
        negative_prompt: values.negative_prompt,
        n: values.n,
        group_count: values.group_count,
        // 保存高级生成参数
        size: values.size || undefined,
        prompt_extend: values.prompt_extend,
        watermark: values.watermark,
        seed: values.seed || undefined,
        // wan2.6-image 专用参数
        enable_interleave: values.enable_interleave,
        max_images: values.max_images
      })
      safeSetState(setTasks, (prev: StudioTask[]) => prev.map(t => t.id === updated.id ? updated : t))
      setSelectedTask(updated)
      message.success('任务已保存')
    } catch (error) {
      message.error('保存失败')
    }
  }

  const generateImages = async () => {
    if (!selectedTask) return
    
    const values = form.getFieldsValue()
    const modelInfo = availableModels[values.model]
    const isTextToImage = modelInfo?.model_type === 'text_to_image'
    const isWan26Image = values.model === 'wan2.6-image'
    const isQwenModel = values.model === 'qwen-image-edit-plus'
    
    // 图生图模型需要参考素材（wan2.6-image 支持无参考图模式）
    const needsReferences = !isTextToImage && !isWan26Image
    if (needsReferences && selectedTask.references.length === 0) {
      message.warning('请先添加参考素材')
      return
    }
    
    // 验证 wan2.6-image 的参考图数量
    if (isWan26Image) {
      const refCount = selectedTask.references.length
      const enableInterleave = values.enable_interleave || false
      if (enableInterleave) {
        // 图文混合模式：最多1张参考图
        if (refCount > 1) {
          message.warning('图文混合模式下最多只能添加1张参考图')
          return
        }
      } else {
        // 参考图模式：0-3张参考图
        if (refCount > 3) {
          message.warning('参考图模式下最多只能添加3张参考图')
          return
        }
      }
    }
    
    // 验证 qwen-image-edit-plus 的参数
    if (isQwenModel) {
      if (values.size && values.n > 1) {
        message.warning('设置输出尺寸时，生图数量必须为1')
        return
      }
      if (selectedTask.references.length > 3) {
        message.warning('qwen-image-edit-plus 最多支持3张输入图片')
        return
      }
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
      
      // qwen-image-edit-plus 专用参数
      if (isQwenModel) {
        if (values.size) generateParams.size = values.size
        generateParams.prompt_extend = values.prompt_extend !== false  // 默认 true
        generateParams.watermark = values.watermark || false
        if (values.seed) generateParams.seed = values.seed
      }
      
      const result = await studioApi.generate(selectedTask.id, generateParams)
      
      safeSetState(setTasks, (prev: StudioTask[]) => prev.map(t => t.id === result.task.id ? result.task : t))
      setSelectedTask(result.task)
      message.success('图片生成完成')
    } catch (error: any) {
      message.error(error?.message || '图片生成失败')
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
                    {task.images.length > 0 ? `${task.images.length} 张图片` : '暂无图片'}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* 新建任务弹窗 */}
      <Modal
        title="新建生图任务"
        open={isCreateModalOpen}
        onOk={createTask}
        onCancel={() => setIsCreateModalOpen(false)}
        okText="创建"
        cancelText="取消"
        width={700}
      >
        <Form form={createForm} layout="vertical">
          <Form.Item name="name" label="任务名称" rules={[{ required: true, message: '请输入任务名称' }]}>
            <Input placeholder="例如：角色合影生成" />
          </Form.Item>
          <Form.Item name="description" label="任务描述">
            <TextArea rows={2} placeholder="描述这个任务的目的" />
          </Form.Item>
          <Form.Item 
            name="references" 
            label="选择参考素材（多图生图）" 
            extra={
              <span style={{ color: '#888' }}>
                按顺序选择参考素材，可在提示词中使用"<strong>第一个图</strong>"、"<strong>第二个图</strong>"等引用不同素材。
                例如："第一个图中的人和第二个图中的人在第三个图的场景中坐着"
              </span>
            }
          >
            <Select
              mode="multiple"
              placeholder="按顺序选择参考素材"
              options={buildReferenceOptions()}
              style={{ width: '100%' }}
              optionFilterProp="children"
            />
          </Form.Item>
          
          {/* 独立的风格选择模块 */}
          <Form.Item 
            name="style_id" 
            label="风格选择" 
            extra={
              <span style={{ color: '#888' }}>
                图片风格：风格图作为最后一个参考图片加入素材。
                文本风格：风格描述嵌入提示词尾部。
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
          
          {/* 显示选中风格的预览 */}
          {selectedStyleId && (() => {
            const style = styles.find(s => s.id === selectedStyleId)
            if (!style) return null
            return (
              <div style={{ 
                marginBottom: 16, 
                padding: 12, 
                background: '#1a1a1a', 
                borderRadius: 8,
                border: '1px solid #333'
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
                    {style.style_type === 'image' && style.style_prompt && (
                      <div style={{ marginTop: 8, fontSize: 12, color: '#888' }}>
                        {style.style_prompt.slice(0, 100)}...
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )
          })()}
          <Form.Item name="model" label="生成模型" extra={
            availableModels[createForm.getFieldValue('model')]?.description
          }>
            <Select 
              options={Object.values(availableModels).map(m => ({ 
                label: m.name, 
                value: m.id 
              }))} 
              onChange={() => createForm.setFieldsValue({})} // 触发重新渲染显示描述
            />
          </Form.Item>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <Form.Item 
              name="n" 
              label="生图数量" 
              tooltip="每次请求生成的图片数量"
              extra={(() => {
                const model = createForm.getFieldValue('model')
                const modelInfo = availableModels[model]
                if (model === 'qwen-image-edit-plus') return '最多6张'
                if (modelInfo?.capabilities?.max_n) return `最多${modelInfo.capabilities.max_n}张`
                return '最多4张'
              })()}
            >
              <InputNumber 
                min={1} 
                max={(() => {
                  const model = createForm.getFieldValue('model')
                  const modelInfo = availableModels[model]
                  if (model === 'qwen-image-edit-plus') return 6
                  if (modelInfo?.capabilities?.max_n) return modelInfo.capabilities.max_n
                  return 4
                })()}
                style={{ width: '100%' }} 
              />
            </Form.Item>
            <Form.Item 
              name="group_count" 
              label="并发组数" 
              tooltip="并发请求数，总图片数 = 生图数量 × 并发组数"
            >
              <InputNumber min={1} max={10} style={{ width: '100%' }} />
            </Form.Item>
          </div>
          <Form.Item name="prompt" label="生成提示词">
            <TextArea rows={3} placeholder="描述要生成的图片内容" />
          </Form.Item>
          <Form.Item name="negative_prompt" label="负向提示词">
            <TextArea rows={2} placeholder="描述不希望出现的内容" />
          </Form.Item>

          {/* 文生图模型参数 */}
          {availableModels[createForm.getFieldValue('model')]?.model_type === 'text_to_image' && (
            <div style={{ 
              padding: '12px', 
              background: '#1a1a1a', 
              borderRadius: 8, 
              marginTop: 16,
              border: '1px solid #333'
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
                    placeholder="默认 1280×1280"
                    allowClear
                    options={[
                      { value: '1280*1280', label: '1280×1280 (1:1)' },
                      { value: '1024*1024', label: '1024×1024 (1:1)' },
                      { value: '1280*720', label: '1280×720 (16:9)' },
                      { value: '720*1280', label: '720×1280 (9:16)' },
                      { value: '1280*960', label: '1280×960 (4:3)' },
                      { value: '960*1280', label: '960×1280 (3:4)' },
                      { value: '1200*800', label: '1200×800 (3:2)' },
                      { value: '800*1200', label: '800×1200 (2:3)' },
                      { value: '1344*576', label: '1344×576 (21:9)' },
                    ]}
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
          {createForm.getFieldValue('model') === 'wan2.6-image' && (
            <div style={{ 
              padding: '12px', 
              background: '#1a1a1a', 
              borderRadius: 8, 
              marginTop: 16,
              border: '1px solid #333'
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
                    placeholder="默认 1280×1280"
                    allowClear
                    options={[
                      { value: '1280*1280', label: '1280×1280 (1:1)' },
                      { value: '1024*1024', label: '1024×1024 (1:1)' },
                      { value: '1280*720', label: '1280×720 (16:9)' },
                      { value: '720*1280', label: '720×1280 (9:16)' },
                      { value: '1280*960', label: '1280×960 (4:3)' },
                      { value: '960*1280', label: '960×1280 (3:4)' },
                      { value: '1200*800', label: '1200×800 (3:2)' },
                      { value: '800*1200', label: '800×1200 (2:3)' },
                      { value: '1344*576', label: '1344×576 (21:9 超宽)' },
                    ]}
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
                        // 图文混合模式：n 固定为 1
                        createForm.setFieldValue('n', 1)
                      }
                    }}
                  />
                </Form.Item>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                <Form.Item 
                  name="n" 
                  label="生图数量"
                  style={{ marginBottom: 0 }}
                  initialValue={4}
                  tooltip={createForm.getFieldValue('enable_interleave') 
                    ? "图文混合模式下固定为1" 
                    : "参考图模式下可选1-4张"}
                >
                  <InputNumber 
                    min={1} 
                    max={createForm.getFieldValue('enable_interleave') ? 1 : 4}
                    disabled={createForm.getFieldValue('enable_interleave')}
                    style={{ width: '100%' }} 
                    placeholder="默认4张"
                  />
                </Form.Item>
                {createForm.getFieldValue('enable_interleave') && (
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
                )}
              </div>
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
                    disabled={createForm.getFieldValue('enable_interleave')}
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
                  {createForm.getFieldValue('enable_interleave') ? (
                    <>• <strong>图文混合模式</strong>：根据提示词生成图文并茂的内容，支持0-1张参考图</>
                  ) : (
                    <>• <strong>参考图模式</strong>：基于1-3张参考图进行风格迁移、主体一致性生成，支持0张时为纯文生图</>
                  )}
                </div>
                <div style={{ color: '#555', marginTop: 4 }}>
                  参考图要求：宽高 384-5000px，格式 JPEG/PNG/BMP/WEBP，≤10MB
                </div>
              </div>
            </div>
          )}
        </Form>
      </Modal>

      {/* 任务详情/编辑弹窗 */}
      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span>任务详情 - {selectedTask?.name}</span>
            {selectedTask && getStatusTag(selectedTask.status)}
          </div>
        }
        open={isModalOpen}
        onCancel={() => setIsModalOpen(false)}
        footer={null}
        width={1100}
      >
        {selectedTask && (
          <div style={{ display: 'flex', gap: 24 }}>
            {/* 左侧：生成结果 */}
            <div style={{ width: 500 }}>
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
              
              {/* 参考素材预览 */}
              {selectedTask.references.length > 0 && (
                <div style={{ marginBottom: 16 }}>
                  <div style={{ fontSize: 12, color: '#888', marginBottom: 8 }}>
                    参考素材（按选择顺序，可在提示词中使用"第一个图"、"第二个图"等引用）：
                  </div>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {selectedTask.references.map((ref, idx) => (
                      <Tooltip key={idx} title={`第${idx + 1}个图: ${ref.name} (${ref.type})`}>
                        <div style={{ 
                          position: 'relative',
                          width: 60, 
                          height: 60, 
                          borderRadius: 6, 
                          overflow: 'hidden',
                          border: '1px solid #333',
                          background: '#1a1a1a'
                        }}>
                          {ref.url ? (
                            <img src={ref.url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                          ) : (
                            <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                              <PictureOutlined style={{ color: '#444' }} />
                            </div>
                          )}
                          {/* 序号标签 */}
                          <div style={{ 
                            position: 'absolute', 
                            top: 2, 
                            left: 2, 
                            background: 'rgba(0,0,0,0.7)', 
                            color: '#fff',
                            fontSize: 10,
                            padding: '1px 4px',
                            borderRadius: 3
                          }}>
                            {idx + 1}
                          </div>
                        </div>
                      </Tooltip>
                    ))}
                  </div>
                </div>
              )}
              
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
                <Empty 
                  description="暂无生成结果，点击右侧生成按钮开始" 
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                />
              )}
            </div>

            {/* 右侧：配置和操作 */}
            <div style={{ flex: 1 }}>
              <Form form={form} layout="vertical">
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
                    selectedTask && availableModels[form.getFieldValue('model') || selectedTask.model]?.description
                  }
                >
                  <Select 
                    options={Object.values(availableModels).map(m => ({ 
                      label: m.name, 
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
                      const model = form.getFieldValue('model') || selectedTask?.model
                      if (model === 'qwen-image-edit-plus') return '最多6张，设置size时只能1张'
                      if (model === 'wan2.5-i2i-preview') return '最多4张'
                      return ''
                    })()}
                  >
                    <InputNumber 
                      min={1} 
                      max={(() => {
                        const model = form.getFieldValue('model') || selectedTask?.model
                        if (model === 'qwen-image-edit-plus') return 6
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
                  (form.getFieldValue('model') || selectedTask?.model) === 'qwen-image-edit-plus'
                    ? '多图时用"图1"、"图2"、"图3"指代不同图片'
                    : ''
                }>
                  <TextArea rows={4} />
                </Form.Item>
                <Form.Item name="negative_prompt" label="负向提示词">
                  <TextArea rows={2} />
                </Form.Item>
                
                {/* 文生图模型参数 */}
                {availableModels[form.getFieldValue('model') || selectedTask?.model || '']?.model_type === 'text_to_image' && (
                  <div style={{ 
                    padding: '12px', 
                    background: '#1a1a1a', 
                    borderRadius: 8, 
                    marginBottom: 16,
                    border: '1px solid #333'
                  }}>
                    <div style={{ marginBottom: 8, color: '#888', fontSize: 12 }}>
                      文生图模型参数（wan2.6-t2i 总像素需在1280×1280到1440×1440之间）
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                      <Form.Item 
                        name="size" 
                        label="输出尺寸"
                        style={{ marginBottom: 0 }}
                      >
                        <Select
                          placeholder="默认 1280×1280"
                          allowClear
                          options={[
                            { value: '1280*1280', label: '1280×1280 (1:1 默认)' },
                            { value: '1696*960', label: '1696×960 (16:9 横屏)' },
                            { value: '960*1696', label: '960×1696 (9:16 竖屏)' },
                            { value: '1472*1104', label: '1472×1104 (4:3 横屏)' },
                            { value: '1104*1472', label: '1104×1472 (3:4 竖屏)' },
                            { value: '1440*1152', label: '1440×1152 (5:4 横屏)' },
                            { value: '1152*1440', label: '1152×1440 (4:5 竖屏)' },
                          ]}
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
                {(form.getFieldValue('model') || selectedTask?.model) === 'wan2.6-image' && (
                  <div style={{ 
                    padding: '12px', 
                    background: '#1a1a1a', 
                    borderRadius: 8, 
                    marginBottom: 16,
                    border: '1px solid #333'
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
                          placeholder="默认 1280×1280"
                          allowClear
                          options={[
                            { value: '1280*1280', label: '1280×1280 (1:1)' },
                            { value: '1024*1024', label: '1024×1024 (1:1)' },
                            { value: '1280*720', label: '1280×720 (16:9)' },
                            { value: '720*1280', label: '720×1280 (9:16)' },
                            { value: '1280*960', label: '1280×960 (4:3)' },
                            { value: '960*1280', label: '960×1280 (3:4)' },
                            { value: '1200*800', label: '1200×800 (3:2)' },
                            { value: '800*1200', label: '800×1200 (2:3)' },
                            { value: '1344*576', label: '1344×576 (21:9 超宽)' },
                          ]}
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
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                      <Form.Item 
                        name="n" 
                        label="生图数量"
                        style={{ marginBottom: 0 }}
                        tooltip={form.getFieldValue('enable_interleave') 
                          ? "图文混合模式下固定为1" 
                          : "参考图模式下可选1-4张"}
                      >
                        <InputNumber 
                          min={1} 
                          max={form.getFieldValue('enable_interleave') ? 1 : 4}
                          disabled={form.getFieldValue('enable_interleave')}
                          style={{ width: '100%' }} 
                          placeholder="默认4张"
                        />
                      </Form.Item>
                      {form.getFieldValue('enable_interleave') && (
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
                      )}
                    </div>
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
                          disabled={form.getFieldValue('enable_interleave')}
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
                        {form.getFieldValue('enable_interleave') ? (
                          <>• <strong>图文混合模式</strong>：根据提示词生成图文并茂的内容，支持0-1张参考图</>
                        ) : (
                          <>• <strong>参考图模式</strong>：基于1-3张参考图进行风格迁移、主体一致性生成，支持0张时为纯文生图</>
                        )}
                      </div>
                      <div style={{ color: '#555', marginTop: 4 }}>
                        参考图要求：宽高 384-5000px，格式 JPEG/PNG/BMP/WEBP，≤10MB
                      </div>
                    </div>
                  </div>
                )}

                {/* qwen-image-edit-plus 专用参数 */}
                {(form.getFieldValue('model') || selectedTask?.model) === 'qwen-image-edit-plus' && (
                  <>
                    <div style={{ 
                      padding: '12px', 
                      background: '#1a1a1a', 
                      borderRadius: 8, 
                      marginBottom: 16,
                      border: '1px solid #333'
                    }}>
                      <div style={{ marginBottom: 8, color: '#888', fontSize: 12 }}>
                        qwen-image-edit-plus 高级参数
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                        <Form.Item 
                          name="size" 
                          label="输出尺寸"
                          style={{ marginBottom: 8 }}
                          extra="仅当生成数量为1时可用"
                        >
                          <Select
                            allowClear
                            placeholder="默认（保持原图比例）"
                            options={[
                              { value: '', label: '默认（保持原图比例）' },
                              { value: '1024*1024', label: '1024×1024 (1:1)' },
                              { value: '1280*720', label: '1280×720 (16:9)' },
                              { value: '720*1280', label: '720×1280 (9:16)' },
                              { value: '1024*768', label: '1024×768 (4:3)' },
                              { value: '768*1024', label: '768×1024 (3:4)' },
                              { value: '1920*1080', label: '1920×1080 (FHD)' },
                              { value: '1080*1920', label: '1080×1920 (FHD竖)' },
                              { value: '2048*2048', label: '2048×2048 (最大)' },
                            ]}
                            disabled={form.getFieldValue('group_count') > 1}
                          />
                        </Form.Item>
                        <Form.Item 
                          name="seed" 
                          label="随机种子"
                          style={{ marginBottom: 8 }}
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
                    </div>
                  </>
                )}
              </Form>
              
              <Space style={{ width: '100%' }} direction="vertical">
                <Button 
                  type="primary" 
                  icon={<ThunderboltOutlined />} 
                  onClick={generateImages}
                  loading={isGenerating}
                  block
                >
                  {selectedTask.images.length > 0 ? '重新生成' : '开始生成'}
                </Button>
                <Button onClick={saveTask} block>
                  保存任务配置
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
              </Space>
              
              {/* 追踪ID显示 */}
              {(selectedTask.last_task_id || selectedTask.last_request_id) && (
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
        )}
      </Modal>
    </div>
  )
}

export default StudioPage

