import { useEffect, useState, useCallback, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { 
  Card, Button, Modal, Form, Input, Empty, Spin, message, 
  Image, Progress, Tooltip, Space, InputNumber, Select, Popconfirm,
  Tag, Tabs, Divider, Switch, Checkbox
} from 'antd'
import { 
  PlayCircleOutlined, ReloadOutlined, PictureOutlined, SettingOutlined,
  DragOutlined, EditOutlined, DeleteOutlined, StopOutlined, ThunderboltOutlined,
  SaveOutlined, PlusOutlined, ExclamationCircleOutlined, ClearOutlined
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
import { framesApi, scriptsApi, galleryApi, charactersApi, scenesApi, propsApi, stylesApi, settingsApi, Frame, Shot, GalleryImage, Character, Scene, Prop, Style } from '../../services/api'
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
}

const SortableShotCard = ({ shot, frameUrl, isGenerating, onClick }: SortableShotCardProps) => {
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
          top: 6, 
          left: 6, 
          zIndex: 10,
          padding: '4px 8px',
          background: 'rgba(0,0,0,0.7)',
          borderRadius: 4,
          cursor: 'grab',
          display: 'flex',
          alignItems: 'center',
          gap: 4
        }}
        title="拖拽调整顺序"
      >
        <DragOutlined style={{ color: '#e5a84b', fontSize: 14 }} />
      </div>
      
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
    setStopGeneration,
  } = useGenerationStore()
  
  const [frames, setFrames] = useState<Frame[]>([])
  const [shots, setShots] = useState<Shot[]>([])
  const [galleryImages, setGalleryImages] = useState<GalleryImage[]>([])
  const [characters, setCharacters] = useState<Character[]>([])
  const [scenes, setScenes] = useState<Scene[]>([])
  const [props, setProps] = useState<Prop[]>([])
  const [styles, setStyles] = useState<Style[]>([])
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
  // 素材选择（不包含风格）
  const [selectedReferences, setSelectedReferences] = useState<Array<{type: 'character' | 'scene' | 'prop', id: string}>>([])
  // 风格选择（独立）
  const [selectedStyleId, setSelectedStyleId] = useState<string | null>(null)
  // 全局风格设置
  const [globalStyleId, setGlobalStyleId] = useState<string | null>(null)
  // 多选保存到图库
  const [selectedGroupsForGallery, setSelectedGroupsForGallery] = useState<Set<number>>(new Set())
  
  // 首帧生成模型和参数设置
  const [frameModel, setFrameModel] = useState<string>('wan2.5-i2i-preview')
  const [frameN, setFrameN] = useState<number>(1)  // 每次请求生成图片数量
  const [framePromptExtend, setFramePromptExtend] = useState<boolean>(true)
  const [frameWatermark, setFrameWatermark] = useState<boolean>(false)
  const [frameSeed, setFrameSeed] = useState<number | null>(null)
  const [frameSize, setFrameSize] = useState<string | null>(null)
  const [frameEnableInterleave, setFrameEnableInterleave] = useState<boolean>(false)  // wan2.6-image 图文混合模式
  
  // 从 API 获取的模型尺寸配置
  const [modelSizeConfigs, setModelSizeConfigs] = useState<Record<string, Array<{width?: number, height?: number, value?: string, label: string}>>>({})
  
  // 可用的模型（图生图 + 文生图 + wan2.6-image）
  const availableImageModels: Record<string, {
    id: string
    name: string
    description: string
    maxN: number
    supportsSize: boolean
    modelType: 'i2i' | 't2i' | 'multi'  // 图生图 / 文生图 / 多功能
    supportsInterleave?: boolean
    supportsReferences?: boolean
    maxReferences?: number
  }> = {
    // 多功能模型 (图生图，支持文生图模式)
    'wan2.6-image': {
      id: 'wan2.6-image',
      name: '图生图 wan2.6-image',
      description: '最强模型，支持参考图生图、图文混合、纯文生图',
      maxN: 4,
      supportsSize: true,
      modelType: 'multi',
      supportsInterleave: true,  // 支持图文混合模式
      supportsReferences: true,  // 支持参考图
      maxReferences: 3,
    },
    // 图生图模型
    'wan2.5-i2i-preview': {
      id: 'wan2.5-i2i-preview',
      name: '图生图 wan2.5-i2i-preview',
      description: '风格迁移和多图融合，最多4张参考图',
      maxN: 4,
      supportsSize: false,
      modelType: 'i2i',
    },
    'qwen-image-edit-plus': {
      id: 'qwen-image-edit-plus',
      name: '图生图 qwen-image-edit-plus',
      description: '支持单图编辑和多图融合，最多3张参考图',
      maxN: 6,
      supportsSize: true,
      modelType: 'i2i',
    },
    // 文生图模型
    'wan2.6-t2i': {
      id: 'wan2.6-t2i',
      name: '文生图 wan2.6-t2i',
      description: 'HTTP同步调用，快速生成高质量图像',
      maxN: 4,
      supportsSize: true,
      modelType: 't2i',
    },
    'wan2.5-t2i-preview': {
      id: 'wan2.5-t2i-preview',
      name: '文生图 wan2.5-t2i-preview',
      description: 'SDK异步调用，自由选尺寸',
      maxN: 4,
      supportsSize: true,
      modelType: 't2i',
    },
  }
  
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
        const [framesRes, galleryRes, charsRes, scenesRes, propsRes, stylesRes, settingsRes] = await Promise.all([
          framesApi.list(projectId),
          galleryApi.list(projectId),
          charactersApi.list(projectId),
          scenesApi.list(projectId),
          propsApi.list(projectId),
          stylesApi.list(projectId),
          settingsApi.getSettings().catch(() => ({ available_image_models: {} })),
        ])
        safeSetState(setFrames, framesRes.frames)
        safeSetState(setGalleryImages, galleryRes.images)
        safeSetState(setCharacters, charsRes.characters)
        safeSetState(setScenes, scenesRes.scenes)
        safeSetState(setProps, propsRes.props)
        safeSetState(setStyles, stylesRes.styles)
        
        // 提取模型的 common_sizes 配置
        const sizeConfigs: Record<string, Array<{width?: number, height?: number, value?: string, label: string}>> = {}
        const models = settingsRes.available_image_models || {}
        for (const [modelId, modelInfo] of Object.entries(models)) {
          if ((modelInfo as any).common_sizes) {
            sizeConfigs[modelId] = (modelInfo as any).common_sizes
          }
        }
        safeSetState(setModelSizeConfigs, sizeConfigs)
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

  // 删除所有镜头
  const deleteAllShots = async () => {
    if (!projectId || shots.length === 0) return
    
    try {
      // 逐个删除所有镜头
      for (const shot of shots) {
        await scriptsApi.deleteShot(projectId, shot.id)
      }
      setShots([])
      setFrames([])
      message.success('所有镜头已删除')
      fetchProject(projectId).catch(() => {})
    } catch (error) {
      message.error('删除失败')
      fetchProject(projectId).catch(() => {})
    }
  }

  // 批量生成首帧
  const generateAllFrames = async () => {
    console.log('[批量生成首帧] 函数被调用，projectId:', projectId, 'shots.length:', shots.length)
    
    if (!projectId) {
      console.log('[批量生成首帧] projectId 为空，退出')
      return
    }
    if (shots.length === 0) {
      console.log('[批量生成首帧] shots 为空，退出')
      message.warning('请先解析分镜脚本')
      return
    }
    
    // 重置停止标志（只使用 ref，避免闭包问题）
    shouldStopRef.current = false
    setStopGeneration(false)
    safeSetState(setGenerating, true)
    safeSetState(setBatchProgress, { current: 0, total: shots.length })
    console.log('[批量生成首帧] 开始生成', shots.length, '个首帧')
    
    let successCount = 0
    let errorCount = 0
    
    for (let i = 0; i < shots.length; i++) {
      // 只使用 ref 检查，避免闭包中旧值问题
      if (shouldStopRef.current) {
        console.log('[批量生成首帧] 用户停止生成')
        break
      }
      
      const shot = shots[i]
      console.log(`[批量生成首帧] 正在生成 ${i + 1}/${shots.length}，shot.id:`, shot.id)
      addGeneratingItem(shot.id)
      safeSetState(setBatchProgress, { current: i + 1, total: shots.length })
      
      try {
        // 自动选择素材
        const autoRefs = autoSelectReferences(shot)
        // 构建首帧提示词（包含全局风格）
        const prompt = buildFramePrompt(shot, autoRefs, globalStyleId)
        console.log(`[批量生成首帧] 镜头${shot.shot_number} prompt:`, prompt.slice(0, 100) + '...')
        
        // 收集参考图片URL
        let referenceUrls = useReferences ? autoRefs
          .map(ref => getReferenceImageUrl(ref))
          .filter((url): url is string => url !== null) : []
        
        // 处理全局风格：如果是图片风格，作为最后一个参考图添加
        if (globalStyleId) {
          const style = styles.find(s => s.id === globalStyleId)
          if (style?.style_type === 'image') {
            const styleUrl = getStyleImageUrl(style)
            if (styleUrl) {
              referenceUrls = [...referenceUrls, styleUrl]
            }
          }
        }
        
        console.log(`[批量生成首帧] 镜头${shot.shot_number} 参考图数量:`, referenceUrls.length)
        
        const result = await framesApi.generate({
          project_id: projectId,
          shot_id: shot.id,
          shot_number: shot.shot_number,
          prompt: prompt,
          negative_prompt: '',
          group_index: 0,
          use_shot_references: useReferences && referenceUrls.length > 0,
          reference_urls: referenceUrls
        })
        
        console.log(`[批量生成首帧] 镜头${shot.shot_number} 生成成功`)
        
        safeSetState(setFrames, (prev: Frame[]) => {
          const exists = prev.find(f => f.shot_id === shot.id)
          if (exists) {
            return prev.map(f => f.shot_id === shot.id ? result.frame : f)
          }
          return [...prev, result.frame]
        })
        successCount++
      } catch (error: any) {
        console.error(`[批量生成首帧] 镜头${shot.shot_number} 生成失败:`, error?.message || error)
        errorCount++
      } finally {
        removeGeneratingItem(shot.id)
      }
    }
    
    safeSetState(setGenerating, false)
    safeSetState(setBatchProgress, { current: 0, total: 0 })
    
    if (shouldStopRef.current) {
      message.info(`已停止生成，完成 ${successCount}/${shots.length} 个首帧`)
    } else if (errorCount === 0) {
      message.success(`成功生成 ${successCount} 个首帧`)
    } else {
      message.warning(`${successCount} 个成功，${errorCount} 个失败`)
    }
    
    fetchProject(projectId).catch(() => {})
  }

  // 构建首帧提示词 - 使用角色名称和详细的构图、位置、动作描述
  const buildFramePrompt = (shot: Shot, refs: Array<{type: 'character' | 'scene' | 'prop', id: string}>, styleId?: string | null) => {
    const promptParts: string[] = []
    
    // 基础画面质量
    promptParts.push('电影级画面，高清细节，专业摄影')
    
    // 景别和构图
    if (shot.scene_type) promptParts.push(`${shot.scene_type}镜头`)
    if (shot.composition) promptParts.push(`${shot.composition}构图`)
    
    // 根据选择的素材顺序构建引用描述
    const charRefs: string[] = []
    const sceneRefs: string[] = []
    const propRefs: string[] = []
    
    refs.forEach((ref, index) => {
      const imageNum = index + 1
      if (ref.type === 'character') {
        const char = characters.find(c => c.id === ref.id)
        if (char) {
          charRefs.push(`第${imageNum}个图中的${char.name}`)
        }
      } else if (ref.type === 'scene') {
        const scene = scenes.find(s => s.id === ref.id)
        if (scene) {
          sceneRefs.push(`第${imageNum}个图中的${scene.name}场景`)
        }
      } else if (ref.type === 'prop') {
        const prop = props.find(p => p.id === ref.id)
        if (prop) {
          propRefs.push(`第${imageNum}个图中的${prop.name}`)
        }
      }
    })
    
    // 场景描述
    if (sceneRefs.length > 0) {
      promptParts.push(`场景设置：使用${sceneRefs.join('、')}作为背景环境`)
    } else if (shot.scene_setting) {
      promptParts.push(`场景：${shot.scene_setting}`)
    }
    
    // 角色描述（位置、动作、表情）
    if (charRefs.length > 0) {
      let charDesc = `画面中出现${charRefs.join('、')}`
      if (shot.character_action) {
        charDesc += `，正在${shot.character_action}`
      }
      if (shot.character_appearance) {
        charDesc += `，${shot.character_appearance}`
      }
      promptParts.push(charDesc)
    } else if (shot.characters?.length) {
      let charDesc = `画面中有${shot.characters.join('、')}`
      if (shot.character_action) charDesc += `，正在${shot.character_action}`
      if (shot.character_appearance) charDesc += `，${shot.character_appearance}`
      promptParts.push(charDesc)
    }
    
    // 道具描述
    if (propRefs.length > 0) {
      promptParts.push(`画面中包含${propRefs.join('、')}`)
    } else if (shot.props?.length) {
      promptParts.push(`画面中有${shot.props.join('、')}`)
    }
    
    // 光线和氛围
    if (shot.lighting) promptParts.push(`光线效果：${shot.lighting}`)
    if (shot.mood) promptParts.push(`画面氛围：${shot.mood}`)
    
    // 处理风格（放在尾部）
    const effectiveStyleId = styleId !== undefined ? styleId : getEffectiveStyleId()
    if (effectiveStyleId) {
      const style = styles.find(s => s.id === effectiveStyleId)
      if (style) {
        if (style.style_type === 'image' && style.style_prompt) {
          // 图片风格：添加风格参考说明（图片会作为最后一个参考图添加）
          const totalRefs = refs.length
          promptParts.push(`参考第${totalRefs + 1}个图的${style.name}风格，${style.style_prompt}`)
        } else if (style.style_type === 'text' && style.text_style_content) {
          // 文本风格：嵌入提示词尾部
          promptParts.push(`风格要求：${style.text_style_content}`)
        }
      }
    }
    
    return promptParts.join('。')
  }

  // 根据分镜信息自动预置素材选择
  const autoSelectReferences = (shot: Shot) => {
    const refs: Array<{type: 'character' | 'scene' | 'prop', id: string}> = []
    
    // 根据分镜中的角色名称匹配角色库
    if (shot.characters?.length) {
      shot.characters.forEach(charName => {
        const matchedChar = characters.find(c => 
          c.name.toLowerCase().includes(charName.toLowerCase()) || 
          charName.toLowerCase().includes(c.name.toLowerCase())
        )
        if (matchedChar && !refs.find(r => r.type === 'character' && r.id === matchedChar.id)) {
          refs.push({ type: 'character', id: matchedChar.id })
        }
      })
    }
    
    // 匹配场景
    if (shot.scene_setting) {
      const matchedScene = scenes.find(s => 
        s.name.toLowerCase().includes(shot.scene_setting?.toLowerCase() || '') ||
        (shot.scene_setting?.toLowerCase() || '').includes(s.name.toLowerCase())
      )
      if (matchedScene) {
        refs.push({ type: 'scene', id: matchedScene.id })
      }
    }
    
    // 根据分镜中的道具名称匹配道具库
    if (shot.props?.length) {
      shot.props.forEach(propName => {
        const matchedProp = props.find(p => 
          p.name.toLowerCase().includes(propName.toLowerCase()) || 
          propName.toLowerCase().includes(p.name.toLowerCase())
        )
        if (matchedProp && !refs.find(r => r.type === 'prop' && r.id === matchedProp.id)) {
          refs.push({ type: 'prop', id: matchedProp.id })
        }
      })
    }
    
    return refs
  }

  // 获取风格图片URL
  const getStyleImageUrl = (style: Style): string | null => {
    if (style.style_type === 'image' && style.image_groups?.[style.selected_group_index]?.url) {
      return style.image_groups[style.selected_group_index].url
    }
    return null
  }

  // 获取素材的图片URL（不含风格）
  const getReferenceImageUrl = (ref: {type: 'character' | 'scene' | 'prop', id: string}): string | null => {
    if (ref.type === 'character') {
      const char = characters.find(c => c.id === ref.id)
      return char ? getCharacterImageUrl(char) : null
    } else if (ref.type === 'scene') {
      const scene = scenes.find(s => s.id === ref.id)
      return scene ? getSceneImageUrl(scene) : null
    } else {
      const prop = props.find(p => p.id === ref.id)
      return prop ? getPropImageUrl(prop) : null
    }
  }

  // 获取素材名称（不含风格）
  const getReferenceName = (ref: {type: 'character' | 'scene' | 'prop', id: string}): string => {
    if (ref.type === 'character') {
      const char = characters.find(c => c.id === ref.id)
      return char ? `角色: ${char.name}` : '未知角色'
    } else if (ref.type === 'scene') {
      const scene = scenes.find(s => s.id === ref.id)
      return scene ? `场景: ${scene.name}` : '未知场景'
    } else {
      const prop = props.find(p => p.id === ref.id)
      return prop ? `道具: ${prop.name}` : '未知道具'
    }
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
  
  // 获取有效的风格（优先使用单张选择，其次使用全局设置）
  const getEffectiveStyleId = (): string | null => {
    return selectedStyleId || globalStyleId
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
    })
    
    // 自动预置素材选择
    const autoRefs = autoSelectReferences(shot)
    setSelectedReferences(autoRefs)
    
    // 构建默认提示词（使用自动预置的素材）
    form.setFieldsValue({
      prompt: frame?.prompt || buildFramePrompt(shot, autoRefs)
    })
    
    // 重置多选保存状态
    setSelectedGroupsForGallery(new Set())
    
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

  // 删除当前分镜
  const deleteCurrentShot = async () => {
    if (!projectId || !selectedShot) return
    
    try {
      await deleteShot(selectedShot.id)
      setIsModalOpen(false)
      setSelectedShot(null)
      setSelectedFrame(null)
    } catch (error) {
      message.error('删除失败')
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
      // 收集参考图片URL（按用户选择的顺序）
      let referenceUrls = useReferences ? selectedReferences
        .map(ref => getReferenceImageUrl(ref))
        .filter((url): url is string => url !== null) : []
      
      // 处理风格：如果选择了图片风格，作为最后一个参考图添加
      const effectiveStyleId = selectedStyleId || globalStyleId
      if (effectiveStyleId) {
        const style = styles.find(s => s.id === effectiveStyleId)
        if (style?.style_type === 'image') {
          const styleUrl = getStyleImageUrl(style)
          if (styleUrl) {
            referenceUrls = [...referenceUrls, styleUrl]
          }
        }
      }
      
      // 判断模型类型
      const modelInfo = availableImageModels[frameModel]
      const isTextToImage = modelInfo?.modelType === 't2i'
      const isMultiModel = modelInfo?.modelType === 'multi'
      
      // 构建请求参数
      const generateParams: any = {
        project_id: projectId,
        shot_id: selectedShot.id,
        shot_number: selectedShot.shot_number,
        prompt: values.prompt,
        negative_prompt: '',
        group_index: groupIndex,
        n: frameN,
        prompt_extend: framePromptExtend,
        watermark: frameWatermark,
        seed: frameSeed,
      }
      
      // 设置参考图和模型
      if (isTextToImage) {
        // 纯文生图模型
        generateParams.use_shot_references = false
        generateParams.reference_urls = []
        generateParams.model = frameModel
      } else if (isMultiModel) {
        // wan2.6-image 多功能模型
        generateParams.model = frameModel
        generateParams.use_shot_references = referenceUrls.length > 0
        generateParams.reference_urls = referenceUrls
        generateParams.enable_interleave = frameEnableInterleave
        if (frameN === 1 && frameSize) {
          generateParams.size = frameSize
        }
      } else {
        // 图生图模型
        generateParams.use_shot_references = referenceUrls.length > 0
        generateParams.reference_urls = referenceUrls
        generateParams.model = referenceUrls.length > 0 ? frameModel : undefined
        if (frameModel === 'qwen-image-edit-plus' && frameN === 1 && frameSize) {
          generateParams.size = frameSize
        }
      }
      
      const result = await framesApi.generate(generateParams)
      
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

  // 保存单个首帧到图库
  const saveFrameToGallery = async (groupIndex?: number) => {
    if (!selectedFrame) return
    
    const targetIndex = groupIndex !== undefined ? groupIndex : selectedFrame.selected_group_index
    const group = selectedFrame.image_groups?.[targetIndex]
    if (!group?.url) {
      message.warning('该组没有生成的图片')
      return
    }
    
    try {
      await framesApi.saveToGallery(selectedFrame.id, {
        name: `首帧 - 镜头${selectedShot?.shot_number} - 第${targetIndex + 1}组`,
        description: '从分镜首帧保存',
        group_index: targetIndex
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

  // 批量保存选中的首帧到图库
  const saveSelectedFramesToGallery = async () => {
    if (!selectedFrame || selectedGroupsForGallery.size === 0) {
      message.warning('请先选择要保存的图片')
      return
    }
    
    let successCount = 0
    let errorCount = 0
    
    for (const groupIndex of selectedGroupsForGallery) {
      const group = selectedFrame.image_groups?.[groupIndex]
      if (!group?.url) continue
      
      try {
        await framesApi.saveToGallery(selectedFrame.id, {
          name: `首帧 - 镜头${selectedShot?.shot_number} - 第${groupIndex + 1}组`,
          description: '从分镜首帧保存',
          group_index: groupIndex
        })
        successCount++
      } catch (error) {
        errorCount++
      }
    }
    
    // 刷新图库数据
    if (projectId) {
      const galleryRes = await galleryApi.list(projectId)
      setGalleryImages(galleryRes.images)
    }
    
    // 清空选择
    setSelectedGroupsForGallery(new Set())
    
    if (errorCount === 0) {
      message.success(`成功保存 ${successCount} 张图片到图库`)
    } else {
      message.warning(`${successCount} 张成功，${errorCount} 张失败`)
    }
  }

  // 切换多选保存
  const toggleGroupSelection = (groupIndex: number) => {
    setSelectedGroupsForGallery(prev => {
      const next = new Set(prev)
      if (next.has(groupIndex)) {
        next.delete(groupIndex)
      } else {
        next.add(groupIndex)
      }
      return next
    })
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
          <Popconfirm
            title="确定删除所有镜头？"
            description="将同时删除所有关联的首帧和视频，此操作不可恢复"
            icon={<ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />}
            onConfirm={deleteAllShots}
            okText="删除所有"
            cancelText="取消"
            okButtonProps={{ danger: true }}
            disabled={shots.length === 0}
          >
            <Button danger icon={<ClearOutlined />} disabled={shots.length === 0}>
              删除所有
            </Button>
          </Popconfirm>
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
                    </Form>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 16 }}>
                      <Popconfirm
                        title="确定删除此镜头？"
                        description="将同时删除关联的首帧和视频，此操作不可恢复"
                        icon={<ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />}
                        onConfirm={deleteCurrentShot}
                        okText="删除"
                        cancelText="取消"
                        okButtonProps={{ danger: true }}
                      >
                        <Button danger icon={<DeleteOutlined />}>
                          删除此镜头
                        </Button>
                      </Popconfirm>
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
                    <div style={{ width: 420 }}>
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
                      
                      {/* 批量保存按钮 */}
                      {selectedGroupsForGallery.size > 0 && (
                        <div style={{ marginBottom: 12, padding: 8, background: '#1a3a1a', borderRadius: 6 }}>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                            <span style={{ fontSize: 12, color: '#52c41a' }}>已选择 {selectedGroupsForGallery.size} 张图片</span>
                            <Button 
                              type="primary" 
                              size="small" 
                              icon={<SaveOutlined />}
                              onClick={saveSelectedFramesToGallery}
                            >
                              保存到图库
                            </Button>
                          </div>
                        </div>
                      )}
                      
                      {/* 多组首帧 */}
                      {Array.from({ length: Math.max(frameGroupCount, selectedFrame?.image_groups?.length || 0) }, (_, groupIndex) => {
                        const group = selectedFrame?.image_groups?.[groupIndex]
                        const isCurrentGroup = selectedFrame?.selected_group_index === groupIndex
                        const key = `${selectedShot.id}-${groupIndex}`
                        const isGeneratingThis = generatingGroups.has(key)
                        const isSelected = selectedGroupsForGallery.has(groupIndex)
                        
                        return (
                          <div 
                            key={groupIndex} 
                            style={{ 
                              marginBottom: 12, 
                              padding: 12, 
                              border: isSelected ? '2px solid #52c41a' : isCurrentGroup ? '2px solid #1890ff' : '1px solid #333', 
                              borderRadius: 8, 
                              background: isSelected ? 'rgba(82, 196, 26, 0.1)' : isCurrentGroup ? 'rgba(24, 144, 255, 0.1)' : '#1a1a1a' 
                            }}
                          >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                              <Space>
                                {group?.url && (
                                  <Checkbox 
                                    checked={isSelected} 
                                    onChange={() => toggleGroupSelection(groupIndex)}
                                  />
                                )}
                                <span>第 {groupIndex + 1} 组</span>
                                {isCurrentGroup && <Tag color="blue">当前使用</Tag>}
                              </Space>
                              <Space>
                                {group?.url && (
                                  <Button 
                                    size="small" 
                                    icon={<SaveOutlined />}
                                    onClick={() => saveFrameToGallery(groupIndex)}
                                  >
                                    单独保存
                                  </Button>
                                )}
                                <Button 
                                  size="small" 
                                  icon={<ReloadOutlined />} 
                                  onClick={() => generateSingleFrame(groupIndex)}
                                  loading={isGeneratingThis}
                                  disabled={generatingGroups.size > 0 && !isGeneratingThis}
                                >
                                  {group?.url ? '重新生成' : '生成'}
                                </Button>
                              </Space>
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
                      {/* 素材选择（统一下拉栏） */}
                      <Card size="small" title="选择参考素材" style={{ background: '#1a1a1a', marginBottom: 16 }}>
                        <div style={{ marginBottom: 8 }}>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                            <span style={{ fontSize: 12, color: '#888' }}>使用素材参照（多图生图）</span>
                            <Switch size="small" checked={useReferences} onChange={setUseReferences} />
                          </div>
                          {useReferences && (
                            <div style={{ fontSize: 11, color: '#666', marginBottom: 8 }}>
                              选择素材的顺序决定了API中图片URL的顺序，提示词中可用"第一个图"、"第二个图"等引用
                            </div>
                          )}
                        </div>
                        
                        {useReferences && (
                          <>
                            <Select
                              style={{ width: '100%', marginBottom: 12 }}
                              placeholder="添加参考素材（角色/场景/道具）"
                              value={undefined}
                              onChange={(value: string) => {
                                const [type, id] = value.split(':') as ['character' | 'scene' | 'prop', string]
                                if (!selectedReferences.find(r => r.type === type && r.id === id)) {
                                  const newRefs = [...selectedReferences, { type, id }]
                                  setSelectedReferences(newRefs)
                                  // 更新提示词
                                  if (selectedShot) {
                                    form.setFieldsValue({
                                      prompt: buildFramePrompt(selectedShot, newRefs, getEffectiveStyleId())
                                    })
                                  }
                                }
                              }}
                              optionLabelProp="label"
                            >
                              <Select.OptGroup label="角色">
                                {characters.map(char => (
                                  <Option 
                                    key={`character:${char.id}`} 
                                    value={`character:${char.id}`} 
                                    label={`角色: ${char.name}`}
                                    disabled={selectedReferences.some(r => r.type === 'character' && r.id === char.id)}
                                  >
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                      {getCharacterImageUrl(char) && (
                                        <img src={getCharacterImageUrl(char)} alt="" style={{ width: 24, height: 24, objectFit: 'cover', borderRadius: 4 }} />
                                      )}
                                      <span>角色: {char.name}</span>
                                    </div>
                                  </Option>
                                ))}
                              </Select.OptGroup>
                              <Select.OptGroup label="场景">
                                {scenes.map(scene => (
                                  <Option 
                                    key={`scene:${scene.id}`} 
                                    value={`scene:${scene.id}`} 
                                    label={`场景: ${scene.name}`}
                                    disabled={selectedReferences.some(r => r.type === 'scene' && r.id === scene.id)}
                                  >
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                      {getSceneImageUrl(scene) && (
                                        <img src={getSceneImageUrl(scene)} alt="" style={{ width: 24, height: 24, objectFit: 'cover', borderRadius: 4 }} />
                                      )}
                                      <span>场景: {scene.name}</span>
                                    </div>
                                  </Option>
                                ))}
                              </Select.OptGroup>
                              <Select.OptGroup label="道具">
                                {props.map(prop => (
                                  <Option 
                                    key={`prop:${prop.id}`} 
                                    value={`prop:${prop.id}`} 
                                    label={`道具: ${prop.name}`}
                                    disabled={selectedReferences.some(r => r.type === 'prop' && r.id === prop.id)}
                                  >
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                      {getPropImageUrl(prop) && (
                                        <img src={getPropImageUrl(prop)} alt="" style={{ width: 24, height: 24, objectFit: 'cover', borderRadius: 4 }} />
                                      )}
                                      <span>道具: {prop.name}</span>
                                    </div>
                                  </Option>
                                ))}
                              </Select.OptGroup>
                            </Select>
                            
                            {/* 已选素材预览（可拖拽排序） */}
                            {selectedReferences.length > 0 && (
                              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                                {selectedReferences.map((ref, index) => {
                                  const url = getReferenceImageUrl(ref)
                                  const name = getReferenceName(ref)
                                  return (
                                    <Tooltip key={`${ref.type}:${ref.id}`} title={`${index + 1}. ${name}`}>
                                      <div 
                                        style={{ 
                                          position: 'relative', 
                                          border: '2px solid #1890ff', 
                                          borderRadius: 4,
                                          background: '#242424'
                                        }}
                                      >
                                        <div style={{
                                          position: 'absolute',
                                          top: -8,
                                          left: -8,
                                          width: 20,
                                          height: 20,
                                          background: '#1890ff',
                                          borderRadius: '50%',
                                          display: 'flex',
                                          alignItems: 'center',
                                          justifyContent: 'center',
                                          fontSize: 11,
                                          fontWeight: 'bold',
                                          color: '#fff'
                                        }}>
                                          {index + 1}
                                        </div>
                                        {url ? (
                                          <img src={url} alt="" style={{ width: 56, height: 56, objectFit: 'cover', borderRadius: 2 }} />
                                        ) : (
                                          <div style={{ width: 56, height: 56, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                            <PictureOutlined style={{ color: '#666' }} />
                                          </div>
                                        )}
                                        <div
                                          style={{
                                            position: 'absolute',
                                            top: 2,
                                            right: 2,
                                            width: 16,
                                            height: 16,
                                            background: 'rgba(255,77,79,0.9)',
                                            borderRadius: '50%',
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'center',
                                            cursor: 'pointer'
                                          }}
                                          onClick={() => {
                                            const newRefs = selectedReferences.filter((_, i) => i !== index)
                                            setSelectedReferences(newRefs)
                                            if (selectedShot) {
                                              form.setFieldsValue({
                                                prompt: buildFramePrompt(selectedShot, newRefs, getEffectiveStyleId())
                                              })
                                            }
                                          }}
                                        >
                                          <DeleteOutlined style={{ fontSize: 10, color: '#fff' }} />
                                        </div>
                                      </div>
                                    </Tooltip>
                                  )
                                })}
                              </div>
                            )}
                            
                            {selectedReferences.length === 0 && (
                              <div style={{ color: '#666', fontSize: 12 }}>
                                暂无选择素材，系统已根据分镜信息自动匹配
                              </div>
                            )}
                          </>
                        )}
                      </Card>
                      
                      {/* 独立风格选择模块 */}
                      <Card 
                        size="small" 
                        title={
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                            <span>风格选择</span>
                            {globalStyleId && !selectedStyleId && (
                              <Tag color="blue" style={{ fontSize: 10 }}>使用全局风格</Tag>
                            )}
                          </div>
                        }
                        style={{ marginTop: 12, background: 'transparent', border: '1px solid #333' }}
                      >
                        <Select
                          style={{ width: '100%' }}
                          placeholder={globalStyleId ? `使用全局风格 (${styles.find(s => s.id === globalStyleId)?.name || ''})` : '选择风格（可选）'}
                          value={selectedStyleId || undefined}
                          onChange={(value) => {
                            setSelectedStyleId(value || null)
                            // 更新提示词
                            if (selectedShot) {
                              form.setFieldsValue({
                                prompt: buildFramePrompt(selectedShot, selectedReferences, value || globalStyleId)
                              })
                            }
                          }}
                          allowClear
                          options={buildStyleOptions()}
                        />
                        
                        {/* 显示选中风格的预览 */}
                        {(() => {
                          const effectiveStyleId = selectedStyleId || globalStyleId
                          if (!effectiveStyleId) return null
                          const style = styles.find(s => s.id === effectiveStyleId)
                          if (!style) return null
                          return (
                            <div style={{ 
                              marginTop: 12, 
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
                                    style={{ width: 60, height: 60, objectFit: 'cover', borderRadius: 4 }}
                                  />
                                )}
                                <div style={{ flex: 1 }}>
                                  <div style={{ fontWeight: 500, marginBottom: 4, fontSize: 13 }}>{style.name}</div>
                                  <Tag color={style.style_type === 'image' ? 'blue' : 'green'} style={{ fontSize: 10 }}>
                                    {style.style_type === 'image' ? '图片风格' : '文本风格'}
                                  </Tag>
                                  {style.style_type === 'text' && style.text_style_content && (
                                    <div style={{ marginTop: 6, fontSize: 11, color: '#888' }}>
                                      {style.text_style_content.slice(0, 80)}...
                                    </div>
                                  )}
                                  {style.style_type === 'image' && style.style_prompt && (
                                    <div style={{ marginTop: 6, fontSize: 11, color: '#888' }}>
                                      {style.style_prompt.slice(0, 80)}...
                                    </div>
                                  )}
                                </div>
                              </div>
                            </div>
                          )
                        })()}
                        
                        <div style={{ marginTop: 8, fontSize: 11, color: '#666' }}>
                          图片风格：作为最后一个参考图片。文本风格：嵌入提示词尾部。
                        </div>
                      </Card>
                      
                      <Form form={form} layout="vertical">
                        <Form.Item 
                          name="prompt" 
                          label="首帧生成提示词"
                          rules={[{ required: true, message: '请输入提示词' }]}
                          extra="提示词根据分镜信息和选择的素材自动生成，使用角色/场景/道具名称引用，你可以手动调整"
                        >
                          <TextArea rows={6} />
                        </Form.Item>
                      </Form>
                      
                      {/* 生成模型和参数设置 */}
                      <Card 
                        size="small" 
                        title="生成设置" 
                        style={{ background: '#1a1a1a', marginBottom: 12 }}
                        extra={
                          <span style={{ fontSize: 11, color: '#666' }}>
                            {(() => {
                              const modelInfo = availableImageModels[frameModel]
                              if (modelInfo?.modelType === 'multi') return 'wan2.6-image 多功能'
                              if (useReferences && selectedReferences.length > 0) return '图生图模式'
                              return '文生图模式'
                            })()}
                          </span>
                        }
                      >
                        <>
                          <div style={{ marginBottom: 12 }}>
                            <div style={{ marginBottom: 4, color: '#888', fontSize: 12 }}>生成模型</div>
                            <Select
                              style={{ width: '100%' }}
                              size="small"
                              value={frameModel}
                              onChange={setFrameModel}
                            >
                              {Object.values(availableImageModels).map(m => (
                                <Option key={m.id} value={m.id}>
                                  {m.name}
                                  {m.modelType === 'multi' && <Tag color="gold" style={{ marginLeft: 8 }}>多功能</Tag>}
                                  {m.modelType === 't2i' && <Tag color="blue" style={{ marginLeft: 8 }}>文生图</Tag>}
                                </Option>
                              ))}
                            </Select>
                            <div style={{ fontSize: 11, color: '#666', marginTop: 4 }}>
                              {availableImageModels[frameModel]?.description}
                            </div>
                          </div>
                          
                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                            <div>
                              <div style={{ marginBottom: 4, color: '#888', fontSize: 12 }}>生图数量</div>
                              <InputNumber
                                style={{ width: '100%' }}
                                size="small"
                                min={1}
                                max={availableImageModels[frameModel]?.maxN || 4}
                                value={frameN}
                                onChange={(v) => setFrameN(v || 1)}
                              />
                              <div style={{ fontSize: 11, color: '#666', marginTop: 2 }}>
                                最多 {availableImageModels[frameModel]?.maxN || 4} 张
                              </div>
                            </div>
                              
                            {availableImageModels[frameModel]?.supportsSize && frameN === 1 && (
                              <div>
                                <div style={{ marginBottom: 4, color: '#888', fontSize: 12 }}>输出尺寸</div>
                                <Select
                                  style={{ width: '100%' }}
                                  size="small"
                                    value={frameSize}
                                    onChange={setFrameSize}
                                    allowClear
                                    placeholder="默认"
                                  >
                                    {modelSizeConfigs[frameModel]?.map((size, idx) => {
                                      const value = size.value !== undefined ? size.value : `${size.width}*${size.height}`
                                      return <Option key={idx} value={value}>{size.label}</Option>
                                    }) || (
                                      <>
                                        <Option value="1280*1280">1280×1280 (1:1)</Option>
                                        <Option value="1024*1024">1024×1024 (1:1)</Option>
                                      </>
                                    )}
                                  </Select>
                                </div>
                              )}
                            </div>
                            
                            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                <Switch
                                  size="small"
                                  checked={framePromptExtend}
                                  onChange={setFramePromptExtend}
                                />
                                <span style={{ fontSize: 12, color: '#888' }}>智能改写</span>
                              </div>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                <Switch
                                  size="small"
                                  checked={frameWatermark}
                                  onChange={setFrameWatermark}
                                />
                                <span style={{ fontSize: 12, color: '#888' }}>水印</span>
                              </div>
                              {/* wan2.6-image 专用：图文混合模式 */}
                              {availableImageModels[frameModel]?.supportsInterleave && (
                                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                  <Switch
                                    size="small"
                                    checked={frameEnableInterleave}
                                    onChange={setFrameEnableInterleave}
                                  />
                                  <Tooltip title="开启后会生成图文混合内容，n固定为1">
                                    <span style={{ fontSize: 12, color: '#888' }}>图文混合</span>
                                  </Tooltip>
                                </div>
                              )}
                            </div>
                            
                            <div style={{ marginTop: 12 }}>
                              <div style={{ marginBottom: 4, color: '#888', fontSize: 12 }}>随机种子（可选）</div>
                              <InputNumber
                                style={{ width: '100%' }}
                                size="small"
                                min={0}
                                max={2147483647}
                                value={frameSeed}
                                onChange={(v) => setFrameSeed(v)}
                                placeholder="留空则随机"
                              />
                            </div>
                          {/* 提示信息 */}
                          {availableImageModels[frameModel]?.modelType === 'i2i' && (!useReferences || selectedReferences.length === 0) && (
                            <div style={{ color: '#ff9800', fontSize: 11, marginTop: 8, padding: 8, background: 'rgba(255,152,0,0.1)', borderRadius: 4 }}>
                              ⚠️ 当前选择的是图生图模型，请添加参考素材
                            </div>
                          )}
                          {availableImageModels[frameModel]?.modelType === 'multi' && (
                            <div style={{ color: '#666', fontSize: 11, marginTop: 8 }}>
                              💡 wan2.6-image 支持无参考图（文生图）或 1-3 张参考图
                              {frameEnableInterleave && (
                                <div style={{ color: '#52c41a', marginTop: 4 }}>
                                  ✨ 图文混合模式：生成图文并茂的内容，生图数量固定为 1
                                </div>
                              )}
                            </div>
                          )}
                        </>
                      </Card>
                      
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
                      
                      {/* 追踪ID显示 */}
                      {selectedFrame && (selectedFrame.last_task_id || selectedFrame.last_request_id) && (
                        <div style={{ 
                          marginTop: 12, 
                          padding: '8px 12px', 
                          background: '#1a1a1a', 
                          borderRadius: 6,
                          fontSize: 11,
                          color: '#666',
                          fontFamily: 'monospace'
                        }}>
                          {selectedFrame.last_task_id && (
                            <div>Task ID: {selectedFrame.last_task_id}</div>
                          )}
                          {selectedFrame.last_request_id && (
                            <div>Request ID: {selectedFrame.last_request_id}</div>
                          )}
                        </div>
                      )}
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
        width={500}
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
          
          <Divider />
          
          <Form.Item 
            label="全局风格设置" 
            extra="设置后，所有分镜首帧生成时将默认使用此风格（单个分镜可覆盖）"
          >
            <Select
              style={{ width: '100%' }}
              placeholder="选择全局风格（可选）"
              value={globalStyleId || undefined}
              onChange={(value) => setGlobalStyleId(value || null)}
              allowClear
              options={buildStyleOptions()}
            />
          </Form.Item>
          
          {/* 全局风格预览 */}
          {globalStyleId && (() => {
            const style = styles.find(s => s.id === globalStyleId)
            if (!style) return null
            return (
              <div style={{ 
                padding: 12, 
                background: '#1a1a1a', 
                borderRadius: 8,
                border: '1px solid #333',
                marginTop: -8
              }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                  {style.style_type === 'image' && getStyleImageUrl(style) && (
                    <img 
                      src={getStyleImageUrl(style)!} 
                      alt={style.name}
                      style={{ width: 60, height: 60, objectFit: 'cover', borderRadius: 4 }}
                    />
                  )}
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 500, marginBottom: 4 }}>{style.name}</div>
                    <Tag color={style.style_type === 'image' ? 'blue' : 'green'}>
                      {style.style_type === 'image' ? '图片风格' : '文本风格'}
                    </Tag>
                    {style.style_type === 'text' && style.text_style_content && (
                      <div style={{ marginTop: 6, fontSize: 12, color: '#888' }}>
                        {style.text_style_content.slice(0, 100)}...
                      </div>
                    )}
                    {style.style_type === 'image' && style.style_prompt && (
                      <div style={{ marginTop: 6, fontSize: 12, color: '#888' }}>
                        {style.style_prompt.slice(0, 100)}...
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )
          })()}
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
