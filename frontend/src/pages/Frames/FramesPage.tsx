import { useEffect, useState, useCallback, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { 
  Card, Button, Modal, Form, Input, Empty, Spin, message, 
  Image, Progress, Tooltip, Space, InputNumber, Select, Popconfirm,
  Tag, Tabs, Divider, Switch
} from 'antd'
import { 
  PlayCircleOutlined, ReloadOutlined, PictureOutlined, SettingOutlined,
  DragOutlined, EditOutlined, DeleteOutlined, StopOutlined, ThunderboltOutlined,
  SaveOutlined, PlusOutlined, ExclamationCircleOutlined
} from '@ant-design/icons'
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from '@dnd-kit/core'
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  horizontalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { framesApi, scriptsApi, galleryApi, charactersApi, scenesApi, propsApi, Frame, Shot, GalleryImage, Character, Scene, Prop } from '../../services/api'
import { useProjectStore } from '../../stores/projectStore'
import { useGenerationStore } from '../../stores/generationStore'

const { TextArea } = Input
const { Option } = Select

// 可拖拽的分镜卡片组件
interface SortableShotCardProps {
  shot: Shot
  frameUrl: string | null
  isGenerating: boolean
  onClick: () => void
  onDelete: () => void
}

const SortableShotCard = ({ shot, frameUrl, isGenerating, onClick, onDelete }: SortableShotCardProps) => {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: shot.id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    cursor: 'grab',
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="timeline-item"
    >
      {/* 拖拽手柄 */}
      <div 
        {...attributes} 
        {...listeners}
        style={{ 
          position: 'absolute', 
          top: 4, 
          left: 4, 
          zIndex: 10,
          padding: '2px 6px',
          background: 'rgba(0,0,0,0.6)',
          borderRadius: 4,
          cursor: 'grab'
        }}
      >
        <DragOutlined style={{ color: '#888', fontSize: 12 }} />
      </div>
      
      {/* 删除按钮 */}
      <Popconfirm
        title="确定删除此镜头？"
        description="将同时删除关联的首帧和视频"
        icon={<ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />}
        onConfirm={(e) => { e?.stopPropagation(); onDelete(); }}
        okText="删除"
        cancelText="取消"
        okButtonProps={{ danger: true }}
      >
        <div
          style={{
            position: 'absolute',
            top: 4,
            right: 4,
            zIndex: 10,
            padding: '2px 6px',
            background: 'rgba(0,0,0,0.6)',
            borderRadius: 4,
            cursor: 'pointer'
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <DeleteOutlined style={{ color: '#ff4d4f', fontSize: 12 }} />
        </div>
      </Popconfirm>
      
      <div 
        className="timeline-item-preview"
        onClick={onClick}
        style={{ cursor: 'pointer' }}
      >
        {isGenerating ? (
          <div style={{ 
            width: '100%', 
            height: '100%', 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center',
            background: '#242424'
          }}>
            <Spin />
          </div>
        ) : frameUrl ? (
          <Image
            src={frameUrl}
            alt={`镜头 ${shot.shot_number}`}
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
            <PictureOutlined style={{ fontSize: 24, color: '#444' }} />
          </div>
        )}
      </div>
      <div className="timeline-item-info" onClick={onClick} style={{ cursor: 'pointer' }}>
        <div style={{ fontWeight: 500, display: 'flex', alignItems: 'center', gap: 4 }}>
          <span>镜头 {shot.shot_number}</span>
          {frameUrl && <Tag color="green" style={{ fontSize: 10, padding: '0 4px', lineHeight: '16px' }}>已生成</Tag>}
        </div>
        <div style={{ color: '#888', fontSize: 11 }}>
          {shot.scene_type || '未设置'} · {shot.duration || 5}秒
        </div>
      </div>
    </div>
  )
}

const FramesPage = () => {
  const { projectId } = useParams<{ projectId: string }>()
  const { currentProject, fetchProject } = useProjectStore()
  const {
    frameGroupCount,
    setFrameGroupCount,
    addGeneratingItem,
    removeGeneratingItem,
    isItemGenerating,
    stopGeneration,
    setStopGeneration,
  } = useGenerationStore()
  
  const [frames, setFrames] = useState<Frame[]>([])
  const [shots, setShots] = useState<Shot[]>([])
  const [galleryImages, setGalleryImages] = useState<GalleryImage[]>([])
  const [characters, setCharacters] = useState<Character[]>([])
  const [scenes, setScenes] = useState<Scene[]>([])
  const [props, setProps] = useState<Prop[]>([])
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [batchProgress, setBatchProgress] = useState({ current: 0, total: 0 })
  const [selectedShot, setSelectedShot] = useState<Shot | null>(null)
  const [selectedFrame, setSelectedFrame] = useState<Frame | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [isGalleryModalOpen, setIsGalleryModalOpen] = useState(false)
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)
  const [settingsModalVisible, setSettingsModalVisible] = useState(false)
  const [form] = Form.useForm()
  const [shotForm] = Form.useForm()
  const [createForm] = Form.useForm()
  const [useReferences, setUseReferences] = useState(true)
  const [generatingGroups, setGeneratingGroups] = useState<Set<string>>(new Set())
  
  const shouldStopRef = useRef(false)
  const isMountedRef = useRef(true)

  // 拖拽传感器配置
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  )

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
        const [framesRes, galleryRes, charsRes, scenesRes, propsRes] = await Promise.all([
          framesApi.list(projectId),
          galleryApi.list(projectId),
          charactersApi.list(projectId),
          scenesApi.list(projectId),
          propsApi.list(projectId),
        ])
        safeSetState(setFrames, framesRes.frames)
        safeSetState(setGalleryImages, galleryRes.images)
        safeSetState(setCharacters, charsRes.characters)
        safeSetState(setScenes, scenesRes.scenes)
        safeSetState(setProps, propsRes.props)
      } catch (error) {
        message.error('加载失败')
      } finally {
        safeSetState(setLoading, false)
      }
    }
    loadData()
  }, [projectId, fetchProject, safeSetState])

  useEffect(() => {
    if (currentProject?.script?.shots) {
      setShots(currentProject.script.shots)
    }
  }, [currentProject])

  // 处理拖拽结束
  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event

    if (over && active.id !== over.id) {
      const oldIndex = shots.findIndex((shot) => shot.id === active.id)
      const newIndex = shots.findIndex((shot) => shot.id === over.id)

      const newShots = arrayMove(shots, oldIndex, newIndex)
      // 更新本地状态
      setShots(newShots)

      // 同步到后端
      if (projectId) {
        try {
          const shotIds = newShots.map(s => s.id)
          const result = await scriptsApi.reorderShots(projectId, shotIds)
          setShots(result.shots)
          message.success('顺序已保存')
          fetchProject(projectId).catch(() => {})
        } catch (error) {
          message.error('保存顺序失败')
          if (currentProject?.script?.shots) {
            setShots(currentProject.script.shots)
          }
        }
      }
    }
  }

  // 新增镜头
  const createShot = async () => {
    if (!projectId) return
    
    try {
      const values = await createForm.validateFields()
      const data = {
        ...values,
        characters: values.characters ? values.characters.split(',').map((s: string) => s.trim()).filter(Boolean) : [],
        props: values.props ? values.props.split(',').map((s: string) => s.trim()).filter(Boolean) : [],
      }
      
      const result = await scriptsApi.createShot(projectId, data)
      setShots(result.shots)
      setIsCreateModalOpen(false)
      createForm.resetFields()
      message.success('镜头已添加')
      fetchProject(projectId).catch(() => {})
    } catch (error) {
      message.error('添加失败')
    }
  }

  // 删除镜头
  const deleteShot = async (shotId: string) => {
    if (!projectId) return
    
    try {
      const result = await scriptsApi.deleteShot(projectId, shotId)
      setShots(result.shots)
      // 同时移除本地的 frame
      setFrames(prev => prev.filter(f => f.shot_id !== shotId))
      message.success('镜头已删除')
      fetchProject(projectId).catch(() => {})
    } catch (error) {
      message.error('删除失败')
    }
  }

  // 批量生成首帧
  const generateAllFrames = async () => {
    if (!projectId) return
    if (shots.length === 0) {
      message.warning('请先解析分镜脚本')
      return
    }
    
    shouldStopRef.current = false
    setStopGeneration(false)
    safeSetState(setGenerating, true)
    safeSetState(setBatchProgress, { current: 0, total: shots.length })
    
    let successCount = 0
    let errorCount = 0
    
    for (let i = 0; i < shots.length; i++) {
      if (shouldStopRef.current || stopGeneration) break
      
      const shot = shots[i]
      addGeneratingItem(shot.id)
      safeSetState(setBatchProgress, { current: i + 1, total: shots.length })
      
      try {
        // 构建首帧提示词
        const prompt = buildFramePrompt(shot)
        
        const result = await framesApi.generate({
          project_id: projectId,
          shot_id: shot.id,
          shot_number: shot.shot_number,
          prompt: prompt,
          negative_prompt: '',
          group_index: 0,
          use_shot_references: useReferences
        })
        
        safeSetState(setFrames, (prev: Frame[]) => {
          const exists = prev.find(f => f.shot_id === shot.id)
          if (exists) {
            return prev.map(f => f.shot_id === shot.id ? result.frame : f)
          }
          return [...prev, result.frame]
        })
        successCount++
      } catch (error) {
        errorCount++
      } finally {
        removeGeneratingItem(shot.id)
      }
    }
    
    safeSetState(setGenerating, false)
    safeSetState(setBatchProgress, { current: 0, total: 0 })
    
    if (shouldStopRef.current || stopGeneration) {
      message.info(`已停止生成，完成 ${successCount}/${shots.length} 个首帧`)
    } else if (errorCount === 0) {
      message.success(`成功生成 ${successCount} 个首帧`)
    } else {
      message.warning(`${successCount} 个成功，${errorCount} 个失败`)
    }
    
    fetchProject(projectId).catch(() => {})
  }

  // 构建首帧提示词
  const buildFramePrompt = (shot: Shot) => {
    const promptParts = ['电影级画面', '高清细节']
    
    if (shot.scene_setting) promptParts.push(`场景: ${shot.scene_setting}`)
    if (shot.scene_type) promptParts.push(`${shot.scene_type}镜头`)
    if (shot.composition) promptParts.push(`构图: ${shot.composition}`)
    if (shot.lighting) promptParts.push(`光线: ${shot.lighting}`)
    if (shot.mood) promptParts.push(`氛围: ${shot.mood}`)
    
    if (shot.characters?.length) {
      let charDesc = `画面中有${shot.characters.join(', ')}`
      if (shot.character_appearance) charDesc += `, ${shot.character_appearance}`
      if (shot.character_action) charDesc += `, 正在${shot.character_action}`
      promptParts.push(charDesc)
    }
    
    if (shot.props?.length) {
      promptParts.push(`道具: ${shot.props.join(', ')}`)
    }
    
    return promptParts.join(', ')
  }

  const handleStopGeneration = () => {
    shouldStopRef.current = true
    setStopGeneration(true)
    message.info('正在停止生成...')
  }

  // 打开分镜编辑弹窗
  const openShotModal = (shot: Shot) => {
    setSelectedShot(shot)
    const frame = frames.find(f => f.shot_id === shot.id)
    setSelectedFrame(frame || null)
    
    // 设置分镜表单
    shotForm.setFieldsValue({
      shot_design: shot.shot_design,
      scene_type: shot.scene_type,
      voice_subject: shot.voice_subject,
      dialogue: shot.dialogue,
      characters: shot.characters?.join(', '),
      character_appearance: shot.character_appearance,
      character_action: shot.character_action,
      scene_setting: shot.scene_setting,
      lighting: shot.lighting,
      mood: shot.mood,
      composition: shot.composition,
      props: shot.props?.join(', '),
      sound_effects: shot.sound_effects,
      duration: shot.duration,
      // 素材关联
      character_ids: shot.character_ids || [],
      scene_id: shot.scene_id,
      prop_ids: shot.prop_ids || [],
    })
    
    // 构建默认提示词
    form.setFieldsValue({
      prompt: frame?.prompt || buildFramePrompt(shot)
    })
    
    setIsModalOpen(true)
  }

  // 保存分镜信息
  const saveShotInfo = async () => {
    if (!projectId || !selectedShot) return
    
    try {
      const values = await shotForm.validateFields()
      const updateData = {
        ...values,
        characters: values.characters ? values.characters.split(',').map((s: string) => s.trim()).filter(Boolean) : [],
        props: values.props ? values.props.split(',').map((s: string) => s.trim()).filter(Boolean) : [],
        character_ids: values.character_ids || [],
        scene_id: values.scene_id || null,
        prop_ids: values.prop_ids || [],
        duration: Math.min(values.duration || 5, 10), // 确保不超过10秒
      }
      
      const result = await scriptsApi.updateShot(projectId, selectedShot.id, updateData)
      
      // 更新本地状态
      setShots(prev => prev.map(s => s.id === selectedShot.id ? result.shot : s))
      setSelectedShot(result.shot)
      
      message.success('分镜信息已保存')
      fetchProject(projectId).catch(() => {})
    } catch (error) {
      message.error('保存失败')
    }
  }

  // 生成单个首帧
  const generateSingleFrame = async (groupIndex: number = 0) => {
    if (!projectId || !selectedShot) return
    
    const values = await form.validateFields()
    const key = `${selectedShot.id}-${groupIndex}`
    
    setGeneratingGroups(prev => new Set([...prev, key]))
    addGeneratingItem(selectedShot.id)
    
    try {
      const result = await framesApi.generate({
        project_id: projectId,
        shot_id: selectedShot.id,
        shot_number: selectedShot.shot_number,
        prompt: values.prompt,
        negative_prompt: '',
        group_index: groupIndex,
        use_shot_references: useReferences
      })
      
      safeSetState(setFrames, (prev: Frame[]) => {
        const exists = prev.find(f => f.shot_id === selectedShot.id)
        if (exists) {
          return prev.map(f => f.shot_id === selectedShot.id ? result.frame : f)
        }
        return [...prev, result.frame]
      })
      
      setSelectedFrame(result.frame)
      message.success(`第 ${groupIndex + 1} 组首帧生成成功`)
      
      fetchProject(projectId).catch(() => {})
    } catch (error) {
      message.error(`第 ${groupIndex + 1} 组首帧生成失败`)
    } finally {
      setGeneratingGroups(prev => { const next = new Set(prev); next.delete(key); return next })
      removeGeneratingItem(selectedShot.id)
    }
  }

  // 生成所有组首帧
  const generateAllGroups = async () => {
    if (!selectedShot) return
    
    for (let i = 0; i < frameGroupCount; i++) {
      await generateSingleFrame(i)
    }
  }

  // 获取分镜的首帧URL
  const getFrameUrl = (shotId: string) => {
    const frame = frames.find(f => f.shot_id === shotId)
    if (frame?.image_groups?.[frame.selected_group_index]?.url) {
      return frame.image_groups[frame.selected_group_index].url
    }
    return null
  }

  // 从图库设置首帧
  const setFrameFromGallery = async (galleryImage: GalleryImage, groupIndex: number = 0) => {
    if (!projectId || !selectedShot) return
    
    try {
      const result = await framesApi.setFromGallery({
        project_id: projectId,
        shot_id: selectedShot.id,
        shot_number: selectedShot.shot_number,
        gallery_image_id: galleryImage.id,
        gallery_image_url: galleryImage.url,
        group_index: groupIndex
      })
      
      safeSetState(setFrames, (prev: Frame[]) => {
        const exists = prev.find(f => f.shot_id === selectedShot.id)
        if (exists) {
          return prev.map(f => f.shot_id === selectedShot.id ? result.frame : f)
        }
        return [...prev, result.frame]
      })
      
      setSelectedFrame(result.frame)
      setIsGalleryModalOpen(false)
      message.success('已从图库设置首帧')
      
      fetchProject(projectId).catch(() => {})
    } catch (error) {
      message.error('设置失败')
    }
  }

  // 保存首帧到图库
  const saveFrameToGallery = async () => {
    if (!selectedFrame) return
    
    try {
      await framesApi.saveToGallery(selectedFrame.id, {
        name: `首帧 - 镜头${selectedShot?.shot_number}`,
        description: '从分镜首帧保存'
      })
      message.success('已保存到图库')
      
      // 刷新图库数据
      if (projectId) {
        const galleryRes = await galleryApi.list(projectId)
        setGalleryImages(galleryRes.images)
      }
    } catch (error) {
      message.error('保存失败')
    }
  }

  // 获取角色选中的图片URL
  const getCharacterImageUrl = (char: Character) => {
    const group = char.image_groups?.[char.selected_group_index]
    return group?.front_url
  }

  // 获取场景选中的图片URL
  const getSceneImageUrl = (scene: Scene) => {
    const group = scene.image_groups?.[scene.selected_group_index]
    return group?.url
  }

  // 获取道具选中的图片URL
  const getPropImageUrl = (prop: Prop) => {
    const group = prop.image_groups?.[prop.selected_group_index]
    return group?.url
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
            分镜首帧
          </h1>
          <p style={{ color: '#888', margin: '4px 0 0', fontSize: 13 }}>
            {currentProject?.name} - 共 {shots.length} 个分镜（可拖拽调整顺序）
          </p>
        </div>
        <Space>
          <Tooltip title="使用分镜关联的角色/场景/道具进行多图生图">
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: '#1a1a1a', padding: '4px 12px', borderRadius: 6 }}>
              <span style={{ fontSize: 12, color: '#888' }}>素材参照</span>
              <Switch size="small" checked={useReferences} onChange={setUseReferences} />
            </div>
          </Tooltip>
          <Button icon={<PlusOutlined />} onClick={() => setIsCreateModalOpen(true)}>
            添加镜头
          </Button>
          <Button icon={<SettingOutlined />} onClick={() => setSettingsModalVisible(true)}>
            设置 ({frameGroupCount}组)
          </Button>
          {generating ? (
            <Button danger icon={<StopOutlined />} onClick={handleStopGeneration}>
              停止生成
            </Button>
          ) : (
            <Button
              type="primary"
              icon={<ThunderboltOutlined />}
              onClick={generateAllFrames}
              disabled={shots.length === 0}
            >
              批量生成首帧
            </Button>
          )}
        </Space>
      </div>

      {generating && (
        <Card style={{ marginBottom: 24 }}>
          <Progress 
            percent={batchProgress.total > 0 ? Math.round((batchProgress.current / batchProgress.total) * 100) : 0} 
            status="active" 
          />
          <p style={{ textAlign: 'center', marginTop: 8, color: '#888' }}>
            正在生成第 {batchProgress.current}/{batchProgress.total} 个首帧...
          </p>
        </Card>
      )}

      {shots.length === 0 ? (
        <Empty 
          description={
            <div>
              <p>请先在分镜脚本页面解析分镜，或点击上方"添加镜头"手动创建</p>
            </div>
          } 
          style={{ marginTop: 100 }}
        >
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setIsCreateModalOpen(true)}>
            添加镜头
          </Button>
        </Empty>
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext
            items={shots.map(s => s.id)}
            strategy={horizontalListSortingStrategy}
          >
            <div className="timeline" style={{ flexWrap: 'wrap', gap: 16 }}>
              {shots.map((shot) => {
                const frameUrl = getFrameUrl(shot.id) || shot.first_frame_url
                const isGeneratingThis = isItemGenerating(shot.id)
                return (
                  <SortableShotCard
                    key={shot.id}
                    shot={shot}
                    frameUrl={frameUrl}
                    isGenerating={isGeneratingThis}
                    onClick={() => openShotModal(shot)}
                    onDelete={() => deleteShot(shot.id)}
                  />
                )
              })}
            </div>
          </SortableContext>
        </DndContext>
      )}

      {/* 分镜编辑弹窗 */}
      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span>编辑分镜 - 镜头 {selectedShot?.shot_number}</span>
            {selectedShot && getFrameUrl(selectedShot.id) && (
              <Tag color="green">首帧已生成</Tag>
            )}
          </div>
        }
        open={isModalOpen}
        onCancel={() => setIsModalOpen(false)}
        footer={null}
        width={1200}
      >
        {selectedShot && (
          <Tabs
            defaultActiveKey="info"
            items={[
              {
                key: 'info',
                label: '分镜信息',
                children: (
                  <div>
                    <Form form={shotForm} layout="vertical">
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                        <Form.Item name="shot_design" label="镜头设计">
                          <TextArea rows={2} placeholder="描述镜头的整体设计" />
                        </Form.Item>
                        <Form.Item name="scene_type" label="景别">
                          <Select placeholder="选择景别">
                            <Option value="远景">远景</Option>
                            <Option value="全景">全景</Option>
                            <Option value="中景">中景</Option>
                            <Option value="近景">近景</Option>
                            <Option value="特写">特写</Option>
                          </Select>
                        </Form.Item>
                        <Form.Item name="scene_setting" label="场景设置">
                          <TextArea rows={2} placeholder="描述场景环境" />
                        </Form.Item>
                        <Form.Item name="lighting" label="光线设计">
                          <Input placeholder="例如：自然光、暖色调灯光" />
                        </Form.Item>
                        <Form.Item name="characters" label="出镜角色（逗号分隔）">
                          <Input placeholder="例如：小明, 小红" />
                        </Form.Item>
                        <Form.Item name="character_appearance" label="角色造型">
                          <Input placeholder="描述角色的穿着打扮" />
                        </Form.Item>
                        <Form.Item name="character_action" label="角色动作">
                          <Input placeholder="描述角色的动作行为" />
                        </Form.Item>
                        <Form.Item name="mood" label="情绪基调">
                          <Input placeholder="例如：紧张、欢快、悲伤" />
                        </Form.Item>
                        <Form.Item name="composition" label="构图方式">
                          <Input placeholder="例如：三分构图、对称构图" />
                        </Form.Item>
                        <Form.Item name="props" label="道具（逗号分隔）">
                          <Input placeholder="例如：手机, 咖啡杯" />
                        </Form.Item>
                        <Form.Item name="voice_subject" label="配音主体">
                          <Input placeholder="哪个角色配音或旁白" />
                        </Form.Item>
                        <Form.Item name="dialogue" label="台词/旁白">
                          <TextArea rows={2} placeholder="该镜头的台词内容" />
                        </Form.Item>
                        <Form.Item name="sound_effects" label="音效">
                          <Input placeholder="例如：脚步声、风声" />
                        </Form.Item>
                        <Form.Item name="duration" label="时长（秒，最大10秒）">
                          <InputNumber min={1} max={10} step={1} style={{ width: '100%' }} />
                        </Form.Item>
                      </div>
                      
                      <Divider>关联素材（用于首帧生成）</Divider>
                      
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
                        <Form.Item name="character_ids" label="选择角色" extra="选择的角色图片将用于首帧生成">
                          <Select
                            mode="multiple"
                            placeholder="选择角色"
                            optionLabelProp="label"
                          >
                            {characters.map(char => (
                              <Option key={char.id} value={char.id} label={char.name}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                  {getCharacterImageUrl(char) && (
                                    <img src={getCharacterImageUrl(char)} alt="" style={{ width: 24, height: 24, objectFit: 'cover', borderRadius: 4 }} />
                                  )}
                                  {char.name}
                                </div>
                              </Option>
                            ))}
                          </Select>
                        </Form.Item>
                        <Form.Item name="scene_id" label="选择场景" extra="选择的场景图片将用于首帧生成">
                          <Select
                            placeholder="选择场景"
                            allowClear
                            optionLabelProp="label"
                          >
                            {scenes.map(scene => (
                              <Option key={scene.id} value={scene.id} label={scene.name}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                  {getSceneImageUrl(scene) && (
                                    <img src={getSceneImageUrl(scene)} alt="" style={{ width: 24, height: 24, objectFit: 'cover', borderRadius: 4 }} />
                                  )}
                                  {scene.name}
                                </div>
                              </Option>
                            ))}
                          </Select>
                        </Form.Item>
                        <Form.Item name="prop_ids" label="选择道具" extra="选择的道具图片将用于首帧生成">
                          <Select
                            mode="multiple"
                            placeholder="选择道具"
                            optionLabelProp="label"
                          >
                            {props.map(prop => (
                              <Option key={prop.id} value={prop.id} label={prop.name}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                  {getPropImageUrl(prop) && (
                                    <img src={getPropImageUrl(prop)} alt="" style={{ width: 24, height: 24, objectFit: 'cover', borderRadius: 4 }} />
                                  )}
                                  {prop.name}
                                </div>
                              </Option>
                            ))}
                          </Select>
                        </Form.Item>
                      </div>
                    </Form>
                    <div style={{ textAlign: 'right', marginTop: 16 }}>
                      <Button type="primary" icon={<SaveOutlined />} onClick={saveShotInfo}>
                        保存分镜信息
                      </Button>
                    </div>
                  </div>
                )
              },
              {
                key: 'frame',
                label: '首帧生成',
                children: (
                  <div style={{ display: 'flex', gap: 24 }}>
                    <div style={{ width: 400 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                        <h4 style={{ margin: 0 }}>首帧预览</h4>
                        <Space>
                          <Button 
                            size="small"
                            icon={<PictureOutlined />} 
                            onClick={() => setIsGalleryModalOpen(true)}
                            disabled={galleryImages.length === 0}
                          >
                            从图库选择
                          </Button>
                          {selectedFrame && selectedFrame.image_groups?.some(g => g.url) && (
                            <Button 
                              size="small"
                              icon={<SaveOutlined />} 
                              onClick={saveFrameToGallery}
                            >
                              保存到图库
                            </Button>
                          )}
                          <Button 
                            type="primary" 
                            size="small"
                            icon={<ThunderboltOutlined />} 
                            onClick={generateAllGroups}
                            disabled={generatingGroups.size > 0}
                          >
                            生成{frameGroupCount}组
                          </Button>
                        </Space>
                      </div>
                      
                      {/* 素材参照开关 */}
                      <div style={{ marginBottom: 12, padding: 8, background: '#1a1a1a', borderRadius: 6 }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                          <span style={{ fontSize: 12, color: '#888' }}>使用素材参照（多图生图）</span>
                          <Switch size="small" checked={useReferences} onChange={setUseReferences} />
                        </div>
                        {useReferences && (
                          <div style={{ fontSize: 11, color: '#666', marginTop: 4 }}>
                            将使用关联的角色、场景、道具图片进行生成
                          </div>
                        )}
                      </div>
                      
                      {/* 多组首帧 */}
                      {Array.from({ length: Math.max(frameGroupCount, selectedFrame?.image_groups?.length || 0) }, (_, groupIndex) => {
                        const group = selectedFrame?.image_groups?.[groupIndex]
                        const isCurrentGroup = selectedFrame?.selected_group_index === groupIndex
                        const key = `${selectedShot.id}-${groupIndex}`
                        const isGeneratingThis = generatingGroups.has(key)
                        
                        return (
                          <div 
                            key={groupIndex} 
                            style={{ 
                              marginBottom: 12, 
                              padding: 12, 
                              border: isCurrentGroup ? '2px solid #1890ff' : '1px solid #333', 
                              borderRadius: 8, 
                              background: isCurrentGroup ? 'rgba(24, 144, 255, 0.1)' : '#1a1a1a' 
                            }}
                          >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                              <Space>
                                <span>第 {groupIndex + 1} 组</span>
                                {isCurrentGroup && <Tag color="blue">当前使用</Tag>}
                              </Space>
                              <Button 
                                size="small" 
                                icon={<ReloadOutlined />} 
                                onClick={() => generateSingleFrame(groupIndex)}
                                loading={isGeneratingThis}
                                disabled={generatingGroups.size > 0 && !isGeneratingThis}
                              >
                                {group?.url ? '重新生成' : '生成'}
                              </Button>
                            </div>
                            <div style={{ 
                              aspectRatio: '16/9', 
                              background: '#242424', 
                              borderRadius: 4, 
                              display: 'flex', 
                              alignItems: 'center', 
                              justifyContent: 'center',
                              overflow: 'hidden'
                            }}>
                              {isGeneratingThis ? (
                                <Spin />
                              ) : group?.url ? (
                                <Image
                                  src={group.url}
                                  alt={`首帧 ${groupIndex + 1}`}
                                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                                />
                              ) : (
                                <PictureOutlined style={{ fontSize: 32, color: '#444' }} />
                              )}
                            </div>
                          </div>
                        )
                      })}
                    </div>

                    <div style={{ flex: 1 }}>
                      <Form form={form} layout="vertical">
                        <Form.Item 
                          name="prompt" 
                          label="首帧生成提示词"
                          rules={[{ required: true, message: '请输入提示词' }]}
                          extra="提示词会根据分镜信息自动生成，你可以手动调整"
                        >
                          <TextArea rows={8} />
                        </Form.Item>
                      </Form>
                      
                      <Divider />
                      
                      <Card size="small" title="分镜信息参考" style={{ background: '#1a1a1a' }}>
                        <div style={{ fontSize: 12, color: '#888' }}>
                          <p><strong>景别：</strong>{selectedShot.scene_type || '未设置'}</p>
                          <p><strong>场景：</strong>{selectedShot.scene_setting || '未设置'}</p>
                          <p><strong>角色：</strong>{selectedShot.characters?.join(', ') || '无'}</p>
                          <p><strong>动作：</strong>{selectedShot.character_action || '未设置'}</p>
                          <p><strong>情绪：</strong>{selectedShot.mood || '未设置'}</p>
                          <p><strong>构图：</strong>{selectedShot.composition || '未设置'}</p>
                          <p style={{ marginBottom: 0 }}><strong>时长：</strong>{selectedShot.duration || 5}秒</p>
                        </div>
                      </Card>
                      
                      {/* 关联素材预览 */}
                      <Card size="small" title="关联素材" style={{ background: '#1a1a1a', marginTop: 16 }}>
                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                          {(selectedShot.character_ids || []).map(charId => {
                            const char = characters.find(c => c.id === charId)
                            const url = char && getCharacterImageUrl(char)
                            return url ? (
                              <Tooltip key={charId} title={`角色: ${char?.name}`}>
                                <img src={url} alt="" style={{ width: 48, height: 48, objectFit: 'cover', borderRadius: 4, border: '1px solid #333' }} />
                              </Tooltip>
                            ) : null
                          })}
                          {selectedShot.scene_id && (() => {
                            const scene = scenes.find(s => s.id === selectedShot.scene_id)
                            const url = scene && getSceneImageUrl(scene)
                            return url ? (
                              <Tooltip key={selectedShot.scene_id} title={`场景: ${scene?.name}`}>
                                <img src={url} alt="" style={{ width: 48, height: 48, objectFit: 'cover', borderRadius: 4, border: '1px solid #333' }} />
                              </Tooltip>
                            ) : null
                          })()}
                          {(selectedShot.prop_ids || []).map(propId => {
                            const prop = props.find(p => p.id === propId)
                            const url = prop && getPropImageUrl(prop)
                            return url ? (
                              <Tooltip key={propId} title={`道具: ${prop?.name}`}>
                                <img src={url} alt="" style={{ width: 48, height: 48, objectFit: 'cover', borderRadius: 4, border: '1px solid #333' }} />
                              </Tooltip>
                            ) : null
                          })}
                          {!(selectedShot.character_ids?.length || selectedShot.scene_id || selectedShot.prop_ids?.length) && (
                            <span style={{ color: '#666', fontSize: 12 }}>暂无关联素材，请在"分镜信息"中选择</span>
                          )}
                        </div>
                      </Card>
                    </div>
                  </div>
                )
              }
            ]}
          />
        )}
      </Modal>

      {/* 新增镜头弹窗 */}
      <Modal
        title="添加镜头"
        open={isCreateModalOpen}
        onOk={createShot}
        onCancel={() => setIsCreateModalOpen(false)}
        okText="添加"
        cancelText="取消"
        width={800}
      >
        <Form form={createForm} layout="vertical">
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <Form.Item name="shot_design" label="镜头设计">
              <TextArea rows={2} placeholder="描述镜头的整体设计" />
            </Form.Item>
            <Form.Item name="scene_type" label="景别">
              <Select placeholder="选择景别">
                <Option value="远景">远景</Option>
                <Option value="全景">全景</Option>
                <Option value="中景">中景</Option>
                <Option value="近景">近景</Option>
                <Option value="特写">特写</Option>
              </Select>
            </Form.Item>
            <Form.Item name="scene_setting" label="场景设置">
              <TextArea rows={2} placeholder="描述场景环境" />
            </Form.Item>
            <Form.Item name="characters" label="出镜角色（逗号分隔）">
              <Input placeholder="例如：小明, 小红" />
            </Form.Item>
            <Form.Item name="character_action" label="角色动作">
              <Input placeholder="描述角色的动作行为" />
            </Form.Item>
            <Form.Item name="duration" label="时长（秒，最大10秒）" initialValue={5}>
              <InputNumber min={1} max={10} step={1} style={{ width: '100%' }} />
            </Form.Item>
          </div>
        </Form>
      </Modal>

      {/* 设置弹窗 */}
      <Modal 
        title="生成设置" 
        open={settingsModalVisible} 
        onCancel={() => setSettingsModalVisible(false)}
        onOk={() => setSettingsModalVisible(false)}
        okText="确定"
        cancelText="取消"
      >
        <Form layout="vertical">
          <Form.Item label="每个分镜首帧生成组数" extra="生成首帧时，每个分镜将生成指定组数的图片">
            <InputNumber 
              min={1} 
              max={10} 
              value={frameGroupCount} 
              onChange={(v) => setFrameGroupCount(v || 3)} 
              style={{ width: '100%' }} 
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* 图库选择弹窗 */}
      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <PictureOutlined />
            <span>从图库选择图片</span>
            <span style={{ color: '#888', fontSize: 13 }}>
              - 镜头 {selectedShot?.shot_number}
            </span>
          </div>
        }
        open={isGalleryModalOpen}
        onCancel={() => setIsGalleryModalOpen(false)}
        footer={null}
        width={900}
      >
        {galleryImages.length === 0 ? (
          <Empty 
            description="图库中暂无图片，请先在图片工作室中生成并保存到图库"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        ) : (
          <div>
            <p style={{ color: '#888', marginBottom: 16 }}>
              点击选择一张图片作为镜头 {selectedShot?.shot_number} 的首帧
            </p>
            <div style={{ 
              display: 'grid', 
              gridTemplateColumns: 'repeat(4, 1fr)', 
              gap: 12, 
              maxHeight: 500, 
              overflow: 'auto' 
            }}>
              {galleryImages.map((img) => (
                <div
                  key={img.id}
                  onClick={() => setFrameFromGallery(img, 0)}
                  style={{
                    cursor: 'pointer',
                    borderRadius: 8,
                    overflow: 'hidden',
                    border: '2px solid transparent',
                    transition: 'all 0.2s',
                    background: '#1a1a1a'
                  }}
                  onMouseOver={(e) => e.currentTarget.style.borderColor = '#1890ff'}
                  onMouseOut={(e) => e.currentTarget.style.borderColor = 'transparent'}
                >
                  <div style={{ aspectRatio: '16/9', overflow: 'hidden' }}>
                    <img
                      src={img.url}
                      alt={img.name}
                      style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                    />
                  </div>
                  <div style={{ padding: 8 }}>
                    <div style={{ 
                      fontWeight: 500, 
                      fontSize: 12, 
                      overflow: 'hidden', 
                      textOverflow: 'ellipsis', 
                      whiteSpace: 'nowrap' 
                    }}>
                      {img.name}
                    </div>
                    {img.description && (
                      <div style={{ 
                        fontSize: 11, 
                        color: '#888', 
                        overflow: 'hidden', 
                        textOverflow: 'ellipsis', 
                        whiteSpace: 'nowrap' 
                      }}>
                        {img.description}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}

export default FramesPage
