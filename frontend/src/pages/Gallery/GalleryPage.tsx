import { useEffect, useState, useCallback, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { 
  Button, Modal, Form, Input, Empty, Spin, message, 
  Image, Space, Popconfirm, Card, Tag, Tooltip
} from 'antd'
import { 
  DeleteOutlined, EditOutlined, PictureOutlined,
  ExclamationCircleOutlined, EyeOutlined
} from '@ant-design/icons'
import { galleryApi, GalleryImage } from '../../services/api'
import { useProjectStore } from '../../stores/projectStore'

const { TextArea } = Input

const GalleryPage = () => {
  const { projectId } = useParams<{ projectId: string }>()
  const { currentProject, fetchProject } = useProjectStore()
  
  const [images, setImages] = useState<GalleryImage[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedImage, setSelectedImage] = useState<GalleryImage | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [form] = Form.useForm()
  
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
        const { images: data } = await galleryApi.list(projectId)
        safeSetState(setImages, data)
      } catch (error) {
        message.error('加载失败')
      } finally {
        safeSetState(setLoading, false)
      }
    }
    loadData()
  }, [projectId, fetchProject, safeSetState])

  const openImageModal = (image: GalleryImage) => {
    setSelectedImage(image)
    form.setFieldsValue({
      name: image.name,
      description: image.description,
      tags: image.tags?.join(', ') || ''
    })
    setIsModalOpen(true)
  }

  const saveImage = async () => {
    if (!selectedImage) return
    try {
      const values = await form.validateFields()
      const tags = values.tags ? values.tags.split(',').map((t: string) => t.trim()).filter(Boolean) : []
      const updated = await galleryApi.update(selectedImage.id, {
        name: values.name,
        description: values.description,
        tags
      })
      safeSetState(setImages, (prev: GalleryImage[]) => prev.map(img => img.id === updated.id ? updated : img))
      setIsModalOpen(false)
      message.success('图片信息已保存')
    } catch (error) {
      message.error('保存失败')
    }
  }

  const deleteImage = async (imageId: string) => {
    try {
      await galleryApi.delete(imageId)
      safeSetState(setImages, (prev: GalleryImage[]) => prev.filter(img => img.id !== imageId))
      message.success('图片已删除')
    } catch (error) {
      message.error('删除失败')
    }
  }

  const deleteAllImages = async () => {
    if (!projectId) return
    try {
      await galleryApi.deleteAll(projectId)
      safeSetState(setImages, [])
      message.success('已删除所有图片')
    } catch (error) {
      message.error('删除失败')
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
      <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 600, margin: 0, color: '#e0e0e0' }}>
            图库
          </h1>
          <p style={{ color: '#888', margin: '4px 0 0', fontSize: 13 }}>
            {currentProject?.name} - 共 {images.length} 张图片
          </p>
        </div>
        <Space>
          {images.length > 0 && (
            <Popconfirm 
              title="确定删除所有图片？" 
              description="此操作不可恢复"
              icon={<ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />}
              onConfirm={deleteAllImages}
              okText="删除"
              cancelText="取消"
              okButtonProps={{ danger: true }}
            >
              <Button danger icon={<DeleteOutlined />}>删除所有</Button>
            </Popconfirm>
          )}
        </Space>
      </div>

      {images.length === 0 ? (
        <Empty 
          description="暂无图片，可在图片工作室中生成并保存到图库" 
          style={{ marginTop: 100 }}
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      ) : (
        <div className="image-grid">
          {images.map((image) => (
            <div 
              key={image.id} 
              className="asset-card"
            >
              <div className="asset-card-image" style={{ position: 'relative' }}>
                <Image
                  src={image.url}
                  alt={image.name}
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                  preview={{
                    mask: <EyeOutlined style={{ fontSize: 24 }} />
                  }}
                />
                <div style={{ position: 'absolute', top: 8, left: 8 }}>
                  <Tag color={image.source === 'studio' ? 'blue' : 'green'}>
                    {image.source === 'studio' ? '工作室' : '上传'}
                  </Tag>
                </div>
              </div>
              <div className="asset-card-info">
                <div className="asset-card-name">{image.name}</div>
                <div className="asset-card-desc">
                  {image.description || '无描述'}
                </div>
                <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
                  <Tooltip title="编辑">
                    <Button 
                      size="small" 
                      icon={<EditOutlined />}
                      onClick={() => openImageModal(image)}
                    />
                  </Tooltip>
                  <Popconfirm
                    title="确定删除此图片？"
                    onConfirm={() => deleteImage(image.id)}
                    okText="删除"
                    cancelText="取消"
                    okButtonProps={{ danger: true }}
                  >
                    <Tooltip title="删除">
                      <Button 
                        size="small" 
                        danger
                        icon={<DeleteOutlined />}
                      />
                    </Tooltip>
                  </Popconfirm>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 编辑图片弹窗 */}
      <Modal
        title={`编辑图片 - ${selectedImage?.name}`}
        open={isModalOpen}
        onOk={saveImage}
        onCancel={() => setIsModalOpen(false)}
        okText="保存"
        cancelText="取消"
        width={600}
      >
        {selectedImage && (
          <div style={{ display: 'flex', gap: 24 }}>
            <div style={{ width: 200 }}>
              <Image
                src={selectedImage.url}
                alt={selectedImage.name}
                style={{ width: '100%', borderRadius: 8 }}
              />
              <div style={{ marginTop: 8, fontSize: 12, color: '#888' }}>
                创建时间: {new Date(selectedImage.created_at).toLocaleString()}
              </div>
              {selectedImage.prompt_used && (
                <div style={{ marginTop: 8 }}>
                  <div style={{ fontSize: 12, color: '#888', marginBottom: 4 }}>生成提示词:</div>
                  <div style={{ fontSize: 11, color: '#666', background: '#1a1a1a', padding: 8, borderRadius: 4, maxHeight: 100, overflow: 'auto' }}>
                    {selectedImage.prompt_used}
                  </div>
                </div>
              )}
            </div>
            <div style={{ flex: 1 }}>
              <Form form={form} layout="vertical">
                <Form.Item name="name" label="图片名称" rules={[{ required: true, message: '请输入名称' }]}>
                  <Input placeholder="输入图片名称" />
                </Form.Item>
                <Form.Item name="description" label="描述">
                  <TextArea rows={3} placeholder="输入图片描述" />
                </Form.Item>
                <Form.Item name="tags" label="标签（逗号分隔）">
                  <Input placeholder="例如：角色, 场景, 道具" />
                </Form.Item>
              </Form>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}

export default GalleryPage

