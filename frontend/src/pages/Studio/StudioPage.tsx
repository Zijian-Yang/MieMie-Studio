import { useEffect, useState, useCallback, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { 
  Button, Modal, Form, Input, Empty, Spin, message, 
  Image, Space, Popconfirm, Card, Tag, Tooltip, Select,
  InputNumber, Checkbox, Tabs, Radio, Progress
} from 'antd'
import { 
  PlusOutlined, DeleteOutlined, EditOutlined, PictureOutlined,
  ExclamationCircleOutlined, ThunderboltOutlined, SaveOutlined,
  CheckCircleOutlined, CloseCircleOutlined, SyncOutlined
} from '@ant-design/icons'
import { 
  studioApi, galleryApi, charactersApi, scenesApi, propsApi,
  StudioTask, GalleryImage, Character, Scene, Prop, ReferenceItem
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
  const [availableModels, setAvailableModels] = useState<string[]>([])
  
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
        
        const [tasksRes, charactersRes, scenesRes, propsRes, galleryRes, modelsRes] = await Promise.all([
          studioApi.list(projectId),
          charactersApi.list(projectId),
          scenesApi.list(projectId),
          propsApi.list(projectId),
          galleryApi.list(projectId),
          studioApi.getAvailableModels().catch(() => ({ models: ['wan2.5-i2i-preview'] }))
        ])
        
        safeSetState(setTasks, tasksRes.tasks)
        safeSetState(setCharacters, charactersRes.characters)
        safeSetState(setScenes, scenesRes.scenes)
        safeSetState(setProps, propsRes.props)
        safeSetState(setGalleryImages, galleryRes.images)
        safeSetState(setAvailableModels, modelsRes.models)
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
      group_count: 3
    })
    setIsCreateModalOpen(true)
  }

  const createTask = async () => {
    if (!projectId) return
    try {
      const values = await createForm.validateFields()
      
      // 解析选中的素材
      const references = (values.references || []).map((ref: string) => {
        const [type, id] = ref.split(':')
        return { type, id }
      })
      
      const task = await studioApi.create({
        project_id: projectId,
        name: values.name,
        description: values.description,
        model: values.model,
        prompt: values.prompt,
        negative_prompt: values.negative_prompt,
        group_count: values.group_count,
        references
      })
      
      safeSetState(setTasks, (prev: StudioTask[]) => [task, ...prev])
      setIsCreateModalOpen(false)
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
      group_count: task.group_count
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
        group_count: values.group_count
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
    
    if (selectedTask.references.length === 0) {
      message.warning('请先添加参考素材')
      return
    }
    
    const values = form.getFieldsValue()
    
    safeSetState(setIsGenerating, true)
    try {
      const result = await studioApi.generate(selectedTask.id, {
        prompt: values.prompt,
        negative_prompt: values.negative_prompt,
        group_count: values.group_count
      })
      
      safeSetState(setTasks, (prev: StudioTask[]) => prev.map(t => t.id === result.task.id ? result.task : t))
      setSelectedTask(result.task)
      message.success('图片生成完成')
    } catch (error) {
      message.error('图片生成失败')
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

  // 构建素材选择选项
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
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <Form.Item name="model" label="生成模型">
              <Select options={availableModels.map(m => ({ label: m, value: m }))} />
            </Form.Item>
            <Form.Item name="group_count" label="生成组数">
              <InputNumber min={1} max={10} style={{ width: '100%' }} />
            </Form.Item>
          </div>
          <Form.Item name="prompt" label="生成提示词">
            <TextArea rows={3} placeholder="描述要生成的图片内容" />
          </Form.Item>
          <Form.Item name="negative_prompt" label="负向提示词">
            <TextArea rows={2} placeholder="描述不希望出现的内容" />
          </Form.Item>
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
                        cursor: 'pointer',
                        border: selectedImages.has(image.id) ? '2px solid #1890ff' : '2px solid transparent'
                      }}
                      onClick={() => toggleImageSelection(image.id)}
                    >
                      {image.url ? (
                        <img 
                          src={image.url} 
                          alt={`第 ${idx + 1} 组`} 
                          style={{ width: '100%', height: '100%', objectFit: 'cover' }} 
                        />
                      ) : (
                        <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                          <PictureOutlined style={{ fontSize: 32, color: '#444' }} />
                        </div>
                      )}
                      <div style={{ position: 'absolute', top: 8, left: 8 }}>
                        <Checkbox checked={selectedImages.has(image.id)} />
                      </div>
                      <div style={{ position: 'absolute', bottom: 8, right: 8 }}>
                        <Tag>第 {idx + 1} 组</Tag>
                      </div>
                      {image.is_selected && (
                        <div style={{ position: 'absolute', top: 8, right: 8 }}>
                          <Tag color="green">已保存</Tag>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
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
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                  <Form.Item name="model" label="生成模型">
                    <Select options={availableModels.map(m => ({ label: m, value: m }))} />
                  </Form.Item>
                  <Form.Item name="group_count" label="生成组数">
                    <InputNumber min={1} max={10} style={{ width: '100%' }} />
                  </Form.Item>
                </div>
                <Form.Item name="prompt" label="生成提示词">
                  <TextArea rows={4} />
                </Form.Item>
                <Form.Item name="negative_prompt" label="负向提示词">
                  <TextArea rows={2} />
                </Form.Item>
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
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}

export default StudioPage

