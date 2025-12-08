import { useEffect, useState, useRef, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { 
  Button, Modal, Form, Input, Empty, Spin, message, 
  Radio, Tooltip, Space, Popconfirm, Image, Alert, Progress,
  InputNumber, Select, Card, Tag, Tabs, List
} from 'antd'
import { 
  PlusOutlined, ReloadOutlined, DeleteOutlined, 
  FormatPainterOutlined, ThunderboltOutlined, SettingOutlined,
  ExclamationCircleOutlined, StopOutlined, CheckCircleOutlined,
  FileTextOutlined, PictureOutlined, SaveOutlined, HistoryOutlined
} from '@ant-design/icons'
import { stylesApi, Style, ImageStylePreset, TextStylePreset, TextStyleVersion } from '../../services/api'
import { useProjectStore } from '../../stores/projectStore'
import { useGenerationStore } from '../../stores/generationStore'

const { TextArea } = Input

const StylesPage = () => {
  const { projectId } = useParams<{ projectId: string }>()
  const { currentProject, fetchProject } = useProjectStore()
  const { 
    styleGroupCount,
    setStyleGroupCount,
    addGeneratingItem,
    removeGeneratingItem,
    isItemGenerating,
  } = useGenerationStore()
  
  const [styles, setStyles] = useState<Style[]>([])
  const [imagePresets, setImagePresets] = useState<Record<string, ImageStylePreset>>({})
  const [textPresets, setTextPresets] = useState<Record<string, TextStylePreset>>({})
  const [loading, setLoading] = useState(true)
  const [selectedStyle, setSelectedStyle] = useState<Style | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)
  const [generatingGroups, setGeneratingGroups] = useState<Set<string>>(new Set())
  const [generatingAll, setGeneratingAll] = useState(false)
  const [form] = Form.useForm()
  const [createForm] = Form.useForm()
  
  const [batchGenerating, setBatchGenerating] = useState(false)
  const [batchProgress, setBatchProgress] = useState({ current: 0, total: 0, currentName: '' })
  const [settingsModalVisible, setSettingsModalVisible] = useState(false)
  const [versionModalVisible, setVersionModalVisible] = useState(false)
  const [saveVersionModalVisible, setSaveVersionModalVisible] = useState(false)
  const [saveVersionForm] = Form.useForm()
  
  const selectedStyleIdRef = useRef<string | null>(null)
  const shouldStopRef = useRef(false)
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
        const [stylesRes, presetsRes] = await Promise.all([
          stylesApi.list(projectId),
          stylesApi.getPresets()
        ])
        safeSetState(setStyles, stylesRes.styles)
        safeSetState(setImagePresets, presetsRes.image_presets)
        safeSetState(setTextPresets, presetsRes.text_presets)
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
    createForm.setFieldValue('style_type', 'image')
    setIsCreateModalOpen(true)
  }

  const createStyle = async () => {
    if (!projectId) return
    try {
      const values = await createForm.validateFields()
      const style = await stylesApi.create({
        project_id: projectId,
        name: values.name,
        style_type: values.style_type,
        style_prompt: values.style_prompt || '',
        negative_prompt: values.negative_prompt || '',
        preset_name: values.preset_name,
        text_style_content: values.text_style_content || '',
        text_preset_name: values.text_preset_name,
      })
      safeSetState(setStyles, (prev: Style[]) => [...prev, style])
      setIsCreateModalOpen(false)
      message.success('风格已创建')
    } catch (error) {
      message.error('创建失败')
    }
  }

  const openStyleModal = (style: Style) => {
    setSelectedStyle(style)
    selectedStyleIdRef.current = style.id
    form.setFieldsValue({
      name: style.name,
      description: style.description,
      style_prompt: style.style_prompt,
      negative_prompt: style.negative_prompt,
      text_style_content: style.text_style_content,
    })
    setIsModalOpen(true)
  }

  const saveStyle = async () => {
    if (!selectedStyle) return
    try {
      const values = await form.validateFields()
      const updated = await stylesApi.update(selectedStyle.id, values)
      safeSetState(setStyles, (prev: Style[]) => prev.map(s => s.id === updated.id ? updated : s))
      setIsModalOpen(false)
      message.success('风格已保存')
    } catch (error) {
      message.error('保存失败')
    }
  }

  // 保存文本风格版本
  const openSaveVersionModal = () => {
    saveVersionForm.resetFields()
    setSaveVersionModalVisible(true)
  }

  const saveTextVersion = async () => {
    if (!selectedStyle) return
    try {
      const versionValues = await saveVersionForm.validateFields()
      const formValues = form.getFieldsValue()
      await stylesApi.saveTextVersion(selectedStyle.id, {
        version_name: versionValues.version_name,
        content: formValues.text_style_content,
        modified_info: versionValues.modified_info || '',
      })
      const updated = await stylesApi.get(selectedStyle.id)
      safeSetState(setStyles, (prev: Style[]) => prev.map(s => s.id === updated.id ? updated : s))
      setSelectedStyle(updated)
      setSaveVersionModalVisible(false)
      message.success('版本已保存')
    } catch (error) {
      message.error('保存失败')
    }
  }

  const loadTextVersion = async (version: TextStyleVersion) => {
    if (!selectedStyle) return
    try {
      const result = await stylesApi.loadTextVersion(selectedStyle.id, version.id)
      form.setFieldValue('text_style_content', result.content)
      const updated = await stylesApi.get(selectedStyle.id)
      setSelectedStyle(updated)
      setVersionModalVisible(false)
      message.success('版本已加载')
    } catch (error) {
      message.error('加载失败')
    }
  }

  const generateImages = async (styleId: string, groupIndex: number) => {
    if (batchGenerating) {
      message.warning('正在批量生成中，请等待完成或停止后再试')
      return
    }
    const formValues = form.getFieldsValue()
    const style = styles.find(s => s.id === styleId)
    if (!style) return
    const key = `${styleId}-${groupIndex}`
    setGeneratingGroups(prev => new Set([...prev, key]))
    addGeneratingItem(styleId)
    try {
      await stylesApi.generate(styleId, {
        group_index: groupIndex,
        style_prompt: formValues.style_prompt || style.style_prompt,
        negative_prompt: formValues.negative_prompt || style.negative_prompt,
      })
      const updated = await stylesApi.get(styleId)
      safeSetState(setStyles, (prev: Style[]) => prev.map(s => s.id === updated.id ? updated : s))
      if (selectedStyleIdRef.current === styleId) setSelectedStyle(updated)
      message.success(`第 ${groupIndex + 1} 组图片生成成功`)
    } catch (error) {
      message.error(`第 ${groupIndex + 1} 组图片生成失败`)
    } finally {
      setGeneratingGroups(prev => { const next = new Set(prev); next.delete(key); return next })
      removeGeneratingItem(styleId)
    }
  }

  const generateAllImages = async (styleId: string) => {
    if (batchGenerating) {
      message.warning('正在批量生成中，请等待完成或停止后再试')
      return
    }
    const formValues = form.getFieldsValue()
    const style = styles.find(s => s.id === styleId)
    if (!style) return
    const keys = Array.from({ length: styleGroupCount }, (_, i) => `${styleId}-${i}`)
    setGeneratingAll(true)
    setGeneratingGroups(new Set(keys))
    addGeneratingItem(styleId)
    try {
      await stylesApi.generateAll(styleId, {
        style_prompt: formValues.style_prompt || style.style_prompt,
        negative_prompt: formValues.negative_prompt || style.negative_prompt,
        group_count: styleGroupCount,
      })
      const updated = await stylesApi.get(styleId)
      safeSetState(setStyles, (prev: Style[]) => prev.map(s => s.id === updated.id ? updated : s))
      if (selectedStyleIdRef.current === styleId) setSelectedStyle(updated)
      message.success(`${styleGroupCount}组图片生成成功`)
    } catch (error) {
      message.error('图片生成失败')
    } finally {
      setGeneratingAll(false)
      setGeneratingGroups(new Set())
      removeGeneratingItem(styleId)
    }
  }

  const generateAllStylesImages = async () => {
    const imageStyles = styles.filter(s => s.style_type === 'image')
    if (imageStyles.length === 0) { message.warning('没有图片风格可生成'); return }
    shouldStopRef.current = false
    setBatchGenerating(true)
    setBatchProgress({ current: 0, total: imageStyles.length, currentName: '' })
    
    const concurrency = 3
    let successCount = 0, failCount = 0, completedCount = 0
    
    const generateOne = async (style: Style): Promise<boolean> => {
      if (shouldStopRef.current) return false
      try {
        addGeneratingItem(style.id)
        await stylesApi.generateAll(style.id, { group_count: styleGroupCount })
        const updated = await stylesApi.get(style.id)
        safeSetState(setStyles, (prev: Style[]) => prev.map(s => s.id === updated.id ? updated : s))
        return true
      } catch (error) { return false }
      finally { removeGeneratingItem(style.id) }
    }
    
    for (let i = 0; i < imageStyles.length; i += concurrency) {
      if (shouldStopRef.current) break
      const batch = imageStyles.slice(i, i + concurrency)
      safeSetState(setBatchProgress, { current: i + 1, total: imageStyles.length, currentName: batch.map(s => s.name).join(', ') })
      const results = await Promise.all(batch.map(generateOne))
      results.forEach(success => { completedCount++; if (success) successCount++; else failCount++ })
      safeSetState(setBatchProgress, { current: completedCount, total: imageStyles.length, currentName: '' })
    }
    
    safeSetState(setBatchGenerating, false)
    safeSetState(setBatchProgress, { current: 0, total: 0, currentName: '' })
    
    if (shouldStopRef.current) message.info(`已停止生成，完成 ${successCount}/${imageStyles.length} 个风格`)
    else if (failCount === 0) message.success(`成功生成所有 ${successCount} 个风格的图片`)
    else message.warning(`生成完成：${successCount} 个成功，${failCount} 个失败`)
  }

  const handleStopGeneration = () => { shouldStopRef.current = true; message.info('正在停止生成...') }

  // 选择图片风格使用哪组图片（不是全局选中，只是为该风格指定使用的图片组）
  const selectGroupForStyle = async (styleId: string, groupIndex: number) => {
    try {
      const updated = await stylesApi.update(styleId, { selected_group_index: groupIndex })
      safeSetState(setStyles, (prev: Style[]) => prev.map(s => 
        s.id === styleId ? { ...s, selected_group_index: groupIndex } : s
      ))
      if (selectedStyle?.id === styleId) setSelectedStyle({ ...selectedStyle, selected_group_index: groupIndex })
      message.success(`已选择第 ${groupIndex + 1} 组作为该风格的参考图`)
    } catch { message.error('选择失败') }
  }

  const deleteStyle = async (styleId: string) => {
    try {
      await stylesApi.delete(styleId)
      safeSetState(setStyles, (prev: Style[]) => prev.filter(s => s.id !== styleId))
      message.success('风格已删除')
    } catch { message.error('删除失败') }
  }

  const deleteAllStyles = async () => {
    if (!projectId) return
    try {
      await stylesApi.deleteAll(projectId)
      safeSetState(setStyles, [])
      message.success('已删除所有风格')
    } catch { message.error('删除失败') }
  }

  // 处理图片预设选择
  const handleImagePresetChange = (presetName: string) => {
    if (presetName && imagePresets[presetName]) {
      const preset = imagePresets[presetName]
      createForm.setFieldsValue({
        style_prompt: preset.prompt,
        negative_prompt: preset.negative_prompt,
      })
    }
  }

  // 处理文本预设选择
  const handleTextPresetChange = (presetName: string) => {
    if (presetName && textPresets[presetName]) {
      const preset = textPresets[presetName]
      createForm.setFieldValue('text_style_content', preset.content)
    }
  }

  const styleType = Form.useWatch('style_type', createForm)

  if (loading) return <div style={{ padding: 24, textAlign: 'center' }}><Spin size="large" /></div>

  const imageStyles = styles.filter(s => s.style_type === 'image')

  return (
    <div style={{ padding: 24 }}>
      <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 600, margin: 0, color: '#e0e0e0' }}>风格管理</h1>
          <p style={{ color: '#888', margin: '4px 0 0', fontSize: 13 }}>
            {currentProject?.name} - 共 {styles.length} 个风格（在角色/场景/道具模块中选择使用）
          </p>
        </div>
        <Space>
          <Button icon={<SettingOutlined />} onClick={() => setSettingsModalVisible(true)}>设置 ({styleGroupCount}组)</Button>
          {imageStyles.length > 0 && (
            <>
              {batchGenerating ? (
                <Button danger icon={<StopOutlined />} onClick={handleStopGeneration}>停止生成</Button>
              ) : (
                <Button type="primary" icon={<ThunderboltOutlined />} onClick={generateAllStylesImages}>一键生成所有图片风格</Button>
              )}
            </>
          )}
          {styles.length > 0 && (
            <Popconfirm title="确定删除所有风格？" description="此操作不可恢复" icon={<ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />} onConfirm={deleteAllStyles} okText="删除" cancelText="取消" okButtonProps={{ danger: true }}>
              <Button danger icon={<DeleteOutlined />} disabled={batchGenerating}>删除所有</Button>
            </Popconfirm>
          )}
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal} disabled={batchGenerating}>新建风格</Button>
        </Space>
      </div>

      {batchGenerating && (
        <Alert message={<div style={{ display: 'flex', alignItems: 'center', gap: 16 }}><Spin size="small" /><span>正在生成: {batchProgress.currentName || `${batchProgress.current}/${batchProgress.total}`}</span></div>}
          description={<Progress percent={batchProgress.total > 0 ? Math.round((batchProgress.current / batchProgress.total) * 100) : 0} status="active" />} type="info" style={{ marginBottom: 24 }}
          action={<Button size="small" danger onClick={handleStopGeneration}>停止</Button>} />
      )}

      {styles.length === 0 ? (
        <Empty description="暂无风格，点击新建创建" style={{ marginTop: 100 }}>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>新建风格</Button>
        </Empty>
      ) : (
        <div className="image-grid">
          {styles.map((style) => {
            const thumbnailUrl = style.style_type === 'image' ? style.image_groups?.[style.selected_group_index]?.url : null
            const isGeneratingThis = isItemGenerating(style.id)
            return (
              <div key={style.id} className="asset-card" onClick={() => openStyleModal(style)} style={{ opacity: isGeneratingThis ? 0.7 : 1 }}>
                <div className="asset-card-image" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative' }}>
                  {style.style_type === 'image' ? (
                    thumbnailUrl ? <Image src={thumbnailUrl} alt={style.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} preview={false} /> : <PictureOutlined style={{ fontSize: 48, color: '#444' }} />
                  ) : (
                    <FileTextOutlined style={{ fontSize: 48, color: '#666' }} />
                  )}
                  {isGeneratingThis && <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Spin /></div>}
                  <div style={{ position: 'absolute', top: 8, left: 8 }}>
                    <Tag color={style.style_type === 'image' ? 'blue' : 'purple'}>
                      {style.style_type === 'image' ? '图片' : '文本'}
                    </Tag>
                  </div>
                </div>
                <div className="asset-card-info">
                  <div className="asset-card-name">{style.name}</div>
                  <div className="asset-card-desc">
                    {style.style_type === 'image' 
                      ? (style.preset_name ? imagePresets[style.preset_name]?.name : '自定义') 
                      : (style.text_preset_name ? textPresets[style.text_preset_name]?.name : '自定义')}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* 新建风格弹窗 */}
      <Modal title="新建风格" open={isCreateModalOpen} onOk={createStyle} onCancel={() => setIsCreateModalOpen(false)} okText="创建" cancelText="取消" width={700}>
        <Form form={createForm} layout="vertical" initialValues={{ style_type: 'image' }}>
          <Form.Item name="name" label="风格名称" rules={[{ required: true, message: '请输入风格名称' }]}>
            <Input placeholder="例如：赛博朋克风格" />
          </Form.Item>
          <Form.Item name="style_type" label="风格类型">
            <Radio.Group>
              <Radio.Button value="image"><PictureOutlined /> 图片风格</Radio.Button>
              <Radio.Button value="text"><FileTextOutlined /> 纯文本风格</Radio.Button>
            </Radio.Group>
          </Form.Item>
          
          {styleType === 'image' ? (
            <>
              <Form.Item name="preset_name" label="预设风格">
                <Select 
                  placeholder="选择预设风格（可选）" 
                  allowClear
                  onChange={handleImagePresetChange}
                  options={Object.entries(imagePresets).map(([key, preset]) => ({
                    label: preset.name,
                    value: key
                  }))}
                />
              </Form.Item>
              <Form.Item name="style_prompt" label="风格提示词" extra="描述风格特征，会用于生成风格参考图">
                <TextArea rows={4} placeholder="详细描述风格特征，包含角色、场景、道具等元素..." />
              </Form.Item>
              <Form.Item name="negative_prompt" label="负向提示词" extra="指定不希望出现的元素">
                <TextArea rows={2} placeholder="例如：blurry, low quality, watermark" />
              </Form.Item>
            </>
          ) : (
            <>
              <Form.Item name="text_preset_name" label="预设风格">
                <Select 
                  placeholder="选择预设风格（可选）" 
                  allowClear
                  onChange={handleTextPresetChange}
                  options={Object.entries(textPresets).map(([key, preset]) => ({
                    label: preset.name,
                    value: key
                  }))}
                />
              </Form.Item>
              <Form.Item name="text_style_content" label="风格描述 (JSON格式)" extra="使用JSON格式详细描述风格的各个方面">
                <TextArea rows={12} placeholder='{"style_definition": {...}, "subject_treatment": {...}, ...}' style={{ fontFamily: 'monospace' }} />
              </Form.Item>
            </>
          )}
        </Form>
      </Modal>

      {/* 编辑风格弹窗 */}
      <Modal title={`编辑风格 - ${selectedStyle?.name}`} open={isModalOpen} onOk={saveStyle} onCancel={() => { setIsModalOpen(false); selectedStyleIdRef.current = null }} width={1000} okText="保存" cancelText="取消">
        {selectedStyle && (
          <div style={{ display: 'flex', gap: 24 }}>
            {selectedStyle.style_type === 'image' ? (
              /* 图片风格编辑 */
              <>
                <div style={{ width: 400 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                    <h4 style={{ margin: 0 }}>风格参考图</h4>
                    <Button type="primary" icon={<ThunderboltOutlined />} onClick={() => generateAllImages(selectedStyle.id)} loading={generatingAll} disabled={generatingGroups.size > 0 || batchGenerating}>一键生成{styleGroupCount}组</Button>
                  </div>
                  {Array.from({ length: Math.max(styleGroupCount, selectedStyle.image_groups?.length || 0) }, (_, groupIndex) => {
                    const group = selectedStyle.image_groups?.[groupIndex]
                    const isCurrentGroup = selectedStyle.selected_group_index === groupIndex
                    const key = `${selectedStyle.id}-${groupIndex}`
                    const isGeneratingThis = generatingGroups.has(key)
                    return (
                      <div key={groupIndex} style={{ marginBottom: 12, padding: 12, border: isCurrentGroup ? '2px solid #e5a84b' : '1px solid #333', borderRadius: 8, background: isCurrentGroup ? 'rgba(229, 168, 75, 0.1)' : '#1a1a1a' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                          <Space>
                            <Radio checked={isCurrentGroup} onChange={() => selectGroupForStyle(selectedStyle.id, groupIndex)}>第 {groupIndex + 1} 组</Radio>
                            {isCurrentGroup && <Tag color="gold">当前使用</Tag>}
                          </Space>
                          <Button size="small" icon={<ReloadOutlined />} onClick={() => generateImages(selectedStyle.id, groupIndex)} loading={isGeneratingThis} disabled={generatingAll || (generatingGroups.size > 0 && !isGeneratingThis) || batchGenerating}>{group?.url ? '重新生成' : '生成'}</Button>
                        </div>
                        <div style={{ aspectRatio: '16/9', background: '#242424', borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                          {isGeneratingThis ? <Spin /> : group?.url ? <Image src={group.url} alt="风格" style={{ width: '100%', height: '100%', objectFit: 'cover' }} /> : <PictureOutlined style={{ fontSize: 32, color: '#444' }} />}
                        </div>
                      </div>
                    )
                  })}
                </div>
                <div style={{ flex: 1 }}>
                  <Form form={form} layout="vertical">
                    <Form.Item name="name" label="风格名称" rules={[{ required: true }]}><Input /></Form.Item>
                    <Form.Item name="description" label="风格描述"><TextArea rows={2} /></Form.Item>
                    <Form.Item name="style_prompt" label="风格提示词"><TextArea rows={4} /></Form.Item>
                    <Form.Item name="negative_prompt" label="负向提示词"><TextArea rows={2} /></Form.Item>
                  </Form>
                  <div style={{ marginTop: 16, textAlign: 'right' }}>
                    <Popconfirm title="确定删除此风格？" onConfirm={() => { deleteStyle(selectedStyle.id); setIsModalOpen(false) }} okText="删除" cancelText="取消" okButtonProps={{ danger: true }}>
                      <Button danger icon={<DeleteOutlined />}>删除风格</Button>
                    </Popconfirm>
                  </div>
                </div>
              </>
            ) : (
              /* 文本风格编辑 */
              <div style={{ flex: 1 }}>
                <Form form={form} layout="vertical">
                  <Form.Item name="name" label="风格名称" rules={[{ required: true }]}><Input /></Form.Item>
                  <Form.Item name="description" label="风格描述"><TextArea rows={2} /></Form.Item>
                  <Form.Item 
                    name="text_style_content" 
                    label={
                      <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
                        <span>风格描述 (JSON格式)</span>
                        <Space>
                          <Button size="small" icon={<HistoryOutlined />} onClick={() => setVersionModalVisible(true)}>
                            版本历史 ({selectedStyle.text_style_versions?.length || 0})
                          </Button>
                          <Button size="small" type="primary" icon={<SaveOutlined />} onClick={openSaveVersionModal}>
                            保存版本
                          </Button>
                        </Space>
                      </div>
                    }
                  >
                    <TextArea rows={16} style={{ fontFamily: 'monospace' }} />
                  </Form.Item>
                </Form>
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 16 }}>
                  <Popconfirm title="确定删除此风格？" onConfirm={() => { deleteStyle(selectedStyle.id); setIsModalOpen(false) }} okText="删除" cancelText="取消" okButtonProps={{ danger: true }}>
                    <Button danger icon={<DeleteOutlined />}>删除风格</Button>
                  </Popconfirm>
                </div>
              </div>
            )}
          </div>
        )}
      </Modal>

      {/* 版本历史弹窗 */}
      <Modal title="版本历史" open={versionModalVisible} onCancel={() => setVersionModalVisible(false)} footer={null} width={600}>
        {selectedStyle?.text_style_versions && selectedStyle.text_style_versions.length > 0 ? (
          <List
            dataSource={selectedStyle.text_style_versions}
            renderItem={(version: TextStyleVersion) => (
              <List.Item
                actions={[
                  <Button type="link" onClick={() => loadTextVersion(version)}>加载</Button>
                ]}
              >
                <List.Item.Meta
                  title={version.name}
                  description={
                    <>
                      <div>保存时间: {new Date(version.created_at).toLocaleString()}</div>
                      {version.modified_info && <div>修改说明: {version.modified_info}</div>}
                    </>
                  }
                />
              </List.Item>
            )}
          />
        ) : (
          <Empty description="暂无版本历史" />
        )}
      </Modal>

      {/* 保存版本弹窗 */}
      <Modal title="保存版本" open={saveVersionModalVisible} onOk={saveTextVersion} onCancel={() => setSaveVersionModalVisible(false)} okText="保存" cancelText="取消">
        <Form form={saveVersionForm} layout="vertical">
          <Form.Item name="version_name" label="版本名称" rules={[{ required: true, message: '请输入版本名称' }]}>
            <Input placeholder="例如：初版，优化后" />
          </Form.Item>
          <Form.Item name="modified_info" label="修改说明">
            <TextArea rows={2} placeholder="描述本次修改的内容" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 设置弹窗 */}
      <Modal title="生成设置" open={settingsModalVisible} onCancel={() => setSettingsModalVisible(false)} onOk={() => setSettingsModalVisible(false)} okText="确定" cancelText="取消">
        <Form layout="vertical">
          <Form.Item label="每个图片风格生成组数" extra="生成图片时，每个图片风格将生成指定组数的参考图">
            <InputNumber min={1} max={10} value={styleGroupCount} onChange={(v) => setStyleGroupCount(v || 3)} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default StylesPage
