import { useEffect, useState, useRef, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { 
  Card, Button, Switch, Select, Input, Upload, message, Spin, 
  Radio, Empty, Tooltip, Space, Modal, Form, List, Tag, Tabs, Table,
  InputNumber, Image, Popconfirm, Collapse
} from 'antd'
import { 
  UploadOutlined, ClearOutlined, SaveOutlined, 
  PlayCircleOutlined, PlusOutlined, MinusOutlined,
  FileTextOutlined, SettingOutlined, HistoryOutlined,
  BookOutlined, EditOutlined, DeleteOutlined, AppstoreOutlined,
  CaretRightOutlined, VideoCameraOutlined, PictureOutlined, UserOutlined
} from '@ant-design/icons'
import type { UploadProps } from 'antd'
import { scriptsApi, generateScriptStream, projectsApi, settingsApi, ConfigResponse, ProjectLLMConfig, Shot, framesApi, videosApi, Frame, Video, Character, Scene, Prop, charactersApi, scenesApi, propsApi } from '../../services/api'
import { useProjectStore } from '../../stores/projectStore'
import { useScriptStore, ScriptVersion, PromptVersion, Column } from '../../stores/scriptStore'
import LLMConfigForm from '../../components/LLMConfigForm'

const { TextArea } = Input

// 将项目配置转换为表单值
const projectConfigToFormValues = (config: ProjectLLMConfig, globalConfig: ConfigResponse['llm']) => {
  return {
    llm_max_tokens: config.max_tokens ?? globalConfig.max_tokens,
    llm_top_p: config.top_p ?? globalConfig.top_p,
    llm_temperature: config.temperature ?? globalConfig.temperature,
    llm_enable_thinking: config.enable_thinking ?? globalConfig.enable_thinking,
    llm_thinking_budget: config.thinking_budget ?? globalConfig.thinking_budget,
    llm_result_format: config.result_format ?? globalConfig.result_format,
    llm_enable_search: config.enable_search ?? globalConfig.enable_search,
  }
}

// 将表单值转换为项目配置
const formValuesToProjectConfig = (values: any): ProjectLLMConfig => {
  return {
    max_tokens: values.llm_max_tokens,
    top_p: values.llm_top_p,
    temperature: values.llm_temperature,
    enable_thinking: values.llm_enable_thinking,
    thinking_budget: values.llm_thinking_budget,
    result_format: values.llm_result_format,
    enable_search: values.llm_enable_search,
  }
}

const ScriptPage = () => {
  const { projectId } = useParams<{ projectId: string }>()
  const { currentProject, fetchProject } = useProjectStore()
  
  // 使用持久化的脚本状态
  const scriptStore = useScriptStore()
  const projectState = projectId ? scriptStore.getProjectState(projectId) : null
  
  const [defaultPrompt, setDefaultPrompt] = useState('')
  const [availableModels, setAvailableModels] = useState<{key: string, name: string}[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [parsing, setParsing] = useState(false)
  
  // 全局设置和项目配置
  const [globalSettings, setGlobalSettings] = useState<ConfigResponse | null>(null)
  const [projectLLMConfigs, setProjectLLMConfigs] = useState<Record<string, ProjectLLMConfig>>({})
  
  // 模型配置弹窗状态
  const [configModalVisible, setConfigModalVisible] = useState(false)
  const [configModalModel, setConfigModalModel] = useState('')
  const [configForm] = Form.useForm()
  
  // 版本管理弹窗状态
  const [scriptVersionModalVisible, setScriptVersionModalVisible] = useState(false)
  const [promptVersionModalVisible, setPromptVersionModalVisible] = useState(false)
  const [saveVersionModalVisible, setSaveVersionModalVisible] = useState(false)
  const [saveVersionType, setSaveVersionType] = useState<'script' | 'prompt'>('script')
  const [versionForm] = Form.useForm()
  
  // 剧本看板状态
  const [showStoryboard, setShowStoryboard] = useState(true)
  const [shots, setShots] = useState<Shot[]>([])
  const [frames, setFrames] = useState<Frame[]>([])
  const [videos, setVideos] = useState<Video[]>([])
  const [characters, setCharacters] = useState<Character[]>([])
  const [scenes, setScenes] = useState<Scene[]>([])
  const [props, setProps] = useState<Prop[]>([])
  const [editingShotId, setEditingShotId] = useState<string | null>(null)
  const [shotForm] = Form.useForm()
  
  // 流式输出的取消函数引用
  const cancelFnRef = useRef<(() => void) | null>(null)
  const initedRef = useRef(false)

  // 从 store 获取状态
  const originalContent = projectState?.originalContent || ''
  const aiEditorEnabled = projectState?.aiEditorEnabled || false
  const columns = projectState?.columns || [{ id: 1, model: 'qwen3-max', content: '', isGenerating: false, selected: true }]
  const customPrompt = projectState?.customPrompt || ''
  const scriptVersions = projectState?.scriptVersions || []
  const promptVersions = projectState?.promptVersions || []
  const selectedScriptVersionId = projectState?.selectedScriptVersionId || null

  // 设置状态的包装函数
  const setOriginalContent = (content: string) => {
    if (projectId) scriptStore.setOriginalContent(projectId, content)
  }
  const setAiEditorEnabled = (enabled: boolean) => {
    if (projectId) scriptStore.setAiEditorEnabled(projectId, enabled)
  }
  const setColumns = (cols: Column[]) => {
    if (projectId) scriptStore.setColumns(projectId, cols)
  }
  const setCustomPrompt = (prompt: string) => {
    if (projectId) scriptStore.setCustomPrompt(projectId, prompt)
  }

  // 加载项目和设置
  useEffect(() => {
    const init = async () => {
      if (!projectId) return
      
      setLoading(true)
      try {
        // 加载项目（不阻塞其他加载）
        fetchProject(projectId).catch(() => {})
        
        // 加载全局设置
        const settings = await settingsApi.getSettings()
        setGlobalSettings(settings)
        
        // 将模型字典转换为数组
        const models = Object.entries(settings.available_llm_models).map(([key, info]) => ({
          key,
          name: info.name
        }))
        setAvailableModels(models)
        
        // 如果是首次加载且没有保存的状态，初始化默认列
        if (!initedRef.current && models.length > 0 && columns.length === 1 && !columns[0].content) {
          setColumns([
            { id: 1, model: settings.llm.model, content: '', isGenerating: false, selected: true }
          ])
        }
        
        // 加载项目级 LLM 配置
        try {
          const { llm_configs } = await projectsApi.getLLMConfigs(projectId)
          setProjectLLMConfigs(llm_configs || {})
        } catch {
          setProjectLLMConfigs({})
        }
        
        // 加载默认提示词
        const { prompt } = await scriptsApi.getDefaultPrompt()
        setDefaultPrompt(prompt)
        
        // 从后端加载剧本数据（包括版本历史）
        try {
          const scriptData = await scriptsApi.get(projectId)
          if (scriptData) {
            // 同步原始内容
            if (scriptData.original_content && !originalContent) {
              setOriginalContent(scriptData.original_content)
            }
            // 同步自定义提示词
            if (scriptData.custom_prompt) {
              setCustomPrompt(scriptData.custom_prompt)
            } else if (!customPrompt) {
              setCustomPrompt(prompt)
            }
            // 同步版本历史到本地 store
            if (scriptData.script_versions && scriptData.script_versions.length > 0) {
              scriptData.script_versions.forEach((v: any) => {
                if (!scriptVersions.find(sv => sv.id === v.id)) {
                  scriptStore.addScriptVersion(projectId, {
                    id: v.id,
                    name: v.name,
                    description: v.description,
                    content: v.content,
                    originalContent: v.original_content,
                    modelUsed: v.model_used,
                    promptUsed: v.prompt_used,
                    createdAt: v.created_at
                  })
                }
              })
            }
            if (scriptData.prompt_versions && scriptData.prompt_versions.length > 0) {
              scriptData.prompt_versions.forEach((v: any) => {
                if (!promptVersions.find(pv => pv.id === v.id)) {
                  scriptStore.addPromptVersion(projectId, {
                    id: v.id,
                    name: v.name,
                    description: v.description,
                    prompt: v.prompt,
                    createdAt: v.created_at
                  })
                }
              })
            }
          }
        } catch {
          // 如果没有自定义提示词，使用默认提示词
          if (!customPrompt) {
            setCustomPrompt(prompt)
          }
        }
        
        initedRef.current = true
      } catch (error) {
        message.error('加载失败')
      } finally {
        setLoading(false)
      }
    }
    
    init()
  }, [projectId])

  // 当项目加载后，同步原始内容（仅当store中没有内容时）
  useEffect(() => {
    if (currentProject?.script && !originalContent && !initedRef.current) {
      setOriginalContent(currentProject.script.original_content || '')
    }
  }, [currentProject])

  // 加载剧本看板数据
  useEffect(() => {
    const loadStoryboardData = async () => {
      if (!projectId) return
      try {
        // 加载分镜、首帧、视频、角色、场景、道具
        const [shotsData, framesData, videosData, charsData, scenesData, propsData] = await Promise.all([
          currentProject?.script?.shots ? Promise.resolve({ shots: currentProject.script.shots }) : scriptsApi.get(projectId).then(s => ({ shots: s?.shots || [] })),
          framesApi.list(projectId),
          videosApi.list(projectId),
          charactersApi.list(projectId),
          scenesApi.list(projectId),
          propsApi.list(projectId),
        ])
        setShots(shotsData.shots || currentProject?.script?.shots || [])
        setFrames(framesData.frames || [])
        setVideos(videosData.videos || [])
        setCharacters(charsData.characters || [])
        setScenes(scenesData.scenes || [])
        setProps(propsData.props || [])
      } catch (error) {
        console.error('加载剧本看板数据失败:', error)
      }
    }
    loadStoryboardData()
  }, [projectId, currentProject?.script?.shots])

  // 更新单个分镜
  const updateShot = async (shotId: string, data: Partial<Shot>) => {
    if (!projectId) return
    try {
      const { shot } = await scriptsApi.updateShot(projectId, shotId, data)
      setShots(prev => prev.map(s => s.id === shotId ? { ...s, ...shot } : s))
      message.success('分镜已更新')
      setEditingShotId(null)
    } catch (error) {
      message.error('更新失败')
    }
  }

  // 删除分镜
  const deleteShot = async (shotId: string) => {
    if (!projectId) return
    try {
      const result = await scriptsApi.deleteShot(projectId, shotId)
      setShots(result.shots)
      message.success('分镜已删除')
    } catch (error) {
      message.error('删除失败')
    }
  }

  // 获取分镜关联的首帧
  const getFrameForShot = (shotId: string) => {
    return frames.find(f => f.shot_id === shotId)
  }

  // 获取分镜关联的视频
  const getVideoForShot = (shotId: string) => {
    return videos.find(v => v.shot_id === shotId)
  }

  // 根据名称获取角色
  const getCharacterByName = (name: string) => {
    return characters.find(c => c.name === name)
  }

  // 根据名称获取场景
  const getSceneByName = (name: string) => {
    return scenes.find(s => s.name === name)
  }

  // 根据名称获取道具
  const getPropByName = (name: string) => {
    return props.find(p => p.name === name)
  }

  // 文件上传配置
  const uploadProps: UploadProps = {
    accept: '.txt,.md,.docx,.pdf',
    showUploadList: false,
    beforeUpload: async (file) => {
      if (!projectId) return false
      
      try {
        const result = await scriptsApi.upload(projectId, file)
        setOriginalContent(result.content)
        message.success(`文件 ${file.name} 上传成功`)
      } catch (error) {
        message.error('文件上传失败')
      }
      return false
    }
  }

  // 添加栏
  const addColumn = () => {
    if (columns.length >= 3) {
      message.warning('最多只能添加3栏')
      return
    }
    const usedModels = columns.map(c => c.model)
    const unusedModel = availableModels.find(m => !usedModels.includes(m.key))
    setColumns([
      ...columns,
      {
        id: Date.now(),
        model: unusedModel?.key || availableModels[0]?.key || 'qwen3-max',
        content: '',
        isGenerating: false,
        selected: false
      }
    ])
  }

  // 删除栏
  const removeColumn = (id: number) => {
    if (columns.length <= 1) {
      message.warning('至少保留一栏')
      return
    }
    if (projectId) scriptStore.removeColumn(projectId, id)
  }

  // 选择栏
  const selectColumn = (id: number) => {
    setColumns(columns.map(c => ({
      ...c,
      selected: c.id === id
    })))
  }

  // 更新栏的模型
  const updateColumnModel = (id: number, model: string) => {
    setColumns(columns.map(c => 
      c.id === id ? { ...c, model } : c
    ))
  }

  // 生成剧本
  const generateScript = useCallback(() => {
    if (!projectId || !originalContent.trim()) {
      message.warning('请先输入剧本内容')
      return
    }

    // 为每个栏启动生成
    columns.forEach(column => {
      if (projectId) {
        scriptStore.updateColumn(projectId, column.id, { content: '', isGenerating: true })
      }

      const cancelFn = generateScriptStream(
        projectId,
        originalContent,
        column.model,
        customPrompt || defaultPrompt,
        // onMessage
        (content) => {
          if (projectId) {
            const currentCol = scriptStore.getProjectState(projectId).columns.find(c => c.id === column.id)
            scriptStore.updateColumn(projectId, column.id, { content: (currentCol?.content || '') + content })
          }
        },
        // onDone
        () => {
          if (projectId) {
            scriptStore.updateColumn(projectId, column.id, { isGenerating: false })
          }
        },
        // onError
        (error) => {
          message.error(`生成失败: ${error}`)
          if (projectId) {
            scriptStore.updateColumn(projectId, column.id, { isGenerating: false })
          }
        }
      )

      if (column.id === columns[0].id) {
        cancelFnRef.current = cancelFn
      }
    })
  }, [projectId, originalContent, columns, customPrompt, defaultPrompt])

  // 打开保存版本弹窗
  const openSaveVersionModal = (type: 'script' | 'prompt') => {
    setSaveVersionType(type)
    versionForm.resetFields()
    setSaveVersionModalVisible(true)
  }

  // 保存版本
  const saveVersion = async () => {
    if (!projectId) return
    
    try {
      const values = await versionForm.validateFields()
      
      if (saveVersionType === 'script') {
        const selectedColumn = columns.find(c => c.selected)
        const contentToSave = aiEditorEnabled ? selectedColumn?.content || '' : originalContent
        
        if (!contentToSave.trim()) {
          message.warning('剧本内容为空')
          return
        }
        
        // 保存到后端（返回带 ID 的版本）
        const result = await scriptsApi.createScriptVersion(projectId, {
          name: values.name || `版本 ${scriptVersions.length + 1}`,
          description: values.description || '',
          content: contentToSave,
          original_content: originalContent,
          model_used: aiEditorEnabled ? selectedColumn?.model : undefined,
          prompt_used: aiEditorEnabled ? (customPrompt || defaultPrompt) : undefined,
        })
        
        // 同步到本地 store
        const version: ScriptVersion = {
          id: result.version.id,
          name: result.version.name,
          description: result.version.description,
          content: result.version.content,
          originalContent: result.version.original_content,
          modelUsed: result.version.model_used,
          promptUsed: result.version.prompt_used,
          createdAt: result.version.created_at,
        }
        scriptStore.addScriptVersion(projectId, version)
        
        // 同时保存当前内容
        await scriptsApi.save({
          project_id: projectId,
          content: contentToSave,
          model_used: version.modelUsed,
          prompt_used: version.promptUsed
        })
        
        message.success('剧本版本已保存')
      } else {
        if (!customPrompt.trim()) {
          message.warning('提示词内容为空')
          return
        }
        
        // 保存提示词到后端
        const result = await scriptsApi.createPromptVersion(projectId, {
          name: values.name || `提示词 ${promptVersions.length + 1}`,
          description: values.description || '',
          prompt: customPrompt,
        })
        
        // 同步到本地 store
        const version: PromptVersion = {
          id: result.version.id,
          name: result.version.name,
          description: result.version.description,
          prompt: result.version.prompt,
          createdAt: result.version.created_at,
        }
        scriptStore.addPromptVersion(projectId, version)
        
        // 同时保存自定义提示词
        await scriptsApi.saveCustomPrompt(projectId, customPrompt)
        
        message.success('提示词版本已保存')
      }
      
      setSaveVersionModalVisible(false)
    } catch (error) {
      message.error('保存失败')
    }
  }

  // 切换剧本版本
  const switchScriptVersion = (version: ScriptVersion) => {
    if (!projectId) return
    
    setOriginalContent(version.originalContent)
    if (version.modelUsed) {
      // 如果有使用模型，切换到 AI 模式并设置内容
      setAiEditorEnabled(true)
      setColumns([{
        id: Date.now(),
        model: version.modelUsed,
        content: version.content,
        isGenerating: false,
        selected: true
      }])
    } else {
      setAiEditorEnabled(false)
    }
    
    scriptStore.setSelectedScriptVersion(projectId, version.id)
    setScriptVersionModalVisible(false)
    message.success(`已切换到版本: ${version.name}`)
  }

  // 切换提示词版本
  const switchPromptVersion = (version: PromptVersion) => {
    if (!projectId) return
    
    setCustomPrompt(version.prompt)
    setPromptVersionModalVisible(false)
    message.success(`已切换到提示词: ${version.name}`)
  }

  // 清除内容
  const clearContent = () => {
    setOriginalContent('')
    setColumns(columns.map(c => ({ ...c, content: '' })))
  }

  // 打开模型配置弹窗
  const openConfigModal = (model: string) => {
    if (!globalSettings) return
    
    setConfigModalModel(model)
    const projectConfig = projectLLMConfigs[model] || {}
    const formValues = projectConfigToFormValues(projectConfig, globalSettings.llm)
    
    configForm.setFieldsValue(formValues)
    setConfigModalVisible(true)
  }

  // 保存模型配置
  const saveModelConfig = async () => {
    if (!projectId || !configModalModel) return
    
    try {
      const values = configForm.getFieldsValue()
      const config = formValuesToProjectConfig(values)
      
      await projectsApi.updateLLMConfig(projectId, configModalModel, config)
      
      setProjectLLMConfigs(prev => ({
        ...prev,
        [configModalModel]: config
      }))
      
      message.success('配置已保存')
      setConfigModalVisible(false)
    } catch (error) {
      message.error('保存配置失败')
    }
  }

  // 重置为全局默认
  const resetToGlobalConfig = () => {
    if (!globalSettings) return
    
    const formValues = {
      llm_max_tokens: globalSettings.llm.max_tokens,
      llm_top_p: globalSettings.llm.top_p,
      llm_temperature: globalSettings.llm.temperature,
      llm_enable_thinking: globalSettings.llm.enable_thinking,
      llm_thinking_budget: globalSettings.llm.thinking_budget,
      llm_result_format: globalSettings.llm.result_format,
      llm_enable_search: globalSettings.llm.enable_search,
    }
    configForm.setFieldsValue(formValues)
  }

  // 检查模型是否有项目级配置
  const hasProjectConfig = (model: string) => {
    return !!projectLLMConfigs[model]
  }

  // 获取当前显示的剧本内容
  const getCurrentScriptContent = () => {
    if (aiEditorEnabled) {
      const selectedColumn = columns.find(c => c.selected)
      return selectedColumn?.content || ''
    }
    return originalContent
  }

  // 解析分镜
  const parseShots = async () => {
    if (!projectId) return
    
    const content = getCurrentScriptContent()
    if (!content?.trim()) {
      message.warning('请先输入或生成剧本内容')
      return
    }
    
    setParsing(true)
    try {
      // 先保存剧本内容
      await scriptsApi.save({
        project_id: projectId,
        content: content,
      })
      
      // 然后解析分镜
      const result = await scriptsApi.parseShots(projectId)
      
      // 刷新项目以获取更新后的分镜数据
      await fetchProject(projectId)
      
      message.success(`成功解析出 ${result.shots?.length || 0} 个分镜，可前往"分镜首帧"页面查看`)
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '解析分镜失败')
    } finally {
      setParsing(false)
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
    <div style={{ padding: 24, height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* 页面标题 */}
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 600, margin: 0, color: '#e0e0e0' }}>
            分镜脚本
          </h1>
          <p style={{ color: '#888', margin: '4px 0 0', fontSize: 13 }}>
            {currentProject?.name}
          </p>
        </div>
        <Space>
          <Button 
            icon={<HistoryOutlined />} 
            onClick={() => setScriptVersionModalVisible(true)}
          >
            剧本版本
            {scriptVersions.length > 0 && (
              <Tag color="gold" style={{ marginLeft: 4 }}>{scriptVersions.length}</Tag>
            )}
          </Button>
          <Switch
            checked={aiEditorEnabled}
            onChange={setAiEditorEnabled}
            checkedChildren="AI 编剧"
            unCheckedChildren="原始"
          />
          <Button icon={<ClearOutlined />} onClick={clearContent}>
            清除
          </Button>
          <Button 
            type="primary" 
            icon={<SaveOutlined />} 
            onClick={() => openSaveVersionModal('script')}
            loading={saving}
          >
            保存剧本
          </Button>
          <Button 
            type="primary"
            icon={<PlayCircleOutlined />} 
            onClick={parseShots}
            loading={parsing}
            disabled={!getCurrentScriptContent()}
          >
            解析分镜
          </Button>
        </Space>
      </div>

      <div style={{ flex: 1, display: 'flex', gap: 16, minHeight: 0 }}>
        {/* 左侧：原始内容输入 */}
        <div style={{ width: 350, display: 'flex', flexDirection: 'column' }}>
          <Card 
            title={
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <FileTextOutlined />
                原始剧本
              </div>
            }
            extra={
              <Upload {...uploadProps}>
                <Button icon={<UploadOutlined />} size="small">
                  上传文件
                </Button>
              </Upload>
            }
            style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
            bodyStyle={{ flex: 1, padding: 12, display: 'flex', flexDirection: 'column' }}
          >
            <TextArea
              value={originalContent}
              onChange={(e) => setOriginalContent(e.target.value)}
              placeholder="在此输入剧本内容，或上传 txt/md/docx/pdf 文件..."
              style={{ 
                flex: 1, 
                resize: 'none',
                background: '#1a1a1a',
                borderColor: '#333'
              }}
            />
          </Card>
        </div>

        {/* 中间：AI 生成区域 */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          {aiEditorEnabled ? (
            <>
              {/* 提示词编辑器 */}
              <Card 
                size="small" 
                style={{ marginBottom: 12 }}
                bodyStyle={{ padding: 12 }}
              >
                <div style={{ marginBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ color: '#888', fontSize: 13 }}>自定义提示词</span>
                  <Space>
                    <Button 
                      size="small" 
                      icon={<HistoryOutlined />}
                      onClick={() => setPromptVersionModalVisible(true)}
                    >
                      提示词版本
                      {promptVersions.length > 0 && (
                        <Tag color="blue" style={{ marginLeft: 4 }}>{promptVersions.length}</Tag>
                      )}
                    </Button>
                    <Button 
                      size="small" 
                      type="link"
                      onClick={() => setCustomPrompt(defaultPrompt)}
                    >
                      重置为默认
                    </Button>
                  </Space>
                </div>
                <TextArea
                  value={customPrompt}
                  onChange={(e) => setCustomPrompt(e.target.value)}
                  rows={2}
                  style={{ background: '#1a1a1a', borderColor: '#333' }}
                />
                <div style={{ marginTop: 12, display: 'flex', gap: 8, justifyContent: 'space-between' }}>
                  <Space>
                    <Button
                      type="primary"
                      icon={<PlayCircleOutlined />}
                      onClick={generateScript}
                      disabled={columns.some(c => c.isGenerating)}
                    >
                      生成剧本
                    </Button>
                    <Button
                      icon={<PlusOutlined />}
                      onClick={addColumn}
                      disabled={columns.length >= 3}
                    >
                      添加对比栏
                    </Button>
                  </Space>
                  <Button
                    icon={<SaveOutlined />}
                    onClick={() => openSaveVersionModal('prompt')}
                  >
                    保存提示词
                  </Button>
                </div>
              </Card>

              {/* 多栏对比 */}
              <div style={{ flex: 1, display: 'flex', gap: 12, minHeight: 0 }}>
                {columns.map((column) => (
                  <div
                    key={column.id}
                    className="compare-column"
                    style={{
                      flex: 1,
                      minWidth: 0,
                      border: column.selected ? '1px solid #e5a84b' : '1px solid #333'
                    }}
                  >
                    <div className="compare-column-header">
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Radio
                          checked={column.selected}
                          onChange={() => selectColumn(column.id)}
                        />
                        <Select
                          value={column.model}
                          onChange={(v) => updateColumnModel(column.id, v)}
                          size="small"
                          style={{ width: 120 }}
                          options={availableModels.map(m => ({ label: m.name, value: m.key }))}
                        />
                        <Tooltip title={hasProjectConfig(column.model) ? '已自定义配置' : '模型参数设置'}>
                          <Button
                            type="text"
                            size="small"
                            icon={<SettingOutlined />}
                            onClick={() => openConfigModal(column.model)}
                            style={{ 
                              color: hasProjectConfig(column.model) ? '#e5a84b' : '#888'
                            }}
                          />
                        </Tooltip>
                      </div>
                      {columns.length > 1 && (
                        <Button
                          type="text"
                          size="small"
                          icon={<MinusOutlined />}
                          onClick={() => removeColumn(column.id)}
                          danger
                        />
                      )}
                    </div>
                    <div 
                      className="compare-column-content"
                      style={{ 
                        whiteSpace: 'pre-wrap',
                        fontFamily: 'monospace',
                        fontSize: 13,
                        lineHeight: 1.6
                      }}
                    >
                      {column.isGenerating ? (
                        <span className="streaming-cursor">{column.content}</span>
                      ) : column.content || (
                        <Empty 
                          description="点击生成剧本" 
                          image={Empty.PRESENTED_IMAGE_SIMPLE} 
                        />
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </>
          ) : (
            // 非 AI 模式，直接显示原始内容
            <Card 
              title="剧本预览"
              style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
              bodyStyle={{ flex: 1, overflow: 'auto', padding: 16 }}
            >
              {originalContent ? (
                <pre style={{ 
                  whiteSpace: 'pre-wrap', 
                  margin: 0,
                  fontFamily: 'inherit',
                  lineHeight: 1.8
                }}>
                  {originalContent}
                </pre>
              ) : (
                <Empty 
                  description="请在左侧输入或上传剧本内容" 
                  image={Empty.PRESENTED_IMAGE_SIMPLE} 
                />
              )}
            </Card>
          )}
        </div>

        {/* 右侧：当前剧本展示 */}
        <div style={{ width: 320, display: 'flex', flexDirection: 'column' }}>
          <Card 
            title={
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <BookOutlined />
                当前剧本
                {selectedScriptVersionId && (
                  <Tag color="gold" size="small">
                    {scriptVersions.find(v => v.id === selectedScriptVersionId)?.name || '已选版本'}
                  </Tag>
                )}
              </div>
            }
            style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
            bodyStyle={{ flex: 1, overflow: 'auto', padding: 12 }}
          >
            {getCurrentScriptContent() ? (
              <pre style={{ 
                whiteSpace: 'pre-wrap', 
                margin: 0,
                fontFamily: 'inherit',
                fontSize: 12,
                lineHeight: 1.6,
                color: '#ccc'
              }}>
                {getCurrentScriptContent()}
              </pre>
            ) : (
              <Empty 
                description="暂无剧本内容" 
                image={Empty.PRESENTED_IMAGE_SIMPLE} 
              />
            )}
          </Card>
        </div>
      </div>

      {/* 剧本看板 */}
      <div style={{ marginTop: 16 }}>
        <Collapse
          activeKey={showStoryboard ? ['storyboard'] : []}
          onChange={(keys) => setShowStoryboard(keys.includes('storyboard'))}
          expandIcon={({ isActive }) => <CaretRightOutlined rotate={isActive ? 90 : 0} />}
          style={{ background: '#1f1f1f', border: '1px solid #333' }}
          items={[{
            key: 'storyboard',
            label: (
              <Space>
                <AppstoreOutlined />
                <span style={{ fontWeight: 600 }}>剧本看板</span>
                <Tag>{shots.length} 个分镜</Tag>
              </Space>
            ),
            children: shots.length === 0 ? (
              <Empty 
                description="暂无分镜，请先解析剧本" 
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              />
            ) : (
              <div style={{ maxHeight: 400, overflow: 'auto' }}>
                <Table
                  dataSource={shots}
                  rowKey="id"
                  size="small"
                  pagination={false}
                  scroll={{ x: 1800 }}
                  columns={[
                    {
                      title: '序号',
                      dataIndex: 'shot_number',
                      width: 60,
                      fixed: 'left',
                      render: (num: number) => <Tag color="blue">{num}</Tag>
                    },
                    {
                      title: '首帧',
                      width: 80,
                      render: (_: any, record: Shot) => {
                        const frame = getFrameForShot(record.id)
                        const frameUrl = frame?.selected_url || record.first_frame_url
                        return frameUrl ? (
                          <Image src={frameUrl} width={60} height={40} style={{ objectFit: 'cover', borderRadius: 4 }} />
                        ) : (
                          <div style={{ width: 60, height: 40, background: '#333', borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                            <PictureOutlined style={{ color: '#666' }} />
                          </div>
                        )
                      }
                    },
                    {
                      title: '视频',
                      width: 80,
                      render: (_: any, record: Shot) => {
                        const video = getVideoForShot(record.id)
                        return video?.video_url ? (
                          <Tag color="green" icon={<VideoCameraOutlined />}>已生成</Tag>
                        ) : (
                          <Tag color="default">待生成</Tag>
                        )
                      }
                    },
                    {
                      title: '镜头设计',
                      dataIndex: 'shot_design',
                      width: 180,
                      ellipsis: true,
                      render: (text: string, record: Shot) => 
                        editingShotId === record.id ? (
                          <Input.TextArea 
                            defaultValue={text} 
                            autoSize={{ minRows: 1, maxRows: 3 }}
                            onChange={(e) => shotForm.setFieldValue('shot_design', e.target.value)}
                          />
                        ) : text || '-'
                    },
                    {
                      title: '景别',
                      dataIndex: 'scene_type',
                      width: 80,
                      render: (type: string, record: Shot) => 
                        editingShotId === record.id ? (
                          <Select 
                            defaultValue={type} 
                            style={{ width: 70 }}
                            size="small"
                            options={[
                              { label: '远景', value: '远景' },
                              { label: '全景', value: '全景' },
                              { label: '中景', value: '中景' },
                              { label: '近景', value: '近景' },
                              { label: '特写', value: '特写' },
                            ]}
                            onChange={(v) => shotForm.setFieldValue('scene_type', v)}
                          />
                        ) : <Tag>{type || '-'}</Tag>
                    },
                    {
                      title: '角色',
                      dataIndex: 'characters',
                      width: 150,
                      render: (chars: string[]) => (
                        <Space size={4} wrap>
                          {chars?.map((name, i) => {
                            const char = getCharacterByName(name)
                            const avatarUrl = char?.image_groups?.[char.selected_group_index]?.front_url
                            return (
                              <Tooltip key={i} title={name}>
                                {avatarUrl ? (
                                  <Image src={avatarUrl} width={24} height={24} style={{ borderRadius: 12, objectFit: 'cover' }} preview={false} />
                                ) : (
                                  <Tag icon={<UserOutlined />} style={{ margin: 0 }}>{name}</Tag>
                                )}
                              </Tooltip>
                            )
                          })}
                          {(!chars || chars.length === 0) && '-'}
                        </Space>
                      )
                    },
                    {
                      title: '台词',
                      dataIndex: 'dialogue',
                      width: 180,
                      ellipsis: true,
                      render: (text: string, record: Shot) => 
                        editingShotId === record.id ? (
                          <Input.TextArea 
                            defaultValue={text} 
                            autoSize={{ minRows: 1, maxRows: 3 }}
                            onChange={(e) => shotForm.setFieldValue('dialogue', e.target.value)}
                          />
                        ) : text || '-'
                    },
                    {
                      title: '场景',
                      dataIndex: 'scene_setting',
                      width: 150,
                      ellipsis: true,
                      render: (text: string) => text || '-'
                    },
                    {
                      title: '动作',
                      dataIndex: 'character_action',
                      width: 150,
                      ellipsis: true,
                      render: (text: string, record: Shot) => 
                        editingShotId === record.id ? (
                          <Input.TextArea 
                            defaultValue={text} 
                            autoSize={{ minRows: 1, maxRows: 3 }}
                            onChange={(e) => shotForm.setFieldValue('character_action', e.target.value)}
                          />
                        ) : text || '-'
                    },
                    {
                      title: '情绪',
                      dataIndex: 'mood',
                      width: 100,
                      render: (text: string) => text || '-'
                    },
                    {
                      title: '时长',
                      dataIndex: 'duration',
                      width: 70,
                      render: (duration: number, record: Shot) => 
                        editingShotId === record.id ? (
                          <InputNumber 
                            defaultValue={duration} 
                            min={1} 
                            max={10} 
                            size="small"
                            style={{ width: 60 }}
                            onChange={(v) => shotForm.setFieldValue('duration', v)}
                          />
                        ) : `${duration || 5}s`
                    },
                    {
                      title: '操作',
                      width: 120,
                      fixed: 'right',
                      render: (_: any, record: Shot) => (
                        <Space size={4}>
                          {editingShotId === record.id ? (
                            <>
                              <Button 
                                type="link" 
                                size="small"
                                onClick={async () => {
                                  const values = shotForm.getFieldsValue()
                                  await updateShot(record.id, values)
                                }}
                              >
                                保存
                              </Button>
                              <Button 
                                type="link" 
                                size="small" 
                                onClick={() => {
                                  setEditingShotId(null)
                                  shotForm.resetFields()
                                }}
                              >
                                取消
                              </Button>
                            </>
                          ) : (
                            <>
                              <Button 
                                type="link" 
                                size="small" 
                                icon={<EditOutlined />}
                                onClick={() => {
                                  setEditingShotId(record.id)
                                  shotForm.setFieldsValue(record)
                                }}
                              />
                              <Popconfirm
                                title="确定删除此分镜？"
                                onConfirm={() => deleteShot(record.id)}
                                okText="删除"
                                cancelText="取消"
                              >
                                <Button type="link" size="small" danger icon={<DeleteOutlined />} />
                              </Popconfirm>
                            </>
                          )}
                        </Space>
                      )
                    }
                  ]}
                />
              </div>
            ),
          }]}
        />
      </div>

      {/* 模型配置弹窗 */}
      <Modal
        title={
          <Space>
            <SettingOutlined />
            {configModalModel} 参数配置
            {hasProjectConfig(configModalModel) && (
              <span style={{ fontSize: 12, color: '#e5a84b' }}>(已自定义)</span>
            )}
          </Space>
        }
        open={configModalVisible}
        onCancel={() => setConfigModalVisible(false)}
        onOk={saveModelConfig}
        okText="保存"
        cancelText="取消"
        width={560}
        styles={{
          body: { maxHeight: '60vh', overflowY: 'auto' }
        }}
        footer={(_, { OkBtn, CancelBtn }) => (
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <Button onClick={resetToGlobalConfig}>
              重置为全局默认
            </Button>
            <Space>
              <CancelBtn />
              <OkBtn />
            </Space>
          </div>
        )}
      >
        {globalSettings && (
          <Form form={configForm} layout="vertical" style={{ marginTop: 16 }}>
            <LLMConfigForm
              form={configForm}
              availableModels={globalSettings.available_llm_models}
              selectedModel={configModalModel}
              compact={true}
              hideModelSelect={true}
            />
          </Form>
        )}
        <div style={{ marginTop: 16, padding: 12, background: '#1a1a1a', borderRadius: 6 }}>
          <p style={{ margin: 0, color: '#888', fontSize: 12 }}>
            💡 这些配置仅对当前项目中使用 <strong style={{ color: '#e5a84b' }}>{configModalModel}</strong> 模型时生效。
          </p>
        </div>
      </Modal>

      {/* 保存版本弹窗 */}
      <Modal
        title={saveVersionType === 'script' ? '保存剧本版本' : '保存提示词版本'}
        open={saveVersionModalVisible}
        onCancel={() => setSaveVersionModalVisible(false)}
        onOk={saveVersion}
        okText="保存"
        cancelText="取消"
      >
        <Form form={versionForm} layout="vertical">
          <Form.Item
            name="name"
            label="版本名称"
            rules={[{ required: true, message: '请输入版本名称' }]}
          >
            <Input placeholder={`例如：${saveVersionType === 'script' ? '初稿' : '优化版提示词'}`} />
          </Form.Item>
          <Form.Item
            name="description"
            label="修改说明"
          >
            <TextArea rows={3} placeholder="描述本次修改的内容（可选）" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 剧本版本管理弹窗 */}
      <Modal
        title={
          <Space>
            <HistoryOutlined />
            剧本版本历史
          </Space>
        }
        open={scriptVersionModalVisible}
        onCancel={() => setScriptVersionModalVisible(false)}
        footer={null}
        width={600}
      >
        {scriptVersions.length === 0 ? (
          <Empty description="暂无历史版本" />
        ) : (
          <List
            dataSource={scriptVersions}
            renderItem={(version) => (
              <List.Item
                actions={[
                  <Button 
                    type="link" 
                    onClick={() => switchScriptVersion(version)}
                    icon={<EditOutlined />}
                  >
                    使用此版本
                  </Button>
                ]}
                style={{
                  background: selectedScriptVersionId === version.id ? 'rgba(229, 168, 75, 0.1)' : 'transparent',
                  borderRadius: 6,
                  padding: '12px 16px',
                  marginBottom: 8
                }}
              >
                <List.Item.Meta
                  title={
                    <Space>
                      <span>{version.name}</span>
                      {version.modelUsed && (
                        <Tag color="blue">{version.modelUsed}</Tag>
                      )}
                      {selectedScriptVersionId === version.id && (
                        <Tag color="gold">当前使用</Tag>
                      )}
                    </Space>
                  }
                  description={
                    <div>
                      <div style={{ color: '#888', fontSize: 12 }}>
                        {new Date(version.createdAt).toLocaleString('zh-CN')}
                      </div>
                      {version.description && (
                        <div style={{ color: '#aaa', fontSize: 12, marginTop: 4 }}>
                          {version.description}
                        </div>
                      )}
                    </div>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Modal>

      {/* 提示词版本管理弹窗 */}
      <Modal
        title={
          <Space>
            <HistoryOutlined />
            提示词版本历史
          </Space>
        }
        open={promptVersionModalVisible}
        onCancel={() => setPromptVersionModalVisible(false)}
        footer={null}
        width={600}
      >
        {promptVersions.length === 0 ? (
          <Empty description="暂无历史版本" />
        ) : (
          <List
            dataSource={promptVersions}
            renderItem={(version) => (
              <List.Item
                actions={[
                  <Button 
                    type="link" 
                    onClick={() => switchPromptVersion(version)}
                    icon={<EditOutlined />}
                  >
                    使用此版本
                  </Button>
                ]}
                style={{
                  background: customPrompt === version.prompt ? 'rgba(24, 144, 255, 0.1)' : 'transparent',
                  borderRadius: 6,
                  padding: '12px 16px',
                  marginBottom: 8
                }}
              >
                <List.Item.Meta
                  title={
                    <Space>
                      <span>{version.name}</span>
                      {customPrompt === version.prompt && (
                        <Tag color="blue">当前使用</Tag>
                      )}
                    </Space>
                  }
                  description={
                    <div>
                      <div style={{ color: '#888', fontSize: 12 }}>
                        {new Date(version.createdAt).toLocaleString('zh-CN')}
                      </div>
                      {version.description && (
                        <div style={{ color: '#aaa', fontSize: 12, marginTop: 4 }}>
                          {version.description}
                        </div>
                      )}
                      <div style={{ 
                        color: '#666', 
                        fontSize: 11, 
                        marginTop: 8,
                        maxHeight: 60,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis'
                      }}>
                        {version.prompt.slice(0, 150)}...
                      </div>
                    </div>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Modal>
    </div>
  )
}

export default ScriptPage
