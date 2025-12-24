import { useState } from 'react'
import { Outlet, useNavigate, useLocation, useParams } from 'react-router-dom'
import { Layout, Menu, Button, Tooltip, Avatar, Dropdown, message } from 'antd'
// Note: We use a plain div instead of Layout.Content for better scrolling behavior
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
  LogoutOutlined,
} from '@ant-design/icons'
import type { MenuProps } from 'antd'
import { useAuthStore } from '../../stores/authStore'
import { authApi } from '../../services/api'

// Using plain div instead of Content for proper scrolling

const MainLayout = () => {
  const [collapsed, setCollapsed] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const { projectId } = useParams()
  const { user, logout } = useAuthStore()

  // 处理登出
  const handleLogout = async () => {
    try {
      await authApi.logout()
    } catch (e) {
      // 忽略错误
    }
    logout()
    message.success('已退出登录')
    navigate('/login')
  }

  // 用户下拉菜单
  const userMenuItems: MenuProps['items'] = [
    {
      key: 'user-info',
      label: (
        <div style={{ padding: '4px 0' }}>
          <div style={{ fontWeight: 500 }}>{user?.display_name}</div>
          <div style={{ fontSize: 12, color: '#888' }}>@{user?.username}</div>
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

  // 工作流程菜单项
  const workflowItems: MenuProps['items'] = projectId ? [
    {
      key: 'divider-workflow',
      type: 'divider',
    },
    {
      key: 'workflow-title',
      label: <span style={{ color: '#888', fontSize: 12 }}>工作流程</span>,
      disabled: true,
    },
    {
      key: `/project/${projectId}/script`,
      icon: <FileTextOutlined />,
      label: '分镜脚本',
    },
    {
      key: `/project/${projectId}/styles`,
      icon: <FormatPainterOutlined />,
      label: '风格',
    },
    {
      key: `/project/${projectId}/characters`,
      icon: <UserOutlined />,
      label: '角色',
    },
    {
      key: `/project/${projectId}/scenes`,
      icon: <PictureOutlined />,
      label: '场景',
    },
    {
      key: `/project/${projectId}/props`,
      icon: <AppstoreOutlined />,
      label: '道具',
    },
    {
      key: `/project/${projectId}/frames`,
      icon: <PlaySquareOutlined />,
      label: '分镜首帧',
    },
    {
      key: `/project/${projectId}/videos`,
      icon: <VideoCameraOutlined />,
      label: '视频生成',
    },
    {
      key: 'divider-tools',
      type: 'divider',
    },
    {
      key: 'tools-title',
      label: <span style={{ color: '#888', fontSize: 12 }}>素材工具</span>,
      disabled: true,
    },
    {
      key: `/project/${projectId}/gallery`,
      icon: <DatabaseOutlined />,
      label: '图库',
    },
    {
      key: `/project/${projectId}/studio`,
      icon: <ExperimentOutlined />,
      label: '图片工作室',
    },
    {
      key: `/project/${projectId}/audio-library`,
      icon: <SoundOutlined />,
      label: '音频库',
    },
    {
      key: `/project/${projectId}/audio-studio`,
      icon: <AudioOutlined />,
      label: '音频工作室',
    },
    {
      key: `/project/${projectId}/video-library`,
      icon: <PlayCircleOutlined />,
      label: '视频库',
    },
    {
      key: `/project/${projectId}/video-studio`,
      icon: <VideoCameraOutlined />,
      label: '视频工作室',
    },
    {
      key: `/project/${projectId}/text-library`,
      icon: <FileTextOutlined />,
      label: '文本库',
    },
  ] : []

  const menuItems: MenuProps['items'] = [
    {
      key: '/projects',
      icon: <FolderOutlined />,
      label: '项目',
    },
    ...workflowItems,
    {
      key: 'divider-settings',
      type: 'divider',
    },
    {
      key: '/settings',
      icon: <SettingOutlined />,
      label: '设置',
    },
  ]

  const handleMenuClick: MenuProps['onClick'] = (e) => {
    if (e.key.startsWith('/')) {
      navigate(e.key)
    }
  }

  // 获取当前选中的菜单项
  const selectedKey = location.pathname

  const siderWidth = collapsed ? 64 : 220

  return (
    <Layout style={{ minHeight: '100vh', background: '#1a1a1a' }}>
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
          background: '#141414',
          borderRight: '1px solid #333',
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
            borderBottom: '1px solid #333',
          }}
        >
          {collapsed ? (
            <VideoCameraOutlined style={{ fontSize: 24, color: '#e5a84b' }} />
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <VideoCameraOutlined style={{ fontSize: 24, color: '#e5a84b' }} />
              <span style={{ fontSize: 16, fontWeight: 600, color: '#e0e0e0' }}>
                淸水Studio
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
              style={{
                width: '100%',
                color: '#888',
              }}
            />
          </Tooltip>
        </div>

        {/* 菜单 - 可滚动区域 */}
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
            style={{
              border: 'none',
              background: 'transparent',
            }}
          />
        </div>

        {/* 用户信息区域 */}
        <div 
          style={{ 
            flexShrink: 0,
            borderTop: '1px solid #333',
            padding: collapsed ? '12px 8px' : '12px 16px',
          }}
        >
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
              }}
              onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.05)'}
              onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
            >
              <Avatar 
                size={collapsed ? 32 : 36} 
                style={{ 
                  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                  flexShrink: 0,
                }}
              >
                {user?.display_name?.[0]?.toUpperCase() || 'U'}
              </Avatar>
              {!collapsed && (
                <div style={{ overflow: 'hidden' }}>
                  <div style={{ 
                    color: '#e0e0e0', 
                    fontWeight: 500, 
                    fontSize: 14,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}>
                    {user?.display_name}
                  </div>
                  <div style={{ 
                    color: '#888', 
                    fontSize: 12,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}>
                    @{user?.username}
                  </div>
                </div>
              )}
            </div>
          </Dropdown>
        </div>
      </div>

      {/* 内容区域 */}
      <div
        style={{
          marginLeft: siderWidth,
          minHeight: '100vh',
          background: '#1a1a1a',
          transition: 'margin-left 0.2s',
        }}
      >
        <Outlet />
      </div>

      {/* 滚动条样式 */}
      <style>{`
        .sidebar-menu-scroll {
          scrollbar-width: thin;
          scrollbar-color: #444 transparent;
        }
        .sidebar-menu-scroll::-webkit-scrollbar {
          width: 6px;
        }
        .sidebar-menu-scroll::-webkit-scrollbar-track {
          background: transparent;
        }
        .sidebar-menu-scroll::-webkit-scrollbar-thumb {
          background: #444;
          border-radius: 3px;
        }
        .sidebar-menu-scroll::-webkit-scrollbar-thumb:hover {
          background: #555;
        }
        .sidebar-menu-scroll .ant-menu {
          height: auto !important;
          overflow: visible !important;
        }
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

