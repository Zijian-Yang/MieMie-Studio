import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  Button,
  Typography,
  Space,
  Modal,
  Form,
  Input,
  message,
  Empty,
  Dropdown,
  Spin,
} from 'antd';
import {
  PlusOutlined,
  FolderOutlined,
  MoreOutlined,
  EditOutlined,
  DeleteOutlined,
  CalendarOutlined,
} from '@ant-design/icons';
import { useAppStore } from '../../store';
import { projectsApi } from '../../services/api';
import type { Project } from '../../types';
import styles from './Projects.module.css';
import dayjs from 'dayjs';

const { Title, Text, Paragraph } = Typography;

export default function Projects() {
  const navigate = useNavigate();
  const { projects, loadProjects, loading, setCurrentProject } = useAppStore();
  const [modalVisible, setModalVisible] = useState(false);
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [form] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  const handleCreate = () => {
    setEditingProject(null);
    form.resetFields();
    setModalVisible(true);
  };

  const handleEdit = (project: Project) => {
    setEditingProject(project);
    form.setFieldsValue({ name: project.name, description: project.description });
    setModalVisible(true);
  };

  const handleDelete = async (project: Project) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除项目「${project.name}」吗？此操作不可恢复。`,
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await projectsApi.delete(project.id);
          message.success('项目已删除');
          loadProjects();
        } catch {
          message.error('删除失败');
        }
      },
    });
  };

  const handleSubmit = async (values: { name: string; description: string }) => {
    setSubmitting(true);
    try {
      if (editingProject) {
        await projectsApi.update(editingProject.id, values);
        message.success('项目已更新');
      } else {
        const newProject = await projectsApi.create(values);
        message.success('项目创建成功');
        setCurrentProject(newProject);
        navigate(`/project/${newProject.id}/script`);
      }
      setModalVisible(false);
      loadProjects();
    } catch {
      message.error(editingProject ? '更新失败' : '创建失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleOpenProject = (project: Project) => {
    setCurrentProject(project);
    navigate(`/project/${project.id}/script`);
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div>
          <Title level={2} className="page-title">
            项目管理
          </Title>
          <Text className="page-description">
            创建和管理您的 AI 视频项目
          </Text>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          size="large"
          onClick={handleCreate}
        >
          新建项目
        </Button>
      </div>

      <Spin spinning={loading}>
        {projects.length === 0 ? (
          <Card className={styles.emptyCard}>
            <Empty
              image={<FolderOutlined style={{ fontSize: 64, color: 'var(--color-text-tertiary)' }} />}
              description={
                <div>
                  <Text style={{ fontSize: 16 }}>还没有任何项目</Text>
                  <br />
                  <Text type="secondary">点击上方按钮创建您的第一个 AI 视频项目</Text>
                </div>
              }
            >
              <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
                新建项目
              </Button>
            </Empty>
          </Card>
        ) : (
          <div className={styles.grid}>
            {projects.map((project) => (
              <Card
                key={project.id}
                className={styles.projectCard}
                onClick={() => handleOpenProject(project)}
                hoverable
              >
                <div className={styles.cardContent}>
                  <div className={styles.cardIcon}>
                    <FolderOutlined />
                  </div>
                  <div className={styles.cardInfo}>
                    <Title level={4} ellipsis className={styles.cardTitle}>
                      {project.name}
                    </Title>
                    <Paragraph
                      type="secondary"
                      ellipsis={{ rows: 2 }}
                      className={styles.cardDesc}
                    >
                      {project.description || '暂无描述'}
                    </Paragraph>
                    <Space className={styles.cardMeta}>
                      <CalendarOutlined />
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {dayjs(project.updated_at).format('YYYY-MM-DD HH:mm')}
                      </Text>
                    </Space>
                  </div>
                  <Dropdown
                    menu={{
                      items: [
                        {
                          key: 'edit',
                          icon: <EditOutlined />,
                          label: '编辑',
                          onClick: (e) => {
                            e.domEvent.stopPropagation();
                            handleEdit(project);
                          },
                        },
                        {
                          key: 'delete',
                          icon: <DeleteOutlined />,
                          label: '删除',
                          danger: true,
                          onClick: (e) => {
                            e.domEvent.stopPropagation();
                            handleDelete(project);
                          },
                        },
                      ],
                    }}
                    trigger={['click']}
                  >
                    <Button
                      type="text"
                      icon={<MoreOutlined />}
                      onClick={(e) => e.stopPropagation()}
                      className={styles.moreBtn}
                    />
                  </Dropdown>
                </div>
              </Card>
            ))}
          </div>
        )}
      </Spin>

      <Modal
        title={editingProject ? '编辑项目' : '新建项目'}
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        footer={null}
        destroyOnClose
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item
            name="name"
            label="项目名称"
            rules={[{ required: true, message: '请输入项目名称' }]}
          >
            <Input placeholder="输入项目名称" size="large" />
          </Form.Item>
          <Form.Item name="description" label="项目描述">
            <Input.TextArea
              placeholder="输入项目描述（可选）"
              rows={3}
              showCount
              maxLength={200}
            />
          </Form.Item>
          <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
            <Space>
              <Button onClick={() => setModalVisible(false)}>取消</Button>
              <Button type="primary" htmlType="submit" loading={submitting}>
                {editingProject ? '保存' : '创建'}
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

