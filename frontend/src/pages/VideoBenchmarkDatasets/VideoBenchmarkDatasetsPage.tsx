import { useEffect, useMemo, useState } from 'react'
import type { Dispatch, SetStateAction } from 'react'
import { useParams } from 'react-router-dom'
import {
  Alert,
  Button,
  Card,
  Empty,
  Form,
  Image,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  Upload,
  message,
  theme,
} from 'antd'
import {
  DeleteOutlined,
  DownloadOutlined,
  EditOutlined,
  ImportOutlined,
  PictureOutlined,
  PlusOutlined,
  SaveOutlined,
  UploadOutlined,
} from '@ant-design/icons'
import type { UploadFile, UploadProps } from 'antd'
import {
  AudioItem,
  GalleryImage,
  VideoBenchmarkDataset,
  VideoBenchmarkDatasetIssue,
  VideoBenchmarkDatasetItem,
  VideoBenchmarkMediaAsset,
  audioApi,
  galleryApi,
  videoBenchmarkApi,
} from '../../services/api'

const { TextArea } = Input
const { Title, Text } = Typography

type BulkTextMode = 'single' | 'list' | 'clear'
type BulkTagMode = 'replace' | 'append' | 'remove' | 'clear'
type MediaApplyMode = 'single' | 'list' | 'clear'
type FrameSourceMode = 'gallery' | 'upload'
type AudioApplyMode = 'single' | 'list' | 'url_list' | 'clear'
type BulkField = 'name' | 'prompt' | 'negative_prompt' | 'tags' | 'duration' | 'first_frame' | 'audio'

const cloneDataset = (dataset: VideoBenchmarkDataset | null) => (
  dataset ? JSON.parse(JSON.stringify(dataset)) as VideoBenchmarkDataset : null
)

const normalizeItems = (items: VideoBenchmarkDatasetItem[]) => (
  items.map((item, index) => ({ ...item, sort_order: index }))
)

const downloadTextFile = (filename: string, content: string, mimeType: string) => {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  window.setTimeout(() => {
    URL.revokeObjectURL(url)
    anchor.remove()
  }, 30000)
}

const parseLines = (value: string) => (
  value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean)
)

const buildImageAsset = (image: GalleryImage): VideoBenchmarkMediaAsset => ({
  url: image.url,
  name: image.name,
  source_label: '图库',
})

const buildAudioAsset = (audio: AudioItem): VideoBenchmarkMediaAsset => ({
  url: audio.url,
  name: audio.name,
  duration: audio.duration ?? null,
  source_label: '音频库',
})

const buildUrlAsset = (url: string, name = '', sourceLabel = 'URL'): VideoBenchmarkMediaAsset => ({
  url,
  name,
  source_label: sourceLabel,
})

const analyzeDatasetDraft = (dataset: VideoBenchmarkDataset | null): {
  warnings: VideoBenchmarkDatasetIssue[]
  blocking_issues: VideoBenchmarkDatasetIssue[]
} => {
  const issues = (dataset?.items || [])
    .filter((item) => !item.first_frame?.url)
    .map((item) => ({
      item_id: item.id,
      item_name: item.name || `样例 ${item.sort_order + 1}`,
      missing_fields: ['first_frame'],
      message: '缺首帧图，无法开始首帧生视频测评',
    }))
  return { warnings: issues, blocking_issues: issues }
}

