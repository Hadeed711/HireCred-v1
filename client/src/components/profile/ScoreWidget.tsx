import { useEffect, useState } from 'react'
import type { CredibilityScore } from '../../lib/types'
import { Trophy, ShieldAlert, Link2, AlertTriangle, CheckCircle2, CircleX, RefreshCw, FileText } from 'lucide-react'
import api from '../../lib/api'
import toast from 'react-hot-toast'

interface Props {
  score: CredibilityScore | null | undefined
  isLoading?: boolean
  userId?: string
  isOwn?: boolean
}

const SIZE = 128
const STROKE = 12
const R = (SIZE - STROKE) / 2
const CIRCUMFERENCE = 2 * Math.PI * R

function scoreColor(score: number): string {
  if (score >= 70) return '#22c55e'
  if (score >= 40) return '#f97316'
  return '#ef4444'
}

function scoreBgClass(score: number): string {
  if (score >= 70) return 'from-emerald-50 to-emerald-100/40 border-emerald-100'
  if (score >= 40) return 'from-amber-50 to-amber-100/40 border-amber-100'
  return 'from-red-50 to-red-100/40 border-red-100'
}

function scoreLabel(score: number): string {
  if (score >= 70) return 'High Trust'
  if (score >= 40) return 'Moderate Trust'
  return 'Low Trust'
}

function scoreSummary(score: number): string {
  if (score >= 85) return 'Excellent profile — strong proof and credibility signals.'
  if (score >= 70) return 'Good credibility profile with verified proof signals.'
  if (score >= 50) return 'Decent profile — adding more proof signals would boost this.'
  if (score >= 30) return 'Profile needs more detail and proof signals.'
  return 'Profile is incomplete. Fill in experience, skills, and proof signals.'
}

