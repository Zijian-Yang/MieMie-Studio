import { useCallback, useEffect, useRef } from 'react'

export interface TaskPollingOptions {
  initialDelayMs?: number
  intervalMs: number
  errorIntervalMs?: number
  continueOnError?: boolean
  onError?: (taskId: string, error: unknown) => void
}

type Poller = () => Promise<boolean>

export function useTaskPolling(options: TaskPollingOptions) {
  const {
    initialDelayMs = 0,
    intervalMs,
    errorIntervalMs = intervalMs,
    continueOnError = true,
    onError,
  } = options

  const activeRef = useRef<Set<string>>(new Set())
  const timerRef = useRef<Map<string, number>>(new Map())
  const mountedRef = useRef(true)

  const stopPolling = useCallback((taskId: string) => {
    activeRef.current.delete(taskId)
    const timer = timerRef.current.get(taskId)
    if (timer !== undefined) {
      window.clearTimeout(timer)
      timerRef.current.delete(taskId)
    }
  }, [])

  const stopAllPolling = useCallback(() => {
    activeRef.current.forEach((taskId) => {
      const timer = timerRef.current.get(taskId)
      if (timer !== undefined) {
        window.clearTimeout(timer)
      }
    })
    activeRef.current.clear()
    timerRef.current.clear()
  }, [])

  const startPolling = useCallback((taskId: string, poller: Poller) => {
    if (activeRef.current.has(taskId)) return
    activeRef.current.add(taskId)

    const run = async () => {
      if (!mountedRef.current || !activeRef.current.has(taskId)) return
      try {
        const done = await poller()
        if (!mountedRef.current || !activeRef.current.has(taskId)) return
        if (done) {
          stopPolling(taskId)
          return
        }
        const timer = window.setTimeout(run, intervalMs)
        timerRef.current.set(taskId, timer)
      } catch (error) {
        onError?.(taskId, error)
        if (!continueOnError || !mountedRef.current || !activeRef.current.has(taskId)) {
          stopPolling(taskId)
          return
        }
        const timer = window.setTimeout(run, errorIntervalMs)
        timerRef.current.set(taskId, timer)
      }
    }

    const timer = window.setTimeout(run, initialDelayMs)
    timerRef.current.set(taskId, timer)
  }, [continueOnError, errorIntervalMs, initialDelayMs, intervalMs, onError, stopPolling])

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      stopAllPolling()
    }
  }, [stopAllPolling])

  return {
    startPolling,
    stopPolling,
    stopAllPolling,
    isPolling: useCallback((taskId: string) => activeRef.current.has(taskId), []),
  }
}
