import type { AdminUser } from '../../services/adminApi'

export const cannotMutateOwnSecurity = (currentUserId: string, target: AdminUser) =>
  currentUserId === target.id

export const roleLabel = (role: AdminUser['role']) =>
  role === 'admin' ? '管理员' : '普通用户'

export const statusLabel = (status: AdminUser['status']) =>
  status === 'active' ? '启用' : '已禁用'
