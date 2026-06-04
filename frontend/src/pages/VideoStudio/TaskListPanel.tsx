import type { ReactNode } from 'react'
import { Button, Card, Empty, List, Popconfirm, Space, Spin, Tag, theme } from 'antd'
import { DeleteOutlined, PlayCircleOutlined, PlusOutlined, VideoCameraOutlined } from '@ant-design/icons'
import type { VideoStudioTask } from '../../services/api'
import {
  TASK_CARD_META_ROW_STYLE,
  TASK_CARD_PROGRESS_STYLE,
  TASK_CARD_TAGS_STYLE,
} from './taskCardLayout'
import { getTaskPreviewUrl } from './taskViewUtils'

interface TaskListPanelProps {
  tasks: VideoStudioTask[]
  loading: boolean
  renderTaskKindTag: (task: VideoStudioTask) => ReactNode
  renderStatusTag: (status: string) => ReactNode
  onCreate: () => void
  onDeleteAll: () => void
  onViewDetail: (task: VideoStudioTask) => void
  onDelete: (task: VideoStudioTask) => void
}

const TaskListPanel = ({
  tasks,
  loading,
  renderTaskKindTag,
  renderStatusTag,
  onCreate,
  onDeleteAll,
  onViewDetail,
  onDelete,
}: TaskListPanelProps) => {
  const { token } = theme.useToken()

  return (
    <Card
      title={
        <Space>
          <VideoCameraOutlined />
          视频工作室
        </Space>
      }
      extra={
        <Space>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={onCreate}
          >
            新建任务
          </Button>
          {tasks.length > 0 && (
            <Popconfirm
              title="确定删除所有任务？"
              onConfirm={onDeleteAll}
            >
              <Button danger icon={<DeleteOutlined />}>
                全部删除
              </Button>
            </Popconfirm>
          )}
        </Space>
      }
    >
      {tasks.length === 0 ? (
        <Empty description="暂无任务" />
      ) : (
        <List
          grid={{ gutter: 16, column: 4 }}
          dataSource={tasks}
          loading={loading}
          renderItem={(task) => (
            <List.Item>
              <Card
                size="small"
                cover={
                  <div
                    style={{
                      height: 120,
                      background: token.colorBgLayout,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      cursor: 'pointer',
                      position: 'relative',
                    }}
                    onClick={() => onViewDetail(task)}
                  >
                    {getTaskPreviewUrl(task) ? (
                      <img
                        src={getTaskPreviewUrl(task)}
                        alt="首帧"
                        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                      />
                    ) : (
                      <PlayCircleOutlined style={{ fontSize: 48, color: token.colorPrimary }} />
                    )}
                    {task.status === 'processing' && (
                      <div style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        right: 0,
                        bottom: 0,
                        background: 'rgba(0,0,0,0.5)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}>
                        <Spin />
                      </div>
                    )}
                  </div>
                }
                actions={[
                  <Button type="link" size="small" onClick={() => onViewDetail(task)}>查看</Button>,
                  <Popconfirm title="确定删除？" onConfirm={() => onDelete(task)}>
                    <Button type="link" size="small" danger>删除</Button>
                  </Popconfirm>,
                ]}
              >
                <div style={{ fontWeight: 500, marginBottom: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {task.name}
                </div>
                <div style={TASK_CARD_META_ROW_STYLE}>
                  <Space size={[4, 4]} wrap style={TASK_CARD_TAGS_STYLE}>
                    {renderTaskKindTag(task)}
                    {task.provider && <Tag>{task.provider.toUpperCase()}</Tag>}
                    {renderStatusTag(task.status)}
                  </Space>
                  <span style={{ ...TASK_CARD_PROGRESS_STYLE, color: token.colorTextSecondary }}>
                    {task.video_urls.length}/{task.group_count}
                  </span>
                </div>
              </Card>
            </List.Item>
          )}
        />
      )}
    </Card>
  )
}

export default TaskListPanel
