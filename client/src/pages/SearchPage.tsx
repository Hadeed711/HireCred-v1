import { useState, FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import api from '../lib/api'
import { useAuthStore } from '../stores/authStore'

interface CandidateResult {
  user_id: string
  uid: number | null
  name: string
  title: string | null
  skills: string[]
  credibility_score: number
  avg_appreciation: number
  appreciation_count: number
  skill_overlap_count: number
  rank_score: number
}

interface ParsedIntent {
  required_skills: string[]
  trust_keywords: string[]
  trust_priority: boolean
  experience_level: string | null
}

interface SearchResponse {
  parsed: ParsedIntent
  results: CandidateResult[]
}

function scoreStyle(score: number) {
  if (score >= 70) return { bg: 'bg-emerald-50', text: 'text-emerald-700', bar: 'bg-emerald-500', border: 'border-emerald-200', label: 'High Trust', dot: 'bg-emerald-400' }
  if (score >= 40) return { bg: 'bg-amber-50',   text: 'text-amber-700',   bar: 'bg-amber-400',   border: 'border-amber-200',   label: 'Moderate',   dot: 'bg-amber-400' }
  return               { bg: 'bg-red-50',        text: 'text-red-700',     bar: 'bg-red-400',     border: 'border-red-200',     label: 'Low Trust',  dot: 'bg-red-400' }
}

const EXAMPLE_QUERIES = [
  'Senior React developer with real project experience',
  'Reliable Python engineer I can trust with deadlines',
  'Full stack developer with a strong portfolio',
  'Mobile app developer with client references',
]

function LoadingState() {
  return (
    <div className="flex flex-col items-center gap-6 py-20">
      <div className="relative">
        <div className="w-16 h-16 rounded-full border-4 border-indigo-100 border-t-indigo-500 animate-spin" />
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-xl">🤖</span>
        </div>
      </div>
      <div className="text-center">
        <p className="text-gray-800 font-semibold">AI is analyzing your request…</p>
        <p className="text-sm text-gray-400 mt-1">Parsing intent, matching skills, ranking by trust score</p>
      </div>
      {/* Animated steps */}
      <div className="flex flex-col gap-2 text-sm text-gray-400 w-64">
        {['Parsing your search intent…', 'Matching candidate skills…', 'Ranking by HireCred score…'].map((step, i) => (
          <div
            key={step}
            className="flex items-center gap-2 animate-pulse"
            style={{ animationDelay: `${i * 0.4}s` }}
          >
            <div className="w-1.5 h-1.5 rounded-full bg-indigo-400 shrink-0" />
            {step}
          </div>
        ))}
      </div>
    </div>
  )
}

export default function SearchPage() {
  const { user } = useAuthStore()
  const [query, setQuery] = useState('')
  const [hasSearched, setHasSearched] = useState(false)

  const { mutate, isPending, data } = useMutation<SearchResponse, Error, string>({
    mutationFn: (q) => api.post('/search', { query: q }).then((r) => r.data),
    onSuccess: () => setHasSearched(true),
  })

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const q = query.trim()
    if (!q) return
    mutate(q)
  }

  function runQuery(q: string) {
    setQuery(q)
    mutate(q)
  }

  return (
    <div className="min-h-screen bg-linear-to-br from-slate-50 via-white to-indigo-50">
      {/* Header */}
      <header className="bg-white/80 backdrop-blur border-b border-gray-200 px-6 py-3 flex items-center justify-between sticky top-0 z-10">
        <Link to="/dashboard" className="text-lg font-bold bg-linear-to-r from-indigo-600 to-violet-600 bg-clip-text text-transparent">
          HireCred
        </Link>
        <div className="flex items-center gap-3">
          <Link to="/leaderboard" className="text-sm text-gray-500 hover:text-indigo-600 transition-colors">
            Leaderboard
          </Link>
          <span className="text-sm text-gray-400">{user?.full_name}</span>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-12">
        {/* Heading */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center gap-2 bg-indigo-50 text-indigo-600 text-xs font-semibold px-3.5 py-1.5 rounded-full mb-4 border border-indigo-100">
            🤖 AI-Powered Search
          </div>
          <h1 className="text-4xl font-bold text-gray-900 mb-3 tracking-tight">Find Trusted Professionals</h1>
          <p className="text-gray-500 max-w-lg mx-auto text-sm leading-relaxed">
            Describe who you're looking for in plain English. Our AI ranks candidates by credibility score, skills match, and verified client ratings.
          </p>
        </div>

        {/* Search input */}
        <form onSubmit={handleSubmit} className="mb-6">
          <div className="flex gap-3 bg-white border border-gray-200 rounded-2xl p-2 shadow-sm focus-within:ring-2 focus-within:ring-indigo-500 focus-within:border-transparent transition-all">
            <div className="flex-1 flex items-center gap-2 pl-2">
              <span className="text-gray-400 shrink-0">🔍</span>
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="e.g. Reliable React developer with 3+ years experience and a strong portfolio"
                className="flex-1 text-sm text-gray-800 placeholder-gray-400 bg-transparent focus:outline-none py-2"
              />
            </div>
            <button
              type="submit"
              disabled={isPending || !query.trim()}
              className="px-5 py-2.5 bg-indigo-600 text-white text-sm font-semibold rounded-xl hover:bg-indigo-700 disabled:opacity-50 transition-colors shadow-sm shadow-indigo-200 shrink-0 whitespace-nowrap"
            >
              {isPending ? 'Searching…' : 'Search'}
            </button>
          </div>
        </form>

        {/* Example queries */}
        {!hasSearched && !isPending && (
          <div className="mb-8">
            <p className="text-xs text-gray-400 font-medium text-center mb-3">Try these examples</p>
            <div className="flex flex-wrap gap-2 justify-center">
              {EXAMPLE_QUERIES.map((tip) => (
                <button
                  key={tip}
                  onClick={() => runQuery(tip)}
                  className="text-xs px-3.5 py-1.5 bg-white border border-gray-200 rounded-full text-gray-600 hover:border-indigo-300 hover:text-indigo-600 hover:bg-indigo-50 transition-all"
                >
                  {tip}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Loading */}
        {isPending && <LoadingState />}

        {/* Parsed intent chips */}
        {!isPending && data && (data.parsed.required_skills.length > 0 || data.parsed.trust_priority || data.parsed.experience_level) && (
          <div className="flex flex-wrap gap-2 mb-5 items-center p-3 bg-indigo-50/60 rounded-xl border border-indigo-100">
            <span className="text-xs text-indigo-500 font-semibold">AI understood:</span>
            {data.parsed.required_skills.map((s) => (
              <span key={s} className="px-2.5 py-0.5 bg-white text-indigo-700 text-xs rounded-full font-semibold capitalize border border-indigo-200 shadow-sm">
                {s}
              </span>
            ))}
            {data.parsed.trust_priority && (
              <span className="px-2.5 py-0.5 bg-emerald-100 text-emerald-700 text-xs rounded-full font-semibold border border-emerald-200">
                ✓ Trust priority
              </span>
            )}
            {data.parsed.experience_level && (
              <span className="px-2.5 py-0.5 bg-violet-100 text-violet-700 text-xs rounded-full font-semibold capitalize border border-violet-200">
                {data.parsed.experience_level} level
              </span>
            )}
          </div>
        )}

        {/* Results */}
        {!isPending && hasSearched && data && (
          <>
            {data.results.length === 0 ? (
              <div className="text-center py-20 bg-white rounded-2xl border border-dashed border-gray-200">
                <p className="text-5xl mb-4">🔍</p>
                <p className="text-gray-700 font-semibold">No candidates found</p>
                <p className="text-gray-400 text-sm mt-1.5 max-w-xs mx-auto">
                  Try a broader description, or different keywords like the technology name.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                <p className="text-xs text-gray-400 font-medium px-1">
                  {data.results.length} candidate{data.results.length !== 1 ? 's' : ''} ranked by HireCred score · skill match · client ratings
                </p>
                {data.results.map((candidate, idx) => {
                  const style = scoreStyle(candidate.credibility_score)
                  const top3Skills = candidate.skills.slice(0, 3)
                  const isTop3 = idx < 3

                  return (
                    <div
                      key={candidate.user_id}
                      className={`bg-white border rounded-2xl p-5 flex items-start gap-4 hover:shadow-md transition-all group ${
                        isTop3 ? 'border-indigo-100 hover:border-indigo-200' : 'border-gray-100 hover:border-gray-200'
                      }`}
                    >
                      {/* Rank */}
                      <div className={`text-sm font-bold w-7 shrink-0 mt-1 transition-colors ${
                        idx === 0 ? 'text-yellow-500' : idx === 1 ? 'text-gray-400' : idx === 2 ? 'text-orange-400' : 'text-gray-300 group-hover:text-indigo-400'
                      }`}>
                        {idx === 0 ? '🥇' : idx === 1 ? '🥈' : idx === 2 ? '🥉' : `#${idx + 1}`}
                      </div>

                      {/* Avatar */}
                      <div className="w-11 h-11 rounded-full bg-linear-to-br from-indigo-100 to-violet-100 flex items-center justify-center text-indigo-600 font-bold text-lg shrink-0">
                        {candidate.name.charAt(0).toUpperCase()}
                      </div>

                      {/* Info */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between gap-3 flex-wrap mb-1.5">
                          <div>
                            <div className="flex items-center gap-2">
                              <p className="font-semibold text-gray-900 text-sm">{candidate.name}</p>
                              {candidate.uid && (
                                <span className="text-xs font-mono text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded">#{candidate.uid}</span>
                              )}
                            </div>
                            {candidate.title && (
                              <p className="text-xs text-gray-500 mt-0.5">{candidate.title}</p>
                            )}
                          </div>
                          {/* Score badge */}
                          <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-xl text-xs font-bold shrink-0 border ${style.bg} ${style.text} ${style.border}`}>
                            <div className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
                            <span>{candidate.credibility_score}</span>
                            <span className="font-medium opacity-75">· {style.label}</span>
                          </div>
                        </div>

                        {/* Score bar */}
                        <div className="h-1 bg-gray-100 rounded-full overflow-hidden w-full mb-2.5">
                          <div
                            className={`h-full rounded-full transition-all duration-700 ${style.bar}`}
                            style={{ width: `${candidate.credibility_score}%` }}
                          />
                        </div>

                        {/* Skills */}
                        {top3Skills.length > 0 && (
                          <div className="flex flex-wrap gap-1.5 mb-3">
                            {top3Skills.map((s) => (
                              <span key={s} className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded-lg font-medium">
                                {s}
                              </span>
                            ))}
                            {candidate.skills.length > 3 && (
                              <span className="text-xs text-gray-400 self-center">
                                +{candidate.skills.length - 3} more
                              </span>
                            )}
                          </div>
                        )}

                        {/* Footer row */}
                        <div className="flex items-center justify-between flex-wrap gap-2">
                          <span className="text-xs text-gray-400">
                            {candidate.appreciation_count > 0
                              ? `⭐ ${candidate.avg_appreciation.toFixed(1)} avg · ${candidate.appreciation_count} review${candidate.appreciation_count !== 1 ? 's' : ''}`
                              : '💬 No reviews yet'}
                          </span>
                          <Link
                            to={`/profile/${candidate.uid ?? candidate.user_id}`}
                            className="text-xs px-3.5 py-1.5 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 transition-colors font-semibold shadow-sm shadow-indigo-200"
                          >
                            View Profile →
                          </Link>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  )
}
