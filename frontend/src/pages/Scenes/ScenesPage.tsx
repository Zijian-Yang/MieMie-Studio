import { useEffect, useState, useRef, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { 
  Button, Modal, Form, Input, Empty, Spin, message, 
  Radio, Tooltip, Space, Popconfirm, Image, Alert, Progress,
  InputNumber, Switch, Select, Tag, Card
} from 'antd'
import { 
  PlusOutlined, ReloadOutlined, DeleteOutlined, 
  PictureOutlined, ThunderboltOutlined, SettingOutlined,
  ExclamationCircleOutlined, StopOutlined, BgColorsOutlined
} from '@ant-design/icons'
import { scenesApi, Scene, stylesApi, Style } from '../../services/api'
import { useProjectStore } from '../../stores/projectStore'
import { useGenerationStore } from '../../stores/generationStore'

const { TextArea } = Input

const ScenesPage = () => {
  const { projectId } = useParams<{ projectId: string }>()
  const { currentProject, fetchProject } = useProjectStore()
  const { 
    sceneGroupCount, 
    setSceneGroupCount,
    sceneUseStyle,
    setSceneUseStyle,
    sceneSelectedStyleId,
    setSceneSelectedStyleId,
    addGeneratingItem,
    removeGeneratingItem,
    isItemGenerating,
  } = useGenerationStore()
  
  const [scenes, setScenes] = useState<Scene[]>([])
  const [loading, setLoading] = useState(true)
  const [extracting, setExtracting] = useState(false)
  const [selectedScene, setSelectedScene] = useState<Scene | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [generatingGroups, setGeneratingGroups] = useState<Set<string>>(new Set())
  const [generatingAll, setGeneratingAll] = useState(false)
  const [form] = Form.useForm()
  
  const [batchGenerating, setBatchGenerating] = useState(false)
  const [batchProgress, setBatchProgress] = useState({ current: 0, total: 0, currentName: '' })
  const [settingsModalVisible, setSettingsModalVisible] = useState(false)
  
  // 风格相关
  const [styles, setStyles] = useState<Style[]>([])
  const [localUseStyle, setLocalUseStyle] = useState<boolean | null>(null)
  const [localStyleId, setLocalStyleId] = useState<string | null>(null)
  
  const selectedSceneIdRef = useRef<string | null>(null)
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
        const [scenesRes, stylesRes] = await Promise.all([
          scenesApi.list(projectId),
          stylesApi.list(projectId)
        ])
        safeSetState(setScenes, scenesRes.scenes)
        safeSetState(setStyles, stylesRes.styles)
      } catch (error) {
        message.error('加载失败')
      } finally {
        safeSetState(setLoading, false)
      }
    }
    loadData()
  }, [projectId, fetchProject, safeSetState])

  const extractScenes = async () => {
    if (!projectId) return
    if (!currentProject?.script?.processed_content && !currentProject?.script?.original_content) {
      message.warning('请先保存剧本')
      return
    }
    safeSetState(setExtracting, true)
    try {
      const { scenes: newScenes } = await scenesApi.extract(projectId)
      safeSetState(setScenes, (prev: Scene[]) => [...prev, ...newScenes])
      message.success(`成功提取 ${newScenes.length} 个场景`)
    } catch (error) {
      message.error('提取失败')
    } finally {
      safeSetState(setExtracting, false)
    }
  }

  const openSceneModal = (scene: Scene) => {
    setSelectedScene(scene)
    selectedSceneIdRef.current = scene.id
    form.setFieldsValue({
      name: scene.name,
      description: scene.description,
      common_prompt: scene.common_prompt,
      scene_prompt: scene.scene_prompt,
      negative_prompt: scene.negative_prompt || '',
    })
    // 重置详情页风格设置
    setLocalUseStyle(null)
    setLocalStyleId(null)
    setIsModalOpen(true)
  }

  // 获取当前有效的风格设置
  const getEffectiveStyleSettings = () => {
    const useStyle = localUseStyle !== null ? localUseStyle : sceneUseStyle
    const styleId = localStyleId !== null ? localStyleId : sceneSelectedStyleId
    return { useStyle, styleId }
  }

  const getSelectedStyle = () => {
    const { styleId } = getEffectiveStyleSettings()
    return styles.find(s => s.id === styleId)
  }

  const saveScene = async () => {
    if (!selectedScene) return
    try {
      const values = await form.validateFields()
      const updated = await scenesApi.update(selectedScene.id, values)
      safeSetState(setScenes, (prev: Scene[]) => prev.map(s => s.id === updated.id ? updated : s))
      setIsModalOpen(false)
      message.success('场景已保存')
    } catch (error) {
      message.error('保存失败')
    }
  }

  const generateImages = async (sceneId: string, groupIndex: number) => {
    if (batchGenerating) {
      message.warning('正在批量生成中，请等待完成或停止后再试')
      return
    }
    const formValues = form.getFieldsValue()
    const scene = scenes.find(s => s.id === sceneId)
    if (!scene) return
    const key = `${sceneId}-${groupIndex}`
    setGeneratingGroups(prev => new Set([...prev, key]))
    addGeneratingItem(sceneId)
    
    const { useStyle, styleId } = getEffectiveStyleSettings()
    
    try {
      await scenesApi.generate(sceneId, {
        group_index: groupIndex,
        common_prompt: formValues.common_prompt || scene.common_prompt,
        scene_prompt: formValues.scene_prompt || scene.scene_prompt,
        negative_prompt: formValues.negative_prompt || scene.negative_prompt,
        use_style: useStyle,
        style_id: styleId || undefined,
      })
      const updated = await scenesApi.get(sceneId)
      safeSetState(setScenes, (prev: Scene[]) => prev.map(s => s.id === updated.id ? updated : s))
      if (selectedSceneIdRef.current === sceneId) setSelectedScene(updated)
      message.success(`第 ${groupIndex + 1} 组图片生成成功`)
    } catch (error) {
      message.error(`第 ${groupIndex + 1} 组图片生成失败`)
    } finally {
      setGeneratingGroups(prev => { const next = new Set(prev); next.delete(key); return next })
      removeGeneratingItem(sceneId)
    }
  }

  const generateAllImages = async (sceneId: string) => {
    if (batchGenerating) {
      message.warning('正在批量生成中，请等待完成或停止后再试')
      return
    }
    const formValues = form.getFieldsValue()
    const scene = scenes.find(s => s.id === sceneId)
    if (!scene) return
    const keys = Array.from({ length: sceneGroupCount }, (_, i) => `${sceneId}-${i}`)
    setGeneratingAll(true)
    setGeneratingGroups(new Set(keys))
    addGeneratingItem(sceneId)
    
    const { useStyle, styleId } = getEffectiveStyleSettings()
    
    try {
      await scenesApi.generateAll(sceneId, {
        common_prompt: formValues.common_prompt || scene.common_prompt,
        scene_prompt: formValues.scene_prompt || scene.scene_prompt,
        negative_prompt: formValues.negative_prompt || scene.negative_prompt,
        group_count: sceneGroupCount,
        use_style: useStyle,
        style_id: styleId || undefined,
      })
      const updated = await scenesApi.get(sceneId)
      safeSetState(setScenes, (prev: Scene[]) => prev.map(s => s.id === updated.id ? updated : s))
      if (selectedSceneIdRef.current === sceneId) setSelectedScene(updated)
      message.success(`${sceneGroupCount}组图片生成成功`)
    } catch (error) {
      message.error('图片生成失败')
    } finally {
      setGeneratingAll(false)
      setGeneratingGroups(new Set())
      removeGeneratingItem(sceneId)
    }
  }

  const generateAllScenesImages = async () => {
    if (scenes.length === 0) { message.warning('没有场景可生成'); return }
    shouldStopRef.current = false
    setBatchGenerating(true)
    setBatchProgress({ current: 0, total: scenes.length, currentName: '' })
    
    const concurrency = 3
    let successCount = 0, failCount = 0, completedCount = 0
    
    const generateOne = async (scene: Scene): Promise<boolean> => {
      if (shouldStopRef.current) return false
      try {
        addGeneratingItem(scene.id)
        await scenesApi.generateAll(scene.id, { 
          group_count: sceneGroupCount,
          use_style: sceneUseStyle,
          style_id: sceneSelectedStyleId || undefined,
        })
        const updated = await scenesApi.get(scene.id)
        safeSetState(setScenes, (prev: Scene[]) => prev.map(s => s.id === updated.id ? updated : s))
        return true
      } catch (error) { return false }
      finally { removeGeneratingItem(scene.id) }
    }
    
    for (let i = 0; i < scenes.length; i += concurrency) {
      if (shouldStopRef.current) break
      const batch = scenes.slice(i, i + concurrency)
      safeSetState(setBatchProgress, { current: i + 1, total: scenes.length, currentName: batch.map(s => s.name).join(', ') })
      const results = await Promise.all(batch.map(generateOne))
      results.forEach(success => { completedCount++; if (success) successCount++; else failCount++ })
      safeSetState(setBatchProgress, { current: completedCount, total: scenes.length, currentName: '' })
    }
    
    safeSetState(setBatchGenerating, false)
    safeSetState(setBatchProgress, { current: 0, total: 0, currentName: '' })
    
    if (shouldStopRef.current) message.info(`已停止生成，完成 ${successCount}/${scenes.length} 个场景`)
    else if (failCount === 0) message.success(`成功生成所有 ${successCount} 个场景的图片`)
    else message.warning(`生成完成：${successCount} 个成功，${failCount} 个失败`)
  }

  const handleStopGeneration = () => { shouldStopRef.current = true; message.info('正在停止生成...') }

  const selectGroup = async (sceneId: string, groupIndex: number) => {
    try {
      const updated = await scenesApi.update(sceneId, { selected_group_index: groupIndex })
      safeSetState(setScenes, (prev: Scene[]) => prev.map(s => s.id === updated.id ? updated : s))
      if (selectedScene?.id === sceneId) setSelectedScene(updated)
    } catch { message.error('选择失败') }
  }

  const deleteScene = async (sceneId: string) => {
    try {
      await scenesApi.delete(sceneId)
      safeSetState(setScenes, (prev: Scene[]) => prev.filter(s => s.id !== sceneId))
      message.success('场景已删除')
    } catch { message.error('删除失败') }
  }

  const deleteAllScenes = async () => {
    if (!projectId) return
    try {
      await scenesApi.deleteAll(projectId)
      safeSetState(setScenes, [])
      message.success('已删除所有场景')
    } catch { message.error('删除失败') }
  }

  if (loading) return <div style={{ padding: 24, textAlign: 'center' }}><Spin size="large" /></div>

  return (
    <div style={{ padding: 24 }}>
      <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 600, margin: 0, color: '#e0e0e0' }}>场景管理</h1>
          <p style={{ color: '#888', margin: '4px 0 0', fontSize: 13 }}>
            {currentProject?.name} - 共 {scenes.length} 个场景
            {sceneUseStyle && sceneSelectedStyleId && (
              <Tag color="blue" style={{ marginLeft: 8 }}>
                <BgColorsOutlined /> 风格参考: {styles.find(s => s.id === sceneSelectedStyleId)?.name || '未知'}
              </Tag>
            )}
          </p>
        </div>
        <Space>
          <Button icon={<SettingOutlined />} onClick={() => setSettingsModalVisible(true)}>设置 ({sceneGroupCount}组)</Button>
          {scenes.length > 0 && (
            <>
              {batchGenerating ? (
                <Button danger icon={<StopOutlined />} onClick={handleStopGeneration}>停止生成</Button>
              ) : (
                <Button type="primary" icon={<ThunderboltOutlined />} onClick={generateAllScenesImages} disabled={extracting}>一键生成所有场景</Button>
              )}
              <Popconfirm title="确定删除所有场景？" description="此操作不可恢复" icon={<ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />} onConfirm={deleteAllScenes} okText="删除" cancelText="取消" okButtonProps={{ danger: true }}>
                <Button danger icon={<DeleteOutlined />} disabled={batchGenerating}>删除所有</Button>
              </Popconfirm>
            </>
          )}
          <Button type="primary" icon={<PlusOutlined />} onClick={extractScenes} loading={extracting} disabled={batchGenerating}>从剧本提取场景</Button>
        </Space>
      </div>

      {batchGenerating && (
        <Alert message={<div style={{ display: 'flex', alignItems: 'center', gap: 16 }}><Spin size="small" /><span>正在生成: {batchProgress.currentName || `${batchProgress.current}/${batchProgress.total}`}</span></div>}
          description={<Progress percent={batchProgress.total > 0 ? Math.round((batchProgress.current / batchProgress.total) * 100) : 0} status="active" />} type="info" style={{ marginBottom: 24 }}
          action={<Button size="small" danger onClick={handleStopGeneration}>停止</Button>} />
      )}

      {scenes.length === 0 ? (
        <Empty description="暂无场景，请从剧本提取" style={{ marginTop: 100 }}><Button type="primary" onClick={extractScenes} loading={extracting}>提取场景</Button></Empty>
      ) : (
        <div className="image-grid">
          {scenes.map((scene) => {
            const thumbnailUrl = scene.image_groups?.[scene.selected_group_index]?.url
            const isGeneratingThis = isItemGenerating(scene.id)
            return (
              <div key={scene.id} className="asset-card" onClick={() => openSceneModal(scene)} style={{ opacity: isGeneratingThis ? 0.7 : 1 }}>
                <div className="asset-card-image" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative' }}>
                  {thumbnailUrl ? <Image src={thumbnailUrl} alt={scene.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} preview={false} /> : <PictureOutlined style={{ fontSize: 48, color: '#444' }} />}
                  {isGeneratingThis && <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Spin /></div>}
                </div>
                <div className="asset-card-info"><div className="asset-card-name">{scene.name}</div><div className="asset-card-desc">{scene.description || '暂无描述'}</div></div>
              </div>
            )
          })}
        </div>
      )}

      <Modal title={`编辑场景 - ${selectedScene?.name}`} open={isModalOpen} onOk={saveScene} onCancel={() => { setIsModalOpen(false); selectedSceneIdRef.current = null }} width={900} okText="保存" cancelText="取消">
        {selectedScene && (
          <div style={{ display: 'flex', gap: 24 }}>
            <div style={{ width: 360 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <h4 style={{ margin: 0 }}>场景图片</h4>
                <Button type="primary" icon={<ThunderboltOutlined />} onClick={() => generateAllImages(selectedScene.id)} loading={generatingAll} disabled={generatingGroups.size > 0 || batchGenerating}>一键生成{sceneGroupCount}组</Button>
              </div>
              {Array.from({ length: Math.max(sceneGroupCount, selectedScene.image_groups?.length || 0) }, (_, groupIndex) => {
                const group = selectedScene.image_groups?.[groupIndex]
                const isSelected = selectedScene.selected_group_index === groupIndex
                const key = `${selectedScene.id}-${groupIndex}`
                const isGeneratingThis = generatingGroups.has(key)
                return (
                  <div key={groupIndex} style={{ marginBottom: 12, padding: 12, border: isSelected ? '2px solid #e5a84b' : '1px solid #333', borderRadius: 8, background: isSelected ? 'rgba(229, 168, 75, 0.1)' : '#1a1a1a' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <Radio checked={isSelected} onChange={() => selectGroup(selectedScene.id, groupIndex)}>第 {groupIndex + 1} 组</Radio>
                      <Button size="small" icon={<ReloadOutlined />} onClick={() => generateImages(selectedScene.id, groupIndex)} loading={isGeneratingThis} disabled={generatingAll || (generatingGroups.size > 0 && !isGeneratingThis) || batchGenerating}>{group?.url ? '重新生成' : '生成'}</Button>
                    </div>
                    <div style={{ aspectRatio: '16/9', background: '#242424', borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      {isGeneratingThis ? <Spin /> : group?.url ? <Image src={group.url} alt="场景" style={{ width: '100%', height: '100%', objectFit: 'cover' }} /> : <PictureOutlined style={{ fontSize: 32, color: '#444' }} />}
                    </div>
                  </div>
                )
              })}
            </div>
            <div style={{ flex: 1 }}>
              <Form form={form} layout="vertical">
                <Form.Item name="name" label="场景名称" rules={[{ required: true }]}><Input /></Form.Item>
                <Form.Item name="description" label="场景描述（说明用）"><TextArea rows={2} placeholder="用于说明，不参与生图" /></Form.Item>
                <Form.Item name="common_prompt" label="通用提示词"><TextArea rows={2} /></Form.Item>
                <Form.Item name="scene_prompt" label="场景提示词（用于生图）"><TextArea rows={2} placeholder="描述场景环境，不要包含角色和道具" /></Form.Item>
                <Form.Item name="negative_prompt" label={<Space>负向提示词<Tooltip title="用于指定图片中不希望出现的元素"><span style={{ color: '#888', fontSize: 12 }}>(?)</span></Tooltip></Space>} extra="指定不希望出现在生成图片中的元素">
                  <TextArea rows={2} placeholder="例如：人物, 文字, 水印, 模糊" />
                </Form.Item>
              </Form>
              
              {/* 风格参考设置 */}
              <Card 
                size="small" 
                title={
                  <Space>
                    <BgColorsOutlined />
                    风格参考（当前场景）
                    {localUseStyle === null && sceneUseStyle && (
                      <Tag color="blue">使用全局设置</Tag>
                    )}
                  </Space>
                }
                style={{ marginTop: 16 }}
              >
                <Space direction="vertical" style={{ width: '100%' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Switch 
                      checked={localUseStyle !== null ? localUseStyle : sceneUseStyle}
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
                  {(localUseStyle !== null ? localUseStyle : sceneUseStyle) && (
                    <Select
                      placeholder="选择风格"
                      value={localStyleId !== null ? localStyleId : sceneSelectedStyleId}
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
              
              <div style={{ marginTop: 16, textAlign: 'right' }}>
                <Popconfirm title="确定删除此场景？" onConfirm={() => { deleteScene(selectedScene.id); setIsModalOpen(false) }} okText="删除" cancelText="取消" okButtonProps={{ danger: true }}>
                  <Button danger icon={<DeleteOutlined />}>删除场景</Button>
                </Popconfirm>
              </div>
            </div>
          </div>
        )}
      </Modal>

      <Modal title="生成设置" open={settingsModalVisible} onCancel={() => setSettingsModalVisible(false)} onOk={() => setSettingsModalVisible(false)} okText="确定" cancelText="取消">
        <Form layout="vertical">
          <Form.Item label="每个场景生成组数" extra="生成图片时，每个场景将生成指定组数的图片">
            <InputNumber min={1} max={10} value={sceneGroupCount} onChange={(v) => setSceneGroupCount(v || 3)} style={{ width: '100%' }} />
          </Form.Item>
          
          <Form.Item 
            label={
              <Space>
                <BgColorsOutlined />
                风格参考（全局）
              </Space>
            }
            extra="开启后将使用选定的风格生成场景图片"
          >
            <Space direction="vertical" style={{ width: '100%' }}>
              <Switch 
                checked={sceneUseStyle}
                onChange={setSceneUseStyle}
                checkedChildren="开启"
                unCheckedChildren="关闭"
              />
              {sceneUseStyle && (
                <Select
                  placeholder="选择风格"
                  value={sceneSelectedStyleId}
                  onChange={setSceneSelectedStyleId}
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
    </div>
  )
}

export default ScenesPage
