import { Navigate, Outlet } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'

export default function AdminRoute() {
  const { isAuthenticated, user } = useAuthStore()

  if (!isAuthenticated) return <Navigate to="/admin/login" replace />
  if (!user?.is_admin) return <Navigate to="/dashboard" replace />

  return <Outlet />
}
