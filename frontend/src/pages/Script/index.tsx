import { useState, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card,
  Button,
  Typography,
  Space,
  Switch,
  Select,
  Input,
  message,
  Upload,
  Checkbox,
  Tabs,
  Collapse,
  Tooltip,
  Spin,
  Empty,
} from 'antd';
import {
  UploadOutlined,
  ClearOutlined,
  SaveOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  MinusOutlined,
  FileTextOutlined,
  RobotOutlined,
  EditOutlined,
} from '@ant-design/icons';
import type { UploadFile } from 'antd/es/upload/interface';
import { scriptsApi } from '../../services/api';
import { useAppStore } from '../../store';
import { LLM_MODELS } from '../../types';
import type { ScriptScene } from '../../types';
import styles from './Script.module.css';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

interface StreamColumn {
  id: number;
  model: string;
  content: string;
  loading: boolean;
  selected: boolean;
}

const DEFAULT_PROMPT = `你是一位专业的影视编剧和分镜师。请根据用户提供的剧本内容，生成详细的分镜脚本。

每个分镜需要包含以下信息，使用"字段名：内容"格式，多个分镜之间用"---"分隔：
- 镜头设计：描述镜头的运动和切换方式
- 景别：远景/全景/中景/近景/特写
- 配音主体：需要配音的角色，无则填"无配音"
- 视频台词：角色台词，无则填"无台词"
- 出镜角色：该镜头中出现的所有角色，用"、"分隔
- 角色造型：角色的服装、发型等外观描述
- 角色动作：角色在该镜头中的具体动作
- 场景设置：场景的环境描述
- 光线设计：光线的来源、强度、色调
- 情绪基调：该镜头想要传达的情绪
- 构图：构图方式
- 道具：镜头中出现的重要道具，用"、"分隔
- 音效：需要的背景音效
- 视频时长：建议的镜头时长（秒）`;

