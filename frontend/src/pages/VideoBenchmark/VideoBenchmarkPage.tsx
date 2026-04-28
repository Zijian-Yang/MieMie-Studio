import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  Alert,
  Button,
  Card,
  Empty,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  message,
  theme,
} from 'antd'
import {
  DeleteOutlined,
  DownloadOutlined,
  FileTextOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  ReloadOutlined,
  SaveOutlined,
} from '@ant-design/icons'
import DynamicModelForm from '../../components/ModelConfig/DynamicModelForm'
import {
  VideoBenchmarkCapabilitiesResponse,
  VideoBenchmarkCellResult,
  VideoBenchmarkDataset,
  VideoBenchmarkRun,
  VideoBenchmarkSuite,
  ModelParameterDef,
  videoBenchmarkApi,
} from '../../services/api'

const { TextArea } = Input
const { Title, Text } = Typography

const statusColorMap: Record<string, string> = {
  pending: 'default',
  running: 'processing',
  completed: 'success',
  failed: 'error',
  unsupported: 'warning',
  skipped: 'default',
}

const cloneSuite = (suite: VideoBenchmarkSuite | null) => (
  suite ? JSON.parse(JSON.stringify(suite)) as VideoBenchmarkSuite : null
)

const downloadBlobFile = (filename: string, blob: Blob) => {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.style.display = 'none'
  document.body.appendChild(anchor)
  anchor.click()
  window.setTimeout(() => {
    URL.revokeObjectURL(url)
    anchor.remove()
  }, 30000)
}

const getManualRetryCount = (run: VideoBenchmarkRun | null) => (
  run ? (run.stats.failure_count || 0) + (run.stats.unsupported_count || 0) : 0
)

const getVideoParameters = (model: any): ModelParameterDef[] => (
  (model?.configurable_parameters || model?.task_profiles?.image_to_video?.parameters || [])
    .filter((param: ModelParameterDef) => !['prompt', 'first_frame', 'audio'].includes(param.name))
)

const buildDefaultValues = (parameters: ModelParameterDef[], profileDefaults?: Record<string, any>) => {
  const defaults: Record<string, any> = { ...(profileDefaults || {}) }
  parameters.forEach((param) => {
    if (param.default !== undefined && param.default !== null && defaults[param.name] === undefined) {
      defaults[param.name] = param.default
    }
  })
  return defaults
}

const buildModelFormInfo = (model: any) => {
  const parameters = getVideoParameters(model)
  return {
    id: model.id,
    name: model.name,
    type: model.type || 'video-benchmark',
    parameters,
    default_values: buildDefaultValues(parameters, model.task_profiles?.image_to_video?.default_values),
  }
}

const getCellGroupCount = (cell: VideoBenchmarkCellResult) => {
  const value = Number(cell.effective_params?.group_count || cell.output_videos?.length || 1)
  return Number.isFinite(value) && value > 0 ? value : 1
}

const JsonPreviewBlock = ({ title, value }: { title: string; value: Record<string, any> | null | undefined }) => (
  <Card size="small" title={title}>
    <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{JSON.stringify(value || {}, null, 2)}</pre>
  </Card>
)

