import { useEffect, useMemo, useState, createContext, useContext } from 'react'
import type { Dispatch, ReactNode, SetStateAction } from 'react'
import { useParams } from 'react-router-dom'
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Empty,
  Form,
  Image,
  Input,
  List,
  Modal,
  Popconfirm,
  Select,
  Space,
  Spin,
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
  DragOutlined,
  EditOutlined,
  ImportOutlined,
  InboxOutlined,
  PictureOutlined,
  PlusOutlined,
  SaveOutlined,
  UploadOutlined,
} from '@ant-design/icons'
import type { UploadFile, UploadProps } from 'antd'
import {
  DndContext,
  PointerSensor,
  KeyboardSensor,
  closestCenter,
  useSensor,
  useSensors,
  DragEndEvent,
} from '@dnd-kit/core'
import {
  SortableContext,
  useSortable,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  arrayMove,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import {
  GalleryImage,
  ImageBenchmarkDataset,
  ImageBenchmarkDatasetImage,
  ImageBenchmarkDatasetIssue,
  ImageBenchmarkDatasetItem,
  ImageBenchmarkImageSlot,
  ImageBenchmarkTaskKind,
  galleryApi,
  imageBenchmarkApi,
} from '../../services/api'
import BBoxEditor from '../Studio/BBoxEditor'

const { TextArea } = Input
const { Title, Text } = Typography

const TASK_KIND_OPTIONS: Array<{ value: ImageBenchmarkTaskKind; label: string; description: string }> = [
  { value: 'text_to_image', label: '文生图', description: '仅包含 prompt 和 negative prompt' },
  { value: 'image_edit', label: '图片编辑', description: '支持输入图1、输入图2、输入图N 等槽位' },
  { value: 'interactive_edit', label: '交互式编辑', description: '仅 wan2.7 image，输入图槽位与 bbox_list 一一对应' },
]

const getTaskKindLabel = (value: ImageBenchmarkTaskKind | string) => (
  TASK_KIND_OPTIONS.find((item) => item.value === value)?.label || value
)

const getTaskKindColor = (value: ImageBenchmarkTaskKind | string) => (
  value === 'text_to_image' ? 'blue' : value === 'interactive_edit' ? 'purple' : 'green'
)

type BulkTextMode = 'single' | 'list' | 'clear'
type BulkTagMode = 'replace' | 'append' | 'remove' | 'clear'
type SlotSourceMode = 'gallery' | 'upload'
type SlotApplyMode = 'single' | 'list' | 'clear'
type BulkField = 'prompt' | 'negative_prompt' | 'tags' | 'image_slot'

interface DragContextValue {
  setActivatorNodeRef?: any
  listeners?: any
}

const RowDragContext = createContext<DragContextValue>({})

const SortableDragHandle = () => {
  const { setActivatorNodeRef, listeners } = useContext(RowDragContext)
  return (
    <Button
      type="text"
      icon={<DragOutlined />}
      ref={setActivatorNodeRef}
      {...listeners}
      style={{ cursor: 'grab' }}
    />
  )
}

const SortableBodyRow = (props: any) => {
  const {
    listeners,
    setNodeRef,
    setActivatorNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: props['data-row-key'] })

  const style = {
    ...props.style,
    transform: CSS.Transform.toString(transform),
    transition,
    ...(isDragging ? { position: 'relative', zIndex: 10 } : {}),
  }

  return (
    <RowDragContext.Provider value={{ setActivatorNodeRef, listeners }}>
      <tr {...props} ref={setNodeRef} style={style} />
    </RowDragContext.Provider>
  )
}

const SortableSlotCard = ({
  slotId,
  title,
  children,
}: {
  slotId: number
  title: string
  children: ReactNode
}) => {
  const {
    listeners,
    setNodeRef,
    setActivatorNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: String(slotId) })

  return (
    <Card
      ref={setNodeRef}
      size="small"
      title={
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
          <span>{title}</span>
          <Button
            type="text"
            size="small"
            icon={<DragOutlined />}
            ref={setActivatorNodeRef}
            {...listeners}
            style={{ cursor: 'grab' }}
          />
        </div>
      }
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.7 : 1,
      }}
    >
      {children}
    </Card>
  )
}

const cloneDataset = (dataset: ImageBenchmarkDataset | null) => (
  dataset ? JSON.parse(JSON.stringify(dataset)) as ImageBenchmarkDataset : null
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

const parseLines = (value: string) => (
  value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean)
)

const sortImageSlots = (slots: ImageBenchmarkImageSlot[]) => (
  [...slots].sort((left, right) => left.position - right.position)
)

const requiresImageSlots = (taskKind?: ImageBenchmarkTaskKind | string | null) => (
  taskKind === 'image_edit' || taskKind === 'interactive_edit'
)

const isInteractiveDataset = (dataset: ImageBenchmarkDataset | null) => dataset?.task_kind === 'interactive_edit'

const normalizeBBoxList = (value: unknown): number[][][] => {
  if (!Array.isArray(value)) return []
  return value.map((group) => {
    if (!Array.isArray(group)) return []
    return group
      .filter((box): box is number[] => Array.isArray(box) && box.length === 4)
      .map((box) => box.map((point) => Number(point)))
  })
}

const getSlotImage = (item: ImageBenchmarkDatasetItem, position: number) => (
  item.image_slots.find((slot) => slot.position === position)?.image || null
)

const setSlotImage = (
  item: ImageBenchmarkDatasetItem,
  position: number,
  image: ImageBenchmarkDatasetImage | null,
): ImageBenchmarkDatasetItem => {
  const nextSlots = item.image_slots.filter((slot) => slot.position !== position)
  if (image?.url) {
    nextSlots.push({ position, image })
  }
  return {
    ...item,
    image_slots: sortImageSlots(nextSlots),
  }
}

const normalizeItems = (items: ImageBenchmarkDatasetItem[]) => (
  items.map((item, index) => ({ ...item, sort_order: index }))
)

const inferMaxSlotIndex = (dataset: ImageBenchmarkDataset | null) => {
  if (!dataset) return 0
  const fromItems = dataset.items.reduce((maxValue, item) => {
    if (!item.image_slots.length) return maxValue
    return Math.max(maxValue, Math.max(...item.image_slots.map((slot) => slot.position)))
  }, 0)
  return Math.max(dataset.max_image_slot_index || 0, fromItems)
}

const buildImageFromGallery = (image: GalleryImage): ImageBenchmarkDatasetImage => ({
  url: image.url,
  name: image.name,
  source_label: '图库',
})

