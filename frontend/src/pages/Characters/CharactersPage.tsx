import { useEffect, useState, useRef, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { 
  Card, Button, Modal, Form, Input, Empty, Spin, message, 
  Radio, Tooltip, Space, Popconfirm, Image, Alert, Progress,
  InputNumber, Switch, Select, Tag
} from 'antd'
import { 
  PlusOutlined, ReloadOutlined, DeleteOutlined, 
  UserOutlined, SoundOutlined, ThunderboltOutlined,
  SettingOutlined, ExclamationCircleOutlined, StopOutlined,
  BgColorsOutlined
} from '@ant-design/icons'
import { charactersApi, Character, stylesApi, Style, galleryApi, GalleryImage } from '../../services/api'
import { useProjectStore } from '../../stores/projectStore'
import { useGenerationStore } from '../../stores/generationStore'

const { TextArea } = Input

const CharactersPage = () => {
  const { projectId } = useParams<{ projectId: string }>()
  const { currentProject, fetchProject } = useProjectStore()
  const { 
    characterGroupCount, 
    setCharacterGroupCount,
    characterUseStyle,
    setCharacterUseStyle,
    characterSelectedStyleId,
    setCharacterSelectedStyleId,
    isGenerating: globalIsGenerating,
    shouldStop,
    startBatchGeneration,
    updateTaskStatus,
    setCurrentTaskIndex,
    stopGeneration,
    resetGeneration,
    batchTasks,
    currentTaskIndex,
    addGeneratingItem,
    removeGeneratingItem,
    isItemGenerating,
  } = useGenerationStore()
  
  const [characters, setCharacters] = useState<Character[]>([])
  const [loading, setLoading] = useState(true)
  const [extracting, setExtracting] = useState(false)
  const [selectedCharacter, setSelectedCharacter] = useState<Character | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [generatingGroups, setGeneratingGroups] = useState<Set<string>>(new Set())
  const [generatingAll, setGeneratingAll] = useState(false)
  const [form] = Form.useForm()
  
  // 批量生成状态
  const [batchGenerating, setBatchGenerating] = useState(false)
  const [batchProgress, setBatchProgress] = useState({ current: 0, total: 0, currentName: '' })
  
  // 设置弹窗
  const [settingsModalVisible, setSettingsModalVisible] = useState(false)
  // 新建角色弹窗
  const [createModalVisible, setCreateModalVisible] = useState(false)
  const [createForm] = Form.useForm()
  
  // 风格相关
  const [styles, setStyles] = useState<Style[]>([])
  // 详情页风格设置（优先级高于全局）
  const [localUseStyle, setLocalUseStyle] = useState<boolean | null>(null)
  const [localStyleId, setLocalStyleId] = useState<string | null>(null)
  
  // 图库相关
  const [galleryImages, setGalleryImages] = useState<GalleryImage[]>([])
  const [galleryModalVisible, setGalleryModalVisible] = useState(false)
  const [selectingForCharacter, setSelectingForCharacter] = useState<Character | null>(null)
  const [selectedGalleryImage, setSelectedGalleryImage] = useState<string>('')
  const [selectingGroupIndex, setSelectingGroupIndex] = useState(0)
  
  const selectedCharacterIdRef = useRef<string | null>(null)
  const shouldStopRef = useRef(false)
  const isMountedRef = useRef(true)

  // 安全的状态更新
  const safeSetState = useCallback(<T,>(setter: React.Dispatch<React.SetStateAction<T>>, value: T | ((prev: T) => T)) => {
    if (isMountedRef.current) {
      setter(value as any)
    }
  }, [])

  useEffect(() => {
    isMountedRef.current = true
    return () => {
      isMountedRef.current = false
    }
  }, [])

  useEffect(() => {
    const loadData = async () => {
      if (!projectId) return
      
      safeSetState(setLoading, true)
      try {
        // 不等待 fetchProject 完成再加载角色列表
        fetchProject(projectId).catch(() => {})
        const [charsRes, stylesRes, galleryRes] = await Promise.all([
          charactersApi.list(projectId),
          stylesApi.list(projectId),
          galleryApi.list(projectId)
        ])
        safeSetState(setCharacters, charsRes.characters)
        safeSetState(setStyles, stylesRes.styles)
        safeSetState(setGalleryImages, galleryRes.images)
      } catch (error) {
        message.error('加载失败')
      } finally {
        safeSetState(setLoading, false)
      }
    }
    loadData()
  }, [projectId, fetchProject, safeSetState])

  const extractCharacters = async () => {
    if (!projectId) return
    
    if (!currentProject?.script?.processed_content && !currentProject?.script?.original_content) {
      message.warning('请先保存剧本')
      return
    }
    
    safeSetState(setExtracting, true)
    try {
      const { characters: newChars } = await charactersApi.extract(projectId)
      safeSetState(setCharacters, (prev: Character[]) => [...prev, ...newChars])
      message.success(`成功提取 ${newChars.length} 个角色`)
    } catch (error) {
      message.error('提取失败')
    } finally {
      safeSetState(setExtracting, false)
    }
  }

  // 手动创建角色
  const createCharacter = async () => {
    if (!projectId) return
    
    try {
      const values = await createForm.validateFields()
      const { character } = await charactersApi.create({
        project_id: projectId,
        name: values.name,
        description: values.description || '',
        appearance: values.appearance || '',
        personality: values.personality || '',
        character_prompt: values.character_prompt || '',
      })
      safeSetState(setCharacters, (prev: Character[]) => [...prev, character])
      setCreateModalVisible(false)
      createForm.resetFields()
      message.success('角色已创建')
      
      // 自动打开编辑弹窗
      openCharacterModal(character)
    } catch (error) {
      message.error('创建失败')
    }
  }

  const openCharacterModal = (character: Character) => {
    setSelectedCharacter(character)
    selectedCharacterIdRef.current = character.id
    form.setFieldsValue({
      name: character.name,
      description: character.description,
      appearance: character.appearance,
      personality: character.personality,
      common_prompt: character.common_prompt,
      character_prompt: character.character_prompt,
      negative_prompt: character.negative_prompt || '',
    })
    // 重置详情页风格设置（使用全局设置）
    setLocalUseStyle(null)
    setLocalStyleId(null)
    setIsModalOpen(true)
  }
  
  // 获取当前有效的风格设置（详情页优先于全局）
  const getEffectiveStyleSettings = () => {
    const useStyle = localUseStyle !== null ? localUseStyle : characterUseStyle
    const styleId = localStyleId !== null ? localStyleId : characterSelectedStyleId
    return { useStyle, styleId }
  }
  
  // 获取选中的风格信息
  const getSelectedStyle = () => {
    const { styleId } = getEffectiveStyleSettings()
    return styles.find(s => s.id === styleId)
  }

  const saveCharacter = async () => {
    if (!selectedCharacter) return
    
    try {
      const values = await form.validateFields()
      const updated = await charactersApi.update(selectedCharacter.id, values)
      safeSetState(setCharacters, (prev: Character[]) => prev.map(c => c.id === updated.id ? updated : c))
      setIsModalOpen(false)
      message.success('角色已保存')
    } catch (error) {
      message.error('保存失败')
    }
  }

  const generateImages = async (characterId: string, groupIndex: number) => {
    // 检查是否正在批量生成
    if (batchGenerating) {
      message.warning('正在批量生成中，请等待完成或停止后再试')
      return
    }
    
    const formValues = form.getFieldsValue()
    const character = characters.find(c => c.id === characterId)
    if (!character) return
    
    const key = `${characterId}-${groupIndex}`
    setGeneratingGroups(prev => new Set([...prev, key]))
    addGeneratingItem(characterId)
    
    // 获取风格设置
    const { useStyle, styleId } = getEffectiveStyleSettings()
    
    try {
      await charactersApi.generate(characterId, {
        group_index: groupIndex,
        common_prompt: formValues.common_prompt || character.common_prompt,
        character_prompt: formValues.character_prompt || character.character_prompt,
        negative_prompt: formValues.negative_prompt || character.negative_prompt,
        use_style: useStyle,
        style_id: styleId || undefined,
      })
      const updated = await charactersApi.get(characterId)
      safeSetState(setCharacters, (prev: Character[]) => prev.map(c => c.id === updated.id ? updated : c))
      if (selectedCharacterIdRef.current === characterId) {
        setSelectedCharacter(updated)
      }
      message.success(`第 ${groupIndex + 1} 组图片生成成功`)
    } catch (error) {
      if (error instanceof Error) {
        message.error(`第 ${groupIndex + 1} 组图片生成失败: ${error.message}`)
      } else {
        message.error(`第 ${groupIndex + 1} 组图片生成失败`)
      }
    } finally {
      setGeneratingGroups(prev => {
        const next = new Set(prev)
        next.delete(key)
        return next
      })
      removeGeneratingItem(characterId)
    }
  }

  const generateAllImages = async (characterId: string) => {
    // 检查是否正在批量生成
    if (batchGenerating) {
      message.warning('正在批量生成中，请等待完成或停止后再试')
      return
    }
    
    const formValues = form.getFieldsValue()
    const character = characters.find(c => c.id === characterId)
    if (!character) return
    
    const keys = Array.from({ length: characterGroupCount }, (_, i) => `${characterId}-${i}`)
    setGeneratingAll(true)
    setGeneratingGroups(new Set(keys))
    addGeneratingItem(characterId)
    
    // 获取风格设置
    const { useStyle, styleId } = getEffectiveStyleSettings()
    
    try {
      await charactersApi.generateAll(characterId, {
        common_prompt: formValues.common_prompt || character.common_prompt,
        character_prompt: formValues.character_prompt || character.character_prompt,
        negative_prompt: formValues.negative_prompt || character.negative_prompt,
        group_count: characterGroupCount,
        use_style: useStyle,
        style_id: styleId || undefined,
      })
      const updated = await charactersApi.get(characterId)
      safeSetState(setCharacters, (prev: Character[]) => prev.map(c => c.id === updated.id ? updated : c))
      if (selectedCharacterIdRef.current === characterId) {
        setSelectedCharacter(updated)
      }
      message.success(`${characterGroupCount}组图片生成成功`)
    } catch (error) {
      if (error instanceof Error) {
        message.error(`图片生成失败: ${error.message}`)
      } else {
        message.error('图片生成失败')
      }
    } finally {
      setGeneratingAll(false)
      setGeneratingGroups(new Set())
      removeGeneratingItem(characterId)
    }
  }

  // 一键生成所有角色的图片（并发版本）
  const generateAllCharactersImages = async () => {
    if (characters.length === 0) {
      message.warning('没有角色可生成')
      return
    }
    
    shouldStopRef.current = false
    setBatchGenerating(true)
    setBatchProgress({ current: 0, total: characters.length, currentName: '' })
    
    // 并发数量限制
    const concurrency = 3
    let successCount = 0
    let failCount = 0
    let completedCount = 0
    
    const generateOne = async (character: Character): Promise<boolean> => {
      if (shouldStopRef.current) return false
      
      try {
        addGeneratingItem(character.id)
        await charactersApi.generateAll(character.id, {
          common_prompt: character.common_prompt,
          character_prompt: character.character_prompt,
          negative_prompt: character.negative_prompt,
          group_count: characterGroupCount,
          use_style: characterUseStyle,
          style_id: characterSelectedStyleId || undefined,
        })
        const updated = await charactersApi.get(character.id)
        safeSetState(setCharacters, (prev: Character[]) => prev.map(c => c.id === updated.id ? updated : c))
        return true
      } catch (error) {
        console.error(`生成角色 ${character.name} 图片失败:`, error)
        return false
      } finally {
        removeGeneratingItem(character.id)
      }
    }
    
    // 分批并发执行
    for (let i = 0; i < characters.length; i += concurrency) {
      if (shouldStopRef.current) break
      
      const batch = characters.slice(i, i + concurrency)
      safeSetState(setBatchProgress, { 
        current: i + 1, 
        total: characters.length, 
        currentName: batch.map(c => c.name).join(', ')
      })
      
      const results = await Promise.all(batch.map(generateOne))
      
      results.forEach(success => {
        completedCount++
        if (success) successCount++
        else failCount++
      })
      
      safeSetState(setBatchProgress, { 
        current: completedCount, 
        total: characters.length, 
        currentName: ''
      })
    }
    
    safeSetState(setBatchGenerating, false)
    safeSetState(setBatchProgress, { current: 0, total: 0, currentName: '' })
    
    if (shouldStopRef.current) {
      message.info(`已停止生成，完成 ${successCount}/${characters.length} 个角色`)
    } else if (failCount === 0) {
      message.success(`成功生成所有 ${successCount} 个角色的图片`)
    } else {
      message.warning(`生成完成：${successCount} 个成功，${failCount} 个失败`)
    }
  }

  const handleStopGeneration = () => {
    shouldStopRef.current = true
    message.info('正在停止生成...')
  }

  const selectGroup = async (characterId: string, groupIndex: number) => {
    try {
      const updated = await charactersApi.update(characterId, {
        selected_group_index: groupIndex
      })
      safeSetState(setCharacters, (prev: Character[]) => prev.map(c => c.id === updated.id ? updated : c))
      if (selectedCharacter?.id === characterId) {
        setSelectedCharacter(updated)
      }
    } catch (error) {
      message.error('选择失败')
    }
  }

  const deleteCharacter = async (characterId: string) => {
    try {
      await charactersApi.delete(characterId)
      safeSetState(setCharacters, (prev: Character[]) => prev.filter(c => c.id !== characterId))
      message.success('角色已删除')
    } catch (error) {
      message.error('删除失败')
    }
  }

  const deleteAllCharacters = async () => {
    if (!projectId) return
    
    try {
      await charactersApi.deleteAll(projectId)
      safeSetState(setCharacters, [])
      message.success('已删除所有角色')
    } catch (error) {
      message.error('删除失败')
    }
  }

  // 打开图库选择弹窗
  const openGalleryModal = (character: Character, groupIndex: number) => {
    setSelectingForCharacter(character)
    setSelectingGroupIndex(groupIndex)
    setSelectedGalleryImage('')
    setGalleryModalVisible(true)
  }

  // 确认从图库选择图片
  const confirmGallerySelect = async () => {
    if (!selectingForCharacter || !selectedGalleryImage) {
      message.warning('请选择一张图片')
      return
    }
    
    try {
      const { character: updated } = await charactersApi.selectImages(selectingForCharacter.id, {
        image_urls: [selectedGalleryImage],
        group_index: selectingGroupIndex
      })
      safeSetState(setCharacters, (prev: Character[]) => prev.map(c => c.id === updated.id ? updated : c))
      if (selectedCharacter?.id === updated.id) {
        setSelectedCharacter(updated)
      }
      setGalleryModalVisible(false)
      message.success('图片已选择')
    } catch (error) {
      message.error('选择失败')
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
      {/* 页面标题 */}
      <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 600, margin: 0, color: '#e0e0e0' }}>
            角色管理
          </h1>
          <p style={{ color: '#888', margin: '4px 0 0', fontSize: 13 }}>
            {currentProject?.name} - 共 {characters.length} 个角色
            {characterUseStyle && characterSelectedStyleId && (
              <Tag color="blue" style={{ marginLeft: 8 }}>
                <BgColorsOutlined /> 风格参考: {styles.find(s => s.id === characterSelectedStyleId)?.name || '未知'}
              </Tag>
            )}
          </p>
        </div>
        <Space>
          <Button
            icon={<SettingOutlined />}
            onClick={() => setSettingsModalVisible(true)}
          >
            设置 ({characterGroupCount}组)
          </Button>
          {characters.length > 0 && (
            <>
              {batchGenerating ? (
                <Button
                  danger
                  icon={<StopOutlined />}
                  onClick={handleStopGeneration}
                >
                  停止生成
                </Button>
              ) : (
                <Button
                  type="primary"
                  icon={<ThunderboltOutlined />}
                  onClick={generateAllCharactersImages}
                  disabled={extracting}
                >
                  一键生成所有角色
                </Button>
              )}
              <Popconfirm
                title="确定删除所有角色？"
                description="此操作不可恢复"
                icon={<ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />}
                onConfirm={deleteAllCharacters}
                okText="删除"
                cancelText="取消"
                okButtonProps={{ danger: true }}
              >
                <Button danger icon={<DeleteOutlined />} disabled={batchGenerating}>
                  删除所有
                </Button>
              </Popconfirm>
            </>
          )}
          <Button
            icon={<PlusOutlined />}
            onClick={() => setCreateModalVisible(true)}
            disabled={batchGenerating}
          >
            手动新建
          </Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={extractCharacters}
            loading={extracting}
            disabled={batchGenerating}
          >
            从剧本提取角色
          </Button>
        </Space>
      </div>

      {/* 批量生成进度条 */}
      {batchGenerating && (
        <Alert
          message={
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <Spin size="small" />
              <span>
                正在生成: {batchProgress.currentName || `${batchProgress.current}/${batchProgress.total}`}
              </span>
            </div>
          }
          description={
            <Progress 
              percent={batchProgress.total > 0 ? Math.round((batchProgress.current / batchProgress.total) * 100) : 0} 
              status="active"
            />
          }
          type="info"
          style={{ marginBottom: 24 }}
          action={
            <Button size="small" danger onClick={handleStopGeneration}>
              停止
            </Button>
          }
        />
      )}

      {characters.length === 0 ? (
        <Empty description="暂无角色，请从剧本提取" style={{ marginTop: 100 }}>
          <Button type="primary" onClick={extractCharacters} loading={extracting}>
            提取角色
          </Button>
        </Empty>
      ) : (
        <div className="image-grid">
          {characters.map((character) => {
            const avatarUrl = character.image_groups?.[character.selected_group_index]?.front_url
            const isGeneratingThis = isItemGenerating(character.id)
            return (
              <div 
                key={character.id} 
                className="asset-card" 
                onClick={() => openCharacterModal(character)}
                style={{ opacity: isGeneratingThis ? 0.7 : 1 }}
              >
                <div className="asset-card-image" style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  position: 'relative',
                }}>
                  {avatarUrl ? (
                    <Image
                      src={avatarUrl}
                      alt={character.name}
                      style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                      preview={false}
                    />
                  ) : (
                    <UserOutlined style={{ fontSize: 48, color: '#444' }} />
                  )}
                  {isGeneratingThis && (
                    <div style={{
                      position: 'absolute',
                      top: 0,
                      left: 0,
                      right: 0,
                      bottom: 0,
                      background: 'rgba(0,0,0,0.5)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}>
                      <Spin />
                    </div>
                  )}
                </div>
                <div className="asset-card-info">
                  <div className="asset-card-name">{character.name}</div>
                  <div className="asset-card-desc">{character.description || '暂无描述'}</div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* 角色编辑弹窗 */}
      <Modal
        title={`编辑角色 - ${selectedCharacter?.name}`}
        open={isModalOpen}
        onOk={saveCharacter}
        onCancel={() => {
          setIsModalOpen(false)
          selectedCharacterIdRef.current = null
        }}
        width={950}
        okText="保存"
        cancelText="取消"
      >
        {selectedCharacter && (
          <div style={{ display: 'flex', gap: 24 }}>
            {/* 左侧：图片 */}
            <div style={{ width: 420 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <h4 style={{ margin: 0 }}>角色三视图</h4>
                <Button
                  type="primary"
                  icon={<ThunderboltOutlined />}
                  onClick={() => generateAllImages(selectedCharacter.id)}
                  loading={generatingAll}
                  disabled={generatingGroups.size > 0 || batchGenerating}
                >
                  一键生成{characterGroupCount}组
                </Button>
              </div>
              
              {Array.from({ length: Math.max(characterGroupCount, selectedCharacter.image_groups?.length || 0) }, (_, groupIndex) => {
                const group = selectedCharacter.image_groups?.[groupIndex]
                const isSelected = selectedCharacter.selected_group_index === groupIndex
                const key = `${selectedCharacter.id}-${groupIndex}`
                const isGeneratingThis = generatingGroups.has(key)
                
                return (
                  <div 
                    key={groupIndex}
                    style={{
                      marginBottom: 16,
                      padding: 12,
                      border: isSelected ? '2px solid #e5a84b' : '1px solid #333',
                      borderRadius: 8,
                      background: isSelected ? 'rgba(229, 168, 75, 0.1)' : '#1a1a1a'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <Radio
                        checked={isSelected}
                        onChange={() => selectGroup(selectedCharacter.id, groupIndex)}
                      >
                        第 {groupIndex + 1} 组
                      </Radio>
                      <Space size={4}>
                        <Button
                          size="small"
                          onClick={() => openGalleryModal(selectedCharacter, groupIndex)}
                          disabled={generatingAll || batchGenerating}
                        >
                          从图库选
                        </Button>
                        <Button
                          size="small"
                          icon={<ReloadOutlined />}
                          onClick={() => generateImages(selectedCharacter.id, groupIndex)}
                          loading={isGeneratingThis}
                          disabled={generatingAll || (generatingGroups.size > 0 && !isGeneratingThis) || batchGenerating}
                        >
                          {group?.front_url ? '重新生成' : '生成'}
                        </Button>
                      </Space>
                    </div>
                    
                    <div 
                      style={{ 
                        background: '#242424',
                        borderRadius: 8,
                        overflow: 'hidden',
                        aspectRatio: '3/1',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      {isGeneratingThis ? (
                        <Spin tip="正在生成三视图..." />
                      ) : group?.front_url ? (
                        <Image 
                          src={group.front_url} 
                          alt="三视图" 
                          style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                        />
                      ) : (
                        <div style={{ color: '#666', textAlign: 'center' }}>
                          <UserOutlined style={{ fontSize: 32, marginBottom: 8 }} />
                          <div style={{ fontSize: 12 }}>点击"生成"创建三视图</div>
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>

            {/* 右侧：表单 */}
            <div style={{ flex: 1 }}>
              <Form form={form} layout="vertical">
                <Form.Item name="name" label="角色名称" rules={[{ required: true }]}>
                  <Input />
                </Form.Item>
                <Form.Item name="description" label="角色描述">
                  <TextArea rows={2} />
                </Form.Item>
                <Form.Item name="appearance" label="外观描述">
                  <TextArea rows={2} />
                </Form.Item>
                <Form.Item name="personality" label="性格特点">
                  <TextArea rows={2} />
                </Form.Item>
                <Form.Item name="common_prompt" label="通用提示词">
                  <TextArea rows={2} />
                </Form.Item>
                <Form.Item name="character_prompt" label="角色提示词">
                  <TextArea rows={2} />
                </Form.Item>
                <Form.Item 
                  name="negative_prompt" 
                  label={
                    <Space>
                      负向提示词
                      <Tooltip title="用于指定图片中不希望出现的元素">
                        <span style={{ color: '#888', fontSize: 12 }}>(?)</span>
                      </Tooltip>
                    </Space>
                  }
                  extra="指定不希望出现在生成图片中的元素"
                >
                  <TextArea rows={2} placeholder="例如：文字, 水印, 模糊, 低质量" />
                </Form.Item>
              </Form>

              {/* 风格参考设置 */}
              <Card 
                size="small" 
                title={
                  <Space>
                    <BgColorsOutlined />
                    风格参考（当前角色）
                    {localUseStyle === null && characterUseStyle && (
                      <Tag color="blue">使用全局设置</Tag>
                    )}
                  </Space>
                }
                style={{ marginTop: 16 }}
              >
                <Space direction="vertical" style={{ width: '100%' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Switch 
                      checked={localUseStyle !== null ? localUseStyle : characterUseStyle}
                      onChange={(checked) => setLocalUseStyle(checked)}
                      checkedChildren="开启"
                      unCheckedChildren="关闭"
                    />
                    {localUseStyle !== null && (
                      <Button 
                        type="link" 
                        size="small" 
                        onClick={() => { setLocalUseStyle(null); setLocalStyleId(null) }}
                      >
                        重置为全局设置
                      </Button>
                    )}
                  </div>
                  {(localUseStyle !== null ? localUseStyle : characterUseStyle) && (
                    <Select
                      placeholder="选择风格"
                      value={localStyleId !== null ? localStyleId : characterSelectedStyleId}
                      onChange={(v) => setLocalStyleId(v)}
                      style={{ width: '100%' }}
                      allowClear
                      options={styles.map(s => ({
                        label: (
                          <Space>
                            <Tag color={s.style_type === 'image' ? 'blue' : 'purple'}>
                              {s.style_type === 'image' ? '图片' : '文本'}
                            </Tag>
                            {s.name}
                            {s.is_selected && <Tag color="gold">已选中</Tag>}
                          </Space>
                        ),
                        value: s.id,
                      }))}
                    />
                  )}
                  {getSelectedStyle() && (
                    <div style={{ padding: 8, background: '#1a1a1a', borderRadius: 4, fontSize: 12, color: '#888' }}>
                      当前风格: <strong style={{ color: '#e0e0e0' }}>{getSelectedStyle()?.name}</strong>
                      {getSelectedStyle()?.style_type === 'image' ? ' (图片风格 - 使用图生图模型)' : ' (文本风格 - 使用文生图模型)'}
                    </div>
                  )}
                </Space>
              </Card>

              {/* 音色设置（占位） */}
              <Card 
                size="small" 
                title={<><SoundOutlined /> 角色音色</>}
                style={{ marginTop: 16 }}
              >
                <p style={{ color: '#888', marginBottom: 12 }}>
                  此功能即将上线，敬请期待
                </p>
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Input placeholder="选择预设音色" disabled />
                  <Button icon={<PlusOutlined />} disabled>
                    上传音频克隆
                  </Button>
                </Space>
              </Card>

              <div style={{ marginTop: 16, textAlign: 'right' }}>
                <Popconfirm
                  title="确定删除此角色？"
                  onConfirm={() => {
                    deleteCharacter(selectedCharacter.id)
                    setIsModalOpen(false)
                  }}
                  okText="删除"
                  cancelText="取消"
                  okButtonProps={{ danger: true }}
                >
                  <Button danger icon={<DeleteOutlined />}>
                    删除角色
                  </Button>
                </Popconfirm>
              </div>
            </div>
          </div>
        )}
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
          <Form.Item 
            label="每个角色生成组数"
            extra="生成图片时，每个角色将生成指定组数的三视图"
          >
            <InputNumber 
              min={1} 
              max={10} 
              value={characterGroupCount}
              onChange={(v) => setCharacterGroupCount(v || 3)}
              style={{ width: '100%' }}
            />
          </Form.Item>
          
          <Form.Item 
            label={
              <Space>
                <BgColorsOutlined />
                风格参考（全局）
              </Space>
            }
            extra="开启后将使用选定的风格生成角色图片"
          >
            <Space direction="vertical" style={{ width: '100%' }}>
              <Switch 
                checked={characterUseStyle}
                onChange={setCharacterUseStyle}
                checkedChildren="开启"
                unCheckedChildren="关闭"
              />
              {characterUseStyle && (
                <Select
                  placeholder="选择风格"
                  value={characterSelectedStyleId}
                  onChange={setCharacterSelectedStyleId}
                  style={{ width: '100%' }}
                  allowClear
                  options={styles.map(s => ({
                    label: (
                      <Space>
                        <Tag color={s.style_type === 'image' ? 'blue' : 'purple'}>
                          {s.style_type === 'image' ? '图片' : '文本'}
                        </Tag>
                        {s.name}
                        {s.is_selected && <Tag color="gold">已选中</Tag>}
                      </Space>
                    ),
                    value: s.id,
                  }))}
                />
              )}
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 新建角色弹窗 */}
      <Modal
        title="新建角色"
        open={createModalVisible}
        onOk={createCharacter}
        onCancel={() => {
          setCreateModalVisible(false)
          createForm.resetFields()
        }}
        okText="创建"
        cancelText="取消"
        width={600}
      >
        <Form form={createForm} layout="vertical">
          <Form.Item
            name="name"
            label="角色名称"
            rules={[{ required: true, message: '请输入角色名称' }]}
          >
            <Input placeholder="例如：李明" />
          </Form.Item>
          <Form.Item
            name="description"
            label="角色简介"
          >
            <TextArea rows={2} placeholder="角色的背景故事和简介" />
          </Form.Item>
          <Form.Item
            name="appearance"
            label="外观描述"
          >
            <TextArea rows={2} placeholder="详细的外貌、服装等描述" />
          </Form.Item>
          <Form.Item
            name="personality"
            label="性格特点"
          >
            <TextArea rows={2} placeholder="角色的性格特征" />
          </Form.Item>
          <Form.Item
            name="character_prompt"
            label="生图提示词"
            extra="用于生成角色图片的提示词，只描述角色本身的样貌特征"
          >
            <TextArea rows={3} placeholder="例如：青年男性，短黑发，浓眉大眼，穿白色T恤" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 图库选择弹窗 */}
      <Modal
        title={`从图库选择图片 - ${selectingForCharacter?.name || ''} 第${selectingGroupIndex + 1}组`}
        open={galleryModalVisible}
        onOk={confirmGallerySelect}
        onCancel={() => setGalleryModalVisible(false)}
        okText="确认选择"
        cancelText="取消"
        width={800}
        okButtonProps={{ disabled: !selectedGalleryImage }}
      >
        <Alert 
          message="选择一张三视图图片作为角色参考图"
          type="info"
          style={{ marginBottom: 16 }}
        />
        {galleryImages.length === 0 ? (
          <Empty description="图库暂无图片，请先上传" />
        ) : (
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', 
            gap: 12,
            maxHeight: 400,
            overflowY: 'auto'
          }}>
            {galleryImages.map(img => {
              const isSelected = selectedGalleryImage === img.url
              return (
                <div
                  key={img.id}
                  onClick={() => setSelectedGalleryImage(img.url)}
                  style={{
                    position: 'relative',
                    cursor: 'pointer',
                    border: isSelected ? '2px solid #e5a84b' : '1px solid #333',
                    borderRadius: 8,
                    overflow: 'hidden',
                    background: '#1a1a1a'
                  }}
                >
                  <Image
                    src={img.url}
                    alt={img.name}
                    style={{ width: '100%', aspectRatio: '3/1', objectFit: 'cover' }}
                    preview={false}
                  />
                  {isSelected && (
                    <div style={{
                      position: 'absolute',
                      top: 4,
                      right: 4,
                      background: '#e5a84b',
                      color: '#000',
                      borderRadius: '50%',
                      width: 24,
                      height: 24,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontWeight: 'bold',
                      fontSize: 12
                    }}>
                      ✓
                    </div>
                  )}
                  <div style={{ 
                    padding: 4, 
                    fontSize: 11, 
                    whiteSpace: 'nowrap', 
                    overflow: 'hidden', 
                    textOverflow: 'ellipsis' 
                  }}>
                    {img.name}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </Modal>
    </div>
  )
}

export default CharactersPage
