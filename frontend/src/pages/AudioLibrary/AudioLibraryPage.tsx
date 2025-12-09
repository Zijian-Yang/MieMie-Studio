import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { Card, Button, List, Modal, Input, Upload, Tabs, message, Popconfirm, Space, Empty } from 'antd'
import { PlusOutlined, DeleteOutlined, UploadOutlined, LinkOutlined, SoundOutlined } from '@ant-design/icons'
import type { UploadFile } from 'antd/es/upload/interface'
import { audioApi, settingsApi, AudioItem } from '../../services/api'
import { useProjectStore } from '../../stores/projectStore'

const { Dragger } = Upload
const { TextArea } = Input

const AudioLibraryPage = () => {
  const { projectId } = useParams<{ projectId: string }>()
  const { fetchProject } = useProjectStore()
  
  const [audios, setAudios] = useState<AudioItem[]>([])
  const [loading, setLoading] = useState(true)
  const [uploadModalVisible, setUploadModalVisible] = useState(false)
  const [editModalVisible, setEditModalVisible] = useState(false)
  const [selectedAudio, setSelectedAudio] = useState<AudioItem | null>(null)
  const [editName, setEditName] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [urlInput, setUrlInput] = useState('')
  const [uploading, setUploading] = useState(false)
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [ossEnabled, setOssEnabled] = useState(false)

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
      const [audiosRes, settingsRes] = await Promise.all([
        audioApi.list(projectId),
        settingsApi.getSettings()
      ])
      setAudios(audiosRes.audios)
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
      const result = await audioApi.uploadFiles(projectId, files)
      
      if (result.success_count > 0) {
        message.success(`成功上传 ${result.success_count} 个音频`)
        setAudios(prev => [...result.audios, ...prev])
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
      const result = await audioApi.uploadUrls(projectId, urls)
      
      if (result.success_count > 0) {
        message.success(`成功导入 ${result.success_count} 个音频`)
        setAudios(prev => [...result.audios, ...prev])
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

  const handleEdit = (audio: AudioItem) => {
    setSelectedAudio(audio)
    setEditName(audio.name)
    setEditDescription(audio.description)
    setEditModalVisible(true)
  }

  const handleSaveEdit = async () => {
    if (!selectedAudio) return
    
    try {
      const updated = await audioApi.update(selectedAudio.id, {
        name: editName,
        description: editDescription
      })
      setAudios(prev => prev.map(a => a.id === updated.id ? updated : a))
      setEditModalVisible(false)
      message.success('保存成功')
    } catch (error: any) {
      message.error(error.message || '保存失败')
    }
  }

  const handleDelete = async (audio: AudioItem) => {
    try {
      await audioApi.delete(audio.id)
      setAudios(prev => prev.filter(a => a.id !== audio.id))
      message.success('删除成功')
    } catch (error: any) {
      message.error(error.message || '删除失败')
    }
  }

  const handleDeleteAll = async () => {
    if (!projectId) return
    try {
      await audioApi.deleteAll(projectId)
      setAudios([])
      message.success('全部删除成功')
    } catch (error: any) {
      message.error(error.message || '删除失败')
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
            <SoundOutlined />
            音频库
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
              上传音频
            </Button>
            {audios.length > 0 && (
              <Popconfirm
                title="确定删除所有音频？"
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
            请先在设置中配置并启用 OSS，才能上传音频文件
          </div>
        )}
        
        {audios.length === 0 ? (
          <Empty description="暂无音频" />
        ) : (
          <List
            grid={{ gutter: 16, column: 4 }}
            dataSource={audios}
            loading={loading}
            renderItem={(audio) => (
              <List.Item>
                <Card
                  size="small"
                  style={{ background: '#242424', borderColor: '#333' }}
                  actions={[
                    <Button type="link" size="small" onClick={() => handleEdit(audio)}>编辑</Button>,
                    <Popconfirm title="确定删除？" onConfirm={() => handleDelete(audio)}>
                      <Button type="link" size="small" danger>删除</Button>
                    </Popconfirm>
                  ]}
                >
                  <div style={{ textAlign: 'center', marginBottom: 8 }}>
                    <SoundOutlined style={{ fontSize: 32, color: '#1890ff' }} />
                  </div>
                  <div style={{ fontWeight: 500, marginBottom: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {audio.name}
                  </div>
                  <div style={{ fontSize: 12, color: '#888' }}>
                    {audio.file_type.toUpperCase()} · {formatFileSize(audio.file_size)}
                  </div>
                  <audio 
                    controls 
                    style={{ width: '100%', marginTop: 8, height: 32 }}
                    src={audio.url}
                  />
                </Card>
              </List.Item>
            )}
          />
        )}
      </Card>

      {/* 上传弹窗 */}
      <Modal
        title="上传音频"
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
                    accept=".mp3,.wav,.m4a,.aac,.ogg,.flac"
                  >
                    <p className="ant-upload-drag-icon">
                      <SoundOutlined style={{ fontSize: 48, color: '#1890ff' }} />
                    </p>
                    <p className="ant-upload-text">点击或拖拽音频文件到此区域</p>
                    <p className="ant-upload-hint">支持 MP3、WAV、M4A、AAC、OGG、FLAC 格式</p>
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
                    placeholder="输入音频 URL，每行一个"
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

      {/* 编辑弹窗 */}
      <Modal
        title="编辑音频"
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
    </div>
  )
}

export default AudioLibraryPage

