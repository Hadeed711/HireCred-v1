import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'react-hot-toast'
import { queryClient } from './lib/queryClient'
import ProtectedRoute from './components/ProtectedRoute'
import AdminRoute from './components/AdminRoute'
import Login from './pages/Login'
import AdminLogin from './pages/AdminLogin'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import ProfileEditor from './pages/ProfileEditor'
import ProfileView from './pages/ProfileView'
import SearchPage from './pages/SearchPage'
import Leaderboard from './pages/Leaderboard'
import Inbox from './pages/Inbox'
import AdminPanel from './pages/AdminPanel'

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/login" element={<Login />} />
          <Route path="/admin/login" element={<AdminLogin />} />
          <Route path="/register" element={<Register />} />
          <Route path="/profile/:userId" element={<ProfileView />} />
          <Route path="/leaderboard" element={<Leaderboard />} />

          <Route element={<ProtectedRoute />}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/profile/edit" element={<ProfileEditor />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/inbox" element={<Inbox />} />
            <Route path="/inbox/:userId" element={<Inbox />} />
          </Route>

          <Route element={<AdminRoute />}>
            <Route path="/admin" element={<AdminPanel />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 3500,
          style: {
            background: 'rgba(255, 255, 255, 0.92)',
            backdropFilter: 'blur(12px)',
            color: '#111827',
            border: '1px solid rgb(229 231 235)',
            borderRadius: '14px',
            boxShadow: '0 8px 30px rgb(79 70 229 / 0.12)',
            fontSize: '13.5px',
            fontWeight: 500,
          },
          success: { iconTheme: { primary: '#4f46e5', secondary: '#fff' } },
        }}
      />
    </QueryClientProvider>
  )
}