export default function ScoreWidget({ score, isLoading, userId, isOwn }: Props) {
  const [refreshing, setRefreshing] = useState(false)
  // Ring sweeps in from 0 on mount / when the score value changes
  const [ringMounted, setRingMounted] = useState(false)
  useEffect(() => {
    setRingMounted(false)
    const t = requestAnimationFrame(() => requestAnimationFrame(() => setRingMounted(true)))
    return () => cancelAnimationFrame(t)
  }, [score?.score])

  async function handleRefresh() {
    if (!userId || refreshing) return
    setRefreshing(true)
    try {
      await api.post(`/profile/${userId}/rescore`)
      toast.success('Score recomputation started — refreshing in a moment…')
    } catch {
      toast.error('Failed to trigger rescore')
    } finally {
      setTimeout(() => setRefreshing(false), 3000)
    }
  }

  const refreshBtn = isOwn && userId ? (
    <button
      onClick={handleRefresh}
      disabled={refreshing}
      title="Recompute HireCred score"
      className="ml-auto flex items-center gap-1.5 text-xs text-indigo-500 hover:text-indigo-700 disabled:opacity-40 transition-colors px-2 py-1 rounded-lg hover:bg-indigo-50"
    >
      <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} />
      {refreshing ? 'Refreshing…' : 'Refresh'}
    </button>
  ) : null

  if (isLoading) {
    return (
      <div className="bg-white rounded-2xl border border-gray-100 p-6">
        <h2 className="text-base font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Trophy className="h-4.5 w-4.5 text-indigo-600" /> HireCred Score
          <span className="flex-1 h-px bg-gray-100 ml-1" />
        </h2>
        <div className="flex flex-col items-center gap-3 py-2">
          <div className="w-32 h-32 rounded-full border-12 border-gray-100 animate-pulse" />
          <p className="text-sm text-gray-400 animate-pulse">Computing score…</p>
        </div>
      </div>
    )
  }

  if (!score) {
    return (
      <div className="bg-white rounded-2xl border border-gray-100 p-6">
        <h2 className="text-base font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Trophy className="h-4.5 w-4.5 text-indigo-600" /> HireCred Score
          <span className="flex-1 h-px bg-gray-100 ml-1" />
          {refreshBtn}
        </h2>
        <div className="text-center py-4">
          <ShieldAlert className="mx-auto mb-2 h-8 w-8 text-indigo-500" />
          <p className="text-sm text-gray-500 font-medium">Score not yet computed</p>
          <p className="text-xs text-gray-400 mt-1">Save your profile or click Refresh to trigger scoring.</p>
        </div>
      </div>
    )
  }

  const pct = score.score / 100
  const dashOffset = ringMounted ? CIRCUMFERENCE * (1 - pct) : CIRCUMFERENCE
  const color = scoreColor(score.score)
  const bgClass = scoreBgClass(score.score)

  // Filter out empty/whitespace entries the LLM occasionally produces
  const strengths = (score.strengths || []).filter((s) => s.trim())
  const risks = (score.risks || []).filter((r) => r.trim())
  const urlWarnings = (score.url_warnings || []).filter((w) => w.trim())
  const authFlags = (score.authenticity_flags || []).filter((f) => f.trim())
  const cvWarnings = (score.cv_match_warnings || []).filter((w) => w.trim())
  const cvMatch = score.cv_match_score
  const cvMatchColor = cvMatch == null ? '' : cvMatch >= 60 ? 'text-emerald-600' : cvMatch >= 30 ? 'text-amber-600' : 'text-red-500'
  const cvMatchBar = cvMatch == null ? '' : cvMatch >= 60 ? 'bg-emerald-500' : cvMatch >= 30 ? 'bg-amber-400' : 'bg-red-400'

  return (
    <div className={`rounded-2xl border p-6 bg-linear-to-br ${bgClass} animate-fade-up`}>
      <h2 className="text-base font-semibold text-gray-900 mb-2 flex items-center gap-2">
        <Trophy className="h-4.5 w-4.5 text-indigo-600" /> HireCred Score
        <span className="flex-1 h-px bg-gray-200/60 ml-1" />
        {score.is_suspicious && (
          <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 border border-amber-200 shrink-0">
            <AlertTriangle className="inline-block h-3.5 w-3.5 mr-1 -mt-0.5" /> Suspicious
          </span>
        )}
        {refreshBtn}
      </h2>

      <div className="flex flex-col sm:flex-row items-center sm:items-start gap-6">
        {/* Ring */}
        <div className="flex flex-col items-center gap-2 shrink-0">
          <div className="relative">
            <div
              className="absolute inset-2 rounded-full blur-xl opacity-25 pointer-events-none"
              style={{ backgroundColor: color }}
            />
            <svg width={SIZE} height={SIZE} className="-rotate-90 relative">
              <circle cx={SIZE / 2} cy={SIZE / 2} r={R} fill="none" stroke="rgba(0,0,0,0.06)" strokeWidth={STROKE} />
              <circle
                cx={SIZE / 2} cy={SIZE / 2} r={R}
                fill="none" stroke={color} strokeWidth={STROKE} strokeLinecap="round"
                strokeDasharray={CIRCUMFERENCE} strokeDashoffset={dashOffset}
                style={{ transition: 'stroke-dashoffset 1.2s cubic-bezier(0.16, 1, 0.3, 1)' }}
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-3xl font-bold" style={{ color }}>{score.score}</span>
              <span className="text-xs font-semibold" style={{ color }}>/100</span>
            </div>
          </div>
          <span className="text-sm font-bold" style={{ color }}>{scoreLabel(score.score)}</span>
        </div>

        {/* Details */}
        <div className="flex-1 space-y-4 w-full">
          <p className="text-xs text-gray-500 leading-relaxed">{scoreSummary(score.score)}</p>

          {strengths.length > 0 && (
            <div>
              <p className="text-xs font-bold text-emerald-700 uppercase tracking-widest mb-2">Strengths</p>
              <ul className="space-y-1.5">
                {strengths.map((s, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" /> {s}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {risks.length > 0 && (
            <div>
              <p className="text-xs font-bold text-red-600 uppercase tracking-widest mb-2">Risks</p>
              <ul className="space-y-1.5">
                {risks.map((r, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                    <CircleX className="mt-0.5 h-4 w-4 shrink-0 text-red-400" /> {r}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {cvMatch != null && (
            <div>
              <p className="text-xs font-bold text-blue-700 uppercase tracking-widest mb-2 flex items-center gap-1.5">
                <FileText className="h-3.5 w-3.5" /> CV ↔ Profile Match
              </p>
              <div className="flex items-center gap-3">
                <div className="flex-1 h-1.5 bg-white/60 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-700 ${cvMatchBar}`}
                    style={{ width: `${cvMatch}%` }}
                  />
                </div>
                <span className={`text-sm font-bold ${cvMatchColor}`}>{cvMatch}/100</span>
              </div>
              {cvWarnings.length > 0 && (
                <ul className="space-y-1.5 mt-2">
                  {cvWarnings.slice(0, 3).map((w, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" /> {w}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {urlWarnings.length > 0 && (
            <div>
              <p className="text-xs font-bold text-violet-600 uppercase tracking-widest mb-2">Link Warnings</p>
              <ul className="space-y-1.5">
                {urlWarnings.map((w, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                    <Link2 className="mt-0.5 h-4 w-4 shrink-0 text-violet-400" /> {w}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {authFlags.length > 0 && (
            <div>
              <p className="text-xs font-bold text-amber-700 uppercase tracking-widest mb-2">Authenticity Flags</p>
              <ul className="space-y-1.5">
                {authFlags.map((f, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                    <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" /> {f}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