const BenchmarkModelOverrideCard = ({
  projectId,
  modelMeta,
  dataset,
  baselineParams,
  currentRun,
  value,
  onChange,
}: {
  projectId?: string
  modelMeta: any
  dataset: VideoBenchmarkDataset | null
  baselineParams: Record<string, any>
  currentRun: VideoBenchmarkRun | null
  value: Record<string, any>
  onChange: (values: Record<string, any>) => void
}) => {
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewPayload, setPreviewPayload] = useState<Record<string, any> | null>(null)
  const firstCase = dataset?.items?.[0]
  const latestRunCell = useMemo(
    () => currentRun?.cell_results?.find((cell) => cell.case_id === firstCase?.id && cell.model_id === modelMeta.id) || null,
    [currentRun?.cell_results, firstCase?.id, modelMeta.id]
  )

  const handlePreview = async () => {
    if (!projectId || !firstCase) {
      message.warning('当前数据集没有可预览样例')
      return
    }
    setPreviewLoading(true)
    try {
      const result = await videoBenchmarkApi.previewCell({
        project_id: projectId,
        model_id: modelMeta.id,
        case_data: firstCase,
        baseline_params: baselineParams,
        override_params: value,
      })
      setPreviewPayload(result)
    } catch (error) {
      if (error instanceof Error) message.error(error.message)
    } finally {
      setPreviewLoading(false)
    }
  }

  return (
    <Card
      size="small"
      title={`${modelMeta.name} ${modelMeta.id}`}
      extra={<Button size="small" onClick={handlePreview} loading={previewLoading}>预览 Payload</Button>}
    >
      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        <DynamicModelForm
          modelInfo={buildModelFormInfo(modelMeta)}
          value={value}
          onChange={onChange}
          layout="vertical"
          columns={2}
        />
        {previewPayload && (
          <Space direction="vertical" style={{ width: '100%' }}>
            <JsonPreviewBlock title="Effective Params（预览）" value={previewPayload.effective_params} />
            <JsonPreviewBlock title="Provider Payload（预览）" value={previewPayload.provider_payload} />
          </Space>
        )}
        {latestRunCell && (
          <Alert
            type={latestRunCell.status === 'completed' ? 'success' : latestRunCell.status === 'unsupported' ? 'warning' : 'error'}
            showIcon
            message={`上一次运行：${latestRunCell.status}`}
            description={latestRunCell.error_message || `生成数量：${getCellGroupCount(latestRunCell)}，输出：${latestRunCell.output_videos.length}`}
          />
        )}
      </Space>
    </Card>
  )
}

