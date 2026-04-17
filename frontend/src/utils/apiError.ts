export function getApiErrorMessage(error: unknown, fallback = '请求失败'): string {
  if (error && typeof error === 'object') {
    const maybeError = error as {
      message?: unknown
      data?: { detail?: unknown; message?: unknown }
      response?: { data?: { detail?: unknown; message?: unknown } }
    }

    const detail =
      maybeError.data?.detail ??
      maybeError.data?.message ??
      maybeError.response?.data?.detail ??
      maybeError.response?.data?.message

    if (typeof detail === 'string' && detail.trim()) {
      return detail
    }

    if (typeof maybeError.message === 'string' && maybeError.message.trim()) {
      return maybeError.message
    }
  }

  if (error instanceof Error && error.message.trim()) {
    return error.message
  }

  return fallback
}
