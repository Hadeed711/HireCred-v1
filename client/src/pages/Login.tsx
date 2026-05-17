import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import toast from 'react-hot-toast'
import { Award, Sparkles, ShieldCheck, BadgeCheck, Eye, EyeOff, LoaderCircle, Mail, Lock } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

const FEATURES: { icon: LucideIcon; title: string; desc: string }[] = [
  { icon: Award, title: 'AI Credibility Score', desc: 'Every candidate scored 0–100 based on real evidence, not self-reported claims.' },
  { icon: Sparkles, title: 'Intent-Based Search', desc: 'Describe who you need in plain English. No filters required.' },
  { icon: ShieldCheck, title: 'Fraud Detection', desc: 'AI automatically flags suspicious review patterns to protect your decisions.' },
  { icon: BadgeCheck, title: 'Verified Appreciations', desc: 'Structured AI ratings replace gameable star systems.' },
]

export default function Login() {
  const navigate = useNavigate()
  const login = useAuthStore((s) => s.login)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    try {
      await login(email, password)
      toast.success('Welcome back!')
      navigate('/dashboard')
    } catch (err: any) {
      toast.error(err.response?.data?.detail ?? 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex">
      {/* ── Left branding panel ── */}
      <div className="hidden lg:flex lg:w-5/12 bg-linear-to-br from-indigo-950 via-indigo-900 to-violet-900 flex-col justify-between p-12 text-white relative overflow-hidden">
        {/* Decorative circles */}
        <div className="absolute -top-20 -right-20 w-64 h-64 rounded-full bg-white/5 pointer-events-none" />
        <div className="absolute top-1/2 -right-10 w-40 h-40 rounded-full bg-white/5 pointer-events-none" />
        <div className="absolute -bottom-12 -left-12 w-56 h-56 rounded-full bg-white/5 pointer-events-none" />
        <div className="absolute bottom-1/3 right-8 w-20 h-20 rounded-full bg-white/5 pointer-events-none" />

        {/* Logo */}
        <div className="relative z-10">
          <div className="text-3xl font-bold tracking-tight mb-1">HireCred</div>
          <p className="text-indigo-300 text-sm font-medium">Trust-based hiring platform</p>
        </div>

        {/* Hero copy + features */}
        <div className="relative z-10 space-y-8">
          <div>
            <h2 className="text-3xl font-bold leading-snug mb-2">
              Hire with confidence.
            </h2>
            <p className="text-indigo-300 text-base leading-relaxed">
              Credibility scores, not just CVs. Every candidate is evaluated by AI on real proof — not self-reported claims.
            </p>
          </div>

          <div className="space-y-5">
            {FEATURES.map((f) => (
              <div key={f.title} className="flex items-start gap-3.5">
                <div className="w-9 h-9 rounded-xl bg-white/10 flex items-center justify-center text-lg shrink-0">
                  <f.icon className="h-4.5 w-4.5" />
                </div>
                <div>
                  <p className="font-semibold text-sm text-white">{f.title}</p>
                  <p className="text-indigo-300 text-xs leading-relaxed mt-0.5">{f.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Bottom */}
        <p className="relative z-10 text-indigo-400 text-xs">
          Built for modern hiring teams that value trust over gut feeling.
        </p>
      </div>

      {/* ── Right form panel ── */}
      <div className="flex-1 flex items-center justify-center px-6 py-12 bg-gray-50">
        <div className="w-full max-w-md">

          {/* Mobile logo */}
          <div className="lg:hidden text-center mb-8">
            <h1 className="text-3xl font-bold text-gray-900">HireCred</h1>
            <p className="mt-1 text-gray-500 text-sm">Trust-based hiring platform</p>
          </div>

          {/* Form card */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8">
            <div className="mb-7">
              <h2 className="text-2xl font-bold text-gray-900">Welcome back</h2>
              <p className="text-gray-500 text-sm mt-1">Sign in to your HireCred account</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Email address</label>
                <div className="relative">
                  <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full pl-10 pr-3.5 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-shadow"
                    placeholder="you@example.com"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Password</label>
                <div className="relative">
                  <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full pl-10 pr-11 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-shadow"
                    placeholder="••••••••"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                    tabIndex={-1}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white font-semibold py-2.5 px-4 rounded-xl transition-colors text-sm shadow-sm shadow-indigo-200 mt-2"
              >
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <LoaderCircle className="h-4 w-4 animate-spin" />
                    Signing in…
                  </span>
                ) : 'Sign in'}
              </button>
            </form>

            <div className="mt-6 pt-5 border-t border-gray-100 text-center">
              <p className="text-sm text-gray-500">
                No account?{' '}
                <Link to="/register" className="text-indigo-600 hover:text-indigo-700 font-semibold hover:underline underline-offset-2">
                  Create one free
                </Link>
              </p>
              <p className="text-xs text-gray-400 mt-2">
                Admin access?{' '}
                <Link to="/admin/login" className="text-red-600 hover:text-red-700 font-semibold hover:underline underline-offset-2">
                  Use dedicated admin login
                </Link>
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
