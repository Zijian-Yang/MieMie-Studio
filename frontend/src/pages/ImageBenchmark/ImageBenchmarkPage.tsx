import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  Alert,
  Button,
  Card,
  Collapse,
  Empty,
  Image,
  Input,
  Modal,
  Popconfirm,
  Segmented,
  Select,
  Space,
  Spin,
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
  LinkOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  ReloadOutlined,
  SaveOutlined,
  ShareAltOutlined,
} from '@ant-design/icons'
import DynamicModelForm from '../../components/ModelConfig/DynamicModelForm'
import {
  ApiError,
  ImageBenchmarkCapabilitiesResponse,
  ImageBenchmarkCellResult,
  ImageBenchmarkDataset,
  ImageBenchmarkDatasetIssue,
  ImageBenchmarkRun,
  ImageBenchmarkSuite,
  ModelParameterDef,
  imageBenchmarkApi,
} from '../../services/api'
import {
  buildWan27QualityTemplateGroups,
  getWan27CustomSizeLimits,
  matchWan27QualityTemplate,
  type ImageQualityLevel,
} from '../../utils/wan27Size'

const { TextArea } = Input
const { Title, Text } = Typography

const cloneSuite = (suite: ImageBenchmarkSuite | null) => (
  suite ? JSON.parse(JSON.stringify(suite)) as ImageBenchmarkSuite : null
)

