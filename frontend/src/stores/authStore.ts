/**
 * 认证状态管理
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface User {
  id: string
  username: string
  display_name: string
  created_at: string
  last_login?: string
}

interface AuthState {
  token: string | null
  user: User | null
  isAuthenticated: boolean
  
  // Actions
  login: (token: string, user: User) => void
  logout: () => void
  updateUser: (user: User) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      isAuthenticated: false,
      
      login: (token: string, user: User) => {
        set({ token, user, isAuthenticated: true })
      },
      
      logout: () => {
        set({ token: null, user: null, isAuthenticated: false })
      },
      
      updateUser: (user: User) => {
        set({ user })
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        token: state.token,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
)

/**
 * 获取 Authorization header
 */
export const getAuthHeader = (): Record<string, string> => {
  const token = useAuthStore.getState().token
  if (token) {
    return { Authorization: `Bearer ${token}` }
  }
  return {}
}

