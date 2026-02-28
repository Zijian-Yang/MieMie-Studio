// @ts-nocheck
// Legacy file — replaced by MainLayout.tsx
import { Outlet, useNavigate, useLocation, useParams } from 'react-router-dom';
import { Layout, Menu, Typography, Space, Button, Dropdown } from 'antd';
import {
  SettingOutlined,
  FileTextOutlined,
  UserOutlined,
  PictureOutlined,
  AppstoreOutlined,
  VideoCameraOutlined,
  PlaySquareOutlined,
  FolderOutlined,
  PlusOutlined,
  DownOutlined,
} from '@ant-design/icons';
import { useEffect } from 'react';
import { useAppStore } from '../../store';
import type { MenuProps } from 'antd';
import styles from './Layout.module.css';

const { Sider, Content } = Layout;
const { Title, Text } = Typography;

export default function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { projectId } = useParams();
  const { projects, currentProject, loadProjects, loadProject, setCurrentProject } = useAppStore();

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  useEffect(() => {
    if (projectId && projectId !== currentProject?.id) {
      loadProject(projectId);
    }
  }, [projectId, currentProject?.id, loadProject]);

  const getSelectedKey = () => {
    const path = location.pathname;
    if (path.includes('/settings')) return 'settings';
    if (path.includes('/projects')) return 'projects';
    if (path.includes('/script')) return 'script';
    if (path.includes('/characters')) return 'characters';
    if (path.includes('/scenes')) return 'scenes';
    if (path.includes('/props')) return 'props';
    if (path.includes('/frames')) return 'frames';
    if (path.includes('/videos')) return 'videos';
    return 'projects';
  };

  const handleMenuClick = (key: string) => {
    if (key === 'settings') {
      navigate('/settings');
    } else if (key === 'projects') {
      setCurrentProject(null);
      navigate('/projects');
    } else if (currentProject) {
      navigate(`/project/${currentProject.id}/${key}`);
    }
  };

  const projectMenuItems: MenuProps['items'] = projects.map((p) => ({
    key: p.id,
    label: p.name,
    onClick: () => {
      loadProject(p.id);
      navigate(`/project/${p.id}/script`);
    },
  }));

  const mainMenuItems = [
    {
      key: 'projects',
      icon: <FolderOutlined />,
      label: '项目管理',
    },
    {
      key: 'settings',
      icon: <SettingOutlined />,
      label: '设置',
    },
  ];

  const workflowMenuItems = currentProject
    ? [
        { key: 'script', icon: <FileTextOutlined />, label: '分镜脚本' },
        { key: 'characters', icon: <UserOutlined />, label: '角色管理' },
        { key: 'scenes', icon: <PictureOutlined />, label: '场景管理' },
        { key: 'props', icon: <AppstoreOutlined />, label: '道具管理' },
        { key: 'frames', icon: <PlaySquareOutlined />, label: '分镜首帧' },
        { key: 'videos', icon: <VideoCameraOutlined />, label: '视频生成' },
      ]
    : [];

  return (
    <Layout className={styles.layout}>
      <Sider width={260} className={styles.sider}>
        <div className={styles.logo}>
          <Title level={4} style={{ margin: 0 }}>
            🎬 AI 视频平台
          </Title>
        </div>

        {/* 项目选择器 */}
        <div className={styles.projectSelector}>
          <Dropdown
            menu={{ items: projectMenuItems }}
            trigger={['click']}
            disabled={projects.length === 0}
          >
            <Button block className={styles.projectButton}>
              <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                <Text ellipsis style={{ color: 'inherit', maxWidth: 160 }}>
                  {currentProject?.name || '选择项目'}
                </Text>
                <DownOutlined />
              </Space>
            </Button>
          </Dropdown>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => navigate('/projects')}
            className={styles.newProjectBtn}
          >
            新建
          </Button>
        </div>

        {/* 工作流菜单 */}
        {currentProject && (
          <>
            <div className={styles.menuSection}>
              <Text className={styles.menuSectionTitle}>工作流程</Text>
            </div>
            <Menu
              mode="inline"
              selectedKeys={[getSelectedKey()]}
              items={workflowMenuItems}
              onClick={({ key }) => handleMenuClick(key)}
              className={styles.menu}
            />
          </>
        )}

        {/* 系统菜单 */}
        <div className={styles.menuSection}>
          <Text className={styles.menuSectionTitle}>系统</Text>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[getSelectedKey()]}
          items={mainMenuItems}
          onClick={({ key }) => handleMenuClick(key)}
          className={styles.menu}
        />
      </Sider>

      <Content className={styles.content}>
        <Outlet />
      </Content>
    </Layout>
  );
}

