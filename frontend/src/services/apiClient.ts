import axios from 'axios'

export interface ApiError extends Error {
  data?: any
  status?: number
}

export const api = axios.create({
  baseURL: '/api',
  timeout: 360000,
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.request.use(
  (config) => {
    const authStorage = localStorage.getItem('auth-storage')
    if (authStorage) {
      try {
        const { state } = JSON.parse(authStorage)
        if (state?.token) {
          config.headers.Authorization = `Bearer ${state.token}`
        }
      } catch {
        // ignore invalid local auth cache
      }
    }
    return config
  },
  (error) => Promise.reject(error)
)

api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth-storage')
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    const message = error.response?.data?.detail || error.message || '请求失败'
    const enhancedError = new Error(
      typeof message === 'string' ? message : '请求失败'
    ) as ApiError
    enhancedError.data = error.response?.data
    enhancedError.status = error.response?.status
    return Promise.reject(enhancedError)
  }
)
