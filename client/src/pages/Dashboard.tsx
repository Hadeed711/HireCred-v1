import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useAuthStore } from '../stores/authStore'
import api from '../lib/api'
import type { Profile, CredibilityScore } from '../lib/types'

export default function Dashboard() {
  const { user, logout } = useAuthStore()

  const { data: profile } = useQuery<Profile>({
    queryKey: ['profile', user?.id],
    queryFn: () => api.get(`/profile/${user?.id}`).then((r) => r.data),
    enabled: !!user?.id && user.role === 'candidate',
  })

  const { data: score } = useQuery<CredibilityScore | null>({
    queryKey: ['score', user?.id],
    queryFn: () => api.get(`/profile/${user?.id}/score`).then((r) => r.data),
    enabled: !!user?.id && user.role === 'candidate',
    refetchInterval: (query) => (!query.state.data ? 8000 : false),
  })

  const scoreColor = score
    ? score.score >= 70 ? 'text-emerald-600' : score.score >= 40 ? 'text-amber-500' : 'text-red-500'
    : 'text-gray-400'
  const scoreLabel = score
    ? score.score >= 70 ? 'High Trust' : score.score >= 40 ? 'Moderate' : 'Low Trust'
    : 'Not yet computed'
  const scoreBarColor = score
    ? score.score >= 70 ? 'bg-emerald-500' : score.score >= 40 ? 'bg-amber-400' : 'bg-red-400'
    : 'bg-gray-200'
  const scoreBg = score
    ? score.score >= 70 ? 'from-emerald-50 to-emerald-100/50 border-emerald-100' : score.score >= 40 ? 'from-amber-50 to-amber-100/50 border-amber-100' : 'from-red-50 to-red-100/50 border-red-100'
    : 'from-gray-50 to-gray-100/50 border-gray-100'

  const profileComplete = profile && (!!profile.bio || profile.skills.length > 0 || profile.experience.length > 0)

  return (
    <div className="min-h-screen bg-linear-to-br from-slate-50 via-white to-indigo-50">
      {/* ── Top nav ── */}
      <header className="glass px-6 py-3 flex items-center justify-between sticky top-0 z-10">
        <span className="text-lg font-bold bg-linear-to-r from-indigo-600 to-violet-600 bg-clip-text text-transparent">
          HireCred
        </span>
        <nav className="flex items-center gap-1">
          {user?.role === 'candidate' && (
            <NavLink to="/profile/edit">My Profile</NavLink>
          )}
          {user?.role === 'client' && (
            <NavLink to="/search">Find Candidates</NavLink>
          )}
          <NavLink to="/leaderboard">Leaderboard</NavLink>
          <NavLink to="/inbox">Inbox</NavLink>
          {user?.is_admin && (
            <NavLink to="/admin">Admin</NavLink>
          )}
          <span className="hidden sm:block text-sm text-gray-500 px-3 border-l border-gray-200 ml-1">{user?.full_name}</span>
          <button
            onClick={logout}
            className="text-sm text-gray-500 hover:text-gray-900 px-3 py-1.5 rounded-lg hover:bg-gray-100 transition-colors ml-1"
          >
            Sign out
          </button>
        </nav>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-10">
        {/* ── Welcome banner ── */}
        <div className="relative overflow-hidden rounded-2xl bg-linear-to-r from-indigo-600 via-indigo-500 to-violet-600 text-white p-8 mb-8 shadow-lg shadow-indigo-200/40 animate-fade-up">
          <div
            className="absolute inset-0 pointer-events-none opacity-30"
            style={{
              backgroundImage: 'radial-gradient(circle, rgb(255 255 255 / 0.16) 1px, transparent 1px)',
              backgroundSize: '22px 22px',
              maskImage: 'radial-gradient(ellipse at 75% 30%, black 20%, transparent 70%)',
            }}
          />
          <div className="relative z-10">
            <p className="text-indigo-200 text-xs font-semibold uppercase tracking-widest mb-1">
              {user?.role === 'candidate' ? 'Professional Dashboard' : 'Hiring Dashboard'}
            </p>
            <h1 className="text-3xl font-bold mb-2">
              Welcome back, {user?.full_name?.split(' ')[0]}!
            </h1>
            <p className="text-indigo-200 text-sm max-w-md">
              {user?.role === 'candidate'
                ? 'Build your credibility profile and get discovered by trusted clients.'
                : 'Find and hire trusted professionals with verified credibility scores.'}
            </p>
          </div>
          <div className="absolute -top-8 -right-8 w-40 h-40 rounded-full bg-white/10 animate-float" />
          <div className="absolute -bottom-12 -right-4 w-56 h-56 rounded-full bg-white/5 animate-float" style={{ animationDelay: '2s' }} />
          <div className="absolute top-1/2 right-32 w-20 h-20 rounded-full bg-white/5 animate-float" style={{ animationDelay: '4s' }} />
        </div>

        {/* ── Stats grid ── */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
          {user?.role === 'candidate' ? (
            <>
              {/* Score card */}
              <div className={`bg-linear-to-br ${scoreBg} rounded-2xl border p-5 shadow-sm card-hover animate-fade-up stagger-1`}>
                <div className="flex items-start justify-between mb-3">
                  <p className="text-sm font-medium text-gray-600">HireCred Score</p>
                  <span className="text-xl">🏆</span>
                </div>
                <p className={`text-4xl font-bold mb-0.5 ${scoreColor}`}>
                  {score ? score.score : '—'}
                </p>
                <p className={`text-xs font-semibold ${scoreColor}`}>{scoreLabel}</p>
                {score && (
                  <div className="mt-3 h-1.5 bg-white/60 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-700 ${scoreBarColor}`}
                      style={{ width: `${score.score}%` }}
                    />
                  </div>
                )}
                {!score && (
                  <p className="text-xs text-gray-400 mt-2">Save your profile to compute</p>
                )}
              </div>

              {/* Profile Views */}
              <div className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm card-hover animate-fade-up stagger-2">
                <div className="flex items-start justify-between mb-3">
                  <p className="text-sm font-medium text-gray-500">Profile Views</p>
                  <span className="text-xl">👁</span>
                </div>
                <p className="text-4xl font-bold text-gray-900 mb-0.5">{profile?.profile_views ?? 0}</p>
                <p className="text-xs text-gray-400">All time views</p>
              </div>

              {/* Proof Signals */}
              <div className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm card-hover animate-fade-up stagger-3">
                <div className="flex items-start justify-between mb-3">
                  <p className="text-sm font-medium text-gray-500">Proof Signals</p>
                  <span className="text-xl">🔗</span>
                </div>
                <p className="text-4xl font-bold text-gray-900 mb-0.5">
                  {profile?.proof_signals?.length ?? 0}
                </p>
                <p className="text-xs text-gray-400">
                  {(profile?.proof_signals?.length ?? 0) === 0
                    ? 'Add proof to boost your score'
                    : 'Verified proof signals'}
                </p>
              </div>
            </>
          ) : (
            <>
              <ClientStatCard
                icon="🔍"
                label="Smart Search"
                value="AI-Powered"
                hint="Natural language candidate search"
                accent="indigo"
                to="/search"
              />
              <ClientStatCard
                icon="🏆"
                label="Trust Leaderboard"
                value="Live"
                hint="Top-ranked verified professionals"
                accent="violet"
                to="/leaderboard"
              />
              <ClientStatCard
                icon="💬"
                label="Inbox"
                value="Open"
                hint="Message candidates directly"
                accent="emerald"
                to="/inbox"
              />
            </>
          )}
        </div>

        {/* ── Quick Actions ── */}
        <div className="bg-white rounded-2xl border border-gray-100 p-6 shadow-sm animate-fade-up stagger-4">
          <h2 className="text-base font-semibold text-gray-900 mb-5">Quick Actions</h2>

          {user?.role === 'candidate' && (
            <>
              <div className="flex flex-wrap gap-3">
                <ActionButton to="/profile/edit" primary>Edit Profile</ActionButton>
                {user?.uid != null && (
                  <ActionButton to={`/profile/${user.uid}`} state={{ from: '/dashboard' }}>View Public Profile</ActionButton>
                )}
                <ActionButton to="/leaderboard">Trust Leaderboard</ActionButton>
                <ActionButton to="/inbox">Inbox</ActionButton>
              </div>

              {/* Incomplete profile warning */}
              {profile && !profileComplete && (
                <div className="mt-5 flex items-start gap-3 p-4 bg-amber-50 border border-amber-200 rounded-xl">
                  <span className="text-amber-500 text-lg mt-0.5">⚠</span>
                  <div>
                    <p className="text-sm font-semibold text-amber-800">Profile incomplete</p>
                    <p className="text-sm text-amber-700 mt-0.5">
                      <Link to="/profile/edit" className="font-semibold underline underline-offset-2">Fill in your profile</Link>
                      {' '}to get your HireCred score and appear in search results.
                    </p>
                  </div>
                </div>
              )}

              {/* Score breakdown */}
              {score && (score.strengths.length > 0 || score.risks.length > 0) && (
                <div className="mt-5 border-t border-gray-100 pt-5">
                  <p className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-3">AI Score Breakdown</p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {score.strengths.slice(0, 3).map((s, i) => (
                      <div key={i} className="flex items-start gap-2 text-sm text-gray-700 bg-emerald-50 rounded-lg px-3 py-2">
                        <span className="text-emerald-500 mt-0.5 shrink-0 font-bold">✓</span>
                        {s}
                      </div>
                    ))}
                    {score.risks.slice(0, 2).map((r, i) => (
                      <div key={i} className="flex items-start gap-2 text-sm text-gray-700 bg-red-50 rounded-lg px-3 py-2">
                        <span className="text-red-400 mt-0.5 shrink-0 font-bold">!</span>
                        {r}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}

          {user?.role === 'client' && (
            <div className="space-y-4">
              <div className="flex flex-wrap gap-3">
                <ActionButton to="/search" primary>Search Candidates</ActionButton>
                <ActionButton to="/leaderboard">Trust Leaderboard</ActionButton>
                <ActionButton to="/inbox">Inbox</ActionButton>
              </div>
              {/* Client tips */}
              <div className="mt-2 p-4 bg-indigo-50 border border-indigo-100 rounded-xl">
                <p className="text-sm font-semibold text-indigo-800 mb-1">💡 How to get the best results</p>
                <p className="text-xs text-indigo-600 leading-relaxed">
                  Use natural language in search — e.g. <em>"reliable React developer with real project experience"</em>.
                  Candidates are ranked by HireCred Score, skill match, and verified appreciation ratings.
                </p>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}

function NavLink({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <Link
      to={to}
      className="text-sm text-gray-600 hover:text-indigo-600 font-medium px-3 py-1.5 rounded-lg hover:bg-indigo-50 transition-colors duration-200"
    >
      {children}
    </Link>
  )
}

function ActionButton({ to, state, primary, children }: { to: string; state?: unknown; primary?: boolean; children: React.ReactNode }) {
  return (
    <Link
      to={to}
      state={state}
      className={`px-4 py-2 text-sm font-medium rounded-xl transition-all duration-150 ${
        primary
          ? 'bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm shadow-indigo-200'
          : 'border border-gray-200 text-gray-700 hover:border-indigo-300 hover:text-indigo-600 hover:bg-indigo-50'
      }`}
    >
      {children}
    </Link>
  )
}

function ClientStatCard({ icon, label, value, hint, accent, to, state }: {
  icon: string; label: string; value: string; hint: string
  accent: 'indigo' | 'violet' | 'emerald'
  to: string
  state?: unknown
}) {
  const colors = {
    indigo: 'bg-indigo-50 border-indigo-100 hover:border-indigo-200',
    violet: 'bg-violet-50 border-violet-100 hover:border-violet-200',
    emerald: 'bg-emerald-50 border-emerald-100 hover:border-emerald-200',
  }
  const textColors = {
    indigo: 'text-indigo-700',
    violet: 'text-violet-700',
    emerald: 'text-emerald-700',
  }
  return (
    <Link
      to={to}
      state={state}
      className={`rounded-2xl border p-5 ${colors[accent]} card-hover animate-fade-up block group`}
    >
      <div className="flex items-start justify-between mb-3">
        <p className="text-sm font-medium text-gray-600">{label}</p>
        <span className="text-xl">{icon}</span>
      </div>
      <p className={`text-2xl font-bold mb-1 ${textColors[accent]}`}>{value}</p>
      <p className="text-xs text-gray-500">{hint}</p>
      <p className={`text-xs font-semibold mt-2 ${textColors[accent]} opacity-0 group-hover:opacity-100 transition-opacity`}>
        Open →
      </p>
    </Link>
  )
}
