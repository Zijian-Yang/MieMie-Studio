import { useState } from 'react'
import { Outlet, useNavigate, useLocation, useParams } from 'react-router-dom'
import { Layout, Menu, Button, Tooltip, Avatar, Dropdown, message, theme } from 'antd'
import {
  FolderOutlined,
  FileTextOutlined,
  UserOutlined,
  PictureOutlined,
  AppstoreOutlined,
  VideoCameraOutlined,
  PlaySquareOutlined,
  SettingOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  FormatPainterOutlined,
  DatabaseOutlined,
  ExperimentOutlined,
  SoundOutlined,
  PlayCircleOutlined,
  AudioOutlined,
  BarChartOutlined,
  LogoutOutlined,
  SunOutlined,
  MoonOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons'
import type { MenuProps } from 'antd'
import { useAuthStore } from '../../stores/authStore'
import { useThemeStore } from '../../stores/themeStore'
import { authApi } from '../../services/api'

const MainLayout = () => {
  const [collapsed, setCollapsed] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const { projectId } = useParams()
  const { user, logout } = useAuthStore()
  const { mode, toggleTheme } = useThemeStore()
  const { token } = theme.useToken()
  const avatarGradient = `linear-gradient(135deg, ${token.colorPrimary} 0%, ${token.colorPrimaryHover} 100%)`

  const handleLogout = async () => {
    try {
      await authApi.logout()
    } catch (e) {
      // ignore
    }
    logout()
    message.success('已退出登录')
    navigate('/login')
  }

  const userMenuItems: MenuProps['items'] = [
    {
      key: 'user-info',
      label: (
        <div style={{ padding: '4px 0' }}>
          <div style={{ fontWeight: 500 }}>{user?.display_name}</div>
          <div style={{ fontSize: 12, color: token.colorTextSecondary }}>@{user?.username}</div>
        </div>
      ),
      disabled: true,
    },
    { type: 'divider' },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      onClick: handleLogout,
    },
  ]

  const sectionTitleStyle = { color: token.colorTextTertiary, fontSize: 12 }

  const projectSectionItems: MenuProps['items'] = projectId ? [
    { key: 'divider-tools', type: 'divider' },
    { key: 'tools-title', label: <span style={sectionTitleStyle}>素材工具</span>, disabled: true },
    { key: `/project/${projectId}/gallery`, icon: <DatabaseOutlined />, label: '图库' },
    { key: `/project/${projectId}/studio`, icon: <ExperimentOutlined />, label: '图片工作室' },
    { key: `/project/${projectId}/audio-library`, icon: <SoundOutlined />, label: '音频库' },
    { key: `/project/${projectId}/audio-studio`, icon: <AudioOutlined />, label: '音频工作室' },
    { key: `/project/${projectId}/video-library`, icon: <PlayCircleOutlined />, label: '视频库' },
    { key: `/project/${projectId}/video-studio`, icon: <VideoCameraOutlined />, label: '视频工作室' },
    { key: `/project/${projectId}/text-library`, icon: <FileTextOutlined />, label: '文本库' },
    { key: `/project/${projectId}/image-benchmark-datasets`, icon: <DatabaseOutlined />, label: '数据集' },
    { key: `/project/${projectId}/image-benchmark`, icon: <BarChartOutlined />, label: '图片测评' },
    { key: `/project/${projectId}/video-benchmark-datasets`, icon: <DatabaseOutlined />, label: '视频数据集' },
    { key: `/project/${projectId}/video-benchmark`, icon: <BarChartOutlined />, label: '视频测评' },
    { key: 'divider-workflow', type: 'divider' },
    { key: 'workflow-title', label: <span style={sectionTitleStyle}>工作流程</span>, disabled: true },
    { key: `/project/${projectId}/script`, icon: <FileTextOutlined />, label: '分镜脚本' },
    { key: `/project/${projectId}/styles`, icon: <FormatPainterOutlined />, label: '风格' },
    { key: `/project/${projectId}/characters`, icon: <UserOutlined />, label: '角色' },
    { key: `/project/${projectId}/scenes`, icon: <PictureOutlined />, label: '场景' },
    { key: `/project/${projectId}/props`, icon: <AppstoreOutlined />, label: '道具' },
    { key: `/project/${projectId}/frames`, icon: <PlaySquareOutlined />, label: '分镜首帧' },
    { key: `/project/${projectId}/videos`, icon: <VideoCameraOutlined />, label: '旧版视频生成' },
  ] : []

  const menuItems: MenuProps['items'] = [
    { key: '/projects', icon: <FolderOutlined />, label: '项目' },
    ...projectSectionItems,
    { key: 'divider-settings', type: 'divider' },
    { key: '/settings', icon: <SettingOutlined />, label: '设置' },
    ...(user?.role === 'admin'
      ? [{ key: '/admin/overview', icon: <SafetyCertificateOutlined />, label: '平台管理' }]
      : []),
  ]

  const handleMenuClick: MenuProps['onClick'] = (e) => {
    if (e.key.startsWith('/')) {
      navigate(e.key)
    }
  }

  const selectedKey = location.pathname
  const siderWidth = collapsed ? 64 : 220

  const siderBg = token.colorBgContainer

  return (
    <Layout style={{ minHeight: '100vh', background: token.colorBgLayout }}>
      {/* 固定侧边栏 */}
      <div
        style={{
          width: siderWidth,
          minWidth: siderWidth,
          maxWidth: siderWidth,
          height: '100vh',
          position: 'fixed',
          left: 0,
          top: 0,
          zIndex: 100,
          background: siderBg,
          borderRight: `1px solid ${token.colorBorderSecondary}`,
          display: 'flex',
          flexDirection: 'column',
          transition: 'width 0.2s',
        }}
      >
        {/* Logo */}
        <div
          style={{
            height: 56,
            flexShrink: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-start',
            padding: collapsed ? 0 : '0 20px',
            borderBottom: `1px solid ${token.colorBorderSecondary}`,
          }}
        >
          {collapsed ? (
            <VideoCameraOutlined style={{ fontSize: 24, color: token.colorPrimary }} />
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <VideoCameraOutlined style={{ fontSize: 24, color: token.colorPrimary }} />
              <span style={{ fontSize: 16, fontWeight: 600, color: token.colorText }}>
                MieMie Studio
              </span>
            </div>
          )}
        </div>

        {/* 折叠按钮 */}
        <div style={{ padding: '12px 16px', flexShrink: 0 }}>
          <Tooltip title={collapsed ? '展开' : '收起'} placement="right">
            <Button
              type="text"
              icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => setCollapsed(!collapsed)}
              style={{ width: '100%', color: token.colorTextSecondary }}
            />
          </Tooltip>
        </div>

        {/* 菜单 */}
        <div
          style={{
            flex: '1 1 0%',
            minHeight: 0,
            overflowY: 'auto',
            overflowX: 'hidden',
            paddingBottom: 20,
          }}
          className="sidebar-menu-scroll"
        >
          <Menu
            mode="inline"
            selectedKeys={[selectedKey]}
            items={menuItems}
            onClick={handleMenuClick}
            inlineCollapsed={collapsed}
            style={{ border: 'none', background: 'transparent' }}
          />
        </div>

        {/* 用户信息区域 + 主题切换 */}
        <div
          style={{
            flexShrink: 0,
            borderTop: `1px solid ${token.colorBorderSecondary}`,
            padding: collapsed ? '12px 8px' : '12px 16px',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            {/* 用户信息（可点击展开菜单） */}
            <Dropdown menu={{ items: userMenuItems }} placement="topRight" trigger={['click']}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  cursor: 'pointer',
                  padding: '8px',
                  borderRadius: 8,
                  transition: 'background 0.2s',
                  flex: 1,
                  minWidth: 0,
                }}
                onMouseEnter={(e) =>
                  (e.currentTarget.style.background = token.colorFillQuaternary)
                }
                onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
              >
                <Avatar
                  size={collapsed ? 32 : 36}
                  style={{
                    background: avatarGradient,
                    flexShrink: 0,
                  }}
                >
                  {user?.display_name?.[0]?.toUpperCase() || 'U'}
                </Avatar>
                {!collapsed && (
                  <div style={{ overflow: 'hidden' }}>
                    <div
                      style={{
                        color: token.colorText,
                        fontWeight: 500,
                        fontSize: 14,
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                    >
                      {user?.display_name}
                    </div>
                    <div
                      style={{
                        color: token.colorTextSecondary,
                        fontSize: 12,
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                    >
                      @{user?.username}
                    </div>
                  </div>
                )}
              </div>
            </Dropdown>

            {/* 主题切换按钮 */}
            {!collapsed && (
              <Tooltip title={mode === 'dark' ? '切换到日间模式' : '切换到夜间模式'}>
                <Button
                  type="text"
                  size="small"
                  icon={mode === 'dark' ? <SunOutlined /> : <MoonOutlined />}
                  onClick={toggleTheme}
                  style={{
                    flexShrink: 0,
                    color: token.colorTextSecondary,
                    fontSize: 16,
                  }}
                />
              </Tooltip>
            )}
          </div>

          {/* 折叠态：独立的主题切换按钮 */}
          {collapsed && (
            <div style={{ marginTop: 8, textAlign: 'center' }}>
              <Tooltip title={mode === 'dark' ? '日间模式' : '夜间模式'} placement="right">
                <Button
                  type="text"
                  size="small"
                  icon={mode === 'dark' ? <SunOutlined /> : <MoonOutlined />}
                  onClick={toggleTheme}
                  style={{ color: token.colorTextSecondary, fontSize: 16 }}
                />
              </Tooltip>
            </div>
          )}
        </div>
      </div>

      {/* 内容区域 */}
      <div
        style={{
          marginLeft: siderWidth,
          minHeight: '100vh',
          background: token.colorBgLayout,
          transition: 'margin-left 0.2s',
        }}
      >
        <Outlet />
      </div>

      <style>{`
        .sidebar-menu-scroll {
          scrollbar-width: thin;
          scrollbar-color: ${token.colorBorderSecondary} transparent;
        }
        .sidebar-menu-scroll::-webkit-scrollbar { width: 6px; }
        .sidebar-menu-scroll::-webkit-scrollbar-track { background: transparent; }
        .sidebar-menu-scroll::-webkit-scrollbar-thumb {
          background: ${token.colorBorderSecondary};
          border-radius: 3px;
        }
        .sidebar-menu-scroll::-webkit-scrollbar-thumb:hover {
          background: ${token.colorTextQuaternary};
        }
        .sidebar-menu-scroll .ant-menu { height: auto !important; overflow: visible !important; }
        .sidebar-menu-scroll .ant-menu-inline .ant-menu-item,
        .sidebar-menu-scroll .ant-menu-inline .ant-menu-submenu-title {
          margin-inline: 4px;
          width: calc(100% - 8px);
        }
      `}</style>
    </Layout>
  )
}

export default MainLayout