const downloadTextFile = (filename: string, content: string, mimeType: string) => {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

const escapeHtml = (value: unknown) => (
  String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
)

const statusColorMap: Record<string, string> = {
  pending: 'default',
  running: 'processing',
  completed: 'success',
  failed: 'error',
  unsupported: 'warning',
  skipped: 'default',
}

const getCaseImages = (item: Record<string, any>) => {
  if (Array.isArray(item.image_slots) && item.image_slots.length > 0) {
    return [...item.image_slots]
      .sort((left, right) => (left.position || 0) - (right.position || 0))
      .map((slot) => slot.image)
      .filter((image) => image?.url)
  }
  return item.input_images || []
}

const getConfigurableParameters = (model: any): ModelParameterDef[] => (
  (model?.configurable_parameters || model?.parameters || []).filter((param: ModelParameterDef) => !['prompt', 'images'].includes(param.name))
)

const getBenchmarkParametersForTask = (model: any, taskKind?: string): ModelParameterDef[] => (
  getConfigurableParameters(model).filter((param) => {
    if (param.name === 'bbox_list' || param.name === 'enable_sequential') return false
    if (param.name === 'thinking_mode' && taskKind !== 'text_to_image') return false
    return true
  })
)

const getTaskKindLabel = (taskKind?: string) => {
  if (taskKind === 'text_to_image') return '文生图'
  if (taskKind === 'interactive_edit') return '交互式编辑'
  return '图片编辑'
}

const getManualRetryCount = (run: ImageBenchmarkRun | null) => (
  run ? (run.stats.failure_count || 0) + (run.stats.unsupported_count || 0) : 0
)

const buildRunHtmlReport = (run: ImageBenchmarkRun, suite?: ImageBenchmarkSuite | null) => {
  const datasetItems = [...((run.dataset_snapshot?.items || []) as Record<string, any>[])]
    .sort((left, right) => (left.sort_order || 0) - (right.sort_order || 0))
  const resultMap = new Map<string, ImageBenchmarkCellResult>()
  ;(run.cell_results || []).forEach((cell) => {
    resultMap.set(`${cell.case_id}__${cell.model_id}`, cell)
  })
  const modelSnapshots = run.model_snapshots || []
  const headers = ['样例', 'Prompt', '输入图', ...modelSnapshots.map((model) => model.name || model.id)]
  const rows = datasetItems.map((item) => {
    const inputImages = getCaseImages(item)
      .map((image: any) => image.url ? `<img src="${escapeHtml(image.url)}" alt="${escapeHtml(image.name || '输入图')}" />` : '')
      .join('')
    const modelCells = modelSnapshots.map((model) => {
      const cell = resultMap.get(`${item.id}__${model.id}`)
      if (!cell) return '<span class="muted">未运行</span>'
      const images = (cell.output_images || [])
        .map((image) => image.url ? `<img src="${escapeHtml(image.url)}" alt="输出图" />` : '')
        .join('')
      const error = cell.error_message ? `<div class="error">${escapeHtml(cell.error_message)}</div>` : ''
      return `<div class="status">${escapeHtml(cell.status)}</div><div class="images">${images}</div>${error}`
    })
    return [
      escapeHtml(item.name || '未命名样例'),
      `<div class="prompt">${escapeHtml(item.prompt || '')}</div>`,
      `<div class="images">${inputImages}</div>`,
      ...modelCells,
    ]
  })
  const tableHead = headers.map((header) => `<th>${escapeHtml(header)}</th>`).join('')
  const tableRows = rows.map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join('')}</tr>`).join('\n')
  return `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${escapeHtml(suite?.name || '图片测评报告')}</title>
  <style>
    body { margin: 0; padding: 24px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #1f1f1f; background: #f5f5f5; }
    h1 { margin: 0 0 8px; font-size: 28px; }
    .meta { display: flex; flex-wrap: wrap; gap: 16px; margin: 16px 0 24px; color: #666; }
    table { width: 100%; border-collapse: collapse; background: #fff; }
    th, td { border: 1px solid #ddd; padding: 12px; vertical-align: top; min-width: 180px; }
    th { background: #fafafa; position: sticky; top: 0; z-index: 1; }
    .prompt { white-space: pre-wrap; max-width: 360px; }
    .images { display: flex; flex-wrap: wrap; gap: 10px; }
    img { max-width: 240px; max-height: 240px; object-fit: contain; border-radius: 6px; background: #eee; }
    .status { display: inline-block; margin-bottom: 8px; padding: 2px 8px; border-radius: 6px; background: #eef4ff; color: #1d4ed8; font-size: 12px; }
    .error { margin-top: 8px; color: #c00; white-space: pre-wrap; }
    .muted { color: #999; }
  </style>
</head>
<body>
  <h1>${escapeHtml(suite?.name || '图片测评报告')}</h1>
  <div>${escapeHtml(suite?.description || '')}</div>
  <div class="meta">
    <span>Run ID: ${escapeHtml(run.id)}</span>
    <span>状态: ${escapeHtml(run.status)}</span>
    <span>样例数: ${escapeHtml(run.stats.case_count || 0)}</span>
    <span>模型数: ${escapeHtml(run.stats.model_count || 0)}</span>
    <span>成功单元: ${escapeHtml(run.stats.success_count || 0)}</span>
    <span>失败单元: ${escapeHtml(run.stats.failure_count || 0)}</span>
  </div>
  <table>
    <thead><tr>${tableHead}</tr></thead>
    <tbody>${tableRows}</tbody>
  </table>
</body>
</html>`
}

const buildWan27SizeParam = (taskKind: string, modelId: string, originalParam?: ModelParameterDef): ModelParameterDef => ({
  ...(originalParam || {
    name: 'size_preset',
    label: '规格档位',
    description: '输出尺寸',
  }),
  type: 'select',
  default: '2K',
  constraint: {
    ...(originalParam?.constraint || {}),
    options: (
      taskKind === 'text_to_image' && modelId === 'wan2.7-image-pro'
        ? [
            { value: '1K', label: '1K' },
            { value: '2K', label: '2K（默认）' },
            { value: '4K', label: '4K' },
          ]
        : [
            { value: '1K', label: '1K' },
            { value: '2K', label: '2K（默认）' },
          ]
    ),
  },
})

const buildQwenImage2SizeParam = (taskKind: string, originalParam?: ModelParameterDef): ModelParameterDef => ({
  ...(originalParam || {
    name: 'size',
    label: '输出尺寸',
    description: '输出分辨率',
  }),
  type: 'select',
  default: taskKind === 'image_edit' ? '' : (originalParam?.default ?? '1024*1024'),
  constraint: {
    ...(originalParam?.constraint || {}),
    options: [
      {
        value: '',
        label: taskKind === 'image_edit'
          ? '不设置尺寸（跟随最后一张输入图分辨率）'
          : '不设置尺寸（使用模型默认）',
      },
      ...((originalParam?.constraint?.options || []) as any[]),
    ],
  },
})

const buildDefaultValues = (parameters: ModelParameterDef[]) => {
  const defaults: Record<string, any> = {}
  parameters.forEach((param) => {
    if (param.default !== undefined && param.default !== null) {
      defaults[param.name] = param.default
    }
  })
  if (parameters.some((param) => param.name === 'n')) {
    defaults.n = 1
  }
  return defaults
}

const buildModelFormInfo = (model: any, taskKind?: string) => {
  const parameters = getBenchmarkParametersForTask(model, taskKind).map((param) => {
    if (param.name === 'size_preset' && model.id?.startsWith('wan2.7-image')) {
      return buildWan27SizeParam(taskKind || '', model.id, param)
    }
    if (param.name === 'size' && (model.id === 'qwen-image-2.0-pro' || model.id === 'qwen-image-2.0')) {
      return buildQwenImage2SizeParam(taskKind || '', param)
    }
    return param
  })
  return {
    id: model.id,
    name: model.name,
    type: model.model_type || 'benchmark',
    parameters,
    default_values: buildDefaultValues(parameters),
  }
}

const JsonPreviewBlock = ({ title, value }: { title: string; value: Record<string, any> | null | undefined }) => (
  <Card size="small" title={title}>
    <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{JSON.stringify(value || {}, null, 2)}</pre>
  </Card>
)

const Wan27SizeOverrideEditor = ({
  modelId,
  taskKind,
  value,
  defaultValues,
  onChange,
}: {
  modelId: string
  taskKind?: string
  value: Record<string, any>
  defaultValues?: Record<string, any>
  onChange: (values: Record<string, any>) => void
}) => {
  const { token } = theme.useToken()
  const referenceCount = taskKind === 'text_to_image' ? 0 : 1
  const limits = useMemo(
    () => getWan27CustomSizeLimits(modelId, (taskKind || 'text_to_image') as any, referenceCount),
    [modelId, referenceCount, taskKind]
  )
  const qualityGroups = useMemo(() => buildWan27QualityTemplateGroups(limits), [limits])
  const effectiveSizeMode = ((value.size_mode ?? defaultValues?.size_mode) || 'custom') as 'preset' | 'custom'
  const effectivePreset = value.size_preset ?? defaultValues?.size_preset ?? '2K'
  const [ratioChoice, setRatioChoice] = useState('1:1')
  const [qualityChoice, setQualityChoice] = useState<ImageQualityLevel>('medium')

  useEffect(() => {
    if (!qualityGroups.length) return
    if (effectiveSizeMode !== 'custom') {
      const firstGroup = qualityGroups[0]
      if (!firstGroup) return
      setRatioChoice(firstGroup.ratio)
      setQualityChoice(firstGroup.options.find((item) => item.quality === 'medium')?.quality || firstGroup.options[0].quality)
      return
    }
    const width = Number(value.custom_width ?? defaultValues?.custom_width ?? 0)
    const height = Number(value.custom_height ?? defaultValues?.custom_height ?? 0)
    const match = matchWan27QualityTemplate(qualityGroups, width, height)
    if (match) {
      setRatioChoice(match.ratio)
      setQualityChoice(match.quality)
      return
    }
    const firstGroup = qualityGroups[0]
    if (!firstGroup) return
    setRatioChoice(firstGroup.ratio)
    setQualityChoice(firstGroup.options.find((item) => item.quality === 'medium')?.quality || firstGroup.options[0].quality)
  }, [defaultValues?.custom_height, defaultValues?.custom_width, effectiveSizeMode, qualityGroups, value.custom_height, value.custom_width])

  const presetOptions = useMemo(() => {
    const allow4K = modelId === 'wan2.7-image-pro' && taskKind === 'text_to_image'
    const presetList = allow4K ? ['1K', '2K', '4K'] : ['1K', '2K']
    const ratioLabel = taskKind === 'text_to_image' ? '纯文生图默认正方形' : '跟随当前样例最后一张输入图比例'
    return presetList.map((preset) => ({
      value: preset,
      label: `${preset}（${ratioLabel}）`,
    }))
  }, [modelId, taskKind])

  const activeGroup = useMemo(
    () => qualityGroups.find((group) => group.ratio === ratioChoice) || qualityGroups[0] || null,
    [qualityGroups, ratioChoice]
  )

  const applyTemplate = (ratio: string, quality: ImageQualityLevel) => {
    const group = qualityGroups.find((item) => item.ratio === ratio) || qualityGroups[0]
    const option = group?.options.find((item) => item.quality === quality) || group?.options[0]
    if (!group || !option) return
    setRatioChoice(group.ratio)
    setQualityChoice(option.quality)
    onChange({
      ...value,
      size_mode: 'custom',
      size_preset: undefined,
      custom_width: option.width,
      custom_height: option.height,
    })
  }

  return (
    <Card
      size="small"
      title="Wan2.7 尺寸设置"
      style={{ marginBottom: 16 }}
    >
      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        <Segmented
          block
          value={effectiveSizeMode}
          options={[
            { value: 'custom', label: '自定义宽高（指定比例）' },
            { value: 'preset', label: '规格档位（1K/2K/4K）' },
          ]}
          onChange={(nextMode) => {
            if (nextMode === 'preset') {
              onChange({
                ...value,
                size_mode: 'preset',
                size_preset: effectivePreset,
                custom_width: undefined,
                custom_height: undefined,
              })
              return
            }
            applyTemplate(ratioChoice, qualityChoice)
          }}
        />
        {effectiveSizeMode === 'preset' ? (
          <>
            <Select
              value={effectivePreset}
              style={{ width: '100%' }}
              options={presetOptions}
              onChange={(nextPreset) => onChange({
                ...value,
                size_mode: 'preset',
                size_preset: nextPreset,
                custom_width: undefined,
                custom_height: undefined,
              })}
            />
            <Text type="secondary">
              规格档位只控制像素档位，不指定横竖比例；纯文生图默认正方形，图像编辑会跟随当前样例最后一张输入图比例。
            </Text>
          </>
        ) : (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <Select
                value={activeGroup?.ratio}
                style={{ width: '100%' }}
                options={qualityGroups.map((group) => ({
                  value: group.ratio,
                  label: `${group.ratio} ${group.orientation}`,
                }))}
                onChange={(nextRatio) => {
                  const nextGroup = qualityGroups.find((group) => group.ratio === nextRatio)
                  const nextOption =
                    nextGroup?.options.find((item) => item.quality === qualityChoice) ||
                    nextGroup?.options.find((item) => item.quality === 'medium') ||
                    nextGroup?.options[0]
                  if (nextOption) {
                    applyTemplate(nextRatio, nextOption.quality)
                  }
                }}
              />
              <Select
                value={qualityChoice}
                style={{ width: '100%' }}
                options={(activeGroup?.options || []).map((option) => ({
                  value: option.quality,
                  label: `${option.qualityLabel} ${option.width}×${option.height}`,
                }))}
                onChange={(nextQuality) => applyTemplate(activeGroup?.ratio || ratioChoice, nextQuality as ImageQualityLevel)}
              />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <Input
                value={value.custom_width ?? defaultValues?.custom_width ?? ''}
                readOnly
                style={{ color: token.colorText }}
                placeholder="宽度"
              />
              <Input
                value={value.custom_height ?? defaultValues?.custom_height ?? ''}
                readOnly
                style={{ color: token.colorText }}
                placeholder="高度"
              />
            </div>
            <Text type="secondary">
              清晰度是平台映射到自定义像素模板的快捷项，不是 Wan2.7 模型原生质量参数。开发者模式预览中会看到最终提交的 `size=宽*高`。
            </Text>
          </>
        )}
      </Space>
    </Card>
  )
}

const BenchmarkModelOverrideCard = ({
  projectId,
  modelMeta,
  taskKind,
  dataset,
  baselineParams,
  currentRun,
  value,
  onChange,
}: {
  projectId?: string
  modelMeta: any
  taskKind?: string
  dataset: ImageBenchmarkDataset | null
  baselineParams?: Record<string, any>
  currentRun: ImageBenchmarkRun | null
  value: Record<string, any>
  onChange: (values: Record<string, any>) => void
}) => {
  const modelInfo = useMemo(() => buildModelFormInfo(modelMeta, taskKind), [modelMeta, taskKind])
  const isWan27Model = String(modelMeta.id || '').startsWith('wan2.7-image')
  const datasetCases = useMemo(
    () => [...(dataset?.items || [])].sort((left, right) => (left.sort_order || 0) - (right.sort_order || 0)),
    [dataset?.items]
  )
  const [developerOpen, setDeveloperOpen] = useState(false)
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(datasetCases[0]?.id || null)
  const [previewData, setPreviewData] = useState<{
    loading: boolean
    error?: string
    result?: {
      effective_params: Record<string, any>
      canonical_request: Record<string, any>
      provider_payload: Record<string, any>
      validation_warnings: string[]
    }
  }>({ loading: false })

  useEffect(() => {
    if (selectedCaseId && datasetCases.some((item) => item.id === selectedCaseId)) return
    setSelectedCaseId(datasetCases[0]?.id || null)
  }, [datasetCases, selectedCaseId])

  const selectedCase = useMemo(
    () => datasetCases.find((item) => item.id === selectedCaseId) || null,
    [datasetCases, selectedCaseId]
  )

  const latestRunCell = useMemo(
    () => currentRun?.cell_results?.find((cell) => cell.case_id === selectedCaseId && cell.model_id === modelMeta.id) || null,
    [currentRun?.cell_results, modelMeta.id, selectedCaseId]
  )

  useEffect(() => {
    if (!developerOpen || !projectId || !selectedCase || !taskKind) return
    let cancelled = false
    const timer = window.setTimeout(async () => {
      setPreviewData((prev) => ({ ...prev, loading: true, error: undefined }))
      try {
        const result = await imageBenchmarkApi.previewCell({
          project_id: projectId,
          task_kind: taskKind as any,
          model_id: modelMeta.id,
          case_data: {
            id: selectedCase.id,
            name: selectedCase.name,
            prompt: selectedCase.prompt,
            negative_prompt: selectedCase.negative_prompt,
            tags: selectedCase.tags,
            image_slots: selectedCase.image_slots,
            bbox_list: selectedCase.bbox_list,
          },
          baseline_params: baselineParams || {},
          override_params: value || {},
        })
        if (cancelled) return
        setPreviewData({
          loading: false,
          result,
        })
      } catch (error) {
        if (cancelled) return
        setPreviewData({
          loading: false,
          error: error instanceof Error ? error.message : '预览失败',
        })
      }
    }, 250)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [baselineParams, developerOpen, modelMeta.id, projectId, selectedCase, taskKind, value])

  return (
    <Card key={modelMeta.id} size="small" title={`模型覆盖：${modelMeta.name}`}>
      {isWan27Model && (
        <Wan27SizeOverrideEditor
          modelId={modelMeta.id}
          taskKind={taskKind}
          value={value}
          defaultValues={modelInfo.default_values}
          onChange={onChange}
        />
      )}
      <DynamicModelForm
        modelInfo={modelInfo as any}
        value={value}
        onChange={onChange}
        columns={2}
        excludeParams={isWan27Model ? ['size_mode', 'size_preset', 'custom_width', 'custom_height'] : []}
      />
      <Collapse
        style={{ marginTop: 12 }}
        onChange={(keys) => setDeveloperOpen(Array.isArray(keys) ? keys.includes('developer-mode') : keys === 'developer-mode')}
        items={[
          {
            key: 'developer-mode',
            label: '开发者模式',
            children: (
              <Space direction="vertical" size={16} style={{ width: '100%' }}>
                <div>
                  <Text style={{ display: 'block', marginBottom: 8 }}>预览样例</Text>
                  <Select
                    value={selectedCaseId || undefined}
                    style={{ width: '100%' }}
                    placeholder="选择用于预览 payload 的样例"
                    options={datasetCases.map((item) => ({
                      value: item.id,
                      label: item.name || item.id,
                    }))}
                    onChange={(nextId) => setSelectedCaseId(nextId)}
                  />
                </div>
                {!selectedCase ? (
                  <Alert type="info" showIcon message="当前数据集没有可预览样例" />
                ) : (
                  <>
                    <Card size="small" title="预览下次单元请求体">
                      <Space direction="vertical" size={12} style={{ width: '100%' }}>
                        <Text type="secondary">
                          当前预览样例：{selectedCase.name || selectedCase.id}
                        </Text>
                        {previewData.loading && <Spin />}
                        {previewData.error && (
                          <Alert type="error" showIcon message={previewData.error} />
                        )}
                        {!previewData.loading && !previewData.error && previewData.result?.validation_warnings?.length ? (
                          <Alert
                            type="warning"
                            showIcon
                            message="校验提醒"
                            description={previewData.result.validation_warnings.join('；')}
                          />
                        ) : null}
                        {!previewData.loading && !previewData.error && previewData.result && (
                          <Space direction="vertical" size={12} style={{ width: '100%' }}>
                            <JsonPreviewBlock title="Effective Params（预览）" value={previewData.result.effective_params} />
                            <JsonPreviewBlock title="Canonical Request（预览）" value={previewData.result.canonical_request} />
                            <JsonPreviewBlock title="Provider Payload（预览）" value={previewData.result.provider_payload} />
                          </Space>
                        )}
                      </Space>
                    </Card>
                    {latestRunCell && (
                      <Card size="small" title="上一次运行请求体">
                        <Space direction="vertical" size={12} style={{ width: '100%' }}>
                          <Tag color={statusColorMap[latestRunCell.status] || 'default'}>{latestRunCell.status}</Tag>
                          {latestRunCell.validation_warnings?.length ? (
                            <Alert
                              type="warning"
                              showIcon
                              message="上一次运行校验提醒"
                              description={latestRunCell.validation_warnings.join('；')}
                            />
                          ) : null}
                          <JsonPreviewBlock title="Effective Params（上一次）" value={latestRunCell.effective_params || {}} />
                          <JsonPreviewBlock title="Canonical Request（上一次）" value={latestRunCell.canonical_request || {}} />
                          <JsonPreviewBlock title="Provider Payload（上一次）" value={latestRunCell.provider_payload || {}} />
                        </Space>
                      </Card>
                    )}
                  </>
                )}
              </Space>
            ),
          },
        ]}
      />
    </Card>
  )
}

const ImageBenchmarkPage = () => {
  const { token } = theme.useToken()
  const { projectId } = useParams<{ projectId: string }>()

  const [capabilities, setCapabilities] = useState<ImageBenchmarkCapabilitiesResponse | null>(null)
  const [datasets, setDatasets] = useState<ImageBenchmarkDataset[]>([])
  const [suites, setSuites] = useState<ImageBenchmarkSuite[]>([])
  const [selectedSuiteId, setSelectedSuiteId] = useState<string | null>(null)
  const [draftSuite, setDraftSuite] = useState<ImageBenchmarkSuite | null>(null)
  const [currentRun, setCurrentRun] = useState<ImageBenchmarkRun | null>(null)
  const [loading, setLoading] = useState(true)

  const [suiteModalOpen, setSuiteModalOpen] = useState(false)
  const [suiteFormValues, setSuiteFormValues] = useState({ name: '', description: '', dataset_id: '' })

  const [detailCell, setDetailCell] = useState<ImageBenchmarkCellResult | null>(null)
  const [blockingIssues, setBlockingIssues] = useState<ImageBenchmarkDatasetIssue[]>([])

  const selectedSuite = useMemo(
    () => suites.find((suite) => suite.id === selectedSuiteId) || null,
    [selectedSuiteId, suites]
  )

  const selectedDataset = useMemo(
    () => datasets.find((dataset) => dataset.id === draftSuite?.dataset_id) || null,
    [datasets, draftSuite?.dataset_id]
  )

  const availableModels = useMemo(() => {
    if (!capabilities || !selectedDataset) return []
    return Object.values(capabilities.models).filter((model) => (model.supported_task_kinds || []).includes(selectedDataset.task_kind))
  }, [capabilities, selectedDataset])

  useEffect(() => {
    if (!projectId) return
    const loadData = async () => {
      setLoading(true)
      try {
        const [capabilityRes, datasetRes, suiteRes] = await Promise.all([
          imageBenchmarkApi.getCapabilities(),
          imageBenchmarkApi.listDatasets(projectId),
          imageBenchmarkApi.listSuites(projectId),
        ])
        setCapabilities(capabilityRes)
        setDatasets(datasetRes.datasets)
        setSuites(suiteRes.suites)
        setSelectedSuiteId((prev) => prev && suiteRes.suites.some((suite) => suite.id === prev) ? prev : suiteRes.suites[0]?.id || null)
      } catch (error) {
        if (error instanceof Error) {
          message.error(error.message)
        }
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [projectId])

  useEffect(() => {
    setDraftSuite(cloneSuite(selectedSuite))
  }, [selectedSuite])

  useEffect(() => {
    if (!draftSuite || !selectedDataset) return
    const allowedModelIds = new Set(availableModels.map((model) => model.id))
    const nextSelectedModels = (draftSuite.selected_models || []).filter((modelId) => allowedModelIds.has(modelId))
    if (nextSelectedModels.length !== draftSuite.selected_models.length) {
      setDraftSuite({
        ...draftSuite,
        selected_models: nextSelectedModels,
      })
    }
  }, [availableModels, draftSuite, selectedDataset])

  useEffect(() => {
    if (!selectedSuite?.latest_run_id) {
      setCurrentRun(null)
      return
    }
    const loadRun = async () => {
      try {
        const runRes = await imageBenchmarkApi.getRun(selectedSuite.latest_run_id as string)
        setCurrentRun(runRes.run)
      } catch (error) {
        if (error instanceof Error) {
          message.error(error.message)
        }
      }
    }
    loadRun()
  }, [selectedSuite?.latest_run_id])

  useEffect(() => {
    if (!currentRun || currentRun.status !== 'running') return
    const timer = window.setInterval(async () => {
      try {
        const runRes = await imageBenchmarkApi.getRun(currentRun.id)
        setCurrentRun(runRes.run)
        if (runRes.run.status !== 'running') {
          const suiteRes = await imageBenchmarkApi.getSuite(runRes.run.suite_id)
          setSuites((prev) => prev.map((item) => item.id === suiteRes.suite.id ? suiteRes.suite : item))
        }
      } catch {
        // ignore polling error
      }
    }, 3000)
    return () => window.clearInterval(timer)
  }, [currentRun])

  const refreshSuites = async (preferredId?: string | null) => {
    if (!projectId) return
    const suiteRes = await imageBenchmarkApi.listSuites(projectId)
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
      const result = await imageBenchmarkApi.createSuite({
        project_id: projectId,
        name: suiteFormValues.name,
        description: suiteFormValues.description,
        dataset_id: suiteFormValues.dataset_id,
        baseline_params: {},
      })
      setSuiteModalOpen(false)
      await refreshSuites(result.suite.id)
      message.success('测评任务已创建')
    } catch (error) {
      if (error instanceof Error) {
        message.error(error.message)
      }
    }
  }

  const handleSaveSuite = async () => {
    if (!draftSuite) return
    try {
      const result = await imageBenchmarkApi.updateSuite(draftSuite.id, {
        name: draftSuite.name,
        description: draftSuite.description,
        dataset_id: draftSuite.dataset_id,
        selected_models: draftSuite.selected_models,
        baseline_params: {},
        model_overrides: draftSuite.model_overrides,
      })
      await refreshSuites(result.suite.id)
      message.success('测评配置已保存')
    } catch (error) {
      if (error instanceof Error) {
        message.error(error.message)
      }
    }
  }

  const handleDeleteSuite = async (suiteId: string) => {
    try {
      await imageBenchmarkApi.deleteSuite(suiteId)
      await refreshSuites(null)
      message.success('测评任务已删除')
    } catch (error) {
      if (error instanceof Error) {
        message.error(error.message)
      }
    }
  }

  const handleRunSuite = async () => {
    if (!draftSuite) return
    try {
      setBlockingIssues([])
      const savedSuite = await imageBenchmarkApi.updateSuite(draftSuite.id, {
        name: draftSuite.name,
        description: draftSuite.description,
        dataset_id: draftSuite.dataset_id,
        selected_models: draftSuite.selected_models,
        baseline_params: {},
        model_overrides: draftSuite.model_overrides,
      })
      const result = await imageBenchmarkApi.runSuite(draftSuite.id)
      setCurrentRun(result.run)
      setSuites((prev) => prev.map((item) => {
        if (item.id === savedSuite.suite.id) return result.suite
        return item
      }))
      setSelectedSuiteId(result.suite.id)
      message.success('测评已开始运行')
    } catch (error) {
      const apiError = error as ApiError
      if (apiError?.data?.blocking_issues) {
        setBlockingIssues(apiError.data.blocking_issues)
      }
      if (error instanceof Error) {
        message.error(error.message)
      }
    }
  }

  const handleExportMarkdown = async () => {
    if (!currentRun) return
    try {
      const result = await imageBenchmarkApi.exportRunMarkdown(currentRun.id)
      downloadTextFile(result.filename, result.content, 'text/markdown;charset=utf-8')
      message.success('Markdown 报告已导出')
    } catch (error) {
      if (error instanceof Error) {
        message.error(error.message)
      }
    }
  }

  const handleExportHtml = () => {
    if (!currentRun) return
    const html = buildRunHtmlReport(currentRun, selectedSuite)
    downloadTextFile(`image_benchmark_${currentRun.id}.html`, html, 'text/html;charset=utf-8')
    message.success('HTML 报告已导出')
  }

  const openShareUrl = (shareUrl: string) => {
    const absoluteUrl = `${window.location.origin}${shareUrl}`
    window.open(absoluteUrl, '_blank', 'noopener,noreferrer')
  }

  const handleEnableShare = async () => {
    if (!draftSuite || !currentRun) return
    try {
      const result = await imageBenchmarkApi.enableSuiteShare(draftSuite.id)
      setSuites((prev) => prev.map((item) => item.id === result.suite.id ? result.suite : item))
      setDraftSuite(result.suite)
      setSelectedSuiteId(result.suite.id)
      openShareUrl(result.share_url)
      message.success('分享链接已开启')
    } catch (error) {
      if (error instanceof Error) {
        message.error(error.message)
      }
    }
  }

  const handleOpenShare = () => {
    if (!draftSuite?.share_token) return
    openShareUrl(`/image-benchmark/share/${draftSuite.share_token}`)
  }

  const handleDisableShare = async () => {
    if (!draftSuite) return
    try {
      const result = await imageBenchmarkApi.disableSuiteShare(draftSuite.id)
      setSuites((prev) => prev.map((item) => item.id === result.suite.id ? result.suite : item))
      setDraftSuite(result.suite)
      setSelectedSuiteId(result.suite.id)
      message.success('分享链接已关闭')
    } catch (error) {
      if (error instanceof Error) {
        message.error(error.message)
      }
    }
  }

  const handleRetryFailedRun = async () => {
    if (!currentRun) return
    try {
      const result = await imageBenchmarkApi.retryFailedRun(currentRun.id)
      setCurrentRun(result.run)
      setSuites((prev) => prev.map((item) => item.id === result.suite.id ? result.suite : item))
      setSelectedSuiteId(result.suite.id)
      message.success('已开始重试失败和未支持任务')
    } catch (error) {
      if (error instanceof Error) {
        message.error(error.message)
      }
    }
  }

  const resultMap = useMemo(() => {
    const map = new Map<string, ImageBenchmarkCellResult>()
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
        key: 'name',
        fixed: 'left' as const,
        width: 160,
      },
      {
        title: 'Prompt',
        dataIndex: 'prompt',
        key: 'prompt',
        fixed: 'left' as const,
        width: 260,
        render: (value: string) => <div style={{ whiteSpace: 'pre-wrap' }}>{value || <Text type="secondary">空</Text>}</div>,
      },
      {
        title: '输入图',
        dataIndex: 'input_images',
        key: 'input_images',
        fixed: 'left' as const,
        width: 180,
        render: (_value: Array<{ url: string }>, record: any) => (
          <Space wrap>
            {getCaseImages(record).map((image: any) => (
              <Image
                key={image.url}
                src={image.url}
                width={56}
                height={56}
                style={{ objectFit: 'cover', borderRadius: 8 }}
              />
            ))}
          </Space>
        ),
      },
    ]

    const modelColumns = (currentRun?.model_snapshots || []).map((model) => ({
      title: model.name || model.id,
      key: model.id,
      width: 260,
      render: (_: unknown, record: any) => {
        const cell = resultMap.get(`${record.id}__${model.id}`)
        if (!cell) {
          return <Text type="secondary">未运行</Text>
        }
        return (
          <Space direction="vertical" size={8} style={{ width: '100%' }}>
            <Tag color={statusColorMap[cell.status] || 'default'}>{cell.status}</Tag>
            {cell.error_message && (
              <Text type="danger" style={{ whiteSpace: 'pre-wrap' }}>{cell.error_message}</Text>
            )}
            {cell.output_images?.length > 0 && (
              <Space wrap>
                {cell.output_images.map((image, index) => image.url ? (
                  <Image
                    key={`${cell.id}-${index}`}
                    src={image.url}
                    width={72}
                    height={72}
                    style={{ objectFit: 'cover', borderRadius: 8 }}
                  />
                ) : (
                  <Tag key={`${cell.id}-${index}`} color="error">失败</Tag>
                ))}
              </Space>
            )}
            <Button size="small" onClick={() => setDetailCell(cell)}>查看详情</Button>
          </Space>
        )
      },
    }))

    return [...baseColumns, ...modelColumns]
  }, [currentRun?.model_snapshots, resultMap])

  if (loading) {
    return (
      <div style={{ padding: 48, textAlign: 'center' }}>
        <Spin size="large" />
      </div>
    )
  }

  return (
    <div style={{ padding: 24 }}>
      <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <Title level={3} style={{ margin: 0, color: token.colorText }}>图片测评</Title>
          <Text type="secondary">选择数据集、模型和参数，运行横向矩阵测评并导出 Markdown 报告。</Text>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreateSuiteModal}>
          新建测评任务
        </Button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: 24, alignItems: 'start' }}>
        <Card title="测评任务">
          {suites.length === 0 ? (
            <Empty description="暂无测评任务" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          ) : (
            <Space direction="vertical" style={{ width: '100%' }}>
              {suites.map((suite) => (
                <Card
                  key={suite.id}
                  size="small"
                  hoverable
                  onClick={() => setSelectedSuiteId(suite.id)}
                  style={{
                    borderColor: suite.id === selectedSuiteId ? token.colorPrimary : token.colorBorderSecondary,
                  }}
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
          <Card>
            <Empty description="请选择或创建一个测评任务" />
          </Card>
        ) : (
          <Space direction="vertical" size={24} style={{ width: '100%' }}>
            <Card
              title="测评配置"
              extra={
                <Space>
                  <Popconfirm
                    title="确定删除该测评任务吗？"
                    description="删除后历史 run 也会一并删除。"
                    onConfirm={() => handleDeleteSuite(draftSuite.id)}
                  >
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
                {!datasets.length && (
                  <Alert type="warning" showIcon message="暂无数据集" description="请先在“数据集”模块创建数据集。" />
                )}

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                  <div>
                    <Text style={{ display: 'block', marginBottom: 8 }}>测评任务名称</Text>
                    <Input
                      value={draftSuite.name}
                      onChange={(event) => setDraftSuite({ ...draftSuite, name: event.target.value })}
                    />
                  </div>
                  <div>
                    <Text style={{ display: 'block', marginBottom: 8 }}>选择数据集</Text>
                    <Select
                      value={draftSuite.dataset_id}
                      style={{ width: '100%' }}
                      options={datasets.map((dataset) => ({
                        value: dataset.id,
                        label: `${dataset.name} (${getTaskKindLabel(dataset.task_kind)})`,
                      }))}
                      onChange={(value) => setDraftSuite({ ...draftSuite, dataset_id: value })}
                    />
                  </div>
                </div>

                <div>
                  <Text style={{ display: 'block', marginBottom: 8 }}>描述</Text>
                  <TextArea
                    rows={3}
                    value={draftSuite.description}
                    onChange={(event) => setDraftSuite({ ...draftSuite, description: event.target.value })}
                  />
                </div>

                <Card size="small" title="模型选择">
                  <Select
                    mode="multiple"
                    style={{ width: '100%' }}
                    value={draftSuite.selected_models}
                    placeholder="选择要参与测评的模型"
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
                          taskKind={selectedDataset?.task_kind}
                          dataset={selectedDataset}
                          baselineParams={draftSuite.baseline_params}
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
                    <Button icon={<ReloadOutlined />} onClick={handleRetryFailedRun}>
                      重试失败/未支持任务
                    </Button>
                  )}
                  {currentRun && (
                    <Button icon={<DownloadOutlined />} onClick={handleExportMarkdown}>
                      导出 Markdown
                    </Button>
                  )}
                  {currentRun && (
                    <Button icon={<FileTextOutlined />} onClick={handleExportHtml}>
                      导出 HTML
                    </Button>
                  )}
                  {draftSuite.share_enabled && draftSuite.share_token ? (
                    <>
                      <Button icon={<LinkOutlined />} onClick={handleOpenShare}>
                        打开分享页
                      </Button>
                      <Popconfirm
                        title="关闭分享链接吗？"
                        description="关闭后，已发出的公开链接将无法继续访问。"
                        onConfirm={handleDisableShare}
                      >
                        <Button danger>关闭分享</Button>
                      </Popconfirm>
                    </>
                  ) : (
                    <Button icon={<ShareAltOutlined />} onClick={handleEnableShare} disabled={!currentRun}>
                      {currentRun ? '分享结果' : '运行后可分享'}
                    </Button>
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
                    <Statistic title="失败单元" value={currentRun.stats.failure_count || 0} />
                  </div>

                  {getManualRetryCount(currentRun) > 0 && currentRun.status !== 'running' && (
                    <Alert
                      type="warning"
                      showIcon
                      message="存在失败或未支持任务"
                      description="限流类失败会先自动重试；仍失败或因预检暂时失败而标为未支持的单元，可以再次提交。"
                    />
                  )}

                  <Table
                    rowKey="id"
                    dataSource={(currentRun.dataset_snapshot.items || []).slice().sort((a: any, b: any) => (a.sort_order || 0) - (b.sort_order || 0))}
                    columns={matrixColumns as any}
                    pagination={false}
                    scroll={{ x: 1200 }}
                  />
                </Space>
              )}
            </Card>
          </Space>
        )}
      </div>

      <Modal
        title="新建测评任务"
        open={suiteModalOpen}
        onOk={handleCreateSuite}
        onCancel={() => setSuiteModalOpen(false)}
        okText="创建"
        cancelText="取消"
      >
        <Space direction="vertical" style={{ width: '100%' }} size={16}>
          <div>
            <Text style={{ display: 'block', marginBottom: 8 }}>名称</Text>
            <Input
              value={suiteFormValues.name}
              onChange={(event) => setSuiteFormValues({ ...suiteFormValues, name: event.target.value })}
            />
          </div>
          <div>
            <Text style={{ display: 'block', marginBottom: 8 }}>描述</Text>
            <TextArea
              rows={3}
              value={suiteFormValues.description}
              onChange={(event) => setSuiteFormValues({ ...suiteFormValues, description: event.target.value })}
            />
          </div>
          <div>
            <Text style={{ display: 'block', marginBottom: 8 }}>数据集</Text>
            <Select
              value={suiteFormValues.dataset_id}
              style={{ width: '100%' }}
              options={datasets.map((dataset) => ({
                value: dataset.id,
                label: `${dataset.name} (${getTaskKindLabel(dataset.task_kind)})`,
              }))}
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
        width={960}
      >
        {detailCell && (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Tag color={statusColorMap[detailCell.status] || 'default'}>{detailCell.status}</Tag>
            {detailCell.validation_warnings?.length > 0 && (
              <Alert
                type="warning"
                showIcon
                message="校验提醒"
                description={detailCell.validation_warnings.join('；')}
              />
            )}
            <Card size="small" title="Effective Params">
              <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{JSON.stringify(detailCell.effective_params || {}, null, 2)}</pre>
            </Card>
            <Card size="small" title="重试信息">
              <div>总尝试次数：{detailCell.attempt_count || 1}</div>
              <div>自动重试次数：{detailCell.auto_retry_count || 0}</div>
            </Card>
            <Card size="small" title="任务追踪 IDs">
              <Space direction="vertical" size={12} style={{ width: '100%' }}>
                <div>
                  <Text strong>Task IDs</Text>
                  {detailCell.task_ids?.length ? (
                    <pre style={{ margin: '8px 0 0', whiteSpace: 'pre-wrap' }}>{detailCell.task_ids.join('\n')}</pre>
                  ) : (
                    <div><Text type="secondary">暂无</Text></div>
                  )}
                </div>
                <div>
                  <Text strong>Request IDs</Text>
                  {detailCell.request_ids?.length ? (
                    <pre style={{ margin: '8px 0 0', whiteSpace: 'pre-wrap' }}>{detailCell.request_ids.join('\n')}</pre>
                  ) : (
                    <div><Text type="secondary">暂无</Text></div>
                  )}
                </div>
              </Space>
            </Card>
            <Card size="small" title="Canonical Request">
              <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{JSON.stringify(detailCell.canonical_request || {}, null, 2)}</pre>
            </Card>
            <Card size="small" title="Provider Payload">
              <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{JSON.stringify(detailCell.provider_payload || {}, null, 2)}</pre>
            </Card>
          </Space>
        )}
      </Modal>

      <Modal
        title="测评运行已阻止"
        open={blockingIssues.length > 0}
        onCancel={() => setBlockingIssues([])}
        footer={[
          <Button key="close" type="primary" onClick={() => setBlockingIssues([])}>
            我知道了
          </Button>,
        ]}
        width={760}
      >
        <Alert
          type="warning"
          showIcon
          message="当前数据集存在图片槽位空缺，必须先补齐后才能开始测评"
          description="后端已阻止本次运行，以避免请求体中的图片数组顺序与槽位语义不一致。"
          style={{ marginBottom: 16 }}
        />
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          {blockingIssues.map((issue) => (
            <Card key={`${issue.item_id}-${issue.missing_positions.join('-')}`} size="small">
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
                <Text strong>{issue.item_name}</Text>
                <Tag color="warning">缺少位置：{issue.missing_positions.join('、')}</Tag>
              </div>
            </Card>
          ))}
        </Space>
      </Modal>
    </div>
  )
}

export default ImageBenchmarkPage