const VideoBenchmarkPage = () => {
  const { token } = theme.useToken()
  const { projectId } = useParams<{ projectId: string }>()

  const [capabilities, setCapabilities] = useState<VideoBenchmarkCapabilitiesResponse | null>(null)
  const [datasets, setDatasets] = useState<VideoBenchmarkDataset[]>([])
  const [suites, setSuites] = useState<VideoBenchmarkSuite[]>([])
  const [selectedSuiteId, setSelectedSuiteId] = useState<string | null>(null)
  const [draftSuite, setDraftSuite] = useState<VideoBenchmarkSuite | null>(null)
  const [currentRun, setCurrentRun] = useState<VideoBenchmarkRun | null>(null)
  const [loading, setLoading] = useState(true)
  const [suiteModalOpen, setSuiteModalOpen] = useState(false)
  const [suiteFormValues, setSuiteFormValues] = useState({ name: '', description: '', dataset_id: '' })
  const [baselineText, setBaselineText] = useState('{}')
  const [detailCell, setDetailCell] = useState<VideoBenchmarkCellResult | null>(null)
  const [exportingFormat, setExportingFormat] = useState<'markdown' | 'html' | null>(null)

  const selectedSuite = useMemo(
    () => suites.find((suite) => suite.id === selectedSuiteId) || null,
    [selectedSuiteId, suites]
  )

  const selectedDataset = useMemo(
    () => datasets.find((dataset) => dataset.id === draftSuite?.dataset_id) || null,
    [datasets, draftSuite?.dataset_id]
  )

  const availableModels = useMemo(() => {
    if (!capabilities) return []
    return Object.values(capabilities.models)
  }, [capabilities])

  useEffect(() => {
    if (!projectId) return
    const loadData = async () => {
      setLoading(true)
      try {
        const [capabilityRes, datasetRes, suiteRes] = await Promise.all([
          videoBenchmarkApi.getCapabilities(),
          videoBenchmarkApi.listDatasets(projectId),
          videoBenchmarkApi.listSuites(projectId),
        ])
        setCapabilities(capabilityRes)
        setDatasets(datasetRes.datasets)
        setSuites(suiteRes.suites)
        setSelectedSuiteId((prev) => prev && suiteRes.suites.some((suite) => suite.id === prev) ? prev : suiteRes.suites[0]?.id || null)
      } catch (error) {
        if (error instanceof Error) message.error(error.message)
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [projectId])

  useEffect(() => {
    const nextSuite = cloneSuite(selectedSuite)
    setDraftSuite(nextSuite)
    setBaselineText(JSON.stringify(nextSuite?.baseline_params || {}, null, 2))
  }, [selectedSuite])

  useEffect(() => {
    if (!selectedSuite?.latest_run_id) {
      setCurrentRun(null)
      return
    }
    const loadRun = async () => {
      try {
        const result = await videoBenchmarkApi.getRun(selectedSuite.latest_run_id as string)
        setCurrentRun(result.run)
      } catch (error) {
        if (error instanceof Error) message.error(error.message)
      }
    }
    loadRun()
  }, [selectedSuite?.latest_run_id])

  useEffect(() => {
    if (!currentRun || currentRun.status !== 'running') return
    const timer = window.setInterval(async () => {
      try {
        const runRes = await videoBenchmarkApi.getRun(currentRun.id)
        setCurrentRun(runRes.run)
        if (runRes.run.status !== 'running') {
          const suiteRes = await videoBenchmarkApi.getSuite(runRes.run.suite_id)
          setSuites((prev) => prev.map((item) => item.id === suiteRes.suite.id ? suiteRes.suite : item))
        }
      } catch {
        // polling keeps the current view stable
      }
    }, 5000)
    return () => window.clearInterval(timer)
  }, [currentRun])

  const parseBaselineParams = () => {
    try {
      const parsed = JSON.parse(baselineText || '{}')
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        throw new Error('Baseline Params 必须是 JSON 对象')
      }
      return parsed
    } catch (error) {
      throw new Error(error instanceof Error ? error.message : 'Baseline Params JSON 格式错误')
    }
  }

  const refreshSuites = async (preferredId?: string | null) => {
    if (!projectId) return
    const suiteRes = await videoBenchmarkApi.listSuites(projectId)
    setSuites(suiteRes.suites)
    const nextId = preferredId ?? selectedSuiteId
    setSelectedSuiteId(nextId && suiteRes.suites.some((suite) => suite.id === nextId) ? nextId : suiteRes.suites[0]?.id || null)
  }

  const openCreateSuiteModal = () => {
    setSuiteFormValues({
      name: '',
      description: '',
      dataset_id: datasets[0]?.id || '',
    })
    setSuiteModalOpen(true)
  }

  const handleCreateSuite = async () => {
    if (!projectId) return
    try {
      const result = await videoBenchmarkApi.createSuite({
        project_id: projectId,
        name: suiteFormValues.name,
        description: suiteFormValues.description,
        dataset_id: suiteFormValues.dataset_id,
        baseline_params: {},
      })
      setSuiteModalOpen(false)
      await refreshSuites(result.suite.id)
      message.success('视频测评任务已创建')
    } catch (error) {
      if (error instanceof Error) message.error(error.message)
    }
  }

  const handleSaveSuite = async () => {
    if (!draftSuite) return
    try {
      const baselineParams = parseBaselineParams()
      const result = await videoBenchmarkApi.updateSuite(draftSuite.id, {
        name: draftSuite.name,
        description: draftSuite.description,
        dataset_id: draftSuite.dataset_id,
        selected_models: draftSuite.selected_models,
        baseline_params: baselineParams,
        model_overrides: draftSuite.model_overrides,
      })
      await refreshSuites(result.suite.id)
      message.success('视频测评配置已保存')
    } catch (error) {
      if (error instanceof Error) message.error(error.message)
    }
  }

  const handleRunSuite = async () => {
    if (!draftSuite) return
    try {
      const baselineParams = parseBaselineParams()
      const savedSuite = await videoBenchmarkApi.updateSuite(draftSuite.id, {
        name: draftSuite.name,
        description: draftSuite.description,
        dataset_id: draftSuite.dataset_id,
        selected_models: draftSuite.selected_models,
        baseline_params: baselineParams,
        model_overrides: draftSuite.model_overrides,
      })
      const result = await videoBenchmarkApi.runSuite(draftSuite.id)
      setCurrentRun(result.run)
      setSuites((prev) => prev.map((item) => item.id === savedSuite.suite.id ? result.suite : item))
      setSelectedSuiteId(result.suite.id)
      message.success('视频测评已开始运行')
    } catch (error) {
      if (error instanceof Error) message.error(error.message)
    }
  }

  const handleDeleteSuite = async (suiteId: string) => {
    try {
      await videoBenchmarkApi.deleteSuite(suiteId)
      await refreshSuites(null)
      message.success('视频测评任务已删除')
    } catch (error) {
      if (error instanceof Error) message.error(error.message)
    }
  }

  const handleRetryFailedRun = async () => {
    if (!currentRun) return
    try {
      const result = await videoBenchmarkApi.retryFailedRun(currentRun.id)
      setCurrentRun(result.run)
      setSuites((prev) => prev.map((item) => item.id === result.suite.id ? result.suite : item))
      setSelectedSuiteId(result.suite.id)
      message.success('已开始重试失败和未支持任务')
    } catch (error) {
      if (error instanceof Error) message.error(error.message)
    }
  }

  const handleExport = async (format: 'markdown' | 'html') => {
    if (!currentRun) return
    setExportingFormat(format)
    try {
      const result = format === 'markdown'
        ? await videoBenchmarkApi.downloadRunMarkdown(currentRun.id)
        : await videoBenchmarkApi.downloadRunHtml(currentRun.id)
      if (!result.filename || result.blob.size <= 0) throw new Error('导出文件为空，请重试')
      downloadBlobFile(result.filename, result.blob)
      message.success(`${format === 'markdown' ? 'Markdown' : 'HTML'} 报告已导出`)
    } catch (error) {
      if (error instanceof Error) message.error(error.message)
    } finally {
      setExportingFormat(null)
    }
  }

  const resultMap = useMemo(() => {
    const map = new Map<string, VideoBenchmarkCellResult>()
    ;(currentRun?.cell_results || []).forEach((cell) => {
      map.set(`${cell.case_id}__${cell.model_id}`, cell)
    })
    return map
  }, [currentRun?.cell_results])

  const matrixColumns = useMemo(() => {
    const baseColumns = [
      {
        title: '样例名',
        dataIndex: 'name',
        fixed: 'left' as const,
        width: 150,
      },
      {
        title: '首帧',
        dataIndex: 'first_frame',
        fixed: 'left' as const,
        width: 100,
        render: (asset: any) => asset?.url ? (
          <img src={asset.url} alt={asset.name || '首帧'} style={{ width: 64, height: 64, objectFit: 'cover', borderRadius: 6 }} />
        ) : <Tag color="error">缺首帧</Tag>,
      },
      {
        title: '时长',
        dataIndex: 'duration',
        fixed: 'left' as const,
        width: 90,
        render: (value: number | null) => value ? `${value}s` : <Text type="secondary">配置</Text>,
      },
      {
        title: 'Prompt',
        dataIndex: 'prompt',
        fixed: 'left' as const,
        width: 260,
        render: (value: string) => <div style={{ whiteSpace: 'pre-wrap' }}>{value || <Text type="secondary">空</Text>}</div>,
      },
    ]
    const modelColumns = (currentRun?.model_snapshots || []).map((model) => ({
      title: model.name || model.id,
      key: model.id,
      width: 300,
      render: (_: unknown, record: any) => {
        const cell = resultMap.get(`${record.id}__${model.id}`)
        if (!cell) return <Text type="secondary">未运行</Text>
        const videos = (cell.output_videos || []).filter((video) => video.url)
        const groupCount = getCellGroupCount(cell)
        return (
          <Space direction="vertical" size={8} style={{ width: '100%' }}>
            <Space size={6} wrap>
              <Tag color={statusColorMap[cell.status] || 'default'}>{cell.status}</Tag>
              <Tag>生成 {groupCount} 条</Tag>
              {videos.length > 0 && <Tag color="success">输出 {videos.length} 条</Tag>}
            </Space>
            {videos.length > 0 && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 8, width: '100%' }}>
                {videos.map((video, index) => (
                  <div key={`${video.url}-${index}`}>
                    <Text type="secondary" style={{ display: 'block', marginBottom: 4 }}>视频 {index + 1}</Text>
                    <video
                      controls
                      preload="metadata"
                      src={video.url || undefined}
                      style={{ width: '100%', maxWidth: 160, borderRadius: 6, background: token.colorFillSecondary }}
                    />
                  </div>
                ))}
              </div>
            )}
            {cell.error_message && <Text type="danger" style={{ whiteSpace: 'pre-wrap' }}>{cell.error_message}</Text>}
            <Button size="small" onClick={() => setDetailCell(cell)}>查看详情</Button>
          </Space>
        )
      },
    }))
    return [...baseColumns, ...modelColumns]
  }, [currentRun?.model_snapshots, resultMap, token.colorFillSecondary])

  if (loading) {
    return <div style={{ padding: 48, textAlign: 'center' }}><Text>加载中...</Text></div>
  }

  return (
    <div style={{ padding: 24 }}>
      <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <Title level={3} style={{ margin: 0, color: token.colorText }}>视频测评</Title>
          <Text type="secondary">基于视频数据集运行首帧生视频横向测评，保留 payload、任务 ID 和输出视频。</Text>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreateSuiteModal}>新建测评任务</Button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: 24, alignItems: 'start' }}>
        <Card title="测评任务">
          {suites.length === 0 ? (
            <Empty description="暂无视频测评任务" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          ) : (
            <Space direction="vertical" style={{ width: '100%' }}>
              {suites.map((suite) => (
                <Card
                  key={suite.id}
                  size="small"
                  hoverable
                  onClick={() => setSelectedSuiteId(suite.id)}
                  style={{ borderColor: suite.id === selectedSuiteId ? token.colorPrimary : token.colorBorderSecondary }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                    <Text strong>{suite.name}</Text>
                    <Tag color={statusColorMap[suite.status] || 'default'}>{suite.status}</Tag>
                  </div>
                  <div style={{ marginTop: 8 }}>
                    <Text type="secondary">模型数：{suite.selected_models.length}</Text>
                  </div>
                  <div style={{ marginTop: 8 }}>
                    <Text type="secondary">{datasets.find((dataset) => dataset.id === suite.dataset_id)?.name || '未找到数据集'}</Text>
                  </div>
                </Card>
              ))}
            </Space>
          )}
        </Card>

        {!draftSuite ? (
          <Card><Empty description="请选择或创建一个视频测评任务" /></Card>
        ) : (
          <Space direction="vertical" size={24} style={{ width: '100%' }}>
            <Card
              title="测评配置"
              extra={
                <Space>
                  <Popconfirm title="删除该测评任务？" onConfirm={() => handleDeleteSuite(draftSuite.id)}>
                    <Button danger icon={<DeleteOutlined />}>删除</Button>
                  </Popconfirm>
                  <Button icon={<SaveOutlined />} onClick={handleSaveSuite}>保存配置</Button>
                  <Button type="primary" icon={<PlayCircleOutlined />} onClick={handleRunSuite} disabled={!draftSuite.selected_models.length}>
                    运行测评
                  </Button>
                </Space>
              }
            >
              <Space direction="vertical" size={16} style={{ width: '100%' }}>
                {!datasets.length && <Alert type="warning" showIcon message="暂无视频数据集" />}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                  <div>
                    <Text style={{ display: 'block', marginBottom: 8 }}>测评任务名称</Text>
                    <Input value={draftSuite.name} onChange={(event) => setDraftSuite({ ...draftSuite, name: event.target.value })} />
                  </div>
                  <div>
                    <Text style={{ display: 'block', marginBottom: 8 }}>选择数据集</Text>
                    <Select
                      value={draftSuite.dataset_id}
                      style={{ width: '100%' }}
                      options={datasets.map((dataset) => ({ value: dataset.id, label: `${dataset.name} (${dataset.items.length} 条)` }))}
                      onChange={(value) => setDraftSuite({ ...draftSuite, dataset_id: value })}
                    />
                  </div>
                </div>
                <div>
                  <Text style={{ display: 'block', marginBottom: 8 }}>描述</Text>
                  <TextArea rows={3} value={draftSuite.description} onChange={(event) => setDraftSuite({ ...draftSuite, description: event.target.value })} />
                </div>
                <div>
                  <Text style={{ display: 'block', marginBottom: 8 }}>Baseline Params JSON</Text>
                  <TextArea
                    rows={5}
                    value={baselineText}
                    onChange={(event) => setBaselineText(event.target.value)}
                  />
                </div>
                <Card size="small" title="模型选择">
                  <Select
                    mode="multiple"
                    style={{ width: '100%' }}
                    value={draftSuite.selected_models}
                    placeholder="选择要参与测评的首帧生视频模型"
                    options={availableModels.map((model) => ({
                      value: model.id,
                      label: `${model.name} ${model.id}`,
                    }))}
                    onChange={(value) => setDraftSuite({
                      ...draftSuite,
                      selected_models: value,
                      model_overrides: Object.fromEntries(
                        Object.entries(draftSuite.model_overrides || {}).filter(([modelId]) => value.includes(modelId))
                      ),
                    })}
                  />
                </Card>
                {draftSuite.selected_models.length > 0 && (
                  <Space direction="vertical" style={{ width: '100%' }}>
                    {draftSuite.selected_models.map((modelId) => {
                      const modelMeta = capabilities?.models[modelId]
                      if (!modelMeta) return null
                      return (
                        <BenchmarkModelOverrideCard
                          key={modelId}
                          projectId={projectId}
                          modelMeta={modelMeta}
                          dataset={selectedDataset}
                          baselineParams={(() => {
                            try { return JSON.parse(baselineText || '{}') } catch { return {} }
                          })()}
                          currentRun={currentRun}
                          value={draftSuite.model_overrides?.[modelId] || {}}
                          onChange={(values) => setDraftSuite({
                            ...draftSuite,
                            model_overrides: {
                              ...(draftSuite.model_overrides || {}),
                              [modelId]: values,
                            },
                          })}
                        />
                      )
                    })}
                  </Space>
                )}
              </Space>
            </Card>

            <Card
              title="运行结果"
              extra={
                <Space>
                  {currentRun && <Tag color={statusColorMap[currentRun.status] || 'default'}>{currentRun.status}</Tag>}
                  {currentRun && currentRun.status !== 'running' && getManualRetryCount(currentRun) > 0 && (
                    <Button icon={<ReloadOutlined />} onClick={handleRetryFailedRun}>重试失败/未支持任务</Button>
                  )}
                  {currentRun && (
                    <>
                      <Button icon={<DownloadOutlined />} onClick={() => handleExport('markdown')} loading={exportingFormat === 'markdown'}>
                        导出 Markdown
                      </Button>
                      <Button icon={<FileTextOutlined />} onClick={() => handleExport('html')} loading={exportingFormat === 'html'}>
                        导出 HTML
                      </Button>
                    </>
                  )}
                </Space>
              }
            >
              {!currentRun ? (
                <Empty description="还没有运行记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              ) : (
                <Space direction="vertical" size={16} style={{ width: '100%' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
                    <Statistic title="样例数" value={currentRun.stats.case_count || 0} />
                    <Statistic title="模型数" value={currentRun.stats.model_count || 0} />
                    <Statistic title="成功单元" value={currentRun.stats.success_count || 0} />
                    <Statistic title="失败/未支持" value={(currentRun.stats.failure_count || 0) + (currentRun.stats.unsupported_count || 0)} />
                  </div>
                  <Table
                    rowKey="id"
                    dataSource={(currentRun.dataset_snapshot.items || []).slice().sort((a: any, b: any) => (a.sort_order || 0) - (b.sort_order || 0))}
                    columns={matrixColumns as any}
                    pagination={false}
                    scroll={{ x: 1280 }}
                  />
                </Space>
              )}
            </Card>
          </Space>
        )}
      </div>

      <Modal
        title="新建视频测评任务"
        open={suiteModalOpen}
        onOk={handleCreateSuite}
        onCancel={() => setSuiteModalOpen(false)}
        okText="创建"
        cancelText="取消"
      >
        <Space direction="vertical" style={{ width: '100%' }} size={16}>
          <div>
            <Text style={{ display: 'block', marginBottom: 8 }}>名称</Text>
            <Input value={suiteFormValues.name} onChange={(event) => setSuiteFormValues({ ...suiteFormValues, name: event.target.value })} />
          </div>
          <div>
            <Text style={{ display: 'block', marginBottom: 8 }}>描述</Text>
            <TextArea rows={3} value={suiteFormValues.description} onChange={(event) => setSuiteFormValues({ ...suiteFormValues, description: event.target.value })} />
          </div>
          <div>
            <Text style={{ display: 'block', marginBottom: 8 }}>数据集</Text>
            <Select
              value={suiteFormValues.dataset_id}
              style={{ width: '100%' }}
              options={datasets.map((dataset) => ({ value: dataset.id, label: `${dataset.name} (${dataset.items.length} 条)` }))}
              onChange={(value) => setSuiteFormValues({ ...suiteFormValues, dataset_id: value })}
            />
          </div>
        </Space>
      </Modal>

      <Modal
        title={detailCell ? `${detailCell.case_name} / ${detailCell.model_name}` : '单元详情'}
        open={!!detailCell}
        onCancel={() => setDetailCell(null)}
        footer={null}
        width={980}
      >
        {detailCell && (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Space size={8} wrap>
              <Tag color={statusColorMap[detailCell.status] || 'default'}>{detailCell.status}</Tag>
              <Tag>生成 {getCellGroupCount(detailCell)} 条</Tag>
              <Tag color="success">输出 {(detailCell.output_videos || []).filter((video) => video.url).length} 条</Tag>
            </Space>
            {(detailCell.output_videos || []).filter((video) => video.url).length > 0 && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 12, width: '100%' }}>
                {(detailCell.output_videos || []).filter((video) => video.url).map((video, index) => (
                  <div key={`${video.url}-${index}`}>
                    <Text strong style={{ display: 'block', marginBottom: 8 }}>输出视频 {index + 1}</Text>
                    <video
                      controls
                      preload="metadata"
                      src={video.url || undefined}
                      style={{ width: '100%', maxHeight: 420, borderRadius: 8, background: token.colorFillSecondary }}
                    />
                  </div>
                ))}
              </div>
            )}
            {detailCell.error_message && <Alert type="error" showIcon message={detailCell.error_message} />}
            <Card size="small" title="任务追踪 IDs">
              <Space direction="vertical" style={{ width: '100%' }}>
                <div>
                  <Text strong>Task IDs</Text>
                  <pre style={{ margin: '8px 0 0', whiteSpace: 'pre-wrap' }}>{(detailCell.task_ids || []).join('\n') || '暂无'}</pre>
                </div>
                <div>
                  <Text strong>Request IDs</Text>
                  <pre style={{ margin: '8px 0 0', whiteSpace: 'pre-wrap' }}>{(detailCell.request_ids || []).join('\n') || '暂无'}</pre>
                </div>
              </Space>
            </Card>
            <JsonPreviewBlock title="Effective Params" value={detailCell.effective_params || {}} />
            <JsonPreviewBlock title="Canonical Request" value={detailCell.canonical_request || {}} />
            <JsonPreviewBlock title="Provider Payload" value={detailCell.provider_payload || {}} />
            <JsonPreviewBlock title="Provider Result Meta" value={detailCell.provider_result_meta || {}} />
          </Space>
        )}
      </Modal>
    </div>
  )
}

export default VideoBenchmarkPage