export default function Script() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { currentProject, updateScript } = useAppStore();

  const [inputContent, setInputContent] = useState('');
  const [aiMode, setAiMode] = useState(false);
  const [customPrompt, setCustomPrompt] = useState(DEFAULT_PROMPT);
  const [showPromptEditor, setShowPromptEditor] = useState(false);
  const [columns, setColumns] = useState<StreamColumn[]>([
    { id: 1, model: 'qwen3-max', content: '', loading: false, selected: true },
  ]);
  const [parsedScenes, setParsedScenes] = useState<ScriptScene[]>([]);
  const [saving, setSaving] = useState(false);
  const [parsing, setParsing] = useState(false);

  const abortControllerRef = useRef<AbortController | null>(null);

  // 处理文件上传
  const handleFileUpload = async (file: UploadFile) => {
    if (!projectId || !file.originFileObj) return false;

    try {
      const result = await scriptsApi.upload(file.originFileObj, projectId);
      setInputContent(result.content);
      message.success(`文件解析成功，共 ${result.length} 字`);
    } catch {
      message.error('文件解析失败');
    }
    return false;
  };

  // 添加对比栏
  const addColumn = () => {
    if (columns.length >= 3) {
      message.warning('最多支持 3 个对比栏');
      return;
    }
    const newId = Math.max(...columns.map((c) => c.id)) + 1;
    setColumns([
      ...columns,
      { id: newId, model: 'qwen-plus-latest', content: '', loading: false, selected: false },
    ]);
  };

  // 移除对比栏
  const removeColumn = (id: number) => {
    if (columns.length <= 1) return;
    const newColumns = columns.filter((c) => c.id !== id);
    // 确保至少有一个选中
    if (!newColumns.some((c) => c.selected)) {
      newColumns[0].selected = true;
    }
    setColumns(newColumns);
  };

  // 选择对比栏
  const selectColumn = (id: number) => {
    setColumns(
      columns.map((c) => ({
        ...c,
        selected: c.id === id,
      }))
    );
  };

  // 更新对比栏模型
  const updateColumnModel = (id: number, model: string) => {
    setColumns(columns.map((c) => (c.id === id ? { ...c, model } : c)));
  };

  // 生成脚本
  const handleGenerate = useCallback(async () => {
    if (!inputContent.trim()) {
      message.warning('请先输入剧本内容');
      return;
    }

    // 重置内容
    setColumns((cols) => cols.map((c) => ({ ...c, content: '', loading: true })));

    // 并行生成所有列
    const promises = columns.map(async (column) => {
      try {
        let content = '';
        for await (const chunk of scriptsApi.generateStream(
          inputContent,
          column.model,
          customPrompt
        )) {
          content += chunk;
          setColumns((cols) =>
            cols.map((c) => (c.id === column.id ? { ...c, content } : c))
          );
        }
        setColumns((cols) =>
          cols.map((c) => (c.id === column.id ? { ...c, loading: false } : c))
        );
      } catch (error) {
        console.error('Generation error:', error);
        setColumns((cols) =>
          cols.map((c) =>
            c.id === column.id
              ? { ...c, loading: false, content: '生成失败，请重试' }
              : c
          )
        );
      }
    });

    await Promise.all(promises);
  }, [inputContent, columns, customPrompt]);

  // 解析分镜
  const handleParse = async () => {
    const selectedColumn = columns.find((c) => c.selected);
    const content = aiMode ? selectedColumn?.content : inputContent;

    if (!content?.trim()) {
      message.warning('没有可解析的内容');
      return;
    }

    setParsing(true);
    try {
      const result = await scriptsApi.parseScenes(content);
      setParsedScenes(result.scenes);
      message.success(`成功解析 ${result.scenes.length} 个分镜`);
    } catch {
      message.error('解析失败');
    } finally {
      setParsing(false);
    }
  };

  // 保存脚本
  const handleSave = async () => {
    if (!projectId) return;

    const selectedColumn = columns.find((c) => c.selected);
    const content = aiMode ? selectedColumn?.content : inputContent;

    if (!content?.trim()) {
      message.warning('没有可保存的内容');
      return;
    }

    setSaving(true);
    try {
      // 先解析
      let scenes = parsedScenes;
      if (scenes.length === 0) {
        const result = await scriptsApi.parseScenes(content);
        scenes = result.scenes;
        setParsedScenes(scenes);
      }

      // 保存
      await scriptsApi.save(projectId, content, scenes);
      updateScript(content, scenes);
      message.success('脚本保存成功');
    } catch {
      message.error('保存失败');
    } finally {
      setSaving(false);
    }
  };

  // 清空
  const handleClear = () => {
    setInputContent('');
    setColumns((cols) => cols.map((c) => ({ ...c, content: '' })));
    setParsedScenes([]);
  };

  // 继续下一步
  const handleNext = () => {
    if (!projectId) return;
    navigate(`/project/${projectId}/characters`);
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div>
          <Title level={2} className="page-title">
            分镜脚本
          </Title>
          <Text className="page-description">
            输入或上传剧本，使用 AI 生成专业的分镜脚本
          </Text>
        </div>
        <Space>
          <Button icon={<ClearOutlined />} onClick={handleClear}>
            清空
          </Button>
          <Button
            type="primary"
            icon={<SaveOutlined />}
            onClick={handleSave}
            loading={saving}
          >
            保存脚本
          </Button>
        </Space>
      </div>

      {/* AI 编剧开关 */}
      <Card className={styles.toggleCard}>
        <Space size="large">
          <Space>
            <RobotOutlined style={{ fontSize: 20 }} />
            <Text strong>AI 编剧模式</Text>
          </Space>
          <Switch
            checked={aiMode}
            onChange={setAiMode}
            checkedChildren="开启"
            unCheckedChildren="关闭"
          />
          <Text type="secondary">
            {aiMode
              ? '使用 AI 模型优化和生成分镜脚本'
              : '直接使用输入的剧本内容'}
          </Text>
        </Space>
      </Card>

      {/* 输入区域 */}
      <Card className={styles.inputCard} title="剧本输入">
        <div className={styles.inputHeader}>
          <Upload
            accept=".txt,.md,.docx,.pdf"
            showUploadList={false}
            beforeUpload={handleFileUpload}
          >
            <Button icon={<UploadOutlined />}>上传文件</Button>
          </Upload>
          <Text type="secondary">支持 .txt, .md, .docx, .pdf 格式</Text>
        </div>
        <TextArea
          value={inputContent}
          onChange={(e) => setInputContent(e.target.value)}
          placeholder="在此输入剧本内容，或上传剧本文件..."
          rows={10}
          className={styles.textarea}
        />
      </Card>

      {/* AI 生成区域 */}
      {aiMode && (
        <Card className={styles.aiCard}>
          <div className={styles.aiHeader}>
            <Space>
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                onClick={handleGenerate}
                loading={columns.some((c) => c.loading)}
              >
                生成分镜脚本
              </Button>
              <Button
                icon={<PlusOutlined />}
                onClick={addColumn}
                disabled={columns.length >= 3}
              >
                添加对比栏
              </Button>
            </Space>
            <Button
              type="link"
              icon={<EditOutlined />}
              onClick={() => setShowPromptEditor(!showPromptEditor)}
            >
              {showPromptEditor ? '收起提示词' : '编辑提示词'}
            </Button>
          </div>

          {/* 提示词编辑器 */}
          {showPromptEditor && (
            <div className={styles.promptEditor}>
              <Text type="secondary" style={{ marginBottom: 8, display: 'block' }}>
                自定义分镜脚本生成提示词：
              </Text>
              <TextArea
                value={customPrompt}
                onChange={(e) => setCustomPrompt(e.target.value)}
                rows={6}
                className={styles.promptTextarea}
              />
              <Button
                size="small"
                onClick={() => setCustomPrompt(DEFAULT_PROMPT)}
                style={{ marginTop: 8 }}
              >
                恢复默认
              </Button>
            </div>
          )}

          {/* 多栏对比 */}
          <div className={styles.columnsContainer}>
            {columns.map((column) => (
              <div key={column.id} className={styles.column}>
                <div className={styles.columnHeader}>
                  <Space>
                    <Checkbox
                      checked={column.selected}
                      onChange={() => selectColumn(column.id)}
                    />
                    <Select
                      value={column.model}
                      onChange={(v) => updateColumnModel(column.id, v)}
                      options={LLM_MODELS.map((m) => ({
                        value: m.code,
                        label: m.name,
                      }))}
                      style={{ width: 140 }}
                      size="small"
                    />
                  </Space>
                  {columns.length > 1 && (
                    <Button
                      type="text"
                      icon={<MinusOutlined />}
                      onClick={() => removeColumn(column.id)}
                      size="small"
                    />
                  )}
                </div>
                <div className={styles.streamOutput}>
                  {column.loading ? (
                    <div className={styles.loadingContent}>
                      {column.content || <Spin size="small" />}
                      <span className="stream-cursor" />
                    </div>
                  ) : column.content ? (
                    <pre>{column.content}</pre>
                  ) : (
                    <Empty
                      image={Empty.PRESENTED_IMAGE_SIMPLE}
                      description="点击生成按钮开始"
                    />
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* 非 AI 模式下的原始内容展示 */}
      {!aiMode && inputContent && (
        <Card className={styles.previewCard} title="剧本预览">
          <pre className={styles.preview}>{inputContent}</pre>
        </Card>
      )}

      {/* 分镜解析结果 */}
      <Card
        className={styles.scenesCard}
        title={
          <Space>
            <FileTextOutlined />
            <span>分镜脚本解析结果</span>
            {parsedScenes.length > 0 && (
              <Text type="secondary">（共 {parsedScenes.length} 个分镜）</Text>
            )}
          </Space>
        }
        extra={
          <Space>
            <Button onClick={handleParse} loading={parsing}>
              解析分镜
            </Button>
            <Button type="primary" onClick={handleNext} disabled={parsedScenes.length === 0}>
              继续：角色管理
            </Button>
          </Space>
        }
      >
        {parsedScenes.length > 0 ? (
          <Collapse
            items={parsedScenes.map((scene, index) => ({
              key: scene.id,
              label: (
                <Space>
                  <Text strong>分镜 {scene.scene_number || index + 1}</Text>
                  <Text type="secondary">{scene.shot_design}</Text>
                </Space>
              ),
              children: (
                <div className={styles.sceneDetail}>
                  <div className={styles.sceneRow}>
                    <Text type="secondary">景别：</Text>
                    <Text>{scene.shot_type || '-'}</Text>
                  </div>
                  <div className={styles.sceneRow}>
                    <Text type="secondary">出镜角色：</Text>
                    <Text>{scene.characters?.join('、') || '-'}</Text>
                  </div>
                  <div className={styles.sceneRow}>
                    <Text type="secondary">角色动作：</Text>
                    <Text>{scene.character_action || '-'}</Text>
                  </div>
                  <div className={styles.sceneRow}>
                    <Text type="secondary">场景设置：</Text>
                    <Text>{scene.scene_setting || '-'}</Text>
                  </div>
                  <div className={styles.sceneRow}>
                    <Text type="secondary">情绪基调：</Text>
                    <Text>{scene.mood || '-'}</Text>
                  </div>
                  <div className={styles.sceneRow}>
                    <Text type="secondary">视频时长：</Text>
                    <Text>{scene.duration}秒</Text>
                  </div>
                </div>
              ),
            }))}
          />
        ) : (
          <Empty description="请先生成或解析分镜脚本" />
        )}
      </Card>
    </div>
  );
}

