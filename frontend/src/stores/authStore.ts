/**
 * 认证状态管理
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface User {
  id: string
  username: string
  display_name: string
  role: 'admin' | 'member'
  status: 'active' | 'disabled'
  must_change_password: boolean
  created_at: string
  updated_at: string
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
        set({
          token,
          user: {
            ...user,
            role: user.role || 'member',
            status: user.status || 'active',
            must_change_password: user.must_change_password || false,
            updated_at: user.updated_at || user.created_at,
          },
          isAuthenticated: true,
        })
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
