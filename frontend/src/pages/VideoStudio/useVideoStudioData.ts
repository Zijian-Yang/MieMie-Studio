import { useCallback, useEffect, useRef, useState } from 'react'
import type { Dispatch, SetStateAction } from 'react'
import { message } from 'antd'
import {
  audioApi,
  galleryApi,
  settingsApi,
  videoLibraryApi,
  videoStudioApi,
} from '../../services/api'
import type {
  AudioItem,
  GalleryImage,
  KeyframeToVideoModelInfo,
  RefVideoModelInfo,
  TextToVideoModelInfo,
  VaceVideoEditModelInfo,
  VaceVideoRepaintingModelInfo,
  VideoLibraryItem,
  VideoModelInfo,
  VideoStudioTask,
} from '../../services/api'
import { useTaskPolling } from '../../hooks/useTaskPolling'

interface UseVideoStudioDataOptions {
  projectId?: string
  fetchProject: (projectId: string) => void | Promise<void>
  setSelectedTask: Dispatch<SetStateAction<VideoStudioTask | null>>
}

export const useVideoStudioData = ({
  projectId,
  fetchProject,
  setSelectedTask,
}: UseVideoStudioDataOptions) => {
  const [tasks, setTasks] = useState<VideoStudioTask[]>([])
  const [loading, setLoading] = useState(true)
  const [galleryImages, setGalleryImages] = useState<GalleryImage[]>([])
  const [audioItems, setAudioItems] = useState<AudioItem[]>([])
  const [videoLibraryItems, setVideoLibraryItems] = useState<VideoLibraryItem[]>([])
  const [videoModels, setVideoModels] = useState<Record<string, VideoModelInfo>>({})
  const [refVideoModels, setRefVideoModels] = useState<Record<string, RefVideoModelInfo>>({})
  const [textToVideoModels, setTextToVideoModels] = useState<Record<string, TextToVideoModelInfo>>({})
  const [keyframeToVideoModels, setKeyframeToVideoModels] = useState<Record<string, KeyframeToVideoModelInfo>>({})
  const [videoRepaintingModels, setVideoRepaintingModels] = useState<Record<string, VaceVideoRepaintingModelInfo>>({})
  const [videoEditModels, setVideoEditModels] = useState<Record<string, VaceVideoEditModelInfo>>({})
  const isMountedRef = useRef(true)
  const videoTaskNotificationsEnabledRef = useRef(false)
  const notifiedResultsRef = useRef<Set<string>>(new Set())

  const maybeNotifyTaskFinished = useCallback((task: VideoStudioTask) => {
    if (!videoTaskNotificationsEnabledRef.current) return
    if (typeof window === 'undefined' || !('Notification' in window)) return
    if (Notification.permission !== 'granted') return
    const dedupeKey = `${task.id}:${task.status}`
    if (notifiedResultsRef.current.has(dedupeKey)) return
    notifiedResultsRef.current.add(dedupeKey)
    const title = task.status === 'succeeded' ? '视频任务已完成' : '视频任务失败'
    const body = task.status === 'succeeded'
      ? `${task.name || '未命名任务'} 已生成完成`
      : `${task.name || '未命名任务'} 失败：${task.error_message || '未知错误'}`
    try {
      const notification = new Notification(title, { body, tag: dedupeKey })
      notification.onclick = () => window.focus()
    } catch {
      // ignore notification failures
    }
  }, [])

  const handlePollingError = useCallback((_taskId: string, error: unknown) => {
    console.error('轮询错误:', error)
  }, [])

  const { startPolling } = useTaskPolling({
    intervalMs: 5000,
    errorIntervalMs: 10000,
    onError: handlePollingError,
  })

  const startTaskPolling = useCallback((taskId: string) => {
    startPolling(taskId, async () => {
      const result = await videoStudioApi.getStatus(taskId)

      if (isMountedRef.current) {
        setTasks(prev => prev.map(t => t.id === taskId ? result.task : t))
        setSelectedTask(prev => {
          if (prev?.id === taskId) return result.task
          return prev
        })
      }

      if (result.task.status === 'succeeded' || result.task.status === 'failed') {
        maybeNotifyTaskFinished(result.task)
        if (result.task.status === 'succeeded') {
          message.success('视频生成完成')
        } else {
          message.error(`视频生成失败: ${result.task.error_message || '未知错误'}`)
        }
        return true
      }

      return false
    })
  }, [maybeNotifyTaskFinished, setSelectedTask, startPolling])

  const loadData = useCallback(async () => {
    if (!projectId) return
    setLoading(true)
    try {
      const [tasksRes, galleryRes, audioRes, videoLibRes, settingsRes] = await Promise.all([
        videoStudioApi.list(projectId),
        galleryApi.list(projectId),
        audioApi.list(projectId),
        videoLibraryApi.list(projectId),
        settingsApi.getSettings(),
      ])
      setTasks(tasksRes.tasks)
      setGalleryImages(galleryRes.images)
      setAudioItems(audioRes.audios)
      setVideoLibraryItems(videoLibRes.videos)
      videoTaskNotificationsEnabledRef.current = !!settingsRes.video_task_notifications_enabled
      setVideoModels({})
      setRefVideoModels({})
      setTextToVideoModels({})
      setKeyframeToVideoModels({})
      setVideoRepaintingModels({})
      setVideoEditModels({})

      tasksRes.tasks.forEach(task => {
        if (task.status === 'processing') {
          startTaskPolling(task.id)
        }
      })
    } catch {
      message.error('加载失败')
    } finally {
      setLoading(false)
    }
  }, [projectId, startTaskPolling])

  useEffect(() => {
    isMountedRef.current = true
    if (projectId) {
      fetchProject(projectId)
      loadData()
    }
    return () => {
      isMountedRef.current = false
    }
  }, [projectId, fetchProject, loadData])

  return {
    tasks,
    setTasks,
    loading,
    galleryImages,
    audioItems,
    videoLibraryItems,
    videoModels,
    refVideoModels,
    textToVideoModels,
    keyframeToVideoModels,
    videoRepaintingModels,
    videoEditModels,
    startTaskPolling,
  }
}
