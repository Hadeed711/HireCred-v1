import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore, type UserRole } from '../stores/authStore'
import toast from 'react-hot-toast'
import { ClipboardList, Cpu, ScanSearch, Eye, EyeOff, LoaderCircle, Mail, Lock, User, Briefcase, Building2 } from 'lucide-react'

const STEPS = [
  { icon: ClipboardList, label: 'Fill your profile' },
  { icon: Cpu, label: 'Get your HireCred score' },
  { icon: ScanSearch, label: 'Get found by trusted clients' },
]

export default function Register() {
  const navigate = useNavigate()
  const register = useAuthStore((s) => s.register)
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [role, setRole] = useState<UserRole>('candidate')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (password.length < 8) {
      toast.error('Password must be at least 8 characters')
      return
    }
    setLoading(true)
    try {
      await register(email, password, fullName, role)
      toast.success('Account created!')
      navigate('/dashboard')
    } catch (err: any) {
      toast.error(err.response?.data?.detail ?? 'Registration failed')
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
        <div className="absolute top-2/3 -right-10 w-40 h-40 rounded-full bg-white/5 pointer-events-none" />
        <div className="absolute -bottom-12 -left-12 w-56 h-56 rounded-full bg-white/5 pointer-events-none" />

        {/* Logo */}
        <div className="relative z-10">
          <div className="text-3xl font-bold tracking-tight mb-1">HireCred</div>
          <p className="text-indigo-300 text-sm font-medium">Trust-based hiring platform</p>
        </div>

        {/* Hero copy */}
        <div className="relative z-10 space-y-8">
          <div>
            <h2 className="text-3xl font-bold leading-snug mb-3">
              Your credibility,<br />
              <span className="text-indigo-300">proven by AI.</span>
            </h2>
            <p className="text-indigo-200 text-base leading-relaxed">
              Stop losing to candidates who just write better CVs. Let your real work speak — through proof signals, verified feedback, and an AI trust score that hiring clients actually believe.
            </p>
          </div>

          {/* How it works */}
          <div>
            <p className="text-xs uppercase font-semibold text-indigo-400 tracking-wider mb-4">How it works</p>
            <div className="space-y-4">
              {STEPS.map((step, i) => (
                <div key={i} className="flex items-center gap-3.5">
                  <div className="w-8 h-8 rounded-full bg-indigo-600/60 border border-indigo-500/40 flex items-center justify-center text-sm font-bold shrink-0">
                    {i + 1}
                  </div>
                  <div className="flex items-center gap-2.5">
                    <step.icon className="h-4 w-4 text-indigo-300 shrink-0" />
                    <p className="text-sm font-medium text-indigo-100">{step.label}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Stat callout */}
          <div className="bg-white/10 rounded-2xl p-4 border border-white/10">
            <p className="text-sm text-indigo-200 leading-relaxed">
              <span className="font-bold text-white text-base">"</span>
              Credibility isn't about what you claim — it's about what you can prove.
              <span className="font-bold text-white text-base">"</span>
            </p>
          </div>
        </div>

        {/* Bottom */}
        <p className="relative z-10 text-indigo-400 text-xs">
          Free to join. No credit card required.
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
            <div className="mb-6">
              <h2 className="text-2xl font-bold text-gray-900">Create your account</h2>
              <p className="text-gray-500 text-sm mt-1">Free to join. Start building your credibility today.</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Full Name</label>
                <div className="relative">
                  <User className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
                  <input
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    className="w-full pl-10 pr-3.5 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-shadow"
                    placeholder="Jane Smith"
                  />
                </div>
              </div>

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
                    placeholder="Min 8 characters"
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

              {/* Role selection */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">I am joining as…</label>
                <div className="grid grid-cols-2 gap-3">
                  {([
                    { value: 'candidate', label: 'Professional', Icon: Briefcase, sub: 'Build my credibility profile' },
                    { value: 'client', label: 'Hiring Client', Icon: Building2, sub: 'Find trusted professionals' },
                  ] as const).map((r) => (
                    <button
                      key={r.value}
                      type="button"
                      onClick={() => setRole(r.value as UserRole)}
                      className={`p-3.5 rounded-xl border-2 text-left transition-all ${
                        role === r.value
                          ? 'border-indigo-500 bg-indigo-50'
                          : 'border-gray-200 hover:border-indigo-300 hover:bg-gray-50'
                      }`}
                    >
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center mb-2 ${role === r.value ? 'bg-indigo-100' : 'bg-gray-100'}`}>
                        <r.Icon className={`h-4 w-4 ${role === r.value ? 'text-indigo-600' : 'text-gray-500'}`} />
                      </div>
                      <p className={`text-sm font-semibold ${role === r.value ? 'text-indigo-700' : 'text-gray-800'}`}>
                        {r.label}
                      </p>
                      <p className={`text-xs mt-0.5 ${role === r.value ? 'text-indigo-500' : 'text-gray-400'}`}>
                        {r.sub}
                      </p>
                    </button>
                  ))}
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white font-semibold py-2.5 px-4 rounded-xl transition-colors text-sm shadow-sm shadow-indigo-200 mt-1"
              >
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <LoaderCircle className="animate-spin h-4 w-4" />
                    Creating account…
                  </span>
                ) : 'Create account'}
              </button>
            </form>

            <div className="mt-6 pt-5 border-t border-gray-100 text-center">
              <p className="text-sm text-gray-500">
                Already have an account?{' '}
                <Link to="/login" className="text-indigo-600 hover:text-indigo-700 font-semibold hover:underline underline-offset-2">
                  Sign in
                </Link>
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
