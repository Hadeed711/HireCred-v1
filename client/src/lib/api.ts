import axios from 'axios'
import { queryClient } from './queryClient'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('hc_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('hc_token')
      queryClient.clear()
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api
