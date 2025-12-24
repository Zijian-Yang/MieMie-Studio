/**
 * 登录页面 - 美观的登录界面，带动态渐变背景
 */

import React, { useState } from 'react'
import { Form, Input, Button, message, Typography, Space } from 'antd'
import { UserOutlined, LockOutlined, LoginOutlined, UserAddOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../stores/authStore'
import { authApi } from '../../services/api'
import './LoginPage.css'

const { Title, Text } = Typography

const LoginPage: React.FC = () => {
  const navigate = useNavigate()
  const { login } = useAuthStore()
  const [loading, setLoading] = useState(false)
  const [isRegister, setIsRegister] = useState(false)
  const [form] = Form.useForm()

  const handleSubmit = async (values: { username: string; password: string; display_name?: string }) => {
    setLoading(true)
    try {
      if (isRegister) {
        // 注册
        const response = await authApi.register(values.username, values.password, values.display_name)
        login(response.token, response.user)
        message.success('注册成功，欢迎使用！')
      } else {
        // 登录
        const response = await authApi.login(values.username, values.password)
        login(response.token, response.user)
        message.success(`欢迎回来，${response.user.display_name}！`)
      }
      navigate('/')
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || (isRegister ? '注册失败' : '登录失败')
      message.error(errorMsg)
    } finally {
      setLoading(false)
    }
  }

  const toggleMode = () => {
    setIsRegister(!isRegister)
    form.resetFields()
  }

  return (
    <div className="login-page">
      {/* 动态渐变背景 */}
      <div className="login-background">
        <div className="gradient-orb orb-1"></div>
        <div className="gradient-orb orb-2"></div>
        <div className="gradient-orb orb-3"></div>
        <div className="gradient-orb orb-4"></div>
      </div>

      {/* 登录卡片 */}
      <div className="login-card">
        {/* Logo 区域 */}
        <div className="login-logo">
          <div className="logo-icon">
            <svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
              <defs>
                <linearGradient id="logoGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#667eea" />
                  <stop offset="100%" stopColor="#764ba2" />
                </linearGradient>
              </defs>
              <circle cx="50" cy="50" r="45" fill="url(#logoGradient)" />
              <path 
                d="M35 40 L50 30 L65 40 L65 60 L50 70 L35 60 Z" 
                fill="white" 
                opacity="0.9"
              />
              <circle cx="50" cy="50" r="8" fill="white" />
              <path 
                d="M50 42 L50 35" 
                stroke="white" 
                strokeWidth="3" 
                strokeLinecap="round"
              />
              <path 
                d="M43 54 L37 58" 
                stroke="white" 
                strokeWidth="3" 
                strokeLinecap="round"
              />
              <path 
                d="M57 54 L63 58" 
                stroke="white" 
                strokeWidth="3" 
                strokeLinecap="round"
              />
            </svg>
          </div>
          <Title level={2} className="logo-title">淸水Studio</Title>
          <Text className="logo-subtitle">AI 视频创作平台</Text>
        </div>

        {/* 表单区域 */}
        <Form
          form={form}
          name="login"
          onFinish={handleSubmit}
          size="large"
          className="login-form"
        >
          <Form.Item
            name="username"
            rules={[
              { required: true, message: '请输入用户名' },
              { min: 2, message: '用户名至少2个字符' },
              { max: 20, message: '用户名最多20个字符' },
            ]}
          >
            <Input
              prefix={<UserOutlined className="input-icon" />}
              placeholder="用户名"
              autoComplete="username"
            />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[
              { required: true, message: '请输入密码' },
              { min: 4, message: '密码至少4个字符' },
            ]}
          >
            <Input.Password
              prefix={<LockOutlined className="input-icon" />}
              placeholder="密码"
              autoComplete={isRegister ? 'new-password' : 'current-password'}
            />
          </Form.Item>

          {isRegister && (
            <Form.Item
              name="display_name"
              rules={[
                { max: 30, message: '显示名称最多30个字符' },
              ]}
            >
              <Input
                prefix={<UserOutlined className="input-icon" />}
                placeholder="显示名称（选填）"
              />
            </Form.Item>
          )}

          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              block
              className="login-button"
              icon={isRegister ? <UserAddOutlined /> : <LoginOutlined />}
            >
              {isRegister ? '注册' : '登录'}
            </Button>
          </Form.Item>

          <div className="login-footer">
            <Space>
              <Text type="secondary">
                {isRegister ? '已有账号？' : '没有账号？'}
              </Text>
              <Button type="link" onClick={toggleMode} className="toggle-button">
                {isRegister ? '立即登录' : '立即注册'}
              </Button>
            </Space>
          </div>
        </Form>
      </div>

      {/* 版权信息 */}
      <div className="login-copyright">
        <Text type="secondary">© 2024 淸水Studio. All rights reserved.</Text>
      </div>
    </div>
  )
}

export default LoginPage

