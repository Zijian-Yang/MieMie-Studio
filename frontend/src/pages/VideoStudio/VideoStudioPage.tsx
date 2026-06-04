import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { Tag } from 'antd'
import type { VideoStudioTask } from '../../services/api'
import { useProjectStore } from '../../stores/projectStore'
import CapabilityCreateModal from './CapabilityCreateModal'
import {
  TASK_KIND_META,
  getResolvedTaskKind,
} from './taskViewUtils'
import { useVideoStudioData } from './useVideoStudioData'
import TaskListPanel from './TaskListPanel'
import TaskDetailModal from './TaskDetailModal'
import { useVideoStudioTaskActions } from './useVideoStudioTaskActions'

const VideoStudioPage = () => {
  const { projectId } = useParams<{ projectId: string }>()
  const { fetchProject } = useProjectStore()

  const [createModalVisible, setCreateModalVisible] = useState(false)
  const [detailModalVisible, setDetailModalVisible] = useState(false)
  const [editModalVisible, setEditModalVisible] = useState(false)
  const [selectedTask, setSelectedTask] = useState<VideoStudioTask | null>(null)
  const {
    tasks,
    setTasks,
    loading,
    galleryImages,
    audioItems,
    videoLibraryItems,
    startTaskPolling,
  } = useVideoStudioData({ projectId, fetchProject, setSelectedTask })
  const {
    extractingFrames,
    regenerating,
    handleSaveToLibrary,
    handleExtractLastFrame,
    handleToggleVideoMarker,
    handleDelete,
    handleRegenerate,
    handleDeleteAll,
  } = useVideoStudioTaskActions({
    projectId,
    tasks,
    selectedTask,
    setTasks,
    setSelectedTask,
    startTaskPolling,
  })

  const getCanonicalTaskTag = (task: VideoStudioTask) => {
    const taskKind = getResolvedTaskKind(task)
    const item = TASK_KIND_META[taskKind]
    return <Tag color={item.color}>{item.text}</Tag>
  }

  const handleViewDetail = (task: VideoStudioTask) => {
    setSelectedTask(task)
    setDetailModalVisible(true)

    // 如果正在处理，启动轮询
    if (task.status === 'processing') {
      startTaskPolling(task.id)
    }
  }

  const openEditModal = (task: VideoStudioTask) => {
    setSelectedTask(task)
    setEditModalVisible(true)
  }

  const getStatusTag = (status: string) => {
    const statusMap: Record<string, { color: string; text: string }> = {
      pending: { color: 'default', text: '等待中' },
      processing: { color: 'processing', text: '生成中' },
      succeeded: { color: 'success', text: '已完成' },
      failed: { color: 'error', text: '失败' }
    }
    const s = statusMap[status] || { color: 'default', text: status }
    return <Tag color={s.color}>{s.text}</Tag>
  }

  return (
    <div style={{ padding: 24 }}>
      <TaskListPanel
        tasks={tasks}
        loading={loading}
        renderTaskKindTag={getCanonicalTaskTag}
        renderStatusTag={getStatusTag}
        onCreate={() => setCreateModalVisible(true)}
        onDeleteAll={handleDeleteAll}
        onViewDetail={handleViewDetail}
        onDelete={handleDelete}
      />

      {projectId && createModalVisible && (
        <CapabilityCreateModal
          open={createModalVisible}
          projectId={projectId}
          galleryImages={galleryImages}
          audioItems={audioItems}
          videoLibraryItems={videoLibraryItems}
          mode="create"
          onCancel={() => setCreateModalVisible(false)}
          onSubmitted={(task) => {
            setTasks((prev) => [task, ...prev.filter((item) => item.id !== task.id)])
            if (task.status === 'processing') {
              startTaskPolling(task.id)
            }
          }}
        />
      )}

      {projectId && editModalVisible && (
        <CapabilityCreateModal
          open={editModalVisible}
          projectId={projectId}
          galleryImages={galleryImages}
          audioItems={audioItems}
          videoLibraryItems={videoLibraryItems}
          mode="edit"
          task={selectedTask}
          onCancel={() => setEditModalVisible(false)}
          onSubmitted={(task) => {
            setTasks((prev) => prev.map((item) => item.id === task.id ? task : item))
            setSelectedTask(task)
            setEditModalVisible(false)
          }}
        />
      )}

      <TaskDetailModal
        open={detailModalVisible}
        task={selectedTask}
        audioItems={audioItems}
        extractingFrames={extractingFrames}
        regenerating={regenerating}
        renderTaskKindTag={getCanonicalTaskTag}
        renderStatusTag={getStatusTag}
        onClose={() => setDetailModalVisible(false)}
        onEdit={openEditModal}
        onRegenerate={handleRegenerate}
        onToggleVideoMarker={handleToggleVideoMarker}
        onSaveToLibrary={handleSaveToLibrary}
        onExtractLastFrame={handleExtractLastFrame}
      />

    </div>
  )
}

export default VideoStudioPage
