import { useState, useEffect } from 'react';
import {
  Card,
  Form,
  Input,
  Button,
  message,
  Space,
  Typography,
  Alert,
  Divider,
} from 'antd';
import {
  KeyOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  SaveOutlined,
} from '@ant-design/icons';
import { settingsApi } from '../../services/api';
import styles from './Settings.module.css';

const { Title, Text, Paragraph } = Typography;

export default function Settings() {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [hasApiKey, setHasApiKey] = useState(false);
  const [verifying, setVerifying] = useState(false);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const settings = await settingsApi.get();
      setHasApiKey(settings.has_api_key);
      if (settings.dashscope_api_key) {
        form.setFieldsValue({ api_key: settings.dashscope_api_key });
      }
    } catch (error) {
      console.error('Failed to load settings:', error);
    }
  };

  const handleSave = async (values: { api_key: string }) => {
    setLoading(true);
    try {
      const result = await settingsApi.update({ dashscope_api_key: values.api_key });
      setHasApiKey(result.has_api_key);
      message.success('API Key 保存成功');
    } catch (error) {
      message.error('保存失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async () => {
    setVerifying(true);
    try {
      await settingsApi.verify();
      message.success('API Key 验证成功');
    } catch (error) {
      message.error('API Key 无效或验证失败');
    } finally {
      setVerifying(false);
    }
  };

  return (
    <div className={styles.container}>
      <div className="page-header">
        <Title level={2} className="page-title">
          设置
        </Title>
        <Text className="page-description">
          配置平台的 API 密钥和其他设置
        </Text>
      </div>

      <Card className={styles.card}>
        <div className={styles.cardHeader}>
          <KeyOutlined className={styles.cardIcon} />
          <div>
            <Title level={4} style={{ margin: 0 }}>
              百炼 DashScope API Key
            </Title>
            <Paragraph type="secondary" style={{ margin: '4px 0 0' }}>
              用于调用通义万相的文生图、图生视频和 Qwen 大模型服务
            </Paragraph>
          </div>
        </div>

        <Divider />

        {hasApiKey ? (
          <Alert
            message="API Key 已配置"
            description="您已成功配置 API Key，可以开始使用平台功能"
            type="success"
            icon={<CheckCircleOutlined />}
            showIcon
            className={styles.alert}
          />
        ) : (
          <Alert
            message="请配置 API Key"
            description="使用平台功能前，需要先配置阿里云百炼 DashScope API Key"
            type="warning"
            icon={<ExclamationCircleOutlined />}
            showIcon
            className={styles.alert}
          />
        )}

        <Form form={form} layout="vertical" onFinish={handleSave}>
          <Form.Item
            name="api_key"
            label="API Key"
            rules={[{ required: true, message: '请输入 API Key' }]}
          >
            <Input.Password
              placeholder="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
              size="large"
            />
          </Form.Item>

          <Form.Item>
            <Space>
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
                icon={<SaveOutlined />}
                size="large"
              >
                保存
              </Button>
              <Button
                onClick={handleVerify}
                loading={verifying}
                disabled={!hasApiKey}
                size="large"
              >
                验证 API Key
              </Button>
            </Space>
          </Form.Item>
        </Form>

        <Divider />

        <div className={styles.helpSection}>
          <Title level={5}>如何获取 API Key？</Title>
          <ol className={styles.helpList}>
            <li>
              访问{' '}
              <a
                href="https://dashscope.console.aliyun.com/"
                target="_blank"
                rel="noopener noreferrer"
              >
                阿里云百炼控制台
              </a>
            </li>
            <li>登录您的阿里云账号</li>
            <li>在「API-KEY 管理」页面创建或查看您的 API Key</li>
            <li>将 API Key 复制到上方输入框中</li>
          </ol>
        </div>
      </Card>
    </div>
  );
}

