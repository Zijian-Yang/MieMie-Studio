import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Alert, Button, Card, Empty, Image, Space, Spin, Table, Tag, Typography, message, theme } from 'antd'
import { CopyOutlined, PushpinFilled, PushpinOutlined } from '@ant-design/icons'
import {
  ImageBenchmarkPublicShareResponse,
  ImageBenchmarkPublicCellResult,
  imageBenchmarkPublicApi,
} from '../../services/api'

const { Title, Text } = Typography

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

type FreezeColumnKey = 'name' | 'prompt' | 'input_images'

const copyText = async (text: string) => {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text)
    return
  }
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.style.position = 'fixed'
  textarea.style.left = '-9999px'
  document.body.appendChild(textarea)
  textarea.focus()
  textarea.select()
  document.execCommand('copy')
  document.body.removeChild(textarea)
}

const ImageBenchmarkSharePage = () => {
  const { token } = theme.useToken()
  const { token: shareToken } = useParams<{ token: string }>()
  const [data, setData] = useState<ImageBenchmarkPublicShareResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [frozenColumns, setFrozenColumns] = useState<FreezeColumnKey[]>(['input_images'])

  useEffect(() => {
    if (!shareToken) {
      setError('分享链接无效')
      setLoading(false)
      return
    }
    const loadShare = async () => {
      setLoading(true)
      setError('')
      try {
        setData(await imageBenchmarkPublicApi.getShare(shareToken))
      } catch (err) {
        setError(err instanceof Error ? err.message : '分享链接无法访问')
      } finally {
        setLoading(false)
      }
    }
    loadShare()
  }, [shareToken])

  const resultMap = useMemo(() => {
    const map = new Map<string, ImageBenchmarkPublicCellResult>()
    ;(data?.run.cell_results || []).forEach((cell) => {
      map.set(`${cell.case_id}__${cell.model_id}`, cell)
    })
    return map
  }, [data?.run.cell_results])

  const toggleFrozenColumn = (columnKey: FreezeColumnKey) => {
    setFrozenColumns((current) => (
      current.includes(columnKey)
        ? current.filter((item) => item !== columnKey)
        : [...current, columnKey]
    ))
  }

  const renderFreezeTitle = (label: string, columnKey: FreezeColumnKey) => {
    const active = frozenColumns.includes(columnKey)
    return (
      <Space size={6}>
        <span>{label}</span>
        <Button
          type="text"
          size="small"
          icon={active ? <PushpinFilled /> : <PushpinOutlined />}
          onClick={(event) => {
            event.stopPropagation()
            toggleFrozenColumn(columnKey)
          }}
          aria-label={active ? `取消冻结${label}列` : `冻结${label}列`}
        />
      </Space>
    )
  }

  const columns = useMemo(() => {
    const baseColumns = [
      {
        title: renderFreezeTitle('样例', 'name'),
        dataIndex: 'name',
        key: 'name',
        fixed: frozenColumns.includes('name') ? 'left' as const : undefined,
        width: 180,
        render: (value: string) => <Text strong>{value || '未命名样例'}</Text>,
      },
      {
        title: renderFreezeTitle('Prompt', 'prompt'),
        dataIndex: 'prompt',
        key: 'prompt',
        fixed: frozenColumns.includes('prompt') ? 'left' as const : undefined,
        width: 320,
        render: (value: string) => (
          <div style={{ whiteSpace: 'pre-wrap', maxHeight: 220, overflow: 'auto' }}>
            {value || <Text type="secondary">空</Text>}
          </div>
        ),
      },
      {
        title: renderFreezeTitle('输入图', 'input_images'),
        key: 'input_images',
        fixed: frozenColumns.includes('input_images') ? 'left' as const : undefined,
        width: 260,
        render: (_: unknown, record: Record<string, any>) => (
          <Image.PreviewGroup>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(96px, 1fr))', gap: 8 }}>
              {getCaseImages(record).map((image: any) => (
                <Image
                  key={image.url}
                  src={image.url}
                  height={112}
                  style={{ width: '100%', objectFit: 'cover', borderRadius: 8 }}
                />
              ))}
            </div>
          </Image.PreviewGroup>
        ),
      },
    ]

    const modelColumns = (data?.run.model_snapshots || []).map((model) => ({
      title: model.name || model.id,
      key: model.id,
      width: 360,
      render: (_: unknown, record: Record<string, any>) => {
        const cell = resultMap.get(`${record.id}__${model.id}`)
        if (!cell) {
          return <Text type="secondary">未运行</Text>
        }
        return (
          <Space direction="vertical" size={10} style={{ width: '100%' }}>
            <Tag color={statusColorMap[cell.status] || 'default'}>{cell.status}</Tag>
            {cell.output_images?.length > 0 && (
              <Image.PreviewGroup>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: 10 }}>
                  {cell.output_images.map((image, index) => image.url ? (
                    <Image
                      key={`${cell.id}-${index}`}
                      src={image.url}
                      height={180}
                      style={{ width: '100%', objectFit: 'cover', borderRadius: 8 }}
                    />
                  ) : (
                    <Tag key={`${cell.id}-${index}`} color="error">失败</Tag>
                  ))}
                </div>
              </Image.PreviewGroup>
            )}
            {cell.error_message && (
              <Text type="danger" style={{ whiteSpace: 'pre-wrap' }}>{cell.error_message}</Text>
            )}
          </Space>
        )
      },
    }))

    return [...baseColumns, ...modelColumns]
  }, [data?.run.model_snapshots, frozenColumns, resultMap])

  const handleCopyMarkdown = async () => {
    if (!shareToken) return
    try {
      const result = await imageBenchmarkPublicApi.getShareMarkdown(shareToken)
      await copyText(result.content)
      message.success('Markdown 已复制')
    } catch (err) {
      message.error(err instanceof Error ? err.message : '复制失败')
    }
  }

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', background: token.colorBgLayout }}>
        <Spin size="large" />
      </div>
    )
  }

  if (error || !data) {
    return (
      <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', padding: 24, background: token.colorBgLayout }}>
        <Alert type="error" showIcon message="无法打开分享结果" description={error || '分享链接不存在或已关闭'} />
      </div>
    )
  }

  const datasetItems = [...((data.run.dataset_snapshot?.items || []) as Record<string, any>[])]
    .sort((left, right) => (left.sort_order || 0) - (right.sort_order || 0))

  return (
    <div style={{ minHeight: '100vh', padding: 24, background: token.colorBgLayout }}>
      <Space direction="vertical" size={18} style={{ width: '100%' }}>
        <Card>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'flex-start', flexWrap: 'wrap' }}>
            <div>
              <Title level={2} style={{ margin: 0 }}>{data.suite.name}</Title>
              <Text type="secondary">{data.suite.description || '公开图片测评结果'}</Text>
              <div style={{ marginTop: 10 }}>
                <Tag color={statusColorMap[data.run.status] || 'default'}>{data.run.status}</Tag>
                <Text type="secondary">Run ID: {data.run.id}</Text>
              </div>
            </div>
            <Button type="primary" icon={<CopyOutlined />} onClick={handleCopyMarkdown}>
              复制为 Markdown
            </Button>
          </div>
        </Card>

        <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap', color: token.colorTextSecondary }}>
          <span>样例数：<Text strong>{data.run.stats.case_count || 0}</Text></span>
          <span>模型数：<Text strong>{data.run.stats.model_count || 0}</Text></span>
          <span>成功单元：<Text strong>{data.run.stats.success_count || 0}</Text></span>
          <span>失败单元：<Text strong>{data.run.stats.failure_count || 0}</Text></span>
        </div>

        <Card>
          {datasetItems.length ? (
            <Table
              rowKey="id"
              dataSource={datasetItems}
              columns={columns as any}
              pagination={false}
              scroll={{ x: 1200 }}
            />
          ) : (
            <Empty description="暂无测评结果" />
          )}
        </Card>
      </Space>
    </div>
  )
}

export default ImageBenchmarkSharePage
