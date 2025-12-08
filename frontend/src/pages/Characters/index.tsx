import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
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
  Spin,
  Checkbox,
  Row,
  Col,
  Image,
  Tabs,
} from 'antd';
import {
  UserOutlined,
  PlusOutlined,
  SyncOutlined,
  EditOutlined,
  SoundOutlined,
  RightOutlined,
} from '@ant-design/icons';
import { charactersApi } from '../../services/api';
import { useAppStore } from '../../store';
import type { Character, CharacterImageSet } from '../../types';
import styles from './Characters.module.css';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

// 通用提示词
const DEFAULT_COMMON_PROMPT = `half-body portrait, white pure background, high detail, consistent lighting, professional photography style, studio lighting, 8k quality`;

export default function Characters() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { currentProject, updateCharacters } = useAppStore();

  const [characters, setCharacters] = useState<Character[]>([]);
  const [loading, setLoading] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [selectedCharacter, setSelectedCharacter] = useState<Character | null>(null);
  const [modalVisible, setModalVisible] = useState(false);
  const [generating, setGenerating] = useState<{ [key: string]: boolean }>({});

  const [form] = Form.useForm();
  const [commonPrompt, setCommonPrompt] = useState(DEFAULT_COMMON_PROMPT);

  useEffect(() => {
    if (projectId) {
      loadCharacters();
    }
  }, [projectId]);

  useEffect(() => {
    if (currentProject?.characters) {
      setCharacters(currentProject.characters);
    }
  }, [currentProject]);

  const loadCharacters = async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const result = await charactersApi.list(projectId);
      setCharacters(result.characters);
    } catch {
      // 可能是空的
    } finally {
      setLoading(false);
    }
  };

  // 从剧本提取角色
  const handleExtract = async () => {
    if (!projectId || !currentProject?.script?.processed_content) {
      message.warning('请先保存分镜脚本');
      return;
    }

    setExtracting(true);
    try {
      const result = await charactersApi.extract(
        projectId,
        currentProject.script.processed_content
      );
      setCharacters(result.characters);
      updateCharacters(result.characters);
      message.success(`成功提取 ${result.count} 个角色`);
    } catch {
      message.error('角色提取失败');
    } finally {
      setExtracting(false);
    }
  };

  // 打开角色编辑
  const handleEditCharacter = (character: Character) => {
    setSelectedCharacter(character);
    form.setFieldsValue({
      name: character.name,
      description: character.description,
      appearance: character.appearance,
      prompt: character.prompt,
    });
    setModalVisible(true);
  };

  // 生成角色图片
  const handleGenerateImages = async (characterId: string, setIndex: number) => {
    const key = `${characterId}-${setIndex}`;
    setGenerating((prev) => ({ ...prev, [key]: true }));

    try {
      const result = await charactersApi.generate(
        characterId,
        setIndex,
        commonPrompt,
        selectedCharacter?.prompt
      );

      // 更新角色数据
      setCharacters((chars) =>
        chars.map((c) => {
          if (c.id === characterId) {
            const newSets = [...c.image_sets];
            newSets[setIndex] = result.image_set;
            return { ...c, image_sets: newSets };
          }
          return c;
        })
      );

      if (selectedCharacter?.id === characterId) {
        setSelectedCharacter((prev) => {
          if (!prev) return null;
          const newSets = [...prev.image_sets];
          newSets[setIndex] = result.image_set;
          return { ...prev, image_sets: newSets };
        });
      }

      message.success(`第 ${setIndex + 1} 组图片生成成功`);
    } catch {
      message.error('图片生成失败');
    } finally {
      setGenerating((prev) => ({ ...prev, [key]: false }));
    }
  };

  // 保存角色修改
  const handleSaveCharacter = async (values: Partial<Character>) => {
    if (!selectedCharacter) return;

    try {
      const updated = await charactersApi.update(selectedCharacter.id, values);
      setCharacters((chars) =>
        chars.map((c) => (c.id === updated.id ? updated : c))
      );
      updateCharacters(
        characters.map((c) => (c.id === updated.id ? updated : c))
      );
      message.success('角色信息已更新');
      setModalVisible(false);
    } catch {
      message.error('保存失败');
    }
  };

  // 选择图片组
  const handleSelectImageSet = async (characterId: string, setId: string) => {
    try {
      const updated = await charactersApi.update(characterId, {
        selected_set_id: setId,
      });
      setCharacters((chars) =>
        chars.map((c) => (c.id === updated.id ? updated : c))
      );
      if (selectedCharacter?.id === characterId) {
        setSelectedCharacter(updated);
      }
    } catch {
      message.error('选择失败');
    }
  };

  const handleNext = () => {
    if (!projectId) return;
    navigate(`/project/${projectId}/scenes`);
  };

  const getSelectedImage = (character: Character): string | undefined => {
    const selectedSet = character.image_sets.find(
      (s) => s.id === character.selected_set_id
    );
    return selectedSet?.front_url || character.image_sets[0]?.front_url;
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div>
          <Title level={2} className="page-title">
            角色管理
          </Title>
          <Text className="page-description">
            提取和管理剧本中的角色，生成角色三视图
          </Text>
        </div>
        <Space>
          <Button
            icon={<SyncOutlined />}
            onClick={handleExtract}
            loading={extracting}
          >
            从剧本提取角色
          </Button>
          <Button type="primary" onClick={handleNext} icon={<RightOutlined />}>
            继续：场景管理
          </Button>
        </Space>
      </div>

      <Spin spinning={loading}>
        {characters.length === 0 ? (
          <Card className={styles.emptyCard}>
            <Empty
              image={
                <UserOutlined
                  style={{ fontSize: 64, color: 'var(--color-text-tertiary)' }}
                />
              }
              description={
                <div>
                  <Text style={{ fontSize: 16 }}>还没有角色</Text>
                  <br />
                  <Text type="secondary">
                    请先保存分镜脚本，然后点击"从剧本提取角色"
                  </Text>
                </div>
              }
            >
              <Button
                type="primary"
                icon={<SyncOutlined />}
                onClick={handleExtract}
                loading={extracting}
              >
                从剧本提取角色
              </Button>
            </Empty>
          </Card>
        ) : (
          <div className={styles.grid}>
            {characters.map((character) => (
              <Card
                key={character.id}
                className={styles.characterCard}
                hoverable
                onClick={() => handleEditCharacter(character)}
              >
                <div className={styles.cardImage}>
                  {getSelectedImage(character) ? (
                    <Image
                      src={getSelectedImage(character)}
                      alt={character.name}
                      preview={false}
                    />
                  ) : (
                    <div className={styles.imagePlaceholder}>
                      <UserOutlined />
                    </div>
                  )}
                </div>
                <div className={styles.cardInfo}>
                  <Title level={5} ellipsis className={styles.cardTitle}>
                    {character.name}
                  </Title>
                  <Paragraph
                    type="secondary"
                    ellipsis={{ rows: 2 }}
                    className={styles.cardDesc}
                  >
                    {character.description || '暂无描述'}
                  </Paragraph>
                </div>
              </Card>
            ))}
          </div>
        )}
      </Spin>

      {/* 角色编辑弹窗 */}
      <Modal
        title={`编辑角色：${selectedCharacter?.name}`}
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        width={900}
        footer={null}
        destroyOnClose
      >
        {selectedCharacter && (
          <Tabs
            items={[
              {
                key: 'info',
                label: '基本信息',
                children: (
                  <Form
                    form={form}
                    layout="vertical"
                    onFinish={handleSaveCharacter}
                  >
                    <Row gutter={16}>
                      <Col span={12}>
                        <Form.Item name="name" label="角色名称">
                          <Input />
                        </Form.Item>
                      </Col>
                      <Col span={12}>
                        <Form.Item name="appearance" label="外貌特征">
                          <Input />
                        </Form.Item>
                      </Col>
                    </Row>
                    <Form.Item name="description" label="角色描述">
                      <TextArea rows={3} />
                    </Form.Item>
                    <Form.Item name="prompt" label="生图提示词">
                      <TextArea rows={4} />
                    </Form.Item>
                    <Form.Item>
                      <Button type="primary" htmlType="submit">
                        保存信息
                      </Button>
                    </Form.Item>
                  </Form>
                ),
              },
              {
                key: 'images',
                label: '角色图片',
                children: (
                  <div className={styles.imagesTab}>
                    <div className={styles.commonPromptSection}>
                      <Text strong>通用提示词：</Text>
                      <TextArea
                        value={commonPrompt}
                        onChange={(e) => setCommonPrompt(e.target.value)}
                        rows={2}
                        className={styles.commonPromptInput}
                      />
                    </div>

                    {selectedCharacter.image_sets.map((imageSet, index) => (
                      <div key={imageSet.id} className={styles.imageSetRow}>
                        <div className={styles.imageSetHeader}>
                          <Checkbox
                            checked={
                              selectedCharacter.selected_set_id === imageSet.id
                            }
                            onChange={() =>
                              handleSelectImageSet(
                                selectedCharacter.id,
                                imageSet.id
                              )
                            }
                          >
                            <Text strong>第 {index + 1} 组</Text>
                          </Checkbox>
                          <Button
                            size="small"
                            icon={<SyncOutlined />}
                            onClick={() =>
                              handleGenerateImages(selectedCharacter.id, index)
                            }
                            loading={
                              generating[`${selectedCharacter.id}-${index}`]
                            }
                          >
                            生成
                          </Button>
                        </div>
                        <div className={styles.imageSetImages}>
                          {['front', 'side', 'back'].map((view) => {
                            const url =
                              imageSet[
                                `${view}_url` as keyof CharacterImageSet
                              ] as string | undefined;
                            return (
                              <div key={view} className={styles.imageItem}>
                                {url ? (
                                  <Image src={url} alt={`${view} view`} />
                                ) : (
                                  <div className={styles.imagePlaceholderSmall}>
                                    <UserOutlined />
                                    <Text type="secondary">
                                      {view === 'front'
                                        ? '正面'
                                        : view === 'side'
                                        ? '侧面'
                                        : '背面'}
                                    </Text>
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                ),
              },
              {
                key: 'voice',
                label: '音色设置',
                children: (
                  <div className={styles.voiceTab}>
                    <Empty
                      image={<SoundOutlined style={{ fontSize: 48 }} />}
                      description="音色功能即将上线"
                    >
                      <Text type="secondary">
                        支持选择预设音色或上传音频进行声音克隆
                      </Text>
                    </Empty>
                  </div>
                ),
              },
            ]}
          />
        )}
      </Modal>
    </div>
  );
}

