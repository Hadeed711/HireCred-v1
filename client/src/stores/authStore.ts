import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import api from '../lib/api'
import { queryClient } from '../lib/queryClient'

export type UserRole = 'candidate' | 'client'

export interface User {
  id: string
  uid: number | null
  email: string
  full_name: string
  role: UserRole
  is_active: boolean
  created_at: string
}

interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, full_name: string, role: UserRole) => Promise<void>
  logout: () => void
  fetchMe: () => Promise<void>
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,

      login: async (email, password) => {
        const { data } = await api.post('/auth/login', { email, password })
        localStorage.setItem('hc_token', data.access_token)
        set({ user: data.user, token: data.access_token, isAuthenticated: true })
      },

      register: async (email, password, full_name, role) => {
        const { data } = await api.post('/auth/register', { email, password, full_name, role })
        localStorage.setItem('hc_token', data.access_token)
        set({ user: data.user, token: data.access_token, isAuthenticated: true })
      },

      logout: () => {
        localStorage.removeItem('hc_token')
        queryClient.clear()
        set({ user: null, token: null, isAuthenticated: false })
      },

      fetchMe: async () => {
        const { data } = await api.get('/auth/me')
        set({ user: data, isAuthenticated: true })
      },
    }),
    {
      name: 'hc_auth',
      partialize: (state) => ({ user: state.user, token: state.token, isAuthenticated: state.isAuthenticated }),
    }
  )
)
