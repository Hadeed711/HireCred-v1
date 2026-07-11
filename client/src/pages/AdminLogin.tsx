import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { useAuthStore } from '../stores/authStore'

export default function AdminLogin() {
  const navigate = useNavigate()
  const loginAdmin = useAuthStore((s) => s.loginAdmin)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    try {
      await loginAdmin(email, password)
      toast.success('Admin session started.')
      navigate('/admin')
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Admin login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-100 bg-grid flex items-center justify-center px-6 py-12">
      <div className="w-full max-w-md bg-white border border-slate-200 rounded-2xl shadow-xl shadow-slate-200/60 p-8 animate-scale-in relative z-10">
        <div className="mb-6">
          <p className="text-xs font-semibold tracking-widest text-red-600 uppercase">Dedicated Admin Portal</p>
          <h1 className="text-2xl font-bold text-slate-900 mt-2">Admin Login</h1>
          <p className="text-sm text-slate-500 mt-1">Only approved admin accounts can continue.</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Admin email</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3.5 py-2.5 border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-transparent"
              placeholder="admin@company.com"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Password</label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3.5 py-2.5 border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-transparent"
              placeholder="••••••••"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white font-semibold py-2.5 px-4 rounded-xl transition-colors text-sm"
          >
            {loading ? 'Signing in...' : 'Sign in as admin'}
          </button>
        </form>

        <div className="mt-5 pt-5 border-t border-slate-100 text-sm text-slate-500 text-center">
          Regular account login?{' '}
          <Link to="/login" className="text-slate-700 font-semibold hover:underline underline-offset-2">
            Go to user login
          </Link>
        </div>
      </div>
    </div>
  )
}
