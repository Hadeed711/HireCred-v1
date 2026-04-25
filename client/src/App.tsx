import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'react-hot-toast'
import { queryClient } from './lib/queryClient'
import ProtectedRoute from './components/ProtectedRoute'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import ProfileEditor from './pages/ProfileEditor'
import ProfileView from './pages/ProfileView'
import SearchPage from './pages/SearchPage'
import Leaderboard from './pages/Leaderboard'
import Inbox from './pages/Inbox'

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/login" element={<Login />} />
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

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster position="top-right" toastOptions={{ duration: 3500 }} />
    </QueryClientProvider>
  )
}
