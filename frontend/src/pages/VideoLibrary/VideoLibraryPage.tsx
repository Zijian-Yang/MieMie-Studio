import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { Card, Button, List, Modal, Input, Upload, Tabs, message, Popconfirm, Space, Empty } from 'antd'
import { PlusOutlined, DeleteOutlined, UploadOutlined, LinkOutlined, PlayCircleOutlined, PictureOutlined } from '@ant-design/icons'
import type { UploadFile } from 'antd/es/upload/interface'
import { videoLibraryApi, settingsApi, VideoLibraryItem } from '../../services/api'
import { useProjectStore } from '../../stores/projectStore'

const { Dragger } = Upload
const { TextArea } = Input

const VideoLibraryPage = () => {
  const { projectId } = useParams<{ projectId: string }>()
  const { fetchProject } = useProjectStore()
  
  const [videos, setVideos] = useState<VideoLibraryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [uploadModalVisible, setUploadModalVisible] = useState(false)
  const [editModalVisible, setEditModalVisible] = useState(false)
  const [previewModalVisible, setPreviewModalVisible] = useState(false)
  const [selectedVideo, setSelectedVideo] = useState<VideoLibraryItem | null>(null)
  const [editName, setEditName] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [urlInput, setUrlInput] = useState('')
  const [uploading, setUploading] = useState(false)
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [ossEnabled, setOssEnabled] = useState(false)
  const [extractingFrame, setExtractingFrame] = useState(false)

  useEffect(() => {
    if (projectId) {
      fetchProject(projectId)
      loadData()
    }
  }, [projectId, fetchProject])

  const loadData = async () => {
    if (!projectId) return
    setLoading(true)
    try {
      const [videosRes, settingsRes] = await Promise.all([
        videoLibraryApi.list(projectId),
        settingsApi.getSettings()
      ])
      setVideos(videosRes.videos)
      setOssEnabled(settingsRes.oss.enabled)
    } catch (error) {
      message.error('加载失败')
    } finally {
      setLoading(false)
    }
  }

  const handleFileUpload = async () => {
    if (!projectId || fileList.length === 0) return
    
    setUploading(true)
    try {
      const files = fileList.map(f => f.originFileObj as File).filter(Boolean)
      const result = await videoLibraryApi.uploadFiles(projectId, files)
      
      if (result.success_count > 0) {
        message.success(`成功上传 ${result.success_count} 个视频`)
        setVideos(prev => [...result.videos, ...prev])
      }
      if (result.error_count > 0) {
        message.warning(`${result.error_count} 个上传失败`)
      }
      
      setFileList([])
      setUploadModalVisible(false)
    } catch (error: any) {
      message.error(error.message || '上传失败')
    } finally {
      setUploading(false)
    }
  }

  const handleUrlUpload = async () => {
    if (!projectId || !urlInput.trim()) return
    
    const urls = urlInput.split('\n').map(u => u.trim()).filter(Boolean)
    if (urls.length === 0) return
    
    setUploading(true)
    try {
      const result = await videoLibraryApi.uploadUrls(projectId, urls)
      
      if (result.success_count > 0) {
        message.success(`成功导入 ${result.success_count} 个视频`)
        setVideos(prev => [...result.videos, ...prev])
      }
      if (result.error_count > 0) {
        message.warning(`${result.error_count} 个导入失败`)
      }
      
      setUrlInput('')
      setUploadModalVisible(false)
    } catch (error: any) {
      message.error(error.message || '导入失败')
    } finally {
      setUploading(false)
    }
  }

  const handleEdit = (video: VideoLibraryItem) => {
    setSelectedVideo(video)
    setEditName(video.name)
    setEditDescription(video.description)
    setEditModalVisible(true)
  }

  const handlePreview = (video: VideoLibraryItem) => {
    setSelectedVideo(video)
    setPreviewModalVisible(true)
  }

  const handleSaveEdit = async () => {
    if (!selectedVideo) return
    
    try {
      const updated = await videoLibraryApi.update(selectedVideo.id, {
        name: editName,
        description: editDescription
      })
      setVideos(prev => prev.map(v => v.id === updated.id ? updated : v))
      setEditModalVisible(false)
      message.success('保存成功')
    } catch (error: any) {
      message.error(error.message || '保存失败')
    }
  }

  const handleDelete = async (video: VideoLibraryItem) => {
    try {
      await videoLibraryApi.delete(video.id)
      setVideos(prev => prev.filter(v => v.id !== video.id))
      message.success('删除成功')
    } catch (error: any) {
      message.error(error.message || '删除失败')
    }
  }

  const handleDeleteAll = async () => {
    if (!projectId) return
    try {
      await videoLibraryApi.deleteAll(projectId)
      setVideos([])
      message.success('全部删除成功')
    } catch (error: any) {
      message.error(error.message || '删除失败')
    }
  }

  const handleExtractLastFrame = async () => {
    if (!selectedVideo) return
    
    setExtractingFrame(true)
    try {
      const result = await videoLibraryApi.extractLastFrame(selectedVideo.id)
      message.success('尾帧已保存到图库')
    } catch (error: any) {
      message.error(error.message || '提取尾帧失败')
    } finally {
      setExtractingFrame(false)
    }
  }

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  return (
    <div style={{ padding: 24 }}>
      <Card
        title={
          <Space>
            <PlayCircleOutlined />
            视频库
          </Space>
        }
        extra={
          <Space>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setUploadModalVisible(true)}
              disabled={!ossEnabled}
            >
              上传视频
            </Button>
            {videos.length > 0 && (
              <Popconfirm
                title="确定删除所有视频？"
                onConfirm={handleDeleteAll}
              >
                <Button danger icon={<DeleteOutlined />}>
                  全部删除
                </Button>
              </Popconfirm>
            )}
          </Space>
        }
        style={{ background: '#1a1a1a', borderColor: '#333' }}
      >
        {!ossEnabled && (
          <div style={{ marginBottom: 16, padding: 12, background: '#2a2a2a', borderRadius: 8, color: '#faad14' }}>
            请先在设置中配置并启用 OSS，才能上传视频文件
          </div>
        )}
        
        {videos.length === 0 ? (
          <Empty description="暂无视频" />
        ) : (
          <List
            grid={{ gutter: 16, column: 4 }}
            dataSource={videos}
            loading={loading}
            renderItem={(video) => (
              <List.Item>
                <Card
                  size="small"
                  style={{ background: '#242424', borderColor: '#333' }}
                  cover={
                    <div 
                      style={{ 
                        height: 120, 
                        background: '#1a1a1a', 
                        display: 'flex', 
                        alignItems: 'center', 
                        justifyContent: 'center',
                        cursor: 'pointer',
                        position: 'relative',
                        overflow: 'hidden'
                      }}
                      onClick={() => handlePreview(video)}
                    >
                      <video
                        src={video.url}
                        style={{ 
                          width: '100%', 
                          height: '100%', 
                          objectFit: 'cover' 
                        }}
                        preload="metadata"
                        muted
                      />
                      <div style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        right: 0,
                        bottom: 0,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        background: 'rgba(0,0,0,0.3)',
                        opacity: 0,
                        transition: 'opacity 0.2s',
                      }}
                      className="video-play-overlay"
                      >
                        <PlayCircleOutlined style={{ fontSize: 48, color: '#fff' }} />
                      </div>
                    </div>
                  }
                  actions={[
                    <Button type="link" size="small" onClick={() => handlePreview(video)}>预览</Button>,
                    <Button type="link" size="small" onClick={() => handleEdit(video)}>编辑</Button>,
                    <Popconfirm title="确定删除？" onConfirm={() => handleDelete(video)}>
                      <Button type="link" size="small" danger>删除</Button>
                    </Popconfirm>
                  ]}
                >
                  <div style={{ fontWeight: 500, marginBottom: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {video.name}
                  </div>
                  <div style={{ fontSize: 12, color: '#888' }}>
                    {video.file_type.toUpperCase()} · {formatFileSize(video.file_size)}
                    {video.duration && ` · ${video.duration}秒`}
                  </div>
                </Card>
              </List.Item>
            )}
          />
        )}
      </Card>

      {/* 上传弹窗 */}
      <Modal
        title="上传视频"
        open={uploadModalVisible}
        onCancel={() => {
          setUploadModalVisible(false)
          setFileList([])
          setUrlInput('')
        }}
        footer={null}
        width={600}
      >
        <Tabs
          items={[
            {
              key: 'file',
              label: (
                <span>
                  <UploadOutlined /> 文件上传
                </span>
              ),
              children: (
                <div>
                  <Dragger
                    multiple
                    fileList={fileList}
                    beforeUpload={() => false}
                    onChange={({ fileList }) => setFileList(fileList)}
                    accept=".mp4,.mov,.avi,.webm,.mkv"
                  >
                    <p className="ant-upload-drag-icon">
                      <PlayCircleOutlined style={{ fontSize: 48, color: '#1890ff' }} />
                    </p>
                    <p className="ant-upload-text">点击或拖拽视频文件到此区域</p>
                    <p className="ant-upload-hint">支持 MP4、MOV、AVI、WebM、MKV 格式</p>
                  </Dragger>
                  <div style={{ marginTop: 16, textAlign: 'right' }}>
                    <Button
                      type="primary"
                      onClick={handleFileUpload}
                      loading={uploading}
                      disabled={fileList.length === 0}
                    >
                      上传 ({fileList.length})
                    </Button>
                  </div>
                </div>
              )
            },
            {
              key: 'url',
              label: (
                <span>
                  <LinkOutlined /> URL 导入
                </span>
              ),
              children: (
                <div>
                  <TextArea
                    value={urlInput}
                    onChange={(e) => setUrlInput(e.target.value)}
                    placeholder="输入视频 URL，每行一个"
                    rows={8}
                  />
                  <div style={{ marginTop: 16, textAlign: 'right' }}>
                    <Button
                      type="primary"
                      onClick={handleUrlUpload}
                      loading={uploading}
                      disabled={!urlInput.trim()}
                    >
                      导入
                    </Button>
                  </div>
                </div>
              )
            }
          ]}
        />
      </Modal>

      {/* 预览弹窗 */}
      <Modal
        title={selectedVideo?.name || '视频预览'}
        open={previewModalVisible}
        onCancel={() => setPreviewModalVisible(false)}
        footer={
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Button
              type="primary"
              icon={<PictureOutlined />}
              onClick={handleExtractLastFrame}
              loading={extractingFrame}
              disabled={!ossEnabled}
            >
              保存尾帧到图库
            </Button>
            <Button onClick={() => setPreviewModalVisible(false)}>
              关闭
            </Button>
          </div>
        }
        width={800}
      >
        {selectedVideo && (
          <video
            controls
            autoPlay
            style={{ width: '100%', maxHeight: '60vh' }}
            src={selectedVideo.url}
          />
        )}
      </Modal>

      {/* 编辑弹窗 */}
      <Modal
        title="编辑视频"
        open={editModalVisible}
        onCancel={() => setEditModalVisible(false)}
        onOk={handleSaveEdit}
      >
        <div style={{ marginBottom: 16 }}>
          <div style={{ marginBottom: 8 }}>名称</div>
          <Input
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
          />
        </div>
        <div>
          <div style={{ marginBottom: 8 }}>描述</div>
          <TextArea
            value={editDescription}
            onChange={(e) => setEditDescription(e.target.value)}
            rows={3}
          />
        </div>
      </Modal>
      
      {/* 视频封面悬停效果样式 */}
      <style>{`
        .ant-card-cover:hover .video-play-overlay {
          opacity: 1 !important;
        }
      `}</style>
    </div>
  )
}

export default VideoLibraryPage

