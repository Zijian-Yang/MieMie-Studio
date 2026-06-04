import { useCallback, useState } from 'react'
import type { Dispatch, SetStateAction } from 'react'
import { message } from 'antd'
import { videoStudioApi } from '../../services/api'
import type { VideoStudioTask } from '../../services/api'

interface UseVideoStudioTaskActionsOptions {
  projectId?: string
  tasks: VideoStudioTask[]
  selectedTask: VideoStudioTask | null
  setTasks: Dispatch<SetStateAction<VideoStudioTask[]>>
  setSelectedTask: Dispatch<SetStateAction<VideoStudioTask | null>>
  startTaskPolling: (taskId: string) => void
}

export const useVideoStudioTaskActions = ({
  projectId,
  tasks,
  selectedTask,
  setTasks,
  setSelectedTask,
  startTaskPolling,
}: UseVideoStudioTaskActionsOptions) => {
  const [extractingFrames, setExtractingFrames] = useState<Set<string>>(new Set())
  const [regenerating, setRegenerating] = useState(false)

  const handleSaveToLibrary = useCallback(async (videoUrl: string) => {
    if (!selectedTask) return

    try {
      await videoStudioApi.saveToLibrary(selectedTask.id, videoUrl)
      message.success('已保存到视频库')
    } catch (error: any) {
      message.error(error.message || '保存失败')
    }
  }, [selectedTask])

  const handleExtractLastFrame = useCallback(async (videoUrl: string) => {
    if (!selectedTask) return
    setExtractingFrames(prev => new Set([...prev, videoUrl]))
    try {
      await videoStudioApi.extractLastFrame(selectedTask.id, videoUrl)
      message.success('尾帧已保存到图库')
    } catch (error: any) {
      message.error(error.message || '提取尾帧失败')
    } finally {
      setExtractingFrames(prev => {
        const next = new Set(prev)
        next.delete(videoUrl)
        return next
      })
    }
  }, [selectedTask])

  const handleToggleVideoMarker = useCallback(async (taskId: string, videoUrl: string, markerKey: string) => {
    const task = tasks.find(t => t.id === taskId)
    if (!task) return
    const currentMarkers = task.video_markers?.[videoUrl] || []
    const newMarkers = currentMarkers.includes(markerKey)
      ? currentMarkers.filter((m: string) => m !== markerKey)
      : [...currentMarkers, markerKey]
    try {
      const res = await videoStudioApi.updateVideoMarkers(taskId, videoUrl, newMarkers)
      const updatedVideoMarkers = res.video_markers
      setTasks(prev => prev.map(t => t.id === taskId ? { ...t, video_markers: updatedVideoMarkers } : t))
      if (selectedTask?.id === taskId) {
        setSelectedTask(prev => prev ? { ...prev, video_markers: updatedVideoMarkers } : prev)
      }
    } catch {
      message.error('标记更新失败')
    }
  }, [selectedTask?.id, setSelectedTask, setTasks, tasks])

  const handleDelete = useCallback(async (task: VideoStudioTask) => {
    try {
      await videoStudioApi.delete(task.id)
      setTasks(prev => prev.filter(t => t.id !== task.id))
      message.success('删除成功')
    } catch (error: any) {
      message.error(error.message || '删除失败')
    }
  }, [setTasks])

  const handleRegenerate = useCallback(async (task: VideoStudioTask) => {
    try {
      setRegenerating(true)
      const { task: updatedTask } = await videoStudioApi.regenerate(task.id)
      setTasks(prev => prev.map(t => t.id === task.id ? updatedTask : t))
      setSelectedTask(updatedTask)

      startTaskPolling(task.id)

      message.success('已开始重新生成')
    } catch (error: any) {
      message.error(error.message || '重新生成失败')
    } finally {
      setRegenerating(false)
    }
  }, [setSelectedTask, setTasks, startTaskPolling])

  const handleDeleteAll = useCallback(async () => {
    if (!projectId) return
    try {
      await videoStudioApi.deleteAll(projectId)
      setTasks([])
      message.success('全部删除成功')
    } catch (error: any) {
      message.error(error.message || '删除失败')
    }
  }, [projectId, setTasks])

  return {
    extractingFrames,
    regenerating,
    handleSaveToLibrary,
    handleExtractLastFrame,
    handleToggleVideoMarker,
    handleDelete,
    handleRegenerate,
    handleDeleteAll,
  }
}