const VideoBenchmarkDatasetsPage = () => {
  const { token } = theme.useToken()
  const { projectId } = useParams<{ projectId: string }>()

  const [datasets, setDatasets] = useState<VideoBenchmarkDataset[]>([])
  const [galleryImages, setGalleryImages] = useState<GalleryImage[]>([])
  const [galleryUploadEnabled, setGalleryUploadEnabled] = useState(false)
  const [audios, setAudios] = useState<AudioItem[]>([])
  const [selectedDatasetId, setSelectedDatasetId] = useState<string | null>(null)
  const [draftDataset, setDraftDataset] = useState<VideoBenchmarkDataset | null>(null)
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [datasetModalOpen, setDatasetModalOpen] = useState(false)
  const [itemModalOpen, setItemModalOpen] = useState(false)
  const [editingItemId, setEditingItemId] = useState<string | null>(null)
  const [uploadFiles, setUploadFiles] = useState<UploadFile[]>([])
  const [promptImportOpen, setPromptImportOpen] = useState(false)
  const [promptImportText, setPromptImportText] = useState('')
  const [bulkAddFramesOpen, setBulkAddFramesOpen] = useState(false)
  const [bulkAddFramesUploadFiles, setBulkAddFramesUploadFiles] = useState<UploadFile[]>([])
  const [fillFirstFrameOpen, setFillFirstFrameOpen] = useState(false)
  const [fillFirstFrameUploadFiles, setFillFirstFrameUploadFiles] = useState<UploadFile[]>([])
  const [bulkEditOpen, setBulkEditOpen] = useState(false)
  const [bulkEditUploadFiles, setBulkEditUploadFiles] = useState<UploadFile[]>([])
  const [datasetForm] = Form.useForm()
  const [itemForm] = Form.useForm()
  const [bulkAddFramesForm] = Form.useForm()
  const [fillFirstFrameForm] = Form.useForm()
  const [bulkEditForm] = Form.useForm()

  const selectedDataset = useMemo(
    () => datasets.find((dataset) => dataset.id === selectedDatasetId) || null,
    [datasets, selectedDatasetId]
  )

  const selectedRowsInOrder = useMemo(() => {
    if (!draftDataset) return []
    const selectedSet = new Set(selectedRowKeys)
    return draftDataset.items.filter((item) => selectedSet.has(item.id))
  }, [draftDataset, selectedRowKeys])

  const localValidation = useMemo(
    () => analyzeDatasetDraft(draftDataset),
    [draftDataset]
  )

  const warningMap = useMemo(
    () => new Map(localValidation.warnings.map((issue) => [issue.item_id, issue])),
    [localValidation.warnings]
  )

  const bulkAddFrameSourceMode = Form.useWatch('source_mode', bulkAddFramesForm) as FrameSourceMode | undefined
  const fillFirstFrameApplyMode = Form.useWatch('apply_mode', fillFirstFrameForm) as MediaApplyMode | undefined
  const fillFirstFrameSourceMode = Form.useWatch('source_mode', fillFirstFrameForm) as FrameSourceMode | undefined
  const bulkEditField = Form.useWatch('field', bulkEditForm) as BulkField | undefined
  const bulkEditTextMode = Form.useWatch('text_mode', bulkEditForm) as BulkTextMode | undefined
  const bulkEditTagMode = Form.useWatch('tag_mode', bulkEditForm) as BulkTagMode | undefined
  const bulkEditDurationMode = Form.useWatch('duration_mode', bulkEditForm) as BulkTextMode | undefined
  const bulkEditFrameMode = Form.useWatch('frame_mode', bulkEditForm) as MediaApplyMode | undefined
  const bulkEditFrameSourceMode = Form.useWatch('frame_source_mode', bulkEditForm) as FrameSourceMode | undefined
  const bulkEditAudioMode = Form.useWatch('audio_mode', bulkEditForm) as AudioApplyMode | undefined

  useEffect(() => {
    if (!projectId) return
    const loadData = async () => {
      setLoading(true)
      try {
        const [datasetRes, galleryRes, audioRes, ossStatus] = await Promise.all([
          videoBenchmarkApi.listDatasets(projectId),
          galleryApi.list(projectId),
          audioApi.list(projectId),
          galleryApi.getOSSStatus(),
        ])
        setDatasets(datasetRes.datasets)
        setGalleryImages(galleryRes.images)
        setAudios(audioRes.audios)
        setGalleryUploadEnabled(!!ossStatus.enabled)
        setSelectedDatasetId((prev) => (
          prev && datasetRes.datasets.some((item) => item.id === prev)
            ? prev
            : datasetRes.datasets[0]?.id || null
        ))
      } catch (error) {
        if (error instanceof Error) message.error(error.message)
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [projectId])

  useEffect(() => {
    if (!selectedDatasetId) {
      setDraftDataset(null)
      setSelectedRowKeys([])
      return
    }
    const loadDataset = async () => {
      try {
        const result = await videoBenchmarkApi.getDataset(selectedDatasetId)
        setDraftDataset(cloneDataset(result.dataset))
        setSelectedRowKeys([])
      } catch (error) {
        if (error instanceof Error) message.error(error.message)
      }
    }
    loadDataset()
  }, [selectedDatasetId])

  const refreshDatasets = async (preferredId?: string | null) => {
    if (!projectId) return
    const result = await videoBenchmarkApi.listDatasets(projectId)
    setDatasets(result.datasets)
    const nextId = preferredId ?? selectedDatasetId
    setSelectedDatasetId(
      nextId && result.datasets.some((item) => item.id === nextId)
        ? nextId
        : result.datasets[0]?.id || null
    )
  }

  const openCreateDatasetModal = () => {
    datasetForm.resetFields()
    setDatasetModalOpen(true)
  }

  const handleCreateDataset = async () => {
    if (!projectId) return
    try {
      const values = await datasetForm.validateFields()
      const result = await videoBenchmarkApi.createDataset({
        project_id: projectId,
        name: values.name,
        description: values.description,
        task_kind: 'image_to_video',
        items: [],
      })
      setDatasetModalOpen(false)
      await refreshDatasets(result.dataset.id)
      message.success('视频数据集已创建')
    } catch (error) {
      if (error instanceof Error) message.error(error.message)
    }
  }

  const updateDraftItems = (updater: (items: VideoBenchmarkDatasetItem[]) => VideoBenchmarkDatasetItem[]) => {
    if (!draftDataset) return
    setDraftDataset({
      ...draftDataset,
      items: normalizeItems(updater(draftDataset.items)),
    })
  }

  const handleSaveDataset = async () => {
    if (!draftDataset) return
    try {
      const result = await videoBenchmarkApi.updateDataset(draftDataset.id, {
        name: draftDataset.name,
        description: draftDataset.description,
        items: normalizeItems(draftDataset.items).map((item) => ({
          id: item.id,
          name: item.name,
          prompt: item.prompt,
          negative_prompt: item.negative_prompt,
          tags: item.tags,
          first_frame: item.first_frame,
          audio: item.audio,
          duration: item.duration,
        })),
      })
      setDraftDataset(cloneDataset(result.dataset))
      await refreshDatasets(result.dataset.id)
      if (result.warnings?.length) {
        message.warning(`视频数据集已保存，但有 ${result.warnings.length} 条样例缺少首帧图`)
      } else {
        message.success('视频数据集已保存')
      }
    } catch (error) {
      if (error instanceof Error) message.error(error.message)
    }
  }

  const handleDeleteDataset = async (datasetId: string) => {
    try {
      await videoBenchmarkApi.deleteDataset(datasetId)
      await refreshDatasets(null)
      message.success('视频数据集已删除')
    } catch (error) {
      if (error instanceof Error) message.error(error.message)
    }
  }

  const handleExportDataset = async () => {
    if (!draftDataset) return
    try {
      const payload = await videoBenchmarkApi.exportDataset(draftDataset.id)
      downloadTextFile(`${draftDataset.name || 'video_dataset'}.json`, JSON.stringify(payload, null, 2), 'application/json')
      message.success('视频数据集 JSON 已导出')
    } catch (error) {
      if (error instanceof Error) message.error(error.message)
    }
  }

  const importUploadProps: UploadProps = {
    accept: '.json,application/json',
    showUploadList: false,
    beforeUpload: async (file) => {
      if (!projectId) return Upload.LIST_IGNORE
      try {
        const data = JSON.parse(await file.text())
        const result = await videoBenchmarkApi.importDataset({ project_id: projectId, data })
        await refreshDatasets(result.dataset.id)
        message.success('视频数据集导入成功')
      } catch (error) {
        if (error instanceof Error) message.error(error.message)
      }
      return Upload.LIST_IGNORE
    },
  }

  const openItemModal = (item?: VideoBenchmarkDatasetItem) => {
    setEditingItemId(item?.id || null)
    setUploadFiles([])
    itemForm.setFieldsValue({
      name: item?.name || '',
      prompt: item?.prompt || '',
      negative_prompt: item?.negative_prompt || '',
      tags: item?.tags || [],
      first_frame_url: item?.first_frame?.url || '',
      first_frame_gallery: item?.first_frame?.url,
      first_frame_name: item?.first_frame?.name || '',
      audio_url: item?.audio?.url || '',
      audio_select: item?.audio?.url,
      audio_name: item?.audio?.name || '',
      duration: item?.duration ?? null,
    })
    setItemModalOpen(true)
  }

  const uploadFilesToGallery = async (uploadFileList: UploadFile[]) => {
    if (!projectId) return []
    const actualFiles: File[] = []
    uploadFileList.forEach((file) => {
      if (file.originFileObj) {
        actualFiles.push(file.originFileObj as File)
      } else if (file instanceof File) {
        actualFiles.push(file)
      }
    })
    if (!actualFiles.length) return []
    const result = await galleryApi.uploadFiles(projectId, actualFiles)
    if (result.images?.length) {
      const galleryRes = await galleryApi.list(projectId)
      setGalleryImages(galleryRes.images)
    }
    if (result.error_count) {
      message.warning(`有 ${result.error_count} 张首帧图上传失败`)
    }
    return result.images || []
  }

  const resolveFirstFramesForSource = async (
    sourceMode: FrameSourceMode,
    galleryUrls: string[],
    files: UploadFile[],
  ): Promise<VideoBenchmarkMediaAsset[]> => {
    if (sourceMode === 'gallery') {
      return galleryUrls
        .map((url) => galleryImages.find((image) => image.url === url))
        .filter((image): image is GalleryImage => !!image)
        .map(buildImageAsset)
    }
    const uploadedImages = await uploadFilesToGallery(files)
    return uploadedImages.map(buildImageAsset)
  }

  const resolveUploadedFirstFrame = async (): Promise<VideoBenchmarkMediaAsset | null> => {
    if (!projectId || !uploadFiles.length) return null
    const images = await uploadFilesToGallery(uploadFiles.slice(0, 1))
    if (images[0]) {
      return buildImageAsset(images[0])
    }
    throw new Error('首帧图上传失败')
  }

  const handleSaveItem = async () => {
    if (!draftDataset) return
    try {
      const values = await itemForm.validateFields()
      const galleryImage = galleryImages.find((image) => image.url === values.first_frame_gallery)
      const uploadedImage = galleryImage ? null : await resolveUploadedFirstFrame()
      const firstFrame: VideoBenchmarkMediaAsset | null = galleryImage
        ? buildImageAsset(galleryImage)
        : uploadedImage || (values.first_frame_url ? {
          url: values.first_frame_url,
          name: values.first_frame_name || '',
          source_label: 'URL',
        } : null)
      const audioItem = audios.find((audio) => audio.url === values.audio_select)
      const audioAsset: VideoBenchmarkMediaAsset | null = audioItem
        ? buildAudioAsset(audioItem)
        : values.audio_url ? {
          url: values.audio_url,
          name: values.audio_name || '',
          source_label: 'URL',
        } : null
      const nextItem: VideoBenchmarkDatasetItem = {
        id: editingItemId || `temp-${Date.now()}`,
        name: values.name || '',
        prompt: values.prompt || '',
        negative_prompt: values.negative_prompt || '',
        tags: values.tags || [],
        first_frame: firstFrame,
        audio: audioAsset,
        duration: values.duration ?? null,
        sort_order: 0,
      }
      const nextItems = editingItemId
        ? draftDataset.items.map((item) => (item.id === editingItemId ? nextItem : item))
        : [...draftDataset.items, nextItem]
      setDraftDataset({ ...draftDataset, items: normalizeItems(nextItems) })
      setItemModalOpen(false)
      itemForm.resetFields()
      setUploadFiles([])
    } catch (error) {
      if (error instanceof Error) message.error(error.message)
    }
  }

  const handlePromptImport = () => {
    if (!draftDataset) return
    const prompts = promptImportText
      .split(/\r?\n/)
      .map((item) => item.trim())
      .filter(Boolean)
    if (!prompts.length) {
      message.warning('请至少输入一条 prompt')
      return
    }
    const nextItems = [...draftDataset.items]
    prompts.forEach((prompt, index) => {
      nextItems.push({
        id: `temp-${Date.now()}-${index}`,
        name: `样例 ${nextItems.length + 1}`,
        prompt,
        negative_prompt: '',
        tags: [],
        first_frame: null,
        audio: null,
        duration: null,
        sort_order: nextItems.length,
      })
    })
    setDraftDataset({ ...draftDataset, items: normalizeItems(nextItems) })
    setPromptImportText('')
    setPromptImportOpen(false)
  }

  const handleBulkAddFirstFrames = async () => {
    if (!draftDataset) return
    try {
      const values = await bulkAddFramesForm.validateFields()
      const sourceMode = values.source_mode as FrameSourceMode
      const frames = await resolveFirstFramesForSource(sourceMode, values.gallery_urls || [], bulkAddFramesUploadFiles)
      if (!frames.length) {
        message.warning('请先选择首帧图')
        return
      }
      const nextItems = [...draftDataset.items]
      frames.forEach((frame, index) => {
        nextItems.push({
          id: `temp-${Date.now()}-${index}`,
          name: frame.name || `样例 ${nextItems.length + 1}`,
          prompt: '',
          negative_prompt: '',
          tags: [],
          first_frame: frame,
          audio: null,
          duration: null,
          sort_order: nextItems.length,
        })
      })
      setDraftDataset({ ...draftDataset, items: normalizeItems(nextItems) })
      setBulkAddFramesOpen(false)
      bulkAddFramesForm.resetFields()
      setBulkAddFramesUploadFiles([])
    } catch (error) {
      if (error instanceof Error) message.error(error.message)
    }
  }

  const applyFirstFrameBulkEdit = async ({
    applyMode,
    sourceMode,
    galleryUrls,
    uploadFileList,
  }: {
    applyMode: MediaApplyMode
    sourceMode?: FrameSourceMode
    galleryUrls?: string[]
    uploadFileList?: UploadFile[]
  }) => {
    if (!draftDataset || !selectedRowsInOrder.length) return
    if (applyMode === 'clear') {
      updateDraftItems((items) => items.map((item) => (
        selectedRowKeys.includes(item.id) ? { ...item, first_frame: null } : item
      )))
      return
    }
    const frames = await resolveFirstFramesForSource(sourceMode || 'gallery', galleryUrls || [], uploadFileList || [])
    if (!frames.length) {
      message.warning('请先选择首帧图')
      return
    }
    if (applyMode === 'single') {
      const firstFrame = frames[0]
      updateDraftItems((items) => items.map((item) => (
        selectedRowKeys.includes(item.id) ? { ...item, first_frame: firstFrame } : item
      )))
      return
    }
    if (frames.length !== selectedRowsInOrder.length) {
      throw new Error('列表模式下，首帧图数量必须与选中样例数完全一致')
    }
    const frameMap = new Map<string, VideoBenchmarkMediaAsset>()
    selectedRowsInOrder.forEach((item, index) => {
      frameMap.set(item.id, frames[index])
    })
    updateDraftItems((items) => items.map((item) => (
      selectedRowKeys.includes(item.id)
        ? { ...item, first_frame: frameMap.get(item.id) || null }
        : item
    )))
  }

  const handleFillFirstFrame = async () => {
    try {
      const values = await fillFirstFrameForm.validateFields()
      await applyFirstFrameBulkEdit({
        applyMode: values.apply_mode as MediaApplyMode,
        sourceMode: values.source_mode,
        galleryUrls: values.gallery_urls,
        uploadFileList: fillFirstFrameUploadFiles,
      })
      setFillFirstFrameOpen(false)
      fillFirstFrameForm.resetFields()
      setFillFirstFrameUploadFiles([])
    } catch (error) {
      if (error instanceof Error) message.error(error.message)
    }
  }

  const applyTextBulkEdit = (field: 'name' | 'prompt' | 'negative_prompt', values: any) => {
    const mode = values.text_mode as BulkTextMode
    if (mode === 'clear') {
      updateDraftItems((items) => items.map((item) => (
        selectedRowKeys.includes(item.id) ? { ...item, [field]: '' } : item
      )))
      return
    }
    if (mode === 'single') {
      const textValue = values.single_text || ''
      updateDraftItems((items) => items.map((item) => (
        selectedRowKeys.includes(item.id) ? { ...item, [field]: textValue } : item
      )))
      return
    }
    const lines = parseLines(values.list_text || '')
    if (lines.length !== selectedRowsInOrder.length) {
      throw new Error('列表模式下，文本条目数量必须与选中样例数完全一致')
    }
    const textMap = new Map<string, string>()
    selectedRowsInOrder.forEach((item, index) => {
      textMap.set(item.id, lines[index])
    })
    updateDraftItems((items) => items.map((item) => (
      selectedRowKeys.includes(item.id) ? { ...item, [field]: textMap.get(item.id) || '' } : item
    )))
  }

  const applyDurationBulkEdit = (values: any) => {
    const mode = values.duration_mode as BulkTextMode
    if (mode === 'clear') {
      updateDraftItems((items) => items.map((item) => (
        selectedRowKeys.includes(item.id) ? { ...item, duration: null } : item
      )))
      return
    }
    if (mode === 'single') {
      const duration = values.single_duration
      updateDraftItems((items) => items.map((item) => (
        selectedRowKeys.includes(item.id) ? { ...item, duration: duration ?? null } : item
      )))
      return
    }
    const durations = parseLines(values.duration_list || '').map((line) => Number(line))
    if (durations.length !== selectedRowsInOrder.length) {
      throw new Error('列表模式下，时长条目数量必须与选中样例数完全一致')
    }
    if (durations.some((value) => !Number.isInteger(value) || value <= 0)) {
      throw new Error('样例时长必须为正整数')
    }
    const durationMap = new Map<string, number>()
    selectedRowsInOrder.forEach((item, index) => {
      durationMap.set(item.id, durations[index])
    })
    updateDraftItems((items) => items.map((item) => (
      selectedRowKeys.includes(item.id)
        ? { ...item, duration: durationMap.get(item.id) ?? null }
        : item
    )))
  }

  const applyAudioBulkEdit = (values: any) => {
    const mode = values.audio_mode as AudioApplyMode
    if (mode === 'clear') {
      updateDraftItems((items) => items.map((item) => (
        selectedRowKeys.includes(item.id) ? { ...item, audio: null } : item
      )))
      return
    }
    if (mode === 'single') {
      const audio = audios.find((item) => item.url === values.audio_select)
      if (!audio) throw new Error('请选择音频')
      const audioAsset = buildAudioAsset(audio)
      updateDraftItems((items) => items.map((item) => (
        selectedRowKeys.includes(item.id) ? { ...item, audio: audioAsset } : item
      )))
      return
    }
    if (mode === 'list') {
      const urls = values.audio_selects || []
      if (urls.length !== selectedRowsInOrder.length) {
        throw new Error('列表模式下，音频数量必须与选中样例数完全一致')
      }
      const audioMap = new Map<string, VideoBenchmarkMediaAsset>()
      selectedRowsInOrder.forEach((item, index) => {
        const audio = audios.find((current) => current.url === urls[index])
        if (audio) audioMap.set(item.id, buildAudioAsset(audio))
      })
      updateDraftItems((items) => items.map((item) => (
        selectedRowKeys.includes(item.id)
          ? { ...item, audio: audioMap.get(item.id) || null }
          : item
      )))
      return
    }
    const urls = parseLines(values.audio_url_list || '')
    if (urls.length !== selectedRowsInOrder.length) {
      throw new Error('URL 列表数量必须与选中样例数完全一致')
    }
    const audioMap = new Map<string, VideoBenchmarkMediaAsset>()
    selectedRowsInOrder.forEach((item, index) => {
      audioMap.set(item.id, buildUrlAsset(urls[index], '', 'URL'))
    })
    updateDraftItems((items) => items.map((item) => (
      selectedRowKeys.includes(item.id)
        ? { ...item, audio: audioMap.get(item.id) || null }
        : item
    )))
  }

  const handleBulkEdit = async () => {
    if (!draftDataset || !selectedRowsInOrder.length) return
    try {
      const values = await bulkEditForm.validateFields()
      const field = values.field as BulkField
      if (field === 'name' || field === 'prompt' || field === 'negative_prompt') {
        applyTextBulkEdit(field, values)
      } else if (field === 'tags') {
        const mode = values.tag_mode as BulkTagMode
        const tags = values.tags || []
        updateDraftItems((items) => items.map((item) => {
          if (!selectedRowKeys.includes(item.id)) return item
          if (mode === 'clear') return { ...item, tags: [] }
          if (mode === 'replace') return { ...item, tags }
          if (mode === 'append') return { ...item, tags: Array.from(new Set([...(item.tags || []), ...tags])) }
          return { ...item, tags: (item.tags || []).filter((tag) => !tags.includes(tag)) }
        }))
      } else if (field === 'duration') {
        applyDurationBulkEdit(values)
      } else if (field === 'first_frame') {
        await applyFirstFrameBulkEdit({
          applyMode: values.frame_mode as MediaApplyMode,
          sourceMode: values.frame_source_mode,
          galleryUrls: values.gallery_urls,
          uploadFileList: bulkEditUploadFiles,
        })
      } else if (field === 'audio') {
        applyAudioBulkEdit(values)
      }
      setBulkEditOpen(false)
      bulkEditForm.resetFields()
      setBulkEditUploadFiles([])
    } catch (error) {
      if (error instanceof Error) message.error(error.message)
    }
  }

  const handleDeleteSelected = () => {
    if (!draftDataset) return
    updateDraftItems((items) => items.filter((item) => !selectedRowKeys.includes(item.id)))
    setSelectedRowKeys([])
  }

  const handleMoveSelected = (direction: 'up' | 'down' | 'top' | 'bottom') => {
    if (!draftDataset || !selectedRowsInOrder.length) return
    const selectedSet = new Set(selectedRowKeys)
    const currentItems = [...draftDataset.items]

    let nextItems = currentItems
    if (direction === 'top') {
      const selectedItems = currentItems.filter((item) => selectedSet.has(item.id))
      const otherItems = currentItems.filter((item) => !selectedSet.has(item.id))
      nextItems = [...selectedItems, ...otherItems]
    } else if (direction === 'bottom') {
      const selectedItems = currentItems.filter((item) => selectedSet.has(item.id))
      const otherItems = currentItems.filter((item) => !selectedSet.has(item.id))
      nextItems = [...otherItems, ...selectedItems]
    } else if (direction === 'up') {
      nextItems = [...currentItems]
      for (let index = 1; index < nextItems.length; index += 1) {
        if (selectedSet.has(nextItems[index].id) && !selectedSet.has(nextItems[index - 1].id)) {
          ;[nextItems[index - 1], nextItems[index]] = [nextItems[index], nextItems[index - 1]]
        }
      }
    } else {
      nextItems = [...currentItems]
      for (let index = nextItems.length - 2; index >= 0; index -= 1) {
        if (selectedSet.has(nextItems[index].id) && !selectedSet.has(nextItems[index + 1].id)) {
          ;[nextItems[index], nextItems[index + 1]] = [nextItems[index + 1], nextItems[index]]
        }
      }
    }

    setDraftDataset({
      ...draftDataset,
      items: normalizeItems(nextItems),
    })
  }

  const columns = [
    {
      title: '样例',
      dataIndex: 'name',
      width: 160,
      render: (value: string, record: VideoBenchmarkDatasetItem) => (
        <Space direction="vertical" size={2}>
          <Text strong>{value || '未命名样例'}</Text>
          <Text type="secondary">{record.tags?.join('、') || '无标签'}</Text>
          {warningMap.has(record.id) && <Tag color="warning">缺首帧</Tag>}
        </Space>
      ),
    },
    {
      title: '首帧',
      dataIndex: 'first_frame',
      width: 110,
      render: (asset: VideoBenchmarkMediaAsset | null) => asset?.url ? (
        <Image src={asset.url} width={72} height={72} style={{ objectFit: 'cover', borderRadius: 6 }} />
      ) : <Tag color="error">缺首帧</Tag>,
    },
    {
      title: 'Prompt',
      dataIndex: 'prompt',
      render: (value: string) => <div style={{ whiteSpace: 'pre-wrap' }}>{value || <Text type="secondary">空</Text>}</div>,
    },
    {
      title: '时长',
      dataIndex: 'duration',
      width: 90,
      render: (value: number | null) => value ? `${value}s` : <Text type="secondary">跟随配置</Text>,
    },
    {
      title: '音频',
      dataIndex: 'audio',
      width: 160,
      render: (asset: VideoBenchmarkMediaAsset | null) => asset?.url ? (asset.name || '已选择') : <Text type="secondary">无</Text>,
    },
    {
      title: '操作',
      width: 130,
      render: (_: unknown, record: VideoBenchmarkDatasetItem) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openItemModal(record)} />
          <Popconfirm
            title="删除该样例？"
            onConfirm={() => {
              if (!draftDataset) return
              setDraftDataset({
                ...draftDataset,
                items: normalizeItems(draftDataset.items.filter((item) => item.id !== record.id)),
              })
            }}
          >
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  const uploadProps: UploadProps = {
    accept: 'image/*',
    fileList: uploadFiles,
    disabled: !galleryUploadEnabled,
    beforeUpload: (file) => {
      setUploadFiles([file])
      return false
    },
    onRemove: () => {
      setUploadFiles([])
    },
    maxCount: 1,
  }

  const bulkUploadProps = (
    fileList: UploadFile[],
    setFileList: Dispatch<SetStateAction<UploadFile[]>>,
  ): UploadProps => ({
    accept: 'image/*',
    multiple: true,
    disabled: !galleryUploadEnabled,
    fileList,
    beforeUpload: (file) => {
      setFileList((prev) => [...prev, file])
      return false
    },
    onRemove: (file) => {
      setFileList((prev) => prev.filter((item) => item.uid !== file.uid))
    },
  })

  if (loading) {
    return <div style={{ padding: 48, textAlign: 'center' }}><Text>加载中...</Text></div>
  }

  return (
    <div style={{ padding: 24 }}>
      <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <Title level={3} style={{ margin: 0, color: token.colorText }}>视频数据集</Title>
          <Text type="secondary">管理首帧生视频测评样例，包含首帧图、提示词、可选音频和样例级时长。</Text>
        </div>
        <Space>
          <Upload {...importUploadProps}>
            <Button icon={<ImportOutlined />}>导入 JSON</Button>
          </Upload>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreateDatasetModal}>新建数据集</Button>
        </Space>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: 24, alignItems: 'start' }}>
        <Card title="数据集">
          {datasets.length === 0 ? (
            <Empty description="暂无视频数据集" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          ) : (
            <Space direction="vertical" style={{ width: '100%' }}>
              {datasets.map((dataset) => (
                <Card
                  key={dataset.id}
                  size="small"
                  hoverable
                  onClick={() => setSelectedDatasetId(dataset.id)}
                  style={{ borderColor: dataset.id === selectedDatasetId ? token.colorPrimary : token.colorBorderSecondary }}
                >
                  <Space direction="vertical" size={4}>
                    <Text strong>{dataset.name}</Text>
                    <Text type="secondary">样例数：{dataset.items.length}</Text>
                  </Space>
                </Card>
              ))}
            </Space>
          )}
        </Card>

        {!draftDataset ? (
          <Card><Empty description="请选择或创建一个视频数据集" /></Card>
        ) : (
          <Card
            title={selectedDataset?.name || '视频数据集'}
            extra={
              <Space>
                <Button icon={<PlusOutlined />} onClick={() => openItemModal()}>添加样例</Button>
                <Button icon={<ImportOutlined />} onClick={() => setPromptImportOpen(true)}>批量 Prompt</Button>
                <Button icon={<PictureOutlined />} onClick={() => {
                  bulkAddFramesForm.resetFields()
                  bulkAddFramesForm.setFieldsValue({ source_mode: 'gallery' })
                  setBulkAddFramesUploadFiles([])
                  setBulkAddFramesOpen(true)
                }}>批量首帧建样例</Button>
                <Button icon={<DownloadOutlined />} onClick={handleExportDataset}>导出 JSON</Button>
                <Popconfirm title="删除该数据集？" onConfirm={() => handleDeleteDataset(draftDataset.id)}>
                  <Button danger icon={<DeleteOutlined />}>删除</Button>
                </Popconfirm>
                <Button type="primary" icon={<SaveOutlined />} onClick={handleSaveDataset}>保存数据集</Button>
              </Space>
            }
          >
            <Space direction="vertical" size={16} style={{ width: '100%' }}>
              {!galleryUploadEnabled && (
                <Alert
                  type="warning"
                  showIcon
                  message="本地上传到图库当前不可用"
                  description="当前未启用 OSS，涉及本地批量上传首帧的入口会被禁用。你仍然可以从图库选择首帧或在单条样例中填写 URL。"
                />
              )}
              {localValidation.warnings.length > 0 && (
                <Alert
                  type="warning"
                  showIcon
                  message="当前视频数据集存在缺首帧样例"
                  description={`共 ${localValidation.warnings.length} 条样例缺少首帧图；可以保存和导出，但开始测评前必须补齐。`}
                />
              )}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                <div>
                  <Text style={{ display: 'block', marginBottom: 8 }}>名称</Text>
                  <Input value={draftDataset.name} onChange={(event) => setDraftDataset({ ...draftDataset, name: event.target.value })} />
                </div>
                <div>
                  <Text style={{ display: 'block', marginBottom: 8 }}>任务类型</Text>
                  <Tag color="blue">首帧生视频</Tag>
                </div>
              </div>
              <div>
                <Text style={{ display: 'block', marginBottom: 8 }}>描述</Text>
                <TextArea rows={3} value={draftDataset.description} onChange={(event) => setDraftDataset({ ...draftDataset, description: event.target.value })} />
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
                <Space wrap>
                  <Button
                    icon={<UploadOutlined />}
                    disabled={!selectedRowsInOrder.length}
                    onClick={() => {
                      fillFirstFrameForm.resetFields()
                      fillFirstFrameForm.setFieldsValue({ apply_mode: 'single', source_mode: 'gallery' })
                      setFillFirstFrameUploadFiles([])
                      setFillFirstFrameOpen(true)
                    }}
                  >
                    批量填充首帧
                  </Button>
                  <Button
                    icon={<EditOutlined />}
                    disabled={!selectedRowsInOrder.length}
                    onClick={() => {
                      bulkEditForm.resetFields()
                      bulkEditForm.setFieldsValue({
                        field: 'prompt',
                        text_mode: 'single',
                        tag_mode: 'replace',
                        duration_mode: 'single',
                        frame_mode: 'single',
                        frame_source_mode: 'gallery',
                        audio_mode: 'single',
                      })
                      setBulkEditUploadFiles([])
                      setBulkEditOpen(true)
                    }}
                  >
                    批量编辑字段
                  </Button>
                  <Button disabled={!selectedRowsInOrder.length} onClick={() => handleMoveSelected('up')}>选中上移</Button>
                  <Button disabled={!selectedRowsInOrder.length} onClick={() => handleMoveSelected('down')}>选中下移</Button>
                  <Button disabled={!selectedRowsInOrder.length} onClick={() => handleMoveSelected('top')}>选中置顶</Button>
                  <Button disabled={!selectedRowsInOrder.length} onClick={() => handleMoveSelected('bottom')}>选中置底</Button>
                  <Button danger disabled={!selectedRowsInOrder.length} onClick={handleDeleteSelected}>删除选中</Button>
                </Space>
                <Text type="secondary">样例数：{draftDataset.items.length}</Text>
              </div>
              {selectedRowsInOrder.length > 0 && (
                <Alert
                  type="info"
                  showIcon
                  message={`已选中 ${selectedRowsInOrder.length} 条样例`}
                  description="列表模式会按当前表格顺序与选中样例一一对应。"
                />
              )}
              <Table
                rowKey="id"
                dataSource={draftDataset.items}
                columns={columns}
                pagination={false}
                rowSelection={{
                  selectedRowKeys,
                  onChange: (keys) => setSelectedRowKeys(keys as string[]),
                }}
              />
            </Space>
          </Card>
        )}
      </div>

      <Modal
        title="新建视频数据集"
        open={datasetModalOpen}
        onOk={handleCreateDataset}
        onCancel={() => setDatasetModalOpen(false)}
        okText="创建"
        cancelText="取消"
      >
        <Form form={datasetForm} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入数据集名称' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={editingItemId ? '编辑样例' : '添加样例'}
        open={itemModalOpen}
        onOk={handleSaveItem}
        onCancel={() => {
          setItemModalOpen(false)
          setUploadFiles([])
        }}
        width={820}
        okText="保存"
        cancelText="取消"
      >
        <Form form={itemForm} layout="vertical">
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <Form.Item name="name" label="样例名">
              <Input />
            </Form.Item>
            <Form.Item name="duration" label="样例时长">
              <InputNumber min={1} precision={0} style={{ width: '100%' }} addonAfter="秒" placeholder="为空时跟随测评配置" />
            </Form.Item>
          </div>
          <Form.Item name="prompt" label="Prompt">
            <TextArea rows={4} />
          </Form.Item>
          <Form.Item name="negative_prompt" label="负向提示词">
            <TextArea rows={2} />
          </Form.Item>
          <Form.Item name="tags" label="标签">
            <Select mode="tags" open={false} placeholder="回车添加标签" />
          </Form.Item>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <Form.Item name="first_frame_gallery" label="图库首帧">
              <Select
                allowClear
                showSearch
                optionFilterProp="label"
                options={galleryImages.map((image) => ({ value: image.url, label: image.name || image.url }))}
              />
            </Form.Item>
            <Form.Item name="first_frame_url" label="首帧 URL">
              <Input />
            </Form.Item>
          </div>
          <Form.Item name="first_frame_name" label="首帧名称">
            <Input />
          </Form.Item>
          <Form.Item label="上传首帧到图库">
            <Upload {...uploadProps}>
              <Button icon={<UploadOutlined />} disabled={!galleryUploadEnabled}>选择图片</Button>
            </Upload>
          </Form.Item>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <Form.Item name="audio_select" label="音频库音频">
              <Select
                allowClear
                showSearch
                optionFilterProp="label"
                options={audios.map((audio) => ({ value: audio.url, label: audio.name || audio.url }))}
              />
            </Form.Item>
            <Form.Item name="audio_url" label="音频 URL">
              <Input />
            </Form.Item>
          </div>
          <Form.Item name="audio_name" label="音频名称">
            <Input />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="批量导入 Prompt"
        open={promptImportOpen}
        onOk={handlePromptImport}
        onCancel={() => setPromptImportOpen(false)}
        okText="导入"
        cancelText="取消"
      >
        <TextArea
          rows={10}
          value={promptImportText}
          onChange={(event) => setPromptImportText(event.target.value)}
          placeholder="每行一条 prompt。导入后请为新增样例补齐首帧图再保存。"
        />
      </Modal>

      <Modal
        title="批量首帧建样例"
        open={bulkAddFramesOpen}
        onOk={handleBulkAddFirstFrames}
        onCancel={() => setBulkAddFramesOpen(false)}
        okText="新增样例"
        cancelText="取消"
      >
        <Form form={bulkAddFramesForm} layout="vertical">
          <Form.Item name="source_mode" label="首帧来源" rules={[{ required: true, message: '请选择首帧来源' }]}>
            <Select
              options={[
                { value: 'gallery', label: '从图库选择' },
                { value: 'upload', label: '本地上传并自动入图库', disabled: !galleryUploadEnabled },
              ]}
            />
          </Form.Item>
          {bulkAddFrameSourceMode === 'gallery' ? (
            <Form.Item name="gallery_urls" label="图库首帧" rules={[{ required: true, message: '请至少选择一张首帧图' }]}>
              <Select
                mode="multiple"
                optionFilterProp="label"
                options={galleryImages.map((image) => ({ value: image.url, label: image.name || image.url }))}
                placeholder="每张图会新增一条视频样例"
              />
            </Form.Item>
          ) : (
            <Form.Item label="本地首帧图片">
              <Upload.Dragger {...bulkUploadProps(bulkAddFramesUploadFiles, setBulkAddFramesUploadFiles)}>
                <p className="ant-upload-drag-icon"><UploadOutlined /></p>
                <p className="ant-upload-text">选择或拖拽图片到此区域，提交时会先自动上传到图库</p>
              </Upload.Dragger>
            </Form.Item>
          )}
        </Form>
      </Modal>

      <Modal
        title={`批量填充首帧${selectedRowsInOrder.length ? `（已选 ${selectedRowsInOrder.length} 条）` : ''}`}
        open={fillFirstFrameOpen}
        onOk={handleFillFirstFrame}
        onCancel={() => setFillFirstFrameOpen(false)}
        okText="应用"
        cancelText="取消"
      >
        <Form form={fillFirstFrameForm} layout="vertical">
          <Form.Item name="apply_mode" label="填充方式" rules={[{ required: true, message: '请选择填充方式' }]}>
            <Select
              options={[
                { value: 'single', label: '单图覆盖全部选中行' },
                { value: 'list', label: '图片列表一一对应填充' },
                { value: 'clear', label: '清空首帧' },
              ]}
            />
          </Form.Item>
          {fillFirstFrameApplyMode !== 'clear' && (
            <Form.Item name="source_mode" label="首帧来源" rules={[{ required: true, message: '请选择首帧来源' }]}>
              <Select
                options={[
                  { value: 'gallery', label: '从图库选择' },
                  { value: 'upload', label: '本地上传并自动入图库', disabled: !galleryUploadEnabled },
                ]}
              />
            </Form.Item>
          )}
          {fillFirstFrameApplyMode !== 'clear' && fillFirstFrameSourceMode === 'gallery' && (
            <Form.Item
              name="gallery_urls"
              label={fillFirstFrameApplyMode === 'single' ? '图库首帧（仅取第一张）' : '图库首帧列表'}
              rules={[{ required: true, message: '请选择首帧图' }]}
            >
              <Select
                mode="multiple"
                optionFilterProp="label"
                options={galleryImages.map((image) => ({ value: image.url, label: image.name || image.url }))}
                placeholder={fillFirstFrameApplyMode === 'single' ? '选择一张图片' : '图片数量必须与选中样例数一致'}
              />
            </Form.Item>
          )}
          {fillFirstFrameApplyMode !== 'clear' && fillFirstFrameSourceMode === 'upload' && (
            <Form.Item label="本地首帧图片">
              <Upload.Dragger {...bulkUploadProps(fillFirstFrameUploadFiles, setFillFirstFrameUploadFiles)}>
                <p className="ant-upload-drag-icon"><UploadOutlined /></p>
                <p className="ant-upload-text">提交时会先上传到图库，再按当前表格顺序填充到选中样例</p>
              </Upload.Dragger>
            </Form.Item>
          )}
        </Form>
      </Modal>

      <Modal
        title={`批量编辑字段${selectedRowsInOrder.length ? `（已选 ${selectedRowsInOrder.length} 条）` : ''}`}
        open={bulkEditOpen}
        onOk={handleBulkEdit}
        onCancel={() => setBulkEditOpen(false)}
        okText="应用"
        cancelText="取消"
        width={760}
      >
        <Form form={bulkEditForm} layout="vertical">
          <Form.Item name="field" label="字段" rules={[{ required: true, message: '请选择字段' }]}>
            <Select
              options={[
                { value: 'name', label: '样例名' },
                { value: 'prompt', label: 'Prompt' },
                { value: 'negative_prompt', label: '负向提示词' },
                { value: 'tags', label: '标签' },
                { value: 'duration', label: '样例时长' },
                { value: 'first_frame', label: '首帧' },
                { value: 'audio', label: '音频' },
              ]}
            />
          </Form.Item>

          {(bulkEditField === 'name' || bulkEditField === 'prompt' || bulkEditField === 'negative_prompt') && (
            <>
              <Form.Item name="text_mode" label="编辑方式" rules={[{ required: true, message: '请选择编辑方式' }]}>
                <Select
                  options={[
                    { value: 'single', label: '单值覆盖' },
                    { value: 'list', label: '列表一一对应覆盖' },
                    { value: 'clear', label: '清空' },
                  ]}
                />
              </Form.Item>
              {bulkEditTextMode === 'single' && (
                <Form.Item name="single_text" label="文本值">
                  <TextArea rows={4} />
                </Form.Item>
              )}
              {bulkEditTextMode === 'list' && (
                <Form.Item name="list_text" label="文本列表">
                  <TextArea rows={8} placeholder="每行一条，数量必须与选中样例数完全一致" />
                </Form.Item>
              )}
            </>
          )}

          {bulkEditField === 'tags' && (
            <>
              <Form.Item name="tag_mode" label="标签操作" rules={[{ required: true, message: '请选择标签操作' }]}>
                <Select
                  options={[
                    { value: 'replace', label: '覆盖' },
                    { value: 'append', label: '追加' },
                    { value: 'remove', label: '删除指定标签' },
                    { value: 'clear', label: '清空' },
                  ]}
                />
              </Form.Item>
              {bulkEditTagMode !== 'clear' && (
                <Form.Item name="tags" label="标签">
                  <Select mode="tags" tokenSeparators={[',', '，', ' ']} />
                </Form.Item>
              )}
            </>
          )}

          {bulkEditField === 'duration' && (
            <>
              <Form.Item name="duration_mode" label="编辑方式" rules={[{ required: true, message: '请选择编辑方式' }]}>
                <Select
                  options={[
                    { value: 'single', label: '单值覆盖' },
                    { value: 'list', label: '列表一一对应覆盖' },
                    { value: 'clear', label: '清空，跟随测评配置' },
                  ]}
                />
              </Form.Item>
              {bulkEditDurationMode === 'single' && (
                <Form.Item name="single_duration" label="时长">
                  <InputNumber min={1} precision={0} style={{ width: '100%' }} addonAfter="秒" />
                </Form.Item>
              )}
              {bulkEditDurationMode === 'list' && (
                <Form.Item name="duration_list" label="时长列表">
                  <TextArea rows={8} placeholder="每行一个正整数秒数，数量必须与选中样例数完全一致" />
                </Form.Item>
              )}
            </>
          )}

          {bulkEditField === 'first_frame' && (
            <>
              <Form.Item name="frame_mode" label="编辑方式" rules={[{ required: true, message: '请选择编辑方式' }]}>
                <Select
                  options={[
                    { value: 'single', label: '单图覆盖全部选中行' },
                    { value: 'list', label: '图片列表一一对应填充' },
                    { value: 'clear', label: '清空首帧' },
                  ]}
                />
              </Form.Item>
              {bulkEditFrameMode !== 'clear' && (
                <Form.Item name="frame_source_mode" label="首帧来源" rules={[{ required: true, message: '请选择首帧来源' }]}>
                  <Select
                    options={[
                      { value: 'gallery', label: '从图库选择' },
                      { value: 'upload', label: '本地上传并自动入图库', disabled: !galleryUploadEnabled },
                    ]}
                  />
                </Form.Item>
              )}
              {bulkEditFrameMode !== 'clear' && bulkEditFrameSourceMode === 'gallery' && (
                <Form.Item name="gallery_urls" label="图库首帧" rules={[{ required: true, message: '请选择首帧图' }]}>
                  <Select
                    mode="multiple"
                    optionFilterProp="label"
                    options={galleryImages.map((image) => ({ value: image.url, label: image.name || image.url }))}
                    placeholder={bulkEditFrameMode === 'single' ? '选择一张图片' : '图片数量必须与选中样例数一致'}
                  />
                </Form.Item>
              )}
              {bulkEditFrameMode !== 'clear' && bulkEditFrameSourceMode === 'upload' && (
                <Form.Item label="本地首帧图片">
                  <Upload.Dragger {...bulkUploadProps(bulkEditUploadFiles, setBulkEditUploadFiles)}>
                    <p className="ant-upload-drag-icon"><UploadOutlined /></p>
                    <p className="ant-upload-text">提交时会先上传到图库，再按规则填充</p>
                  </Upload.Dragger>
                </Form.Item>
              )}
            </>
          )}

          {bulkEditField === 'audio' && (
            <>
              <Form.Item name="audio_mode" label="编辑方式" rules={[{ required: true, message: '请选择编辑方式' }]}>
                <Select
                  options={[
                    { value: 'single', label: '单音频覆盖全部选中行' },
                    { value: 'list', label: '音频库列表一一对应' },
                    { value: 'url_list', label: '音频 URL 列表一一对应' },
                    { value: 'clear', label: '清空音频' },
                  ]}
                />
              </Form.Item>
              {bulkEditAudioMode === 'single' && (
                <Form.Item name="audio_select" label="音频库音频" rules={[{ required: true, message: '请选择音频' }]}>
                  <Select
                    showSearch
                    optionFilterProp="label"
                    options={audios.map((audio) => ({ value: audio.url, label: audio.name || audio.url }))}
                  />
                </Form.Item>
              )}
              {bulkEditAudioMode === 'list' && (
                <Form.Item name="audio_selects" label="音频库音频列表" rules={[{ required: true, message: '请选择音频列表' }]}>
                  <Select
                    mode="multiple"
                    optionFilterProp="label"
                    options={audios.map((audio) => ({ value: audio.url, label: audio.name || audio.url }))}
                    placeholder="音频数量必须与选中样例数一致"
                  />
                </Form.Item>
              )}
              {bulkEditAudioMode === 'url_list' && (
                <Form.Item name="audio_url_list" label="音频 URL 列表" rules={[{ required: true, message: '请输入音频 URL 列表' }]}>
                  <TextArea rows={8} placeholder="每行一个音频 URL，数量必须与选中样例数完全一致" />
                </Form.Item>
              )}
            </>
          )}
        </Form>
      </Modal>
    </div>
  )
}

export default VideoBenchmarkDatasetsPage
