import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import api from '../lib/api'

interface LeaderboardEntry {
  rank: number
  user_id: string
  uid: number | null
  name: string
  skills: string[]
  credibility_score: number
  appreciation_count: number
  avg_ratings: number
  proof_signal_count: number
  fraud_risk: 'low' | 'medium' | 'high'
  insufficient_data: boolean
}

const RANK_META: Record<number, { ring: string; badge: string; emoji: string }> = {
  1: { ring: 'ring-2 ring-yellow-300', badge: 'bg-yellow-400 text-yellow-900', emoji: '🥇' },
  2: { ring: 'ring-2 ring-gray-300',   badge: 'bg-gray-300 text-gray-800',    emoji: '🥈' },
  3: { ring: 'ring-2 ring-orange-300', badge: 'bg-orange-300 text-orange-900', emoji: '🥉' },
}

function scoreColor(score: number) {
  if (score >= 70) return { text: 'text-emerald-600', bg: 'bg-emerald-50' }
  if (score >= 40) return { text: 'text-amber-500',   bg: 'bg-amber-50' }
  return               { text: 'text-red-500',        bg: 'bg-red-50' }
}

function SkeletonRow() {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-4 flex items-center gap-4 animate-pulse">
      <div className="w-10 h-10 rounded-full bg-gray-200 shrink-0" />
      <div className="w-10 h-10 rounded-full bg-gray-200 shrink-0" />
      <div className="flex-1 space-y-2">
        <div className="h-3.5 bg-gray-200 rounded w-1/3" />
        <div className="h-2.5 bg-gray-100 rounded w-1/2" />
      </div>
      <div className="w-12 h-8 bg-gray-200 rounded-lg" />
    </div>
  )
}

export default function Leaderboard() {
  const navigate = useNavigate()

  const { data, isLoading, isError } = useQuery<LeaderboardEntry[]>({
    queryKey: ['leaderboard'],
    queryFn: () => api.get('/leaderboard').then((r) => r.data),
    staleTime: 2 * 60_000,
  })

  const insufficientData = data && data.length > 0 && data[0].insufficient_data
  const qualifiedData = data?.filter((e) => !e.insufficient_data) ?? data

  return (
    <div className="min-h-screen bg-linear-to-br from-slate-50 via-white to-indigo-50">
      <header className="bg-white/80 backdrop-blur border-b border-gray-200 px-6 py-4 flex items-center justify-between sticky top-0 z-10">
        <button
          onClick={() => navigate(-1)}
          className="text-sm text-gray-500 hover:text-gray-700 flex items-center gap-1.5 hover:bg-gray-100 px-3 py-1.5 rounded-lg transition-colors"
        >
          ← Back
        </button>
        <div className="flex flex-col items-center">
          <h1 className="text-base font-bold text-gray-900">Trust Leaderboard</h1>
          <p className="text-xs text-gray-400">Refreshes every 2 min</p>
        </div>
        <div className="w-20" />
      </header>

      <main className="max-w-2xl mx-auto px-4 py-8">
        {/* Hero banner */}
        <div className="bg-linear-to-r from-indigo-600 to-violet-600 text-white rounded-2xl p-6 mb-6 text-center shadow-lg">
          <p className="text-4xl mb-2">🏆</p>
          <h2 className="text-xl font-bold mb-1">Top Trusted Professionals</h2>
          <p className="text-indigo-200 text-sm">
            Ranked by HireCred score · client appreciation · proof signals · activity
          </p>
        </div>

        {/* Insufficient data notice */}
        {insufficientData && (
          <div className="flex items-center gap-2 p-3 mb-5 bg-amber-50 border border-amber-200 rounded-xl text-sm text-amber-700">
            <span>🌱</span>
            <span>Not enough verified data yet — showing profiles sorted by trust completeness.</span>
          </div>
        )}

        {isLoading && (
          <div className="space-y-3">
            {Array.from({ length: 8 }).map((_, i) => <SkeletonRow key={i} />)}
          </div>
        )}

        {isError && (
          <div className="text-center py-16">
            <p className="text-3xl mb-3">😕</p>
            <p className="text-gray-600 font-medium">Failed to load leaderboard</p>
            <p className="text-gray-400 text-sm mt-1">Try again later.</p>
          </div>
        )}

        {data && data.length === 0 && (
          <div className="text-center py-16">
            <p className="text-4xl mb-3">🌱</p>
            <p className="text-gray-600 font-medium">No qualified candidates yet</p>
            <p className="text-gray-400 text-sm mt-1 max-w-xs mx-auto">
              Candidates appear here after completing their profile and receiving at least one client appreciation.
            </p>
          </div>
        )}

        {qualifiedData && qualifiedData.length > 0 && (
          <div className="space-y-3">
            {qualifiedData.map((entry) => {
              const meta = RANK_META[entry.rank]
              const colors = scoreColor(entry.credibility_score)
              return (
                <button
                  key={entry.user_id}
                  onClick={() => navigate(`/profile/${entry.uid ?? entry.user_id}`)}
                  className={`w-full bg-white rounded-2xl border border-gray-100 p-4 flex items-center gap-4
                    hover:border-indigo-200 hover:shadow-md transition-all text-left group ${meta?.ring ?? ''}`}
                >
                  {/* Rank badge */}
                  <div
                    className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold shrink-0 ${
                      meta ? meta.badge : 'bg-gray-100 text-gray-500'
                    }`}
                  >
                    {meta ? meta.emoji : `#${entry.rank}`}
                  </div>

                  {/* Avatar */}
                  <div className="w-10 h-10 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 font-bold text-sm shrink-0">
                    {entry.name.charAt(0).toUpperCase()}
                  </div>

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="font-semibold text-gray-900 text-sm truncate group-hover:text-indigo-600 transition-colors">
                        {entry.name}
                      </p>
                      {entry.uid && (
                        <span className="text-xs font-mono text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded shrink-0">
                          #{entry.uid}
                        </span>
                      )}
                      {entry.fraud_risk === 'medium' && (
                        <span className="text-xs px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded font-medium shrink-0">
                          ⚠ Unverified reviews
                        </span>
                      )}
                    </div>
                    {entry.skills.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1.5">
                        {entry.skills.map((s) => (
                          <span key={s} className="text-xs px-2 py-0.5 bg-indigo-50 text-indigo-600 rounded-md font-medium">
                            {s}
                          </span>
                        ))}
                      </div>
                    )}
                    <div className="flex items-center gap-3 mt-1.5 flex-wrap">
                      {entry.appreciation_count > 0 && (
                        <span className="text-xs text-gray-400">
                          ⭐ {entry.avg_ratings.toFixed(1)} avg · {entry.appreciation_count} review{entry.appreciation_count !== 1 ? 's' : ''}
                        </span>
                      )}
                      {entry.proof_signal_count > 0 && (
                        <span className="text-xs text-gray-400">
                          🔐 {entry.proof_signal_count} proof signal{entry.proof_signal_count !== 1 ? 's' : ''}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Score */}
                  <div className={`px-3 py-1.5 rounded-xl shrink-0 ${colors.bg}`}>
                    <span className={`text-xl font-bold ${colors.text}`}>
                      {entry.credibility_score}
                    </span>
                  </div>
                </button>
              )
            })}
          </div>
        )}
      </main>
    </div>
  )
}
