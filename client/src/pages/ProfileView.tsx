import { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import api from '../lib/api'
import { useAuthStore } from '../stores/authStore'
import type { Profile, ExperienceItem, PortfolioItem, ProofSignal, SignalType, CredibilityScore } from '../lib/types'
import ScoreWidget from '../components/profile/ScoreWidget'
import AppreciationModal from '../components/appreciation/AppreciationModal'
import AppreciationSection from '../components/appreciation/AppreciationSection'

const SIGNAL_ICONS: Record<SignalType, string> = {
  github: '🔗',
  portfolio_link: '🌐',
  client_reference: '💬',
  screenshot: '🖼️',
}

const SIGNAL_LABELS: Record<SignalType, string> = {
  github: 'GitHub / Project Link',
  portfolio_link: 'Portfolio Link',
  client_reference: 'Client Reference',
  screenshot: 'Work Screenshot',
}

const SIGNAL_COLORS: Record<SignalType, string> = {
  github: 'bg-gray-900 text-white',
  portfolio_link: 'bg-blue-600 text-white',
  client_reference: 'bg-violet-600 text-white',
  screenshot: 'bg-emerald-600 text-white',
}

export default function ProfileView() {
  const { userId } = useParams<{ userId: string }>()
  const navigate = useNavigate()
  const { user, isAuthenticated } = useAuthStore()
  const [showAppreciationModal, setShowAppreciationModal] = useState(false)

  const { data: profile, isLoading, isError } = useQuery<Profile>({
    queryKey: ['profile', userId],
    queryFn: () => api.get(`/profile/${userId}`).then((r) => r.data),
    enabled: !!userId,
  })

  const profileUserId = profile?.user_id

  const { data: score, isLoading: scoreLoading } = useQuery<CredibilityScore | null>({
    queryKey: ['score', profileUserId],
    queryFn: () => api.get(`/profile/${profileUserId}/score`).then((r) => r.data),
    enabled: !!profileUserId,
    refetchInterval: (query) => (!query.state.data ? 5000 : false),
  })

  if (isLoading) {
    return (
      <div className="min-h-screen bg-linear-to-br from-slate-50 via-white to-indigo-50">
        <header className="bg-white/80 backdrop-blur border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <div className="w-12 h-5 bg-gray-200 rounded animate-pulse" />
          <div className="w-24 h-8 bg-gray-200 rounded-lg animate-pulse" />
        </header>
        <main className="max-w-3xl mx-auto px-4 py-8 space-y-4">
          <div className="bg-white rounded-2xl border border-gray-100 p-6 animate-pulse">
            <div className="flex gap-4">
              <div className="w-20 h-20 rounded-full bg-gray-200 shrink-0" />
              <div className="flex-1 space-y-2">
                <div className="h-5 bg-gray-200 rounded w-1/3" />
                <div className="h-4 bg-gray-100 rounded w-1/4" />
                <div className="h-3 bg-gray-100 rounded w-1/5" />
              </div>
            </div>
            <div className="mt-4 space-y-2">
              <div className="h-3 bg-gray-100 rounded w-full" />
              <div className="h-3 bg-gray-100 rounded w-5/6" />
            </div>
          </div>
          <div className="bg-white rounded-2xl border border-gray-100 p-6 flex flex-col items-center gap-3 animate-pulse">
            <div className="w-28 h-28 rounded-full border-8 border-gray-100" />
            <div className="h-3 bg-gray-100 rounded w-24" />
          </div>
          {[1, 2].map((i) => (
            <div key={i} className="bg-white rounded-2xl border border-gray-100 p-6 animate-pulse space-y-3">
              <div className="h-4 bg-gray-200 rounded w-1/5" />
              <div className="flex gap-2">
                {[1,2,3,4].map((j) => <div key={j} className="h-7 w-20 bg-gray-100 rounded-lg" />)}
              </div>
            </div>
          ))}
        </main>
      </div>
    )
  }

  if (isError || !profile) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center flex-col gap-4">
        <div className="text-5xl">😕</div>
        <p className="text-gray-700 font-semibold">Profile not found</p>
        <p className="text-gray-400 text-sm">This profile doesn't exist or may have been removed.</p>
        <button
          onClick={() => navigate('/dashboard')}
          className="mt-2 text-sm px-4 py-2 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 transition-colors"
        >
          Back to Dashboard
        </button>
      </div>
    )
  }

  const isOwn = user?.id === profile.user_id
  const isClient = user?.role === 'client'

  const scoreRingColor = score
    ? score.score >= 70 ? '#22c55e' : score.score >= 40 ? '#f97316' : '#ef4444'
    : '#e5e7eb'

  return (
    <div className="min-h-screen bg-linear-to-br from-slate-50 via-white to-indigo-50">
      {/* ── Sticky header ── */}
      <header className="bg-white/90 backdrop-blur border-b border-gray-200 px-6 py-3.5 flex items-center justify-between sticky top-0 z-10">
        <button
          onClick={() => navigate(-1)}
          className="text-sm text-gray-500 hover:text-gray-700 flex items-center gap-1.5 hover:bg-gray-100 px-2.5 py-1.5 rounded-lg transition-colors"
        >
          ← Back
        </button>

        <span className="text-sm font-bold bg-linear-to-r from-indigo-600 to-violet-600 bg-clip-text text-transparent">
          HireCred
        </span>

        <div className="flex items-center gap-2">
          {isOwn && (
            <Link
              to="/profile/edit"
              className="text-sm px-3.5 py-1.5 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors font-medium"
            >
              Edit Profile
            </Link>
          )}
          {isAuthenticated && !isOwn && (
            <div className="flex items-center gap-2">
              {isClient && (
                <button
                  onClick={() => setShowAppreciationModal(true)}
                  className="text-sm px-3.5 py-1.5 border border-gray-200 rounded-xl hover:border-violet-300 hover:text-violet-600 hover:bg-violet-50 transition-all font-medium"
                >
                  Give Appreciation
                </button>
              )}
              <button
                onClick={() => navigate(`/inbox/${profile.user_id}`, { state: { name: profile.owner_name } })}
                className="text-sm px-4 py-1.5 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 transition-colors font-medium shadow-sm shadow-indigo-200"
              >
                Send Message
              </button>
            </div>
          )}
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-8 space-y-5">

        {/* ── Hero card ── */}
        <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden shadow-sm">
          {/* Gradient banner */}
          <div className="h-24 bg-linear-to-r from-indigo-500 via-violet-500 to-purple-600 relative">
            {score && (
              <div className="absolute right-5 top-1/2 -translate-y-1/2 flex items-center gap-2 bg-white/20 backdrop-blur-sm rounded-2xl px-3 py-1.5 border border-white/30">
                <svg width="20" height="20" className="-rotate-90">
                  <circle cx="10" cy="10" r="8" fill="none" stroke="rgba(255,255,255,0.3)" strokeWidth="3" />
                  <circle
                    cx="10" cy="10" r="8"
                    fill="none"
                    stroke="white"
                    strokeWidth="3"
                    strokeLinecap="round"
                    strokeDasharray={`${2 * Math.PI * 8}`}
                    strokeDashoffset={`${2 * Math.PI * 8 * (1 - score.score / 100)}`}
                  />
                </svg>
                <span className="text-white font-bold text-sm">{score.score}</span>
                <span className="text-white/80 text-xs">
                  {score.score >= 70 ? 'High Trust' : score.score >= 40 ? 'Moderate' : 'Low Trust'}
                </span>
              </div>
            )}
          </div>

          {/* Avatar + info */}
          <div className="px-6 pb-6">
            {/* Avatar sits fully below the banner */}
            <div className="pt-4 mb-3">
              <div className="w-20 h-20 rounded-2xl bg-indigo-100 flex items-center justify-center text-3xl font-bold text-indigo-600">
                {profile.owner_name.charAt(0).toUpperCase()}
              </div>
            </div>

            {/* Name + title fully below the banner */}
            <div className="mb-4">
              <div className="flex items-center gap-2 flex-wrap">
                <h1 className="text-xl font-bold text-gray-900">{profile.owner_name}</h1>
                {profile.owner_uid && (
                  <span className="text-xs font-mono text-gray-400 bg-gray-100 px-2 py-0.5 rounded-md">
                    #{profile.owner_uid}
                  </span>
                )}
              </div>
              {profile.title && <p className="text-gray-600 text-sm mt-0.5">{profile.title}</p>}
            </div>

            <div className="flex flex-wrap items-center gap-4 text-sm text-gray-400 mb-4">
              {profile.location && (
                <span className="flex items-center gap-1.5">
                  <span className="text-base">📍</span> {profile.location}
                </span>
              )}
              <span className="flex items-center gap-1.5">
                <span className="text-base">👁</span> {profile.profile_views} views
              </span>
              {profile.skills.length > 0 && (
                <span className="flex items-center gap-1.5">
                  <span className="text-base">🛠</span> {profile.skills.length} skills
                </span>
              )}
            </div>

            {profile.bio && (
              <p className="text-gray-700 text-sm leading-relaxed whitespace-pre-line border-t border-gray-100 pt-4">
                {profile.bio}
              </p>
            )}
          </div>
        </div>

        {/* ── HireCred Score ── */}
        <ScoreWidget score={score} isLoading={scoreLoading} />

        {/* ── Skills ── */}
        {profile.skills.length > 0 && (
          <ViewSection title="Skills" icon="🛠">
            <div className="flex flex-wrap gap-2">
              {profile.skills.map((s) => (
                <span key={s} className="px-3 py-1.5 bg-indigo-50 text-indigo-700 rounded-xl text-sm font-medium border border-indigo-100">
                  {s}
                </span>
              ))}
            </div>
          </ViewSection>
        )}

        {/* ── Experience ── */}
        {profile.experience.length > 0 && (
          <ViewSection title="Experience" icon="💼">
            <div className="space-y-5">
              {(profile.experience as ExperienceItem[]).map((exp, i) => (
                <div key={exp.id || i} className="flex gap-4">
                  <div className="w-2 shrink-0 flex flex-col items-center pt-1.5">
                    <div className="w-2.5 h-2.5 rounded-full bg-indigo-400 ring-2 ring-indigo-100" />
                    {i < profile.experience.length - 1 && <div className="flex-1 w-px bg-gray-200 mt-1.5" />}
                  </div>
                  <div className="pb-4 flex-1">
                    <p className="font-semibold text-gray-900 text-sm">{exp.title}</p>
                    <p className="text-gray-600 text-sm">{exp.company}</p>
                    <p className="text-xs text-gray-400 mt-0.5">
                      {exp.start_date} — {exp.current ? 'Present' : (exp.end_date ?? '—')}
                    </p>
                    {exp.description && (
                      <p className="text-sm text-gray-600 mt-1.5 leading-relaxed">{exp.description}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </ViewSection>
        )}

        {/* ── Portfolio ── */}
        {profile.portfolio.length > 0 && (
          <ViewSection title="Portfolio" icon="🗂">
            <div className="grid grid-cols-1 gap-4">
              {(profile.portfolio as PortfolioItem[]).map((item, i) => (
                <div key={item.id || i} className="border border-gray-200 rounded-xl p-4 hover:border-indigo-200 hover:bg-indigo-50/30 transition-colors group">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <p className="font-semibold text-gray-900 text-sm">{item.title}</p>
                        {item.url && (
                          <a
                            href={item.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs px-2 py-0.5 bg-indigo-100 text-indigo-600 rounded-md hover:bg-indigo-200 transition-colors font-medium shrink-0"
                          >
                            View →
                          </a>
                        )}
                      </div>
                      {item.description && (
                        <p className="text-sm text-gray-600 mt-1 leading-relaxed">{item.description}</p>
                      )}
                      {item.tech_stack.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 mt-2.5">
                          {item.tech_stack.map((t) => (
                            <span key={t} className="text-xs px-2 py-0.5 bg-gray-100 text-gray-600 rounded-md font-medium">{t}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </ViewSection>
        )}

        {/* ── Proof Signals ── */}
        {profile.proof_signals.length > 0 && (
          <ViewSection title="Proof Signals" icon="🔐">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {profile.proof_signals.map((s: ProofSignal) => (
                <div key={s.id} className="flex items-start gap-3 p-3.5 bg-gray-50 rounded-xl border border-gray-100 hover:border-gray-200 transition-colors">
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-sm shrink-0 ${SIGNAL_COLORS[s.signal_type]}`}>
                    {SIGNAL_ICONS[s.signal_type]}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-gray-800 leading-tight">{s.title}</p>
                    <p className="text-xs text-gray-400 capitalize mt-0.5">{SIGNAL_LABELS[s.signal_type]}</p>
                    {s.url && (
                      <a href={s.url} target="_blank" rel="noopener noreferrer" className="text-xs text-indigo-500 hover:underline break-all mt-0.5 block">
                        {s.url.length > 40 ? s.url.slice(0, 40) + '…' : s.url}
                      </a>
                    )}
                    {s.file_path && (
                      <a href={`/uploads/${s.file_path}`} target="_blank" rel="noopener noreferrer" className="text-xs text-indigo-500 hover:underline">
                        View uploaded file ↗
                      </a>
                    )}
                    {s.description && <p className="text-xs text-gray-500 mt-0.5">{s.description}</p>}
                  </div>
                </div>
              ))}
            </div>
          </ViewSection>
        )}

        {/* Empty profile state */}
        {!profile.bio && profile.skills.length === 0 && profile.experience.length === 0 && (
          <div className="bg-white rounded-2xl border border-dashed border-gray-300 p-10 text-center">
            <p className="text-4xl mb-3">📝</p>
            <p className="text-gray-600 font-medium">This profile hasn't been filled in yet.</p>
            {isOwn && (
              <Link to="/profile/edit" className="mt-3 inline-block text-sm px-4 py-2 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 transition-colors">
                Complete your profile →
              </Link>
            )}
          </div>
        )}

        {/* ── Appreciations ── */}
        {profileUserId && <AppreciationSection userId={profileUserId} fraudRisk={score?.fraud_risk} />}

      </main>

      {/* Appreciation modal */}
      {showAppreciationModal && profileUserId && profile && (
        <AppreciationModal
          toUserId={profileUserId}
          toUserName={profile.owner_name}
          onClose={() => setShowAppreciationModal(false)}
        />
      )}
    </div>
  )
}

function ViewSection({ title, icon, children }: { title: string; icon: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-6 shadow-sm hover:shadow-md transition-shadow">
      <h2 className="text-base font-semibold text-gray-900 mb-4 flex items-center gap-2">
        <span>{icon}</span>
        {title}
        <span className="flex-1 h-px bg-gray-100 ml-1" />
      </h2>
      {children}
    </div>
  )
}
