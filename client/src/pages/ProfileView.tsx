import { useState } from 'react'
import { useParams, useNavigate, useLocation, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import api from '../lib/api'
import { useAuthStore } from '../stores/authStore'
import {
  ArrowLeft, AlertTriangle, MapPin, Eye, BriefcaseBusiness, FileText, Flag,
  GitBranch, Globe, MessageCircle, Image, ExternalLink, X, SearchX, ClipboardList,
  Wrench, FolderGit2, ShieldCheck, ArrowRight,
} from 'lucide-react'
import type {
  Profile, ExperienceItem, PortfolioItem, ProofSignal, SignalType,
  CredibilityScore, CvAnalysis, ReportReason,
} from '../lib/types'
import ScoreWidget from '../components/profile/ScoreWidget'
import AppreciationModal from '../components/appreciation/AppreciationModal'
import AppreciationSection from '../components/appreciation/AppreciationSection'

const SIGNAL_ICONS: Record<SignalType, React.ElementType> = {
  github: GitBranch,
  portfolio_link: Globe,
  client_reference: MessageCircle,
  screenshot: Image,
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

const REPORT_REASONS: { value: ReportReason; label: string }[] = [
  { value: 'fake_account', label: 'Fake or bot account' },
  { value: 'impersonation', label: 'Impersonating someone' },
  { value: 'fake_credentials', label: 'Fake credentials / experience' },
  { value: 'inappropriate_content', label: 'Inappropriate content' },
  { value: 'spam', label: 'Spam or self-promotion' },
  { value: 'other', label: 'Other' },
]

export default function ProfileView() {
  const { userId } = useParams<{ userId: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const { user, isAuthenticated } = useAuthStore()
  const [showAppreciationModal, setShowAppreciationModal] = useState(false)
  const [showReportModal, setShowReportModal] = useState(false)

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
    staleTime: 0,
    refetchOnMount: 'always',
    refetchInterval: (query) => (!query.state.data ? 3000 : false),
  })

  const backTarget = (location.state as { from?: string } | null)?.from ?? (profile && user?.id === profile.user_id ? '/profile/edit' : '/dashboard')

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
          </div>
        </main>
      </div>
    )
  }

  if (isError || !profile) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center flex-col gap-4">
        <div className="w-16 h-16 rounded-2xl bg-gray-100 flex items-center justify-center">
          <SearchX className="h-8 w-8 text-gray-400" />
        </div>
        <p className="text-gray-700 font-semibold">Profile not found</p>
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
  const isHirer = isAuthenticated && !isOwn

  return (
    <div className="min-h-screen bg-linear-to-br from-slate-50 via-white to-indigo-50">
      {/* ── Sticky header ── */}
      <header className="glass px-6 py-3.5 flex items-center justify-between sticky top-0 z-10">
        <button
          onClick={() => navigate(backTarget)}
          className="text-sm text-gray-500 hover:text-gray-700 flex items-center gap-1.5 hover:bg-gray-100 px-2.5 py-1.5 rounded-lg transition-colors"
        >
          <ArrowLeft className="h-4 w-4" /> Back
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
              {/* Report Account — visible to all authenticated non-owners */}
              <button
                onClick={() => setShowReportModal(true)}
                className="text-sm px-3 py-1.5 border border-red-200 text-red-500 rounded-xl hover:bg-red-50 hover:border-red-300 transition-all font-medium"
                title="Report this account"
              >
                <Flag className="inline-block h-4 w-4 mr-1 -mt-0.5" /> Report
              </button>
            </div>
          )}
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-8 space-y-5">

        {/* ── Suspicious account banner ── */}
        {score?.is_suspicious && (
          <div className="bg-amber-50 border border-amber-300 rounded-2xl px-5 py-3.5 flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 text-amber-500 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-amber-800">Suspicious Account</p>
              <p className="text-xs text-amber-700 mt-0.5">
                This account has been flagged as suspicious by our authenticity system or by a verified report.
                Engage with caution.
              </p>
            </div>
          </div>
        )}

        {/* ── Hero card ── */}
        <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden shadow-sm animate-fade-up">
          <div className="h-24 bg-linear-to-r from-indigo-500 via-violet-500 to-purple-600 relative">
            <div
              className="absolute inset-0 pointer-events-none opacity-30"
              style={{
                backgroundImage: 'radial-gradient(circle, rgb(255 255 255 / 0.18) 1px, transparent 1px)',
                backgroundSize: '20px 20px',
                maskImage: 'linear-gradient(105deg, black 30%, transparent 80%)',
              }}
            />
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
                {score.is_suspicious && (
                  <span className="text-amber-300 text-xs font-bold ml-1 inline-flex items-center gap-1">
                    <AlertTriangle className="h-3.5 w-3.5" /> Suspicious
                  </span>
                )}
              </div>
            )}
          </div>

          <div className="px-6 pb-6">
            <div className="pt-4 mb-3">
              <div className="w-20 h-20 rounded-2xl bg-indigo-100 flex items-center justify-center text-3xl font-bold text-indigo-600">
                {profile.owner_name.charAt(0).toUpperCase()}
              </div>
            </div>

            <div className="mb-4">
              <div className="flex items-center gap-2 flex-wrap">
                <h1 className="text-xl font-bold text-gray-900">{profile.owner_name}</h1>
                {profile.owner_uid && (
                  <span className="text-xs font-mono text-gray-400 bg-gray-100 px-2 py-0.5 rounded-md">
                    #{profile.owner_uid}
                  </span>
                )}
                {score?.is_suspicious && (
                  <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 border border-amber-200">
                    <AlertTriangle className="inline-block h-3.5 w-3.5 mr-1 -mt-0.5" /> Suspicious
                  </span>
                )}
              </div>
              {profile.title && <p className="text-gray-600 text-sm mt-0.5">{profile.title}</p>}
            </div>

            <div className="flex flex-wrap items-center gap-4 text-sm text-gray-400 mb-4">
              {profile.location && (
                <span className="flex items-center gap-1.5">
                  <MapPin className="h-4 w-4" /> {profile.location}
                </span>
              )}
              <span className="flex items-center gap-1.5">
                <Eye className="h-4 w-4" /> {profile.profile_views} views
              </span>
              {profile.skills.length > 0 && (
                <span className="flex items-center gap-1.5">
                  <BriefcaseBusiness className="h-4 w-4" /> {profile.skills.length} skills
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
        <ScoreWidget score={score} isLoading={scoreLoading} userId={profileUserId} isOwn={isOwn} />

        {/* ── Skills ── */}
        {profile.skills.length > 0 && (
          <ViewSection title="Skills" icon={Wrench}>
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
          <ViewSection title="Experience" icon={BriefcaseBusiness}>
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
          <ViewSection title="Portfolio" icon={FolderGit2}>
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
                            className="text-xs px-2 py-0.5 bg-indigo-100 text-indigo-600 rounded-md hover:bg-indigo-200 transition-colors font-medium shrink-0 inline-flex items-center gap-1"
                          >
                            View <ExternalLink className="h-3 w-3" />
                          </a>
                        )}
                      </div>
                      {item.description && (
                        <p className="text-sm text-gray-600 mt-1 leading-relaxed">{item.description}</p>
                      )}
                      {item.tech_stack.length > 0 && (
                        <div className="mt-2.5">
                          <p className="text-xs text-gray-400 font-medium mb-1.5">Skills</p>
                          <div className="flex flex-wrap gap-1.5">
                            {item.tech_stack.map((t) => (
                              <span key={t} className="text-xs px-2 py-0.5 bg-indigo-50 text-indigo-600 rounded-md font-medium border border-indigo-100">{t}</span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </ViewSection>
        )}

        {/* ── CV (visible to hirers only) ── */}
        {isHirer && profile.cv_url && (
          <CvSection cvUrl={profile.cv_url} cvAnalysis={profile.cv_analysis} />
        )}

        {/* ── Proof Signals ── */}
        {profile.proof_signals.length > 0 && (
          <ViewSection title="Proof Signals" icon={ShieldCheck}>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {profile.proof_signals.map((s: ProofSignal) => {
                const SignalIcon = SIGNAL_ICONS[s.signal_type]
                return (
                <div key={s.id} className="flex items-start gap-3 p-3.5 bg-gray-50 rounded-xl border border-gray-100 hover:border-gray-200 transition-colors">
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${SIGNAL_COLORS[s.signal_type]}`}>
                    <SignalIcon className="h-4 w-4" />
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
                      <a href={`/uploads/${s.file_path}`} target="_blank" rel="noopener noreferrer" className="text-xs text-indigo-500 hover:underline inline-flex items-center gap-1">
                        View uploaded file <ExternalLink className="h-3 w-3" />
                      </a>
                    )}
                    {s.description && <p className="text-xs text-gray-500 mt-0.5">{s.description}</p>}
                  </div>
                </div>
              )})}
            </div>
          </ViewSection>
        )}

        {!profile.bio && profile.skills.length === 0 && profile.experience.length === 0 && (
          <div className="bg-white rounded-2xl border border-dashed border-gray-300 p-10 text-center">
            <div className="w-14 h-14 rounded-2xl bg-indigo-50 flex items-center justify-center mx-auto mb-3">
              <ClipboardList className="h-7 w-7 text-indigo-400" />
            </div>
            <p className="text-gray-600 font-medium">This profile hasn't been filled in yet.</p>
            {isOwn && (
              <Link to="/profile/edit" className="mt-3 inline-flex items-center gap-1.5 text-sm px-4 py-2 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 transition-colors">
                Complete your profile <ArrowRight className="h-3.5 w-3.5" />
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

      {/* Report modal */}
      {showReportModal && profileUserId && (
        <ReportModal
          reportedUserId={profileUserId}
          reportedUserName={profile.owner_name}
          onClose={() => setShowReportModal(false)}
        />
      )}
    </div>
  )
}

// ── Report Account Modal ──────────────────────────────────────────────────────

function ReportModal({
  reportedUserId,
  reportedUserName,
  onClose,
}: {
  reportedUserId: string
  reportedUserName: string
  onClose: () => void
}) {
  const [reason, setReason] = useState<ReportReason>('fake_account')
  const [evidence, setEvidence] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    try {
      await api.post('/reports', {
        reported_user_id: reportedUserId,
        reason,
        evidence_text: evidence.trim() || null,
      })
      toast.success('Report submitted. An admin will review it.')
      onClose()
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Failed to submit report.'
      toast.error(msg)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-bold text-gray-900">Report Account</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 p-1 rounded-lg hover:bg-gray-100 transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>

        <p className="text-sm text-gray-500 mb-5">
          Reporting <span className="font-semibold text-gray-700">{reportedUserName}</span>.
          An admin will review your report and take action if appropriate.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-1.5">Reason</label>
            <select
              value={reason}
              onChange={(e) => setReason(e.target.value as ReportReason)}
              className="w-full text-sm border border-gray-300 rounded-xl px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-indigo-300"
            >
              {REPORT_REASONS.map((r) => (
                <option key={r.value} value={r.value}>{r.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-1.5">
              Evidence <span className="text-gray-400 font-normal">(optional)</span>
            </label>
            <textarea
              value={evidence}
              onChange={(e) => setEvidence(e.target.value)}
              placeholder="Describe what you noticed — specific details help the admin decide faster..."
              rows={4}
              className="w-full text-sm border border-gray-300 rounded-xl px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-indigo-300 resize-none"
            />
          </div>

          <div className="flex gap-3 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 text-sm py-2.5 border border-gray-300 rounded-xl hover:bg-gray-50 transition-colors font-medium"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="flex-1 text-sm py-2.5 bg-red-500 text-white rounded-xl hover:bg-red-600 disabled:opacity-60 transition-colors font-medium"
            >
              {submitting ? 'Submitting…' : 'Submit Report'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Shared components ─────────────────────────────────────────────────────────

function CvSection({ cvUrl, cvAnalysis }: { cvUrl: string; cvAnalysis: CvAnalysis | null }) {
  return (
          <ViewSection title="CV / Resume" icon={FileText}>
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex-1 min-w-0">
          {cvAnalysis?.experience_summary && (
            <p className="text-sm text-gray-600 mb-2">{cvAnalysis.experience_summary}</p>
          )}
          {cvAnalysis?.cv_title && (
            <p className="text-xs text-gray-500 mb-2">CV title: <span className="font-medium">{cvAnalysis.cv_title}</span></p>
          )}
          {cvAnalysis?.extracted_skills && cvAnalysis.extracted_skills.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {cvAnalysis.extracted_skills.slice(0, 8).map((s) => (
                <span key={s} className="text-xs px-2 py-0.5 bg-blue-50 text-blue-700 rounded-md font-medium border border-blue-100">
                  {s}
                </span>
              ))}
              {cvAnalysis.extracted_skills.length > 8 && (
                <span className="text-xs text-gray-400 self-center">+{cvAnalysis.extracted_skills.length - 8} more</span>
              )}
            </div>
          )}
        </div>
        <a
          href={cvUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="shrink-0 text-sm px-4 py-2 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 transition-colors font-medium shadow-sm shadow-indigo-200 inline-flex items-center gap-1.5"
        >
          View CV <ExternalLink className="h-3.5 w-3.5" />
        </a>
      </div>
    </ViewSection>
  )
}

function ViewSection({ title, icon: Icon, children }: { title: string; icon: React.ElementType; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-6 shadow-sm hover:shadow-md transition-shadow duration-300 animate-fade-up">
      <h2 className="text-base font-semibold text-gray-900 mb-4 flex items-center gap-2">
        <Icon className="h-4.5 w-4.5 text-indigo-600" />
        {title}
        <span className="flex-1 h-px bg-gray-100 ml-1" />
      </h2>
      {children}
    </div>
  )
}
