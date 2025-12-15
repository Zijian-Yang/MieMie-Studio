import { useEffect, useState, useRef, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { 
  Button, Modal, Form, Input, Empty, Spin, message, 
  Radio, Tooltip, Space, Popconfirm, Image, Alert, Progress,
  InputNumber, Switch, Select, Tag, Card
} from 'antd'
import { 
  PlusOutlined, ReloadOutlined, DeleteOutlined, 
  AppstoreOutlined, ThunderboltOutlined, SettingOutlined,
  ExclamationCircleOutlined, StopOutlined, BgColorsOutlined
} from '@ant-design/icons'
import { propsApi, Prop, stylesApi, Style } from '../../services/api'
import { useProjectStore } from '../../stores/projectStore'
import { useGenerationStore } from '../../stores/generationStore'

const { TextArea } = Input

const PropsPage = () => {
  const { projectId } = useParams<{ projectId: string }>()
  const { currentProject, fetchProject } = useProjectStore()
  const { 
    propGroupCount, 
    setPropGroupCount,
    propUseStyle,
    setPropUseStyle,
    propSelectedStyleId,
    setPropSelectedStyleId,
    addGeneratingItem,
    removeGeneratingItem,
    isItemGenerating,
  } = useGenerationStore()
  
  const [props, setProps] = useState<Prop[]>([])
  const [loading, setLoading] = useState(true)
  const [extracting, setExtracting] = useState(false)
  const [selectedProp, setSelectedProp] = useState<Prop | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [generatingGroups, setGeneratingGroups] = useState<Set<string>>(new Set())
  const [generatingAll, setGeneratingAll] = useState(false)
  const [form] = Form.useForm()
  
  const [batchGenerating, setBatchGenerating] = useState(false)
  const [batchProgress, setBatchProgress] = useState({ current: 0, total: 0, currentName: '' })
  const [settingsModalVisible, setSettingsModalVisible] = useState(false)
  // 新建道具弹窗
  const [createModalVisible, setCreateModalVisible] = useState(false)
  const [createForm] = Form.useForm()
  
  // 风格相关
  const [styles, setStyles] = useState<Style[]>([])
  const [localUseStyle, setLocalUseStyle] = useState<boolean | null>(null)
  const [localStyleId, setLocalStyleId] = useState<string | null>(null)
  
  const selectedPropIdRef = useRef<string | null>(null)
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
        const [propsRes, stylesRes] = await Promise.all([
          propsApi.list(projectId),
          stylesApi.list(projectId)
        ])
        safeSetState(setProps, propsRes.props)
        safeSetState(setStyles, stylesRes.styles)
      } catch (error) {
        message.error('加载失败')
      } finally {
        safeSetState(setLoading, false)
      }
    }
    loadData()
  }, [projectId, fetchProject, safeSetState])

  const extractProps = async () => {
    if (!projectId) return
    if (!currentProject?.script?.processed_content && !currentProject?.script?.original_content) {
      message.warning('请先保存剧本')
      return
    }
    safeSetState(setExtracting, true)
    try {
      const { props: newProps } = await propsApi.extract(projectId)
      safeSetState(setProps, (prev: Prop[]) => [...prev, ...newProps])
      message.success(`成功提取 ${newProps.length} 个道具`)
    } catch (error) {
      message.error('提取失败')
    } finally {
      safeSetState(setExtracting, false)
    }
  }

  // 手动创建道具
  const createProp = async () => {
    if (!projectId) return
    try {
      const values = await createForm.validateFields()
      const { prop } = await propsApi.create({
        project_id: projectId,
        name: values.name,
        description: values.description || '',
        prop_prompt: values.prop_prompt || '',
      })
      safeSetState(setProps, (prev: Prop[]) => [...prev, prop])
      setCreateModalVisible(false)
      createForm.resetFields()
      message.success('道具已创建')
      openPropModal(prop)
    } catch (error) {
      message.error('创建失败')
    }
  }

  const openPropModal = (prop: Prop) => {
    setSelectedProp(prop)
    selectedPropIdRef.current = prop.id
    form.setFieldsValue({
      name: prop.name,
      description: prop.description,
      common_prompt: prop.common_prompt,
      prop_prompt: prop.prop_prompt,
      negative_prompt: prop.negative_prompt || '',
    })
    // 重置详情页风格设置
    setLocalUseStyle(null)
    setLocalStyleId(null)
    setIsModalOpen(true)
  }

  // 获取当前有效的风格设置
  const getEffectiveStyleSettings = () => {
    const useStyle = localUseStyle !== null ? localUseStyle : propUseStyle
    const styleId = localStyleId !== null ? localStyleId : propSelectedStyleId
    return { useStyle, styleId }
  }

  const getSelectedStyle = () => {
    const { styleId } = getEffectiveStyleSettings()
    return styles.find(s => s.id === styleId)
  }

  const saveProp = async () => {
    if (!selectedProp) return
    try {
      const values = await form.validateFields()
      const updated = await propsApi.update(selectedProp.id, values)
      safeSetState(setProps, (prev: Prop[]) => prev.map(p => p.id === updated.id ? updated : p))
      setIsModalOpen(false)
      message.success('道具已保存')
    } catch (error) {
      message.error('保存失败')
    }
  }

  const generateImages = async (propId: string, groupIndex: number) => {
    if (batchGenerating) {
      message.warning('正在批量生成中，请等待完成或停止后再试')
      return
    }
    const formValues = form.getFieldsValue()
    const prop = props.find(p => p.id === propId)
    if (!prop) return
    const key = `${propId}-${groupIndex}`
    setGeneratingGroups(prev => new Set([...prev, key]))
    addGeneratingItem(propId)
    
    const { useStyle, styleId } = getEffectiveStyleSettings()
    
    try {
      await propsApi.generate(propId, {
        group_index: groupIndex,
        common_prompt: formValues.common_prompt || prop.common_prompt,
        prop_prompt: formValues.prop_prompt || prop.prop_prompt,
        negative_prompt: formValues.negative_prompt || prop.negative_prompt,
        use_style: useStyle,
        style_id: styleId || undefined,
      })
      const updated = await propsApi.get(propId)
      safeSetState(setProps, (prev: Prop[]) => prev.map(p => p.id === updated.id ? updated : p))
      if (selectedPropIdRef.current === propId) setSelectedProp(updated)
      message.success(`第 ${groupIndex + 1} 组图片生成成功`)
    } catch (error) {
      message.error(`第 ${groupIndex + 1} 组图片生成失败`)
    } finally {
      setGeneratingGroups(prev => { const next = new Set(prev); next.delete(key); return next })
      removeGeneratingItem(propId)
    }
  }

  const generateAllImages = async (propId: string) => {
    if (batchGenerating) {
      message.warning('正在批量生成中，请等待完成或停止后再试')
      return
    }
    const formValues = form.getFieldsValue()
    const prop = props.find(p => p.id === propId)
    if (!prop) return
    const keys = Array.from({ length: propGroupCount }, (_, i) => `${propId}-${i}`)
    setGeneratingAll(true)
    setGeneratingGroups(new Set(keys))
    addGeneratingItem(propId)
    
    const { useStyle, styleId } = getEffectiveStyleSettings()
    
    try {
      await propsApi.generateAll(propId, {
        common_prompt: formValues.common_prompt || prop.common_prompt,
        prop_prompt: formValues.prop_prompt || prop.prop_prompt,
        negative_prompt: formValues.negative_prompt || prop.negative_prompt,
        group_count: propGroupCount,
        use_style: useStyle,
        style_id: styleId || undefined,
      })
      const updated = await propsApi.get(propId)
      safeSetState(setProps, (prev: Prop[]) => prev.map(p => p.id === updated.id ? updated : p))
      if (selectedPropIdRef.current === propId) setSelectedProp(updated)
      message.success(`${propGroupCount}组图片生成成功`)
    } catch (error) {
      message.error('图片生成失败')
    } finally {
      setGeneratingAll(false)
      setGeneratingGroups(new Set())
      removeGeneratingItem(propId)
    }
  }

  const generateAllPropsImages = async () => {
    if (props.length === 0) { message.warning('没有道具可生成'); return }
    shouldStopRef.current = false
    setBatchGenerating(true)
    setBatchProgress({ current: 0, total: props.length, currentName: '' })
    
    const concurrency = 3
    let successCount = 0, failCount = 0, completedCount = 0
    
    const generateOne = async (prop: Prop): Promise<boolean> => {
      if (shouldStopRef.current) return false
      try {
        addGeneratingItem(prop.id)
        await propsApi.generateAll(prop.id, { 
          group_count: propGroupCount,
          use_style: propUseStyle,
          style_id: propSelectedStyleId || undefined,
        })
        const updated = await propsApi.get(prop.id)
        safeSetState(setProps, (prev: Prop[]) => prev.map(p => p.id === updated.id ? updated : p))
        return true
      } catch (error) { return false }
      finally { removeGeneratingItem(prop.id) }
    }
    
    for (let i = 0; i < props.length; i += concurrency) {
      if (shouldStopRef.current) break
      const batch = props.slice(i, i + concurrency)
      safeSetState(setBatchProgress, { current: i + 1, total: props.length, currentName: batch.map(p => p.name).join(', ') })
      const results = await Promise.all(batch.map(generateOne))
      results.forEach(success => { completedCount++; if (success) successCount++; else failCount++ })
      safeSetState(setBatchProgress, { current: completedCount, total: props.length, currentName: '' })
    }
    
    safeSetState(setBatchGenerating, false)
    safeSetState(setBatchProgress, { current: 0, total: 0, currentName: '' })
    
    if (shouldStopRef.current) message.info(`已停止生成，完成 ${successCount}/${props.length} 个道具`)
    else if (failCount === 0) message.success(`成功生成所有 ${successCount} 个道具的图片`)
    else message.warning(`生成完成：${successCount} 个成功，${failCount} 个失败`)
  }

  const handleStopGeneration = () => { shouldStopRef.current = true; message.info('正在停止生成...') }

  const selectGroup = async (propId: string, groupIndex: number) => {
    try {
      const updated = await propsApi.update(propId, { selected_group_index: groupIndex })
      safeSetState(setProps, (prev: Prop[]) => prev.map(p => p.id === updated.id ? updated : p))
      if (selectedProp?.id === propId) setSelectedProp(updated)
    } catch { message.error('选择失败') }
  }

  const deleteProp = async (propId: string) => {
    try {
      await propsApi.delete(propId)
      safeSetState(setProps, (prev: Prop[]) => prev.filter(p => p.id !== propId))
      message.success('道具已删除')
    } catch { message.error('删除失败') }
  }

  const deleteAllProps = async () => {
    if (!projectId) return
    try {
      await propsApi.deleteAll(projectId)
      safeSetState(setProps, [])
      message.success('已删除所有道具')
    } catch { message.error('删除失败') }
  }

  if (loading) return <div style={{ padding: 24, textAlign: 'center' }}><Spin size="large" /></div>

  return (
    <div style={{ padding: 24 }}>
      <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 600, margin: 0, color: '#e0e0e0' }}>道具管理</h1>
          <p style={{ color: '#888', margin: '4px 0 0', fontSize: 13 }}>
            {currentProject?.name} - 共 {props.length} 个道具
            {propUseStyle && propSelectedStyleId && (
              <Tag color="blue" style={{ marginLeft: 8 }}>
                <BgColorsOutlined /> 风格参考: {styles.find(s => s.id === propSelectedStyleId)?.name || '未知'}
              </Tag>
            )}
          </p>
        </div>
        <Space>
          <Button icon={<SettingOutlined />} onClick={() => setSettingsModalVisible(true)}>设置 ({propGroupCount}组)</Button>
          {props.length > 0 && (
            <>
              {batchGenerating ? (
                <Button danger icon={<StopOutlined />} onClick={handleStopGeneration}>停止生成</Button>
              ) : (
                <Button type="primary" icon={<ThunderboltOutlined />} onClick={generateAllPropsImages} disabled={extracting}>一键生成所有道具</Button>
              )}
              <Popconfirm title="确定删除所有道具？" description="此操作不可恢复" icon={<ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />} onConfirm={deleteAllProps} okText="删除" cancelText="取消" okButtonProps={{ danger: true }}>
                <Button danger icon={<DeleteOutlined />} disabled={batchGenerating}>删除所有</Button>
              </Popconfirm>
            </>
          )}
          <Button icon={<PlusOutlined />} onClick={() => setCreateModalVisible(true)} disabled={batchGenerating}>手动新建</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={extractProps} loading={extracting} disabled={batchGenerating}>从剧本提取道具</Button>
        </Space>
      </div>

      {batchGenerating && (
        <Alert message={<div style={{ display: 'flex', alignItems: 'center', gap: 16 }}><Spin size="small" /><span>正在生成: {batchProgress.currentName || `${batchProgress.current}/${batchProgress.total}`}</span></div>}
          description={<Progress percent={batchProgress.total > 0 ? Math.round((batchProgress.current / batchProgress.total) * 100) : 0} status="active" />} type="info" style={{ marginBottom: 24 }}
          action={<Button size="small" danger onClick={handleStopGeneration}>停止</Button>} />
      )}

      {props.length === 0 ? (
        <Empty description="暂无道具，请从剧本提取" style={{ marginTop: 100 }}><Button type="primary" onClick={extractProps} loading={extracting}>提取道具</Button></Empty>
      ) : (
        <div className="image-grid">
          {props.map((prop) => {
            const thumbnailUrl = prop.image_groups?.[prop.selected_group_index]?.url
            const isGeneratingThis = isItemGenerating(prop.id)
            return (
              <div key={prop.id} className="asset-card" onClick={() => openPropModal(prop)} style={{ opacity: isGeneratingThis ? 0.7 : 1 }}>
                <div className="asset-card-image" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative' }}>
                  {thumbnailUrl ? <Image src={thumbnailUrl} alt={prop.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} preview={false} /> : <AppstoreOutlined style={{ fontSize: 48, color: '#444' }} />}
                  {isGeneratingThis && <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Spin /></div>}
                </div>
                <div className="asset-card-info"><div className="asset-card-name">{prop.name}</div><div className="asset-card-desc">{prop.description || '暂无描述'}</div></div>
              </div>
            )
          })}
        </div>
      )}

      <Modal title={`编辑道具 - ${selectedProp?.name}`} open={isModalOpen} onOk={saveProp} onCancel={() => { setIsModalOpen(false); selectedPropIdRef.current = null }} width={900} okText="保存" cancelText="取消">
        {selectedProp && (
          <div style={{ display: 'flex', gap: 24 }}>
            <div style={{ width: 320 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <h4 style={{ margin: 0 }}>道具图片</h4>
                <Button type="primary" icon={<ThunderboltOutlined />} onClick={() => generateAllImages(selectedProp.id)} loading={generatingAll} disabled={generatingGroups.size > 0 || batchGenerating}>一键生成{propGroupCount}组</Button>
              </div>
              {Array.from({ length: Math.max(propGroupCount, selectedProp.image_groups?.length || 0) }, (_, groupIndex) => {
                const group = selectedProp.image_groups?.[groupIndex]
                const isSelected = selectedProp.selected_group_index === groupIndex
                const key = `${selectedProp.id}-${groupIndex}`
                const isGeneratingThis = generatingGroups.has(key)
                return (
                  <div key={groupIndex} style={{ marginBottom: 12, padding: 12, border: isSelected ? '2px solid #e5a84b' : '1px solid #333', borderRadius: 8, background: isSelected ? 'rgba(229, 168, 75, 0.1)' : '#1a1a1a' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <Radio checked={isSelected} onChange={() => selectGroup(selectedProp.id, groupIndex)}>第 {groupIndex + 1} 组</Radio>
                      <Button size="small" icon={<ReloadOutlined />} onClick={() => generateImages(selectedProp.id, groupIndex)} loading={isGeneratingThis} disabled={generatingAll || (generatingGroups.size > 0 && !isGeneratingThis) || batchGenerating}>{group?.url ? '重新生成' : '生成'}</Button>
                    </div>
                    <div style={{ aspectRatio: '1', background: '#242424', borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      {isGeneratingThis ? <Spin /> : group?.url ? <Image src={group.url} alt="道具" style={{ width: '100%', height: '100%', objectFit: 'cover' }} /> : <AppstoreOutlined style={{ fontSize: 32, color: '#444' }} />}
                    </div>
                  </div>
                )
              })}
            </div>
            <div style={{ flex: 1 }}>
              <Form form={form} layout="vertical">
                <Form.Item name="name" label="道具名称" rules={[{ required: true }]}><Input /></Form.Item>
                <Form.Item name="description" label="道具描述（说明用）"><TextArea rows={2} placeholder="用于说明，不参与生图" /></Form.Item>
                <Form.Item name="common_prompt" label="通用提示词"><TextArea rows={2} /></Form.Item>
                <Form.Item name="prop_prompt" label="道具提示词（用于生图）"><TextArea rows={2} placeholder="描述道具本身，不要包含角色和场景" /></Form.Item>
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
                    风格参考（当前道具）
                    {localUseStyle === null && propUseStyle && (
                      <Tag color="blue">使用全局设置</Tag>
                    )}
                  </Space>
                }
                style={{ marginTop: 16 }}
              >
                <Space direction="vertical" style={{ width: '100%' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Switch 
                      checked={localUseStyle !== null ? localUseStyle : propUseStyle}
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
                  {(localUseStyle !== null ? localUseStyle : propUseStyle) && (
                    <Select
                      placeholder="选择风格"
                      value={localStyleId !== null ? localStyleId : propSelectedStyleId}
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
                <Popconfirm title="确定删除此道具？" onConfirm={() => { deleteProp(selectedProp.id); setIsModalOpen(false) }} okText="删除" cancelText="取消" okButtonProps={{ danger: true }}>
                  <Button danger icon={<DeleteOutlined />}>删除道具</Button>
                </Popconfirm>
              </div>
            </div>
          </div>
        )}
      </Modal>

      <Modal title="生成设置" open={settingsModalVisible} onCancel={() => setSettingsModalVisible(false)} onOk={() => setSettingsModalVisible(false)} okText="确定" cancelText="取消">
        <Form layout="vertical">
          <Form.Item label="每个道具生成组数" extra="生成图片时，每个道具将生成指定组数的图片">
            <InputNumber min={1} max={10} value={propGroupCount} onChange={(v) => setPropGroupCount(v || 3)} style={{ width: '100%' }} />
          </Form.Item>
          
          <Form.Item 
            label={
              <Space>
                <BgColorsOutlined />
                风格参考（全局）
              </Space>
            }
            extra="开启后将使用选定的风格生成道具图片"
          >
            <Space direction="vertical" style={{ width: '100%' }}>
              <Switch 
                checked={propUseStyle}
                onChange={setPropUseStyle}
                checkedChildren="开启"
                unCheckedChildren="关闭"
              />
              {propUseStyle && (
                <Select
                  placeholder="选择风格"
                  value={propSelectedStyleId}
                  onChange={setPropSelectedStyleId}
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

      {/* 新建道具弹窗 */}
      <Modal
        title="新建道具"
        open={createModalVisible}
        onOk={createProp}
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
            label="道具名称"
            rules={[{ required: true, message: '请输入道具名称' }]}
          >
            <Input placeholder="例如：复古怀表" />
          </Form.Item>
          <Form.Item
            name="description"
            label="道具描述"
          >
            <TextArea rows={2} placeholder="道具的详细描述" />
          </Form.Item>
          <Form.Item
            name="prop_prompt"
            label="生图提示词"
            extra="用于生成道具图片的提示词"
          >
            <TextArea rows={3} placeholder="例如：精致的复古黄铜怀表，链条，白色背景" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default PropsPage
