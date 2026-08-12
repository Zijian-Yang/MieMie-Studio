import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'

const AdminRoute = ({ children }: { children: ReactNode }) => {
  const user = useAuthStore((state) => state.user)

  if (user?.role !== 'admin' || user.status !== 'active') {
    return <Navigate to="/projects" replace />
  }

  return <>{children}</>
}

export default AdminRoute
