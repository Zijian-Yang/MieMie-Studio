import { api } from './apiClient'

export interface AdminUser {
  id: string
  username: string
  display_name: string
  role: 'admin' | 'member'
  status: 'active' | 'disabled'
  must_change_password: boolean
  created_at: string
  updated_at: string
  last_login?: string | null
}

export interface BootstrapStatus {
  admin_configured: boolean
  registration_enabled: boolean
}

export interface AdminUserPage {
  items: AdminUser[]
  page: number
  page_size: number
  total: number
}

export interface AdminAuditItem {
  id: string
  actor_user_id: string
  action: string
  target_type: string
  target_id?: string | null
  request_id?: string | null
  result: string
  changes: Record<string, unknown>
  created_at: string
}

export interface AdminAuditPage {
  items: AdminAuditItem[]
  page: number
  page_size: number
  total: number
}

export interface AdminUserFilters {
  page?: number
  page_size?: number
  query?: string
  role?: AdminUser['role']
  status?: AdminUser['status']
}

export interface AdminUserCreateInput {
  username: string
  password: string
  display_name?: string
  role?: AdminUser['role']
  must_change_password?: boolean
}

export interface AdminUserUpdateInput {
  username?: string
  display_name?: string
  role?: AdminUser['role']
  status?: AdminUser['status']
}

export const adminApi = {
  bootstrapStatus: () => api.get<never, BootstrapStatus>('/bootstrap/status'),

  listUsers: (params: AdminUserFilters) =>
    api.get<never, AdminUserPage>('/admin/users', { params }),

  createUser: (data: AdminUserCreateInput) =>
    api.post<never, AdminUser>('/admin/users', data),

  updateUser: (userId: string, data: AdminUserUpdateInput) =>
    api.patch<never, AdminUser>(`/admin/users/${userId}`, data),

  resetPassword: (
    userId: string,
    data: { new_password: string; must_change_password: boolean },
  ) => api.post<never, AdminUser>(`/admin/users/${userId}/reset-password`, data),

  deleteUser: (userId: string) => api.delete<never, AdminUser>(`/admin/users/${userId}`),

  getPlatformSettings: () =>
    api.get<never, { registration_enabled: boolean }>('/admin/platform-settings'),

  updatePlatformSettings: (registrationEnabled: boolean) =>
    api.put<never, { registration_enabled: boolean }>('/admin/platform-settings', {
      registration_enabled: registrationEnabled,
    }),

  listAuditLogs: (params: { page?: number; page_size?: number; action?: string }) =>
    api.get<never, AdminAuditPage>('/admin/audit-logs', { params }),
}
