import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { Card, Button, List, Modal, Input, message, Popconfirm, Space, Empty, Tag, Select, Tooltip, Timeline } from 'antd'
import { PlusOutlined, DeleteOutlined, EditOutlined, CopyOutlined, HistoryOutlined, FileTextOutlined } from '@ant-design/icons'
import { textLibraryApi, TextLibraryItem, TextItemVersion } from '../../services/api'
import { useProjectStore } from '../../stores/projectStore'

const { TextArea } = Input

const TextLibraryPage = () => {
  const { projectId } = useParams<{ projectId: string }>()
  const { fetchProject } = useProjectStore()
  
  const [texts, setTexts] = useState<TextLibraryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [createModalVisible, setCreateModalVisible] = useState(false)
  const [editModalVisible, setEditModalVisible] = useState(false)
  const [versionModalVisible, setVersionModalVisible] = useState(false)
  const [selectedText, setSelectedText] = useState<TextLibraryItem | null>(null)
  const [newName, setNewName] = useState('')
  const [newContent, setNewContent] = useState('')
  const [newCategory, setNewCategory] = useState('')
  const [editName, setEditName] = useState('')
  const [editContent, setEditContent] = useState('')
  const [editCategory, setEditCategory] = useState('')
  const [saveVersion, setSaveVersion] = useState(false)
  const [versionDescription, setVersionDescription] = useState('')
  const [categoryFilter, setCategoryFilter] = useState<string>('')

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
      const result = await textLibraryApi.list(projectId, categoryFilter || undefined)
      setTexts(result.texts)
    } catch (error) {
      message.error('加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (projectId) {
      loadData()
    }
  }, [categoryFilter])

  const handleCreate = async () => {
    if (!projectId || !newName.trim() || !newContent.trim()) return
    
    try {
      const text = await textLibraryApi.create({
        project_id: projectId,
        name: newName.trim(),
        content: newContent,
        category: newCategory.trim()
      })
      setTexts(prev => [text, ...prev])
      setCreateModalVisible(false)
      setNewName('')
      setNewContent('')
      setNewCategory('')
      message.success('创建成功')
    } catch (error: any) {
      message.error(error.message || '创建失败')
    }
  }

  const handleEdit = (text: TextLibraryItem) => {
    setSelectedText(text)
    setEditName(text.name)
    setEditContent(text.content)
    setEditCategory(text.category)
    setSaveVersion(false)
    setVersionDescription('')
    setEditModalVisible(true)
  }

  const handleSaveEdit = async () => {
    if (!selectedText) return
    
    try {
      const updated = await textLibraryApi.update(selectedText.id, {
        name: editName,
        content: editContent,
        category: editCategory,
        save_version: saveVersion,
        version_description: versionDescription
      })
      setTexts(prev => prev.map(t => t.id === updated.id ? updated : t))
      setEditModalVisible(false)
      message.success('保存成功')
    } catch (error: any) {
      message.error(error.message || '保存失败')
    }
  }

  const handleCopy = (text: TextLibraryItem) => {
    navigator.clipboard.writeText(text.content)
    message.success('已复制到剪贴板')
  }

  const handleViewVersions = (text: TextLibraryItem) => {
    setSelectedText(text)
    setVersionModalVisible(true)
  }

  const handleRestoreVersion = async (version: TextItemVersion) => {
    if (!selectedText) return
    
    try {
      const result = await textLibraryApi.restoreVersion(selectedText.id, version.id)
      setTexts(prev => prev.map(t => t.id === result.text.id ? result.text : t))
      setSelectedText(result.text)
      message.success('版本已恢复')
    } catch (error: any) {
      message.error(error.message || '恢复失败')
    }
  }

  const handleDelete = async (text: TextLibraryItem) => {
    try {
      await textLibraryApi.delete(text.id)
      setTexts(prev => prev.filter(t => t.id !== text.id))
      message.success('删除成功')
    } catch (error: any) {
      message.error(error.message || '删除失败')
    }
  }

  const handleDeleteAll = async () => {
    if (!projectId) return
    try {
      await textLibraryApi.deleteAll(projectId, categoryFilter || undefined)
      setTexts([])
      message.success('全部删除成功')
    } catch (error: any) {
      message.error(error.message || '删除失败')
    }
  }

  // 获取所有分类
  const categories = [...new Set(texts.map(t => t.category).filter(Boolean))]

  return (
    <div style={{ padding: 24 }}>
      <Card
        title={
          <Space>
            <FileTextOutlined />
            文本库
          </Space>
        }
        extra={
          <Space>
            <Select
              placeholder="筛选分类"
              allowClear
              style={{ width: 150 }}
              value={categoryFilter || undefined}
              onChange={(v) => setCategoryFilter(v || '')}
              options={categories.map(c => ({ label: c, value: c }))}
            />
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setCreateModalVisible(true)}
            >
              新建文本
            </Button>
            {texts.length > 0 && (
              <Popconfirm
                title="确定删除所有文本？"
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
        {texts.length === 0 ? (
          <Empty description="暂无文本" />
        ) : (
          <List
            dataSource={texts}
            loading={loading}
            renderItem={(text) => (
              <List.Item
                style={{ background: '#242424', marginBottom: 8, padding: 16, borderRadius: 8 }}
                actions={[
                  <Tooltip title="复制">
                    <Button type="text" icon={<CopyOutlined />} onClick={() => handleCopy(text)} />
                  </Tooltip>,
                  <Tooltip title="版本历史">
                    <Button type="text" icon={<HistoryOutlined />} onClick={() => handleViewVersions(text)}>
                      {text.versions.length}
                    </Button>
                  </Tooltip>,
                  <Button type="text" icon={<EditOutlined />} onClick={() => handleEdit(text)}>
                    编辑
                  </Button>,
                  <Popconfirm title="确定删除？" onConfirm={() => handleDelete(text)}>
                    <Button type="text" danger icon={<DeleteOutlined />} />
                  </Popconfirm>
                ]}
              >
                <List.Item.Meta
                  title={
                    <Space>
                      {text.name}
                      {text.category && <Tag color="blue">{text.category}</Tag>}
                    </Space>
                  }
                  description={
                    <div style={{ 
                      maxHeight: 80, 
                      overflow: 'hidden', 
                      textOverflow: 'ellipsis',
                      color: '#888',
                      whiteSpace: 'pre-wrap'
                    }}>
                      {text.content}
                    </div>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Card>

      {/* 创建弹窗 */}
      <Modal
        title="新建文本"
        open={createModalVisible}
        onCancel={() => {
          setCreateModalVisible(false)
          setNewName('')
          setNewContent('')
          setNewCategory('')
        }}
        onOk={handleCreate}
        okButtonProps={{ disabled: !newName.trim() || !newContent.trim() }}
        width={600}
      >
        <div style={{ marginBottom: 16 }}>
          <div style={{ marginBottom: 8 }}>名称 *</div>
          <Input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="输入文本名称"
          />
        </div>
        <div style={{ marginBottom: 16 }}>
          <div style={{ marginBottom: 8 }}>分类</div>
          <Input
            value={newCategory}
            onChange={(e) => setNewCategory(e.target.value)}
            placeholder="输入分类（可选）"
          />
        </div>
        <div>
          <div style={{ marginBottom: 8 }}>内容 *</div>
          <TextArea
            value={newContent}
            onChange={(e) => setNewContent(e.target.value)}
            placeholder="输入文本内容"
            rows={8}
          />
        </div>
      </Modal>

      {/* 编辑弹窗 */}
      <Modal
        title="编辑文本"
        open={editModalVisible}
        onCancel={() => setEditModalVisible(false)}
        onOk={handleSaveEdit}
        width={600}
      >
        <div style={{ marginBottom: 16 }}>
          <div style={{ marginBottom: 8 }}>名称</div>
          <Input
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
          />
        </div>
        <div style={{ marginBottom: 16 }}>
          <div style={{ marginBottom: 8 }}>分类</div>
          <Input
            value={editCategory}
            onChange={(e) => setEditCategory(e.target.value)}
          />
        </div>
        <div style={{ marginBottom: 16 }}>
          <div style={{ marginBottom: 8 }}>内容</div>
          <TextArea
            value={editContent}
            onChange={(e) => setEditContent(e.target.value)}
            rows={8}
          />
        </div>
        <div style={{ marginBottom: 16 }}>
          <Space>
            <input
              type="checkbox"
              checked={saveVersion}
              onChange={(e) => setSaveVersion(e.target.checked)}
              id="saveVersion"
            />
            <label htmlFor="saveVersion">保存为新版本</label>
          </Space>
        </div>
        {saveVersion && (
          <div>
            <div style={{ marginBottom: 8 }}>版本描述</div>
            <Input
              value={versionDescription}
              onChange={(e) => setVersionDescription(e.target.value)}
              placeholder="输入版本描述（可选）"
            />
          </div>
        )}
      </Modal>

      {/* 版本历史弹窗 */}
      <Modal
        title={`版本历史 - ${selectedText?.name}`}
        open={versionModalVisible}
        onCancel={() => setVersionModalVisible(false)}
        footer={null}
        width={700}
      >
        {selectedText && selectedText.versions.length > 0 ? (
          <Timeline
            items={selectedText.versions.slice().reverse().map((version, index) => ({
              color: index === 0 ? 'green' : 'gray',
              children: (
                <div style={{ background: '#242424', padding: 12, borderRadius: 8, marginBottom: 8 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                    <Space>
                      <strong>{version.description || `版本 ${selectedText.versions.length - index}`}</strong>
                      <span style={{ color: '#888', fontSize: 12 }}>
                        {new Date(version.created_at).toLocaleString()}
                      </span>
                    </Space>
                    <Popconfirm
                      title="确定恢复到此版本？"
                      onConfirm={() => handleRestoreVersion(version)}
                    >
                      <Button size="small" type="link">恢复</Button>
                    </Popconfirm>
                  </div>
                  <div style={{ 
                    maxHeight: 100, 
                    overflow: 'auto', 
                    background: '#1a1a1a', 
                    padding: 8, 
                    borderRadius: 4,
                    fontSize: 12,
                    whiteSpace: 'pre-wrap'
                  }}>
                    {version.content}
                  </div>
                </div>
              )
            }))}
          />
        ) : (
          <Empty description="暂无版本历史" />
        )}
      </Modal>
    </div>
  )
}

export default TextLibraryPage

