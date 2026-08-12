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

export interface PlatformOperationsSettings {
  registration_enabled: boolean
  backup_enabled: boolean
  backup_schedule: string
  backup_retention_days: number
  backup_min_keep: number
  backup_local_subdirectory: string
  backup_oss_enabled: boolean
  backup_oss_endpoint?: string | null
  backup_oss_bucket_name?: string | null
  backup_oss_prefix: string
  backup_oss_credentials_configured: boolean
  backup_oss_access_key_id_masked: string
  webhook_enabled: boolean
  webhook_configured: boolean
  webhook_url_masked: string
  webhook_timeout_seconds: number
  webhook_retry_count: number
  webhook_alert_on_warning: boolean
}

export interface PlatformOperationsSettingsPatch {
  registration_enabled?: boolean
  backup_enabled?: boolean
  backup_schedule?: string
  backup_retention_days?: number
  backup_min_keep?: number
  backup_local_subdirectory?: string
  backup_oss_enabled?: boolean
  backup_oss_endpoint?: string
  backup_oss_bucket_name?: string
  backup_oss_prefix?: string
  backup_oss_access_key_id?: string
  backup_oss_access_key_secret?: string
  clear_backup_oss_credentials?: boolean
  webhook_enabled?: boolean
  webhook_url?: string
  clear_webhook_url?: boolean
  webhook_timeout_seconds?: number
  webhook_retry_count?: number
  webhook_alert_on_warning?: boolean
}

export type OperationType = 'backup' | 'oss_test' | 'webhook_test' | 'restore_rehearsal'
export type OperationStatus = 'queued' | 'running' | 'succeeded' | 'failed'

export interface OperationRun {
  id: string
  operation_type: OperationType
  status: OperationStatus
  trigger_source: 'manual' | 'scheduled' | 'cli'
  requested_by?: string | null
  local_status: 'pending' | 'succeeded' | 'failed' | 'skipped'
  oss_status: 'pending' | 'succeeded' | 'failed' | 'skipped'
  local_path_relative?: string | null
  oss_object_key?: string | null
  oss_etag?: string | null
  sha256?: string | null
  size_bytes?: number | null
  summary: Record<string, unknown>
  error_category?: string | null
  created_at: string
  started_at?: string | null
  finished_at?: string | null
  updated_at: string
}

export interface OperationRunPage {
  items: OperationRun[]
  page: number
  page_size: number
  total: number
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
    api.get<never, PlatformOperationsSettings>('/admin/platform-settings'),

  patchPlatformSettings: (data: PlatformOperationsSettingsPatch) =>
    api.patch<never, PlatformOperationsSettings>('/admin/platform-settings', data),

  updatePlatformSettings: (registrationEnabled: boolean) =>
    api.put<never, { registration_enabled: boolean }>('/admin/platform-settings', {
      registration_enabled: registrationEnabled,
    }),

  createBackup: () => api.post<never, OperationRun>('/admin/backups'),

  testBackupOss: () => api.post<never, OperationRun>('/admin/backups/test-oss'),

  testWebhook: () => api.post<never, OperationRun>('/admin/alerts/test'),

  listOperationRuns: (params: {
    page?: number
    page_size?: number
    operation_type?: OperationType
    status?: OperationStatus
  }) => api.get<never, OperationRunPage>('/admin/backups', { params }),

  listAuditLogs: (params: { page?: number; page_size?: number; action?: string }) =>
    api.get<never, AdminAuditPage>('/admin/audit-logs', { params }),
}