const analyzeDatasetDraft = (dataset: ImageBenchmarkDataset | null): { warnings: ImageBenchmarkDatasetIssue[]; blockingIssues: ImageBenchmarkDatasetIssue[] } => {
  if (!dataset || !requiresImageSlots(dataset.task_kind)) {
    return { warnings: [], blockingIssues: [] }
  }
  const warnings: ImageBenchmarkDatasetIssue[] = []
  const blockingIssues: ImageBenchmarkDatasetIssue[] = []
  for (const item of dataset.items) {
    const positions = sortImageSlots(item.image_slots)
      .map((slot) => slot.position)
      .filter((position) => position > 0)
    const itemName = item.name || `样例 ${item.sort_order + 1}`
    if (!positions.length) {
      const issue = {
        item_id: item.id,
        item_name: itemName,
        missing_positions: [1],
        message: '未填写任何输入图',
      }
      warnings.push(issue)
      blockingIssues.push(issue)
      continue
    }
    const maxFilledPosition = Math.max(...positions)
    const missingPositions = Array.from({ length: maxFilledPosition }, (_, index) => index + 1)
      .filter((position) => !positions.includes(position))
    if (missingPositions.length) {
      const issue = {
        item_id: item.id,
        item_name: itemName,
        missing_positions: missingPositions,
        message: `缺少输入图位置：${missingPositions.join('、')}`,
      }
      warnings.push(issue)
      blockingIssues.push(issue)
    }
    if (dataset.task_kind === 'interactive_edit') {
      const bboxList = normalizeBBoxList(item.bbox_list)
      if (bboxList.length !== positions.length) {
        const issue = {
          item_id: item.id,
          item_name: itemName,
          missing_positions: [],
          message: `bbox_list 长度需与输入图数量一致：当前 ${bboxList.length}，应为 ${positions.length}`,
        }
        warnings.push(issue)
        blockingIssues.push(issue)
      }
    }
  }
  return { warnings, blockingIssues }
}

