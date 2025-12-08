import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, Button, Modal, Form, Input, Empty, Spin, message, Popconfirm } from 'antd'
import { PlusOutlined, DeleteOutlined, EditOutlined, FolderOpenOutlined } from '@ant-design/icons'
import { useProjectStore } from '../../stores/projectStore'
import dayjs from 'dayjs'

const ProjectsPage = () => {
  const navigate = useNavigate()
  const { projects, loading, fetchProjects, createProject, deleteProject, setCurrentProject } = useProjectStore()
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [form] = Form.useForm()

  useEffect(() => {
    fetchProjects()
  }, [fetchProjects])

  const handleCreateProject = async () => {
    try {
      const values = await form.validateFields()
      const project = await createProject(values.name, values.description)
      setIsModalOpen(false)
      form.resetFields()
      message.success('项目创建成功')
      // 跳转到新项目的分镜脚本页面
      navigate(`/project/${project.id}/script`)
    } catch (error) {
      if (error instanceof Error) {
        message.error(error.message)
      }
    }
  }

  const handleOpenProject = (projectId: string) => {
    const project = projects.find(p => p.id === projectId)
    if (project) {
      setCurrentProject(project)
      navigate(`/project/${projectId}/script`)
    }
  }

  const handleDeleteProject = async (projectId: string) => {
    try {
      await deleteProject(projectId)
      message.success('项目已删除')
    } catch (error) {
      if (error instanceof Error) {
        message.error(error.message)
      }
    }
  }

  return (
    <div style={{ padding: 24 }}>
      {/* 页面标题 */}
      <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 600, margin: 0, color: '#e0e0e0' }}>
            项目列表
          </h1>
          <p style={{ color: '#888', marginTop: 8 }}>
            管理您的 AI 视频生成项目
          </p>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          size="large"
          onClick={() => setIsModalOpen(true)}
        >
          新建项目
        </Button>
      </div>

      {/* 项目列表 */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: 100 }}>
          <Spin size="large" />
        </div>
      ) : projects.length === 0 ? (
        <Empty
          description="暂无项目"
          style={{ marginTop: 100 }}
        >
          <Button type="primary" onClick={() => setIsModalOpen(true)}>
            创建第一个项目
          </Button>
        </Empty>
      ) : (
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', 
          gap: 20 
        }}>
          {projects.map((project) => (
            <Card
              key={project.id}
              hoverable
              style={{
                background: '#242424',
                borderColor: '#333',
              }}
              actions={[
                <Button
                  key="open"
                  type="text"
                  icon={<FolderOpenOutlined />}
                  onClick={() => handleOpenProject(project.id)}
                >
                  打开
                </Button>,
                <Popconfirm
                  key="delete"
                  title="确定要删除这个项目吗？"
                  description="删除后将无法恢复"
                  onConfirm={() => handleDeleteProject(project.id)}
                  okText="删除"
                  cancelText="取消"
                  okButtonProps={{ danger: true }}
                >
                  <Button
                    type="text"
                    danger
                    icon={<DeleteOutlined />}
                  >
                    删除
                  </Button>
                </Popconfirm>,
              ]}
            >
              <Card.Meta
                title={
                  <span style={{ color: '#e0e0e0', fontSize: 16 }}>
                    {project.name}
                  </span>
                }
                description={
                  <div>
                    <p style={{ 
                      color: '#888', 
                      marginBottom: 12,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}>
                      {project.description || '暂无描述'}
                    </p>
                    <div style={{ fontSize: 12, color: '#666' }}>
                      <div>分镜数：{project.script?.shots?.length || 0}</div>
                      <div>角色数：{project.character_ids?.length || 0}</div>
                      <div>更新时间：{dayjs(project.updated_at).format('YYYY-MM-DD HH:mm')}</div>
                    </div>
                  </div>
                }
              />
            </Card>
          ))}
        </div>
      )}

      {/* 新建项目弹窗 */}
      <Modal
        title="新建项目"
        open={isModalOpen}
        onOk={handleCreateProject}
        onCancel={() => {
          setIsModalOpen(false)
          form.resetFields()
        }}
        okText="创建"
        cancelText="取消"
      >
        <Form
          form={form}
          layout="vertical"
          style={{ marginTop: 20 }}
        >
          <Form.Item
            name="name"
            label="项目名称"
            rules={[{ required: true, message: '请输入项目名称' }]}
          >
            <Input placeholder="输入项目名称" />
          </Form.Item>
          <Form.Item
            name="description"
            label="项目描述"
          >
            <Input.TextArea 
              placeholder="输入项目描述（可选）" 
              rows={3}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default ProjectsPage

