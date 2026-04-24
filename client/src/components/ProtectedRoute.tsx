import { Navigate, Outlet } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'

interface Props {
  allowedRoles?: ('candidate' | 'client')[]
}

export default function ProtectedRoute({ allowedRoles }: Props) {
  const { isAuthenticated, user } = useAuthStore()

  if (!isAuthenticated) return <Navigate to="/login" replace />
  if (allowedRoles && user && !allowedRoles.includes(user.role)) {
    return <Navigate to="/dashboard" replace />
  }

  return <Outlet />
}