const ImageBenchmarkDatasetsPage = () => {
  const { token } = theme.useToken()
  const { projectId } = useParams<{ projectId: string }>()

  const [datasets, setDatasets] = useState<ImageBenchmarkDataset[]>([])
  const [galleryImages, setGalleryImages] = useState<GalleryImage[]>([])
  const [galleryUploadEnabled, setGalleryUploadEnabled] = useState(false)
  const [migrateImagesOnImport, setMigrateImagesOnImport] = useState(false)
  const [loading, setLoading] = useState(true)
  const [selectedDatasetId, setSelectedDatasetId] = useState<string | null>(null)
  const [draftDataset, setDraftDataset] = useState<ImageBenchmarkDataset | null>(null)
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([])
  const [datasetModalOpen, setDatasetModalOpen] = useState(false)
  const [datasetForm] = Form.useForm()

  const [itemModalOpen, setItemModalOpen] = useState(false)
  const [editingItemId, setEditingItemId] = useState<string | null>(null)
  const [itemModalSlotCount, setItemModalSlotCount] = useState(0)
  const [itemModalSlotOrder, setItemModalSlotOrder] = useState<number[]>([])
  const [itemModalBBoxList, setItemModalBBoxList] = useState<number[][][]>([])
  const [itemForm] = Form.useForm()
  const itemFormValues = Form.useWatch([], itemForm) || {}

  const [promptImportOpen, setPromptImportOpen] = useState(false)
  const [promptImportForm] = Form.useForm()

  const [bulkAddImagesOpen, setBulkAddImagesOpen] = useState(false)
  const [bulkAddImagesForm] = Form.useForm()
  const [bulkAddUploadFiles, setBulkAddUploadFiles] = useState<UploadFile[]>([])

  const [fillSlotOpen, setFillSlotOpen] = useState(false)
  const [fillSlotForm] = Form.useForm()
  const [fillSlotUploadFiles, setFillSlotUploadFiles] = useState<UploadFile[]>([])

  const [batchReorderOpen, setBatchReorderOpen] = useState(false)
  const [batchReorderOrder, setBatchReorderOrder] = useState<number[]>([])

  const [bulkEditOpen, setBulkEditOpen] = useState(false)
  const [bulkEditForm] = Form.useForm()
  const [bulkEditUploadFiles, setBulkEditUploadFiles] = useState<UploadFile[]>([])

  const maxSlotIndex = useMemo(
    () => inferMaxSlotIndex(draftDataset),
    [draftDataset]
  )

  const localValidation = useMemo(
    () => analyzeDatasetDraft(draftDataset),
    [draftDataset]
  )

  const warningMap = useMemo(
    () => new Map(localValidation.warnings.map((issue) => [issue.item_id, issue])),
    [localValidation.warnings]
  )

  const selectedRowsInOrder = useMemo(() => {
    if (!draftDataset) return []
    const selectedSet = new Set(selectedRowKeys)
    return draftDataset.items.filter((item) => selectedSet.has(item.id))
  }, [draftDataset, selectedRowKeys])

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  )

  const fillSlotSourceMode = Form.useWatch('source_mode', fillSlotForm) as SlotSourceMode | undefined
  const fillSlotApplyMode = Form.useWatch('apply_mode', fillSlotForm) as SlotApplyMode | undefined
  const bulkAddSourceMode = Form.useWatch('source_mode', bulkAddImagesForm) as SlotSourceMode | undefined
  const bulkEditField = Form.useWatch('field', bulkEditForm) as BulkField | undefined
  const bulkEditTextMode = Form.useWatch('text_mode', bulkEditForm) as BulkTextMode | undefined
  const bulkEditTagMode = Form.useWatch('tag_mode', bulkEditForm) as BulkTagMode | undefined
  const bulkEditSlotMode = Form.useWatch('slot_mode', bulkEditForm) as SlotApplyMode | undefined
  const bulkEditSlotSourceMode = Form.useWatch('slot_source_mode', bulkEditForm) as SlotSourceMode | undefined

  useEffect(() => {
    if (!projectId) return
    const loadData = async () => {
      setLoading(true)
      try {
        const [datasetRes, galleryRes, ossStatus] = await Promise.all([
          imageBenchmarkApi.listDatasets(projectId),
          galleryApi.list(projectId),
          galleryApi.getOSSStatus(),
        ])
        setDatasets(datasetRes.datasets)
        setGalleryImages(galleryRes.images)
        setGalleryUploadEnabled(!!ossStatus.enabled)
        const initialId = datasetRes.datasets[0]?.id || null
        setSelectedDatasetId((prev) => (
          prev && datasetRes.datasets.some((item) => item.id === prev)
            ? prev
            : initialId
        ))
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
    if (!selectedDatasetId) {
      setDraftDataset(null)
      setSelectedRowKeys([])
      return
    }
    const loadDataset = async () => {
      try {
        const result = await imageBenchmarkApi.getDataset(selectedDatasetId)
        setDraftDataset(cloneDataset(result.dataset))
        setSelectedRowKeys([])
      } catch (error) {
        if (error instanceof Error) {
          message.error(error.message)
        }
      }
    }
    loadDataset()
  }, [selectedDatasetId])

  const refreshDatasets = async (preferredId?: string | null) => {
    if (!projectId) return
    const datasetRes = await imageBenchmarkApi.listDatasets(projectId)
    setDatasets(datasetRes.datasets)
    const nextId = preferredId ?? selectedDatasetId
    setSelectedDatasetId(
      nextId && datasetRes.datasets.some((item) => item.id === nextId)
        ? nextId
        : datasetRes.datasets[0]?.id || null
    )
  }

  const openCreateDatasetModal = () => {
    datasetForm.resetFields()
    datasetForm.setFieldsValue({ task_kind: 'text_to_image' })
    setDatasetModalOpen(true)
  }

  const handleCreateDataset = async () => {
    if (!projectId) return
    try {
      const values = await datasetForm.validateFields()
      const result = await imageBenchmarkApi.createDataset({
        project_id: projectId,
        name: values.name,
        description: values.description,
        task_kind: values.task_kind,
        items: [],
        max_image_slot_index: requiresImageSlots(values.task_kind) ? 0 : 0,
      })
      setDatasetModalOpen(false)
      await refreshDatasets(result.dataset.id)
      message.success('数据集已创建')
    } catch (error) {
      if (error instanceof Error) {
        message.error(error.message)
      }
    }
  }

  const updateDraftItems = (updater: (items: ImageBenchmarkDatasetItem[]) => ImageBenchmarkDatasetItem[]) => {
    if (!draftDataset) return
    const nextItems = normalizeItems(updater(draftDataset.items))
    const nextDataset: ImageBenchmarkDataset = {
      ...draftDataset,
      items: nextItems,
      max_image_slot_index: Math.max(draftDataset.max_image_slot_index || 0, inferMaxSlotIndex({ ...draftDataset, items: nextItems })),
    }
    setDraftDataset(nextDataset)
  }

  const handleSaveDataset = async () => {
    if (!draftDataset) return
    try {
      const result = await imageBenchmarkApi.updateDataset(draftDataset.id, {
        name: draftDataset.name,
        description: draftDataset.description,
        max_image_slot_index: draftDataset.max_image_slot_index,
        items: draftDataset.items.map((item) => ({
          id: item.id,
          name: item.name,
          prompt: item.prompt,
          negative_prompt: item.negative_prompt,
          tags: item.tags,
          bbox_list: normalizeBBoxList(item.bbox_list),
          image_slots: sortImageSlots(item.image_slots),
        })),
      })
      setDraftDataset(cloneDataset(result.dataset))
      await refreshDatasets(result.dataset.id)
      if (result.warnings?.length) {
        message.warning(`数据集已保存，但有 ${result.warnings.length} 条样例存在图片槽位空缺`)
      } else {
        message.success('数据集已保存')
      }
    } catch (error) {
      if (error instanceof Error) {
        message.error(error.message)
      }
    }
  }

  const handleDeleteDataset = async (datasetId: string) => {
    try {
      await imageBenchmarkApi.deleteDataset(datasetId)
      await refreshDatasets(null)
      message.success('数据集已删除')
    } catch (error) {
      if (error instanceof Error) {
        message.error(error.message)
      }
    }
  }

  const handleExportDataset = async () => {
    if (!draftDataset) return
    try {
      const payload = await imageBenchmarkApi.exportDataset(draftDataset.id)
      downloadTextFile(`${draftDataset.name || 'dataset'}.json`, JSON.stringify(payload, null, 2), 'application/json')
      message.success('数据集 JSON 已导出')
    } catch (error) {
      if (error instanceof Error) {
        message.error(error.message)
      }
    }
  }

  const importUploadProps: UploadProps = {
    accept: '.json,application/json',
    showUploadList: false,
    beforeUpload: async (file) => {
      if (!projectId) return Upload.LIST_IGNORE
      try {
        const rawText = await file.text()
        const data = JSON.parse(rawText)
        const result = await imageBenchmarkApi.importDataset({
          project_id: projectId,
          data,
          migrate_images_to_oss: migrateImagesOnImport,
        })
        await refreshDatasets(result.dataset.id)
        if (result.migration_report) {
          const report = result.migration_report
          if (!report.enabled) {
            message.warning('数据集已导入；当前 OSS 未启用，图片 URL 保持原样')
          } else if (report.failed > 0) {
            message.warning(`数据集已导入；图片转存成功 ${report.succeeded} 个，失败 ${report.failed} 个`)
          } else {
            message.success(`数据集导入成功，已转存 ${report.succeeded} 个图片`)
          }
        } else {
          message.success('数据集导入成功')
        }
      } catch (error) {
        if (error instanceof Error) {
          message.error(error.message)
        }
      }
      return Upload.LIST_IGNORE
    },
  }

  const openItemModal = (item?: ImageBenchmarkDatasetItem) => {
    const workingItem = item || {
      id: '',
      name: '',
      prompt: '',
      negative_prompt: '',
      sort_order: 0,
      tags: [],
      image_slots: [],
      bbox_list: [],
    }
    const slotCount = Math.max(maxSlotIndex, requiresImageSlots(draftDataset?.task_kind) ? 1 : 0, ...workingItem.image_slots.map((slot) => slot.position), 0)
    setItemModalSlotCount(slotCount)
    setItemModalBBoxList(Array.from({ length: slotCount }, (_, index) => normalizeBBoxList(workingItem.bbox_list)[index] || []))

    const nextValues: Record<string, any> = {
      name: workingItem.name,
      prompt: workingItem.prompt,
      negative_prompt: workingItem.negative_prompt,
      tags: workingItem.tags,
    }
    for (let position = 1; position <= slotCount; position += 1) {
      const currentImage = getSlotImage(workingItem, position)
      const galleryMatch = currentImage?.url
        ? galleryImages.find((gallery) => gallery.url === currentImage.url)
        : null
      nextValues[`slot_gallery_${position}`] = galleryMatch?.url
      nextValues[`slot_url_${position}`] = currentImage?.url || ''
      nextValues[`slot_name_${position}`] = currentImage?.name || ''
    }
    itemForm.setFieldsValue(nextValues)
    setEditingItemId(item?.id || null)
    setItemModalSlotOrder(Array.from({ length: slotCount }, (_, index) => index + 1))
    setItemModalOpen(true)
  }

  const reorderItemModalSlots = (fromPosition: number, toPosition: number) => {
    const slotEntries = Array.from({ length: itemModalSlotCount }, (_, index) => {
      const position = index + 1
      return {
        slot_gallery: itemForm.getFieldValue(`slot_gallery_${position}`),
        slot_url: itemForm.getFieldValue(`slot_url_${position}`),
        slot_name: itemForm.getFieldValue(`slot_name_${position}`),
        bbox_list: itemModalBBoxList[position - 1] || [],
      }
    })
    const fromIndex = fromPosition - 1
    const toIndex = toPosition - 1
    if (fromIndex < 0 || toIndex < 0 || fromIndex >= slotEntries.length || toIndex >= slotEntries.length) return
    const reorderedEntries = arrayMove(slotEntries, fromIndex, toIndex)
    const nextValues: Record<string, any> = {}
    reorderedEntries.forEach((entry, index) => {
      const position = index + 1
      nextValues[`slot_gallery_${position}`] = entry.slot_gallery
      nextValues[`slot_url_${position}`] = entry.slot_url
      nextValues[`slot_name_${position}`] = entry.slot_name
    })
    itemForm.setFieldsValue(nextValues)
    setItemModalBBoxList(reorderedEntries.map((entry) => entry.bbox_list || []))
    setItemModalSlotOrder(Array.from({ length: reorderedEntries.length }, (_, index) => index + 1))
  }

  const handleItemModalDragEnd = (event: DragEndEvent) => {
    if (!event.over || event.active.id === event.over.id) return
    const fromPosition = Number(event.active.id)
    const toPosition = Number(event.over.id)
    if (!Number.isFinite(fromPosition) || !Number.isFinite(toPosition)) return
    reorderItemModalSlots(fromPosition, toPosition)
  }

  const handleSaveItem = async () => {
    if (!draftDataset) return
    try {
      const values = await itemForm.validateFields()
      const imageSlots: ImageBenchmarkImageSlot[] = []
      for (let position = 1; position <= itemModalSlotCount; position += 1) {
        const galleryUrl = values[`slot_gallery_${position}`]
        const slotUrl = (values[`slot_url_${position}`] || '').trim()
        const finalUrl = galleryUrl || slotUrl
        if (!finalUrl) continue
        const galleryMatch = galleryImages.find((image) => image.url === finalUrl)
        imageSlots.push({
          position,
          image: galleryMatch
            ? buildImageFromGallery(galleryMatch)
            : {
              url: finalUrl,
              name: values[`slot_name_${position}`] || '',
              source_label: galleryUrl ? '图库' : 'URL',
            },
        })
      }

      const nextItem: ImageBenchmarkDatasetItem = {
        id: editingItemId || `temp-${Date.now()}`,
        name: values.name || '',
        prompt: values.prompt || '',
        negative_prompt: values.negative_prompt || '',
        tags: values.tags || [],
        image_slots: sortImageSlots(requiresImageSlots(draftDataset.task_kind) ? imageSlots : []),
        bbox_list: draftDataset.task_kind === 'interactive_edit'
          ? sortImageSlots(imageSlots).map((slot) => itemModalBBoxList[slot.position - 1] || [])
          : [],
        sort_order: 0,
      }

      const nextItems = editingItemId
        ? draftDataset.items.map((item) => (item.id === editingItemId ? nextItem : item))
        : [...draftDataset.items, nextItem]

      setDraftDataset({
        ...draftDataset,
        items: normalizeItems(nextItems),
        max_image_slot_index: Math.max(draftDataset.max_image_slot_index || 0, itemModalSlotCount),
      })
      setItemModalOpen(false)
      setItemModalSlotOrder([])
      setItemModalBBoxList([])
      itemForm.resetFields()
    } catch (error) {
      if (error instanceof Error) {
        message.error(error.message)
      }
    }
  }

  const handleBatchPromptImport = async () => {
    if (!draftDataset) return
    try {
      const values = await promptImportForm.validateFields()
      const prompts = parseLines(values.prompts_text || '')
      if (!prompts.length) {
        message.warning('请至少输入一条提示词')
        return
      }
      const nextItems = [...draftDataset.items]
      prompts.forEach((prompt, index) => {
        nextItems.push({
          id: `temp-${Date.now()}-${index}`,
          name: `样例 ${nextItems.length + 1}`,
          prompt,
          negative_prompt: values.shared_negative_prompt || '',
          tags: [],
          image_slots: [],
          bbox_list: [],
          sort_order: nextItems.length,
        })
      })
      setDraftDataset({
        ...draftDataset,
        items: normalizeItems(nextItems),
      })
      setPromptImportOpen(false)
      promptImportForm.resetFields()
    } catch (error) {
      if (error instanceof Error) {
        message.error(error.message)
      }
    }
  }

  const uploadFilesToGallery = async (files: UploadFile[]) => {
    if (!projectId) return []
    const actualFiles = files
      .map((file) => {
        if (file.originFileObj instanceof File) {
          return file.originFileObj
        }
        return file instanceof File ? file : null
      })
      .filter(Boolean) as File[]
    if (!actualFiles.length) return []
    const uploadResult = await galleryApi.uploadFiles(projectId, actualFiles)
    if (uploadResult.images?.length) {
      const galleryRes = await galleryApi.list(projectId)
      setGalleryImages(galleryRes.images)
    }
    if (uploadResult.error_count) {
      message.warning(`有 ${uploadResult.error_count} 张图片上传失败`)
    }
    return uploadResult.images || []
  }

  const resolveImagesForSource = async (
    sourceMode: SlotSourceMode,
    galleryUrls: string[],
    uploadFiles: UploadFile[],
  ): Promise<ImageBenchmarkDatasetImage[]> => {
    if (sourceMode === 'gallery') {
      return galleryUrls
        .map((url) => galleryImages.find((image) => image.url === url))
        .filter((image): image is GalleryImage => !!image)
        .map(buildImageFromGallery)
    }

    const uploadedImages = await uploadFilesToGallery(uploadFiles)
    return uploadedImages.map(buildImageFromGallery)
  }

  const handleBulkAddImages = async () => {
    if (!draftDataset) return
    try {
      const values = await bulkAddImagesForm.validateFields()
      const slotPosition = Number(values.slot_position)
      const sourceMode = values.source_mode as SlotSourceMode
      const images = await resolveImagesForSource(sourceMode, values.gallery_urls || [], bulkAddUploadFiles)
      if (!images.length) {
        message.warning('请先选择图片')
        return
      }
      const nextItems = [...draftDataset.items]
      images.forEach((image, index) => {
        nextItems.push({
          id: `temp-${Date.now()}-${index}`,
          name: image.name || `样例 ${nextItems.length + 1}`,
          prompt: '',
          negative_prompt: '',
          tags: [],
          image_slots: [{ position: slotPosition, image }],
          bbox_list: draftDataset.task_kind === 'interactive_edit' ? [[]] : [],
          sort_order: nextItems.length,
        })
      })
      setDraftDataset({
        ...draftDataset,
        items: normalizeItems(nextItems),
        max_image_slot_index: Math.max(draftDataset.max_image_slot_index || 0, slotPosition),
      })
      setBulkAddImagesOpen(false)
      bulkAddImagesForm.resetFields()
      setBulkAddUploadFiles([])
    } catch (error) {
      if (error instanceof Error) {
        message.error(error.message)
      }
    }
  }

  const applySlotBulkEdit = async ({
    slotPosition,
    applyMode,
    sourceMode,
    galleryUrls,
    uploadFiles,
  }: {
    slotPosition: number
    applyMode: SlotApplyMode
    sourceMode?: SlotSourceMode
    galleryUrls?: string[]
    uploadFiles?: UploadFile[]
  }) => {
    if (!draftDataset || !selectedRowsInOrder.length) return

    if (applyMode === 'clear') {
      updateDraftItems((items) => items.map((item) => (
        selectedRowKeys.includes(item.id)
          ? setSlotImage(item, slotPosition, null)
          : item
      )))
      return
    }

    const images = await resolveImagesForSource(sourceMode || 'gallery', galleryUrls || [], uploadFiles || [])
    if (!images.length) {
      message.warning('请先选择图片')
      return
    }

    if (applyMode === 'single') {
      const targetImage = images[0]
      updateDraftItems((items) => items.map((item) => (
        selectedRowKeys.includes(item.id)
          ? setSlotImage(item, slotPosition, targetImage)
          : item
      )))
      setDraftDataset((prev) => prev ? {
        ...prev,
        max_image_slot_index: Math.max(prev.max_image_slot_index || 0, slotPosition),
      } : prev)
      return
    }

    if (images.length !== selectedRowsInOrder.length) {
      throw new Error('列表模式下，图片数量必须与选中样例数完全一致')
    }

    const imageMap = new Map<string, ImageBenchmarkDatasetImage>()
    selectedRowsInOrder.forEach((item, index) => {
      imageMap.set(item.id, images[index])
    })
    updateDraftItems((items) => items.map((item) => (
      selectedRowKeys.includes(item.id)
        ? setSlotImage(item, slotPosition, imageMap.get(item.id) || null)
        : item
    )))
    setDraftDataset((prev) => prev ? {
      ...prev,
      max_image_slot_index: Math.max(prev.max_image_slot_index || 0, slotPosition),
    } : prev)
  }

  const handleFillSlot = async () => {
    try {
      const values = await fillSlotForm.validateFields()
      await applySlotBulkEdit({
        slotPosition: Number(values.slot_position),
        applyMode: values.apply_mode as SlotApplyMode,
        sourceMode: values.source_mode,
        galleryUrls: values.gallery_urls,
        uploadFiles: fillSlotUploadFiles,
      })
      setFillSlotOpen(false)
      fillSlotForm.resetFields()
      setFillSlotUploadFiles([])
    } catch (error) {
      if (error instanceof Error) {
        message.error(error.message)
      }
    }
  }

  const openBatchReorderModal = () => {
    setBatchReorderOrder(Array.from({ length: maxSlotIndex }, (_, index) => index + 1))
    setBatchReorderOpen(true)
  }

  const handleBatchReorderDragEnd = (event: DragEndEvent) => {
    if (!event.over || event.active.id === event.over.id) return
    const fromPosition = Number(event.active.id)
    const toPosition = Number(event.over.id)
    const fromIndex = batchReorderOrder.findIndex((value) => value === fromPosition)
    const toIndex = batchReorderOrder.findIndex((value) => value === toPosition)
    if (fromIndex < 0 || toIndex < 0) return
    setBatchReorderOrder((prev) => arrayMove(prev, fromIndex, toIndex))
  }

  const handleApplyBatchReorder = () => {
    if (!draftDataset || !selectedRowsInOrder.length || !batchReorderOrder.length) return
    const selectedSet = new Set(selectedRowKeys)
    updateDraftItems((items) => items.map((item) => {
      if (!selectedSet.has(item.id)) return item
      const slotImageMap = new Map<number, ImageBenchmarkDatasetImage>()
      const slotBBoxMap = new Map<number, number[][]>()
      sortImageSlots(item.image_slots).forEach((slot, index) => {
        slotImageMap.set(slot.position, slot.image)
        slotBBoxMap.set(slot.position, normalizeBBoxList(item.bbox_list)[index] || [])
      })
      const nextSlots: ImageBenchmarkImageSlot[] = []
      const nextBBoxList: number[][][] = []
      batchReorderOrder.forEach((oldPosition, index) => {
        const image = slotImageMap.get(oldPosition)
        if (!image) return
        nextSlots.push({
          position: index + 1,
          image,
        })
        nextBBoxList.push(slotBBoxMap.get(oldPosition) || [])
      })
      return {
        ...item,
        image_slots: sortImageSlots(nextSlots),
        bbox_list: item.bbox_list?.length ? nextBBoxList : [],
      }
    }))
    setBatchReorderOpen(false)
  }

  const handleBulkEdit = async () => {
    if (!draftDataset || !selectedRowsInOrder.length) return
    try {
      const values = await bulkEditForm.validateFields()
      const field = values.field as BulkField

      if (field === 'prompt' || field === 'negative_prompt') {
        const mode = values.text_mode as BulkTextMode
        if (mode === 'clear') {
          updateDraftItems((items) => items.map((item) => (
            selectedRowKeys.includes(item.id)
              ? { ...item, [field]: '' }
              : item
          )))
        } else if (mode === 'single') {
          const textValue = values.single_text || ''
          updateDraftItems((items) => items.map((item) => (
            selectedRowKeys.includes(item.id)
              ? { ...item, [field]: textValue }
              : item
          )))
        } else {
          const lines = parseLines(values.list_text || '')
          if (lines.length !== selectedRowsInOrder.length) {
            throw new Error('列表模式下，文本条目数量必须与选中样例数完全一致')
          }
          const textMap = new Map<string, string>()
          selectedRowsInOrder.forEach((item, index) => {
            textMap.set(item.id, lines[index])
          })
          updateDraftItems((items) => items.map((item) => (
            selectedRowKeys.includes(item.id)
              ? { ...item, [field]: textMap.get(item.id) || '' }
              : item
          )))
        }
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
      } else if (field === 'image_slot') {
        await applySlotBulkEdit({
          slotPosition: Number(values.slot_position),
          applyMode: values.slot_mode as SlotApplyMode,
          sourceMode: values.slot_source_mode,
          galleryUrls: values.gallery_urls,
          uploadFiles: bulkEditUploadFiles,
        })
      }

      setBulkEditOpen(false)
      bulkEditForm.resetFields()
      setBulkEditUploadFiles([])
    } catch (error) {
      if (error instanceof Error) {
        message.error(error.message)
      }
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

  const handleDragEnd = ({ active, over }: DragEndEvent) => {
    if (!draftDataset || !over || active.id === over.id) return
    const oldIndex = draftDataset.items.findIndex((item) => item.id === active.id)
    const newIndex = draftDataset.items.findIndex((item) => item.id === over.id)
    if (oldIndex < 0 || newIndex < 0) return
    const nextItems = arrayMove(draftDataset.items, oldIndex, newIndex)
    setDraftDataset({
      ...draftDataset,
      items: normalizeItems(nextItems),
    })
  }

  const columns = useMemo(() => {
    const baseColumns: any[] = [
      {
        title: '',
        dataIndex: 'sort_order',
        width: 52,
        fixed: 'left',
        render: () => <SortableDragHandle />,
      },
      {
        title: '#',
        dataIndex: 'sort_order',
        width: 60,
        fixed: 'left',
        render: (_: number, record: ImageBenchmarkDatasetItem) => record.sort_order + 1,
      },
      {
        title: '样例名',
        dataIndex: 'name',
        width: 180,
        fixed: 'left',
        render: (value: string, record: ImageBenchmarkDatasetItem) => (
          <Space direction="vertical" size={4}>
            <Text>{value || '未命名'}</Text>
            {warningMap.get(record.id) && (
              <Tag color="warning">{warningMap.get(record.id)?.message}</Tag>
            )}
          </Space>
        ),
      },
      {
        title: 'Prompt',
        dataIndex: 'prompt',
        width: 260,
        render: (value: string) => <div style={{ whiteSpace: 'pre-wrap' }}>{value || <Text type="secondary">空</Text>}</div>,
      },
      {
        title: 'Negative Prompt',
        dataIndex: 'negative_prompt',
        width: 220,
        render: (value: string) => value || <Text type="secondary">空</Text>,
      },
    ]

    const slotColumns = requiresImageSlots(draftDataset?.task_kind)
      ? Array.from({ length: maxSlotIndex }, (_, index) => {
        const position = index + 1
        return {
          title: `输入图${position}`,
          key: `slot-${position}`,
          width: 140,
          render: (_: unknown, record: ImageBenchmarkDatasetItem) => {
            const image = getSlotImage(record, position)
            return image?.url ? (
              <Space direction="vertical" size={4}>
                <Image
                  src={image.url}
                  width={64}
                  height={64}
                  style={{ objectFit: 'cover', borderRadius: 8 }}
                />
                <Text type="secondary" style={{ maxWidth: 96 }} ellipsis>{image.name || `图片${position}`}</Text>
              </Space>
            ) : (
              <Tag color="default">空</Tag>
            )
          },
        }
      })
      : []

    return [
      ...baseColumns,
      ...slotColumns,
      {
        title: '标签',
        dataIndex: 'tags',
        width: 180,
        render: (value: string[]) => (
          <Space wrap>
            {(value || []).length ? value.map((tag) => <Tag key={tag}>{tag}</Tag>) : <Text type="secondary">无</Text>}
          </Space>
        ),
      },
      {
        title: '操作',
        key: 'actions',
        width: 160,
        fixed: 'right',
        render: (_: unknown, record: ImageBenchmarkDatasetItem) => (
          <Space>
            <Button type="text" icon={<EditOutlined />} onClick={() => openItemModal(record)} />
            <Button type="text" danger icon={<DeleteOutlined />} onClick={() => updateDraftItems((items) => items.filter((item) => item.id !== record.id))} />
          </Space>
        ),
      },
    ]
  }, [draftDataset?.task_kind, maxSlotIndex, warningMap])

  const bulkUploadProps = (
    fileList: UploadFile[],
    setFileList: Dispatch<SetStateAction<UploadFile[]>>,
  ): UploadProps => ({
    multiple: true,
    beforeUpload: (file) => {
      setFileList((prev) => [...prev, file])
      return false
    },
    onRemove: (file) => {
      setFileList((prev) => prev.filter((item) => item.uid !== file.uid))
    },
    fileList,
  })

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
          <Title level={3} style={{ margin: 0, color: token.colorText }}>数据集</Title>
          <Text type="secondary">使用图片槽位管理可复用的测评样例，支持批量填充、批量编辑和拖拽排序。</Text>
        </div>
        <Space>
          <Checkbox
            checked={migrateImagesOnImport}
            onChange={(event) => setMigrateImagesOnImport(event.target.checked)}
          >
            导入时转存图片到当前 OSS
          </Checkbox>
          <Upload {...importUploadProps}>
            <Button icon={<ImportOutlined />}>导入 JSON</Button>
          </Upload>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreateDatasetModal}>
            新建数据集
          </Button>
        </Space>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: 24, alignItems: 'start' }}>
        <Card title="数据集列表">
          {datasets.length === 0 ? (
            <Empty description="暂无数据集" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          ) : (
            <List
              dataSource={datasets}
              renderItem={(item) => (
                <List.Item
                  style={{
                    cursor: 'pointer',
                    paddingInline: 12,
                    borderRadius: 8,
                    background: item.id === selectedDatasetId ? token.colorFillTertiary : 'transparent',
                    marginBottom: 8,
                  }}
                  onClick={() => setSelectedDatasetId(item.id)}
                >
                  <div style={{ width: '100%' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                      <Text strong>{item.name}</Text>
                      <Tag color={getTaskKindColor(item.task_kind)}>
                        {getTaskKindLabel(item.task_kind)}
                      </Tag>
                    </div>
                    <Text type="secondary">{item.description || '暂无描述'}</Text>
                    <div style={{ marginTop: 8 }}>
                      <Text type="secondary">样例数：{item.items.length}</Text>
                    </div>
                  </div>
                </List.Item>
              )}
            />
          )}
        </Card>

        {!draftDataset ? (
          <Card>
            <Empty description="请选择或创建一个数据集" />
          </Card>
        ) : (
          <Card
            title={
              <Space>
                <span>{draftDataset.name || '未命名数据集'}</span>
                <Tag color={getTaskKindColor(draftDataset.task_kind)}>
                  {getTaskKindLabel(draftDataset.task_kind)}
                </Tag>
              </Space>
            }
            extra={
              <Space>
                <Button icon={<DownloadOutlined />} onClick={handleExportDataset}>导出 JSON</Button>
                <Popconfirm
                  title="确定删除该数据集吗？"
                  description="删除后无法恢复。"
                  onConfirm={() => handleDeleteDataset(draftDataset.id)}
                >
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
                  description="当前未启用 OSS，涉及“本地上传并自动入图库”的入口会被禁用。你仍然可以从图库选择图片或填入图片 URL。"
                />
              )}

              {localValidation.warnings.length > 0 && (
                <Alert
                  type="warning"
                  showIcon
                  message="当前数据集存在图片槽位空缺"
                  description={`共 ${localValidation.warnings.length} 条样例存在缺图位；保存会成功，但开始测评前必须补齐。`}
                />
              )}

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                <div>
                  <Text style={{ display: 'block', marginBottom: 8 }}>数据集名称</Text>
                  <Input
                    value={draftDataset.name}
                    onChange={(event) => setDraftDataset({ ...draftDataset, name: event.target.value })}
                  />
                </div>
                <div>
                  <Text style={{ display: 'block', marginBottom: 8 }}>任务类型</Text>
                  <Select
                    value={draftDataset.task_kind}
                    disabled
                    style={{ width: '100%' }}
                    options={TASK_KIND_OPTIONS.map((item) => ({ value: item.value, label: item.label }))}
                  />
                </div>
              </div>

              <div>
                <Text style={{ display: 'block', marginBottom: 8 }}>描述</Text>
                <TextArea
                  rows={3}
                  value={draftDataset.description}
                  onChange={(event) => setDraftDataset({ ...draftDataset, description: event.target.value })}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                <Space wrap>
                  <Button type="primary" icon={<PlusOutlined />} onClick={() => openItemModal()}>
                    新增样例
                  </Button>
                  <Button icon={<InboxOutlined />} onClick={() => setPromptImportOpen(true)}>
                    批量导入 Prompt
                  </Button>
                  {requiresImageSlots(draftDataset.task_kind) && (
                    <>
                      <Button icon={<PictureOutlined />} onClick={() => {
                        bulkAddImagesForm.resetFields()
                        bulkAddImagesForm.setFieldsValue({ slot_position: Math.max(1, maxSlotIndex || 1), source_mode: 'gallery' })
                        setBulkAddUploadFiles([])
                        setBulkAddImagesOpen(true)
                      }}>
                        批量新增样例（基于图片）
                      </Button>
                      <Button
                        icon={<UploadOutlined />}
                        disabled={!selectedRowsInOrder.length}
                        onClick={() => {
                          fillSlotForm.resetFields()
                          fillSlotForm.setFieldsValue({ slot_position: 1, apply_mode: 'single', source_mode: 'gallery' })
                          setFillSlotUploadFiles([])
                          setFillSlotOpen(true)
                        }}
                      >
                        批量填充图片槽位
                      </Button>
                    </>
                  )}
                  <Button
                    icon={<EditOutlined />}
                    disabled={!selectedRowsInOrder.length}
                    onClick={() => {
                      bulkEditForm.resetFields()
                      bulkEditForm.setFieldsValue({ field: 'prompt', text_mode: 'single', tag_mode: 'replace', slot_mode: 'single', slot_source_mode: 'gallery', slot_position: 1 })
                      setBulkEditUploadFiles([])
                      setBulkEditOpen(true)
                    }}
                  >
                    批量编辑字段
                  </Button>
                  {requiresImageSlots(draftDataset.task_kind) && (
                    <Button disabled={!selectedRowsInOrder.length || maxSlotIndex < 2} onClick={openBatchReorderModal}>
                      批量调整输入图顺序
                    </Button>
                  )}
                  <Button disabled={!selectedRowsInOrder.length} onClick={() => handleMoveSelected('up')}>
                    选中上移
                  </Button>
                  <Button disabled={!selectedRowsInOrder.length} onClick={() => handleMoveSelected('down')}>
                    选中下移
                  </Button>
                  <Button disabled={!selectedRowsInOrder.length} onClick={() => handleMoveSelected('top')}>
                    选中置顶
                  </Button>
                  <Button disabled={!selectedRowsInOrder.length} onClick={() => handleMoveSelected('bottom')}>
                    选中置底
                  </Button>
                  <Button danger disabled={!selectedRowsInOrder.length} onClick={handleDeleteSelected}>
                    删除选中
                  </Button>
                </Space>
                <Text type="secondary">样例数：{draftDataset.items.length}，当前最高图片槽位：{draftDataset.max_image_slot_index || 0}</Text>
              </div>

              {selectedRowsInOrder.length > 0 && (
                <Alert
                  type="info"
                  showIcon
                  message={`已选中 ${selectedRowsInOrder.length} 条样例`}
                  description="批量填充图片槽位和批量编辑字段都会按当前表格顺序作用于这些样例。"
                />
              )}

              <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
                <SortableContext items={draftDataset.items.map((item) => item.id)} strategy={verticalListSortingStrategy}>
                  <Table
                    rowKey="id"
                    dataSource={draftDataset.items}
                    columns={columns as any}
                    pagination={false}
                    rowSelection={{
                      selectedRowKeys,
                      onChange: (keys) => setSelectedRowKeys(keys as string[]),
                    }}
                    scroll={{ x: 1400 }}
                    components={{
                      body: {
                        row: SortableBodyRow,
                      },
                    }}
                  />
                </SortableContext>
              </DndContext>
            </Space>
          </Card>
        )}
      </div>

      <Modal
        title="新建数据集"
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
          <Form.Item name="task_kind" label="任务类型" rules={[{ required: true, message: '请选择任务类型' }]}>
            <Select options={TASK_KIND_OPTIONS.map((item) => ({ value: item.value, label: item.label }))} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={editingItemId ? '编辑样例' : '新增样例'}
        open={itemModalOpen}
        onOk={handleSaveItem}
        onCancel={() => setItemModalOpen(false)}
        okText="保存"
        cancelText="取消"
        width={880}
      >
        <Form form={itemForm} layout="vertical">
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <Form.Item name="name" label="样例名">
              <Input placeholder="例如：海报 01" />
            </Form.Item>
            <Form.Item name="tags" label="标签">
              <Select mode="tags" tokenSeparators={[',', '，', ' ']} placeholder="输入标签后回车" />
            </Form.Item>
          </div>
          <Form.Item name="prompt" label="Prompt">
            <TextArea rows={4} placeholder="输入提示词" />
          </Form.Item>
          <Form.Item name="negative_prompt" label="Negative Prompt">
            <TextArea rows={3} placeholder="输入负面提示词（可选）" />
          </Form.Item>

          {requiresImageSlots(draftDataset?.task_kind) && (
            <Space direction="vertical" style={{ width: '100%' }} size={16}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Text strong>图片槽位</Text>
                <Button
                  type="dashed"
                  onClick={() => {
                    const nextCount = itemModalSlotCount + 1
                    setItemModalSlotCount(nextCount)
                    setItemModalBBoxList((prev) => [...prev, []])
                    setItemModalSlotOrder(Array.from({ length: nextCount }, (_, index) => index + 1))
                    if (draftDataset) {
                      setDraftDataset({
                        ...draftDataset,
                        max_image_slot_index: Math.max(draftDataset.max_image_slot_index || 0, nextCount),
                      })
                    }
                  }}
                >
                  新增一个图片槽位
                </Button>
              </div>
              <Alert
                type="info"
                showIcon
                message="支持拖拽调整输入图顺序"
                description="拖动图片槽位卡片后，会直接改动该样例最终请求体中的图片数组顺序。"
              />
              <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleItemModalDragEnd}>
                <SortableContext items={itemModalSlotOrder.map((position) => String(position))} strategy={verticalListSortingStrategy}>
                  <Space direction="vertical" style={{ width: '100%' }} size={12}>
                    {itemModalSlotOrder.map((position) => (
                      <SortableSlotCard key={position} slotId={position} title={`输入图${position}`}>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 120px', gap: 12 }}>
                          <Form.Item name={`slot_gallery_${position}`} label="从图库选择" style={{ marginBottom: 0 }}>
                            <Select
                              allowClear
                              optionLabelProp="label"
                              placeholder="可选"
                            >
                              {galleryImages.map((image) => (
                                <Select.Option key={image.id} value={image.url} label={image.name}>
                                  <Space>
                                    <Image src={image.url} width={36} height={36} preview={false} style={{ objectFit: 'cover', borderRadius: 6 }} />
                                    <span>{image.name}</span>
                                  </Space>
                                </Select.Option>
                              ))}
                            </Select>
                          </Form.Item>
                          <Form.Item name={`slot_url_${position}`} label="或填写图片 URL" style={{ marginBottom: 0 }}>
                            <Input placeholder="未选择图库时可直接输入 URL" />
                          </Form.Item>
                          <Form.Item name={`slot_name_${position}`} label="名称" style={{ marginBottom: 0 }}>
                            <Input placeholder="可选" />
                          </Form.Item>
                        </div>
                        {isInteractiveDataset(draftDataset) && (
                          <div style={{ marginTop: 12 }}>
                            {itemFormValues[`slot_gallery_${position}`] || itemFormValues[`slot_url_${position}`] ? (
                              <BBoxEditor
                                imageUrl={itemFormValues[`slot_gallery_${position}`] || itemFormValues[`slot_url_${position}`]}
                                value={itemModalBBoxList[position - 1] || []}
                                onChange={(boxes) => {
                                  const current = [...itemModalBBoxList]
                                  current[position - 1] = boxes
                                  setItemModalBBoxList(current)
                                }}
                              />
                            ) : (
                              <Alert type="info" showIcon message="选择图片后可在此绘制交互式框选区域" />
                            )}
                          </div>
                        )}
                      </SortableSlotCard>
                    ))}
                  </Space>
                </SortableContext>
              </DndContext>
            </Space>
          )}
        </Form>
      </Modal>

      <Modal
        title="批量导入 Prompt"
        open={promptImportOpen}
        onOk={handleBatchPromptImport}
        onCancel={() => setPromptImportOpen(false)}
        okText="导入"
        cancelText="取消"
      >
        <Form form={promptImportForm} layout="vertical">
          <Form.Item name="shared_negative_prompt" label="共享 Negative Prompt">
            <Input placeholder="可选，导入的每个样例都会带上这个值" />
          </Form.Item>
          <Form.Item
            name="prompts_text"
            label="Prompt 列表"
            rules={[{ required: true, message: '请至少输入一条提示词' }]}
          >
            <TextArea rows={8} placeholder="每行一条 prompt" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="批量新增样例（基于图片）"
        open={bulkAddImagesOpen}
        onOk={handleBulkAddImages}
        onCancel={() => setBulkAddImagesOpen(false)}
        okText="新增样例"
        cancelText="取消"
      >
        <Form form={bulkAddImagesForm} layout="vertical">
          <Form.Item name="slot_position" label="图片写入槽位 N" rules={[{ required: true, message: '请选择目标槽位' }]}>
            <Select
              options={Array.from({ length: Math.max(6, maxSlotIndex + 3) }, (_, index) => ({
                value: index + 1,
                label: `第 ${index + 1} 张图`,
              }))}
            />
          </Form.Item>
          <Form.Item name="source_mode" label="图片来源" rules={[{ required: true, message: '请选择图片来源' }]}>
            <Select
              options={[
                { value: 'gallery', label: '从图库选择' },
                { value: 'upload', label: '本地上传并自动入图库', disabled: !galleryUploadEnabled },
              ]}
            />
          </Form.Item>
          {bulkAddSourceMode === 'gallery' ? (
            <Form.Item name="gallery_urls" label="图库图片" rules={[{ required: true, message: '请至少选择一张图片' }]}>
              <Select mode="multiple" placeholder="多选后会新建多条样例">
                {galleryImages.map((image) => (
                  <Select.Option key={image.id} value={image.url}>
                    {image.name}
                  </Select.Option>
                ))}
              </Select>
            </Form.Item>
          ) : (
            <Form.Item label="本地图片文件">
              <Upload.Dragger {...bulkUploadProps(bulkAddUploadFiles, setBulkAddUploadFiles)}>
                <p className="ant-upload-drag-icon"><UploadOutlined /></p>
                <p className="ant-upload-text">选择或拖拽图片到此区域，提交时会先自动上传到图库</p>
              </Upload.Dragger>
            </Form.Item>
          )}
        </Form>
      </Modal>

      <Modal
        title={`批量填充图片槽位${selectedRowsInOrder.length ? `（已选 ${selectedRowsInOrder.length} 条）` : ''}`}
        open={fillSlotOpen}
        onOk={handleFillSlot}
        onCancel={() => setFillSlotOpen(false)}
        okText="应用"
        cancelText="取消"
      >
        <Form form={fillSlotForm} layout="vertical">
          <Form.Item name="slot_position" label="目标槽位 N" rules={[{ required: true, message: '请选择目标槽位' }]}>
            <Select
              options={Array.from({ length: Math.max(6, maxSlotIndex + 3) }, (_, index) => ({
                value: index + 1,
                label: `第 ${index + 1} 张图`,
              }))}
            />
          </Form.Item>
          <Form.Item name="apply_mode" label="填充方式" rules={[{ required: true, message: '请选择填充方式' }]}>
            <Select
              options={[
                { value: 'single', label: '单图覆盖全部选中行' },
                { value: 'list', label: '图片列表一一对应填充' },
                { value: 'clear', label: '清空该槽位' },
              ]}
            />
          </Form.Item>
          {fillSlotApplyMode !== 'clear' && (
            <Form.Item name="source_mode" label="图片来源" rules={[{ required: true, message: '请选择图片来源' }]}>
              <Select
                options={[
                  { value: 'gallery', label: '从图库选择' },
                  { value: 'upload', label: '本地上传并自动入图库', disabled: !galleryUploadEnabled },
                ]}
              />
            </Form.Item>
          )}
          {fillSlotApplyMode !== 'clear' && fillSlotSourceMode === 'gallery' && (
            <Form.Item
              name="gallery_urls"
              label={fillSlotApplyMode === 'single' ? '图库图片（仅取第一张）' : '图库图片列表'}
              rules={[{ required: true, message: '请选择图片' }]}
            >
              <Select
                mode="multiple"
                placeholder={fillSlotApplyMode === 'single' ? '选择一张图片' : '图片数量必须与选中样例数一致'}
              >
                {galleryImages.map((image) => (
                  <Select.Option key={image.id} value={image.url}>
                    {image.name}
                  </Select.Option>
                ))}
              </Select>
            </Form.Item>
          )}
          {fillSlotApplyMode !== 'clear' && fillSlotSourceMode === 'upload' && (
            <Form.Item label="本地图片文件">
              <Upload.Dragger {...bulkUploadProps(fillSlotUploadFiles, setFillSlotUploadFiles)}>
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
                { value: 'prompt', label: 'Prompt' },
                { value: 'negative_prompt', label: 'Negative Prompt' },
                { value: 'tags', label: '标签' },
                ...(requiresImageSlots(draftDataset?.task_kind) ? [{ value: 'image_slot', label: '指定槽位图片' }] : []),
              ]}
            />
          </Form.Item>

          {(bulkEditField === 'prompt' || bulkEditField === 'negative_prompt') && (
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

          {bulkEditField === 'image_slot' && (
            <>
              <Alert
                type="info"
                showIcon
                message="指定槽位图片的批量编辑与“批量填充图片槽位”共用同一套规则"
                description="列表模式会严格按当前表格顺序与选中样例一一对应；数量不一致会直接报错。"
                style={{ marginBottom: 16 }}
              />
              <Form.Item name="slot_position" label="目标槽位 N" rules={[{ required: true, message: '请选择目标槽位' }]}>
                <Select
                  options={Array.from({ length: Math.max(6, maxSlotIndex + 3) }, (_, index) => ({
                    value: index + 1,
                    label: `第 ${index + 1} 张图`,
                  }))}
                />
              </Form.Item>
              <Form.Item name="slot_mode" label="编辑方式" rules={[{ required: true, message: '请选择编辑方式' }]}>
                <Select
                  options={[
                    { value: 'single', label: '单图覆盖全部选中行' },
                    { value: 'list', label: '图片列表一一对应填充' },
                    { value: 'clear', label: '清空该槽位' },
                  ]}
                />
              </Form.Item>
              {bulkEditSlotMode !== 'clear' && (
                <Form.Item name="slot_source_mode" label="图片来源" rules={[{ required: true, message: '请选择图片来源' }]}>
                  <Select
                    options={[
                      { value: 'gallery', label: '从图库选择' },
                      { value: 'upload', label: '本地上传并自动入图库', disabled: !galleryUploadEnabled },
                    ]}
                  />
                </Form.Item>
              )}
              {bulkEditSlotMode !== 'clear' && bulkEditSlotSourceMode === 'gallery' && (
                <Form.Item name="gallery_urls" label="图库图片" rules={[{ required: true, message: '请选择图片' }]}>
                  <Select
                    mode="multiple"
                    placeholder={bulkEditSlotMode === 'single' ? '选择一张图片' : '图片数量必须与选中样例数一致'}
                  >
                    {galleryImages.map((image) => (
                      <Select.Option key={image.id} value={image.url}>
                        {image.name}
                      </Select.Option>
                    ))}
                  </Select>
                </Form.Item>
              )}
              {bulkEditSlotMode !== 'clear' && bulkEditSlotSourceMode === 'upload' && (
                <Form.Item label="本地图片文件">
                  <Upload.Dragger {...bulkUploadProps(bulkEditUploadFiles, setBulkEditUploadFiles)}>
                    <p className="ant-upload-drag-icon"><UploadOutlined /></p>
                    <p className="ant-upload-text">提交时会先上传到图库，再按规则填充</p>
                  </Upload.Dragger>
                </Form.Item>
              )}
            </>
          )}
        </Form>
      </Modal>

      <Modal
        title={`批量调整输入图顺序${selectedRowsInOrder.length ? `（已选 ${selectedRowsInOrder.length} 条）` : ''}`}
        open={batchReorderOpen}
        onOk={handleApplyBatchReorder}
        onCancel={() => setBatchReorderOpen(false)}
        okText="应用顺序"
        cancelText="取消"
      >
        <Space direction="vertical" style={{ width: '100%' }} size={16}>
          <Alert
            type="info"
            showIcon
            message="拖拽调整统一的输入图顺序"
            description="应用后，所有选中样例都会按这套顺序重排其输入图槽位内容，实际请求体图片数组顺序也会同步变化。"
          />
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleBatchReorderDragEnd}>
            <SortableContext items={batchReorderOrder.map((position) => String(position))} strategy={verticalListSortingStrategy}>
              <Space direction="vertical" style={{ width: '100%' }} size={12}>
                {batchReorderOrder.map((position, index) => (
                  <SortableSlotCard
                    key={position}
                    slotId={position}
                    title={`应用后第 ${index + 1} 张图 ← 当前第 ${position} 张图`}
                  >
                    <Text type="secondary">
                      所有选中样例中，原本位于“输入图{position}”的图片，将移动到新的“输入图{index + 1}”。
                    </Text>
                  </SortableSlotCard>
                ))}
              </Space>
            </SortableContext>
          </DndContext>
        </Space>
      </Modal>
    </div>
  )
}

export default ImageBenchmarkDatasetsPage
