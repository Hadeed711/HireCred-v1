import type { CredibilityScore } from '../../lib/types'

interface Props {
  score: CredibilityScore | null | undefined
  isLoading?: boolean
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

export default function ScoreWidget({ score, isLoading }: Props) {
  if (isLoading) {
    return (
      <div className="bg-white rounded-2xl border border-gray-100 p-6">
        <h2 className="text-base font-semibold text-gray-900 mb-4 flex items-center gap-2">
          🏆 HireCred Score
          <span className="flex-1 h-px bg-gray-100 ml-1" />
        </h2>
        <div className="flex flex-col items-center gap-3 py-2">
          <div className="w-32 h-32 rounded-full border-12 border-gray-100 animate-pulse" />
          <p className="text-sm text-gray-400 animate-pulse">Computing AI score…</p>
          <p className="text-xs text-gray-300">This takes 5–10 seconds</p>
        </div>
      </div>
    )
  }

  if (!score) {
    return (
      <div className="bg-white rounded-2xl border border-gray-100 p-6">
        <h2 className="text-base font-semibold text-gray-900 mb-4 flex items-center gap-2">
          🏆 HireCred Score
          <span className="flex-1 h-px bg-gray-100 ml-1" />
        </h2>
        <div className="text-center py-4">
          <p className="text-3xl mb-2">🤖</p>
          <p className="text-sm text-gray-500 font-medium">Score not yet computed</p>
          <p className="text-xs text-gray-400 mt-1">Save your profile to trigger AI scoring.</p>
        </div>
      </div>
    )
  }

  const pct = score.score / 100
  const dashOffset = CIRCUMFERENCE * (1 - pct)
  const color = scoreColor(score.score)
  const bgClass = scoreBgClass(score.score)

  return (
    <div className={`rounded-2xl border p-6 bg-linear-to-br ${bgClass}`}>
      <h2 className="text-base font-semibold text-gray-900 mb-5 flex items-center gap-2">
        🏆 HireCred Score
        <span className="flex-1 h-px bg-gray-200/60 ml-1" />
      </h2>

      <div className="flex flex-col sm:flex-row items-center sm:items-start gap-6">
        {/* Ring */}
        <div className="flex flex-col items-center gap-2 shrink-0">
          <div className="relative">
            <svg width={SIZE} height={SIZE} className="-rotate-90">
              <circle
                cx={SIZE / 2}
                cy={SIZE / 2}
                r={R}
                fill="none"
                stroke="rgba(0,0,0,0.06)"
                strokeWidth={STROKE}
              />
              <circle
                cx={SIZE / 2}
                cy={SIZE / 2}
                r={R}
                fill="none"
                stroke={color}
                strokeWidth={STROKE}
                strokeLinecap="round"
                strokeDasharray={CIRCUMFERENCE}
                strokeDashoffset={dashOffset}
                style={{ transition: 'stroke-dashoffset 1s ease' }}
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-3xl font-bold" style={{ color }}>{score.score}</span>
              <span className="text-xs font-semibold" style={{ color }}>/100</span>
            </div>
          </div>
          <div className="text-center">
            <span className="text-sm font-bold" style={{ color }}>{scoreLabel(score.score)}</span>
          </div>
        </div>

        {/* Details */}
        <div className="flex-1 space-y-4 w-full">
          <p className="text-xs text-gray-500 leading-relaxed">{scoreSummary(score.score)}</p>

          {score.strengths.length > 0 && (
            <div>
              <p className="text-xs font-bold text-emerald-700 uppercase tracking-widest mb-2">Strengths</p>
              <ul className="space-y-1.5">
                {score.strengths.map((s, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                    <span className="text-emerald-500 mt-0.5 shrink-0 font-bold text-xs">✓</span>
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {score.risks.length > 0 && (
            <div>
              <p className="text-xs font-bold text-red-600 uppercase tracking-widest mb-2">Risks</p>
              <ul className="space-y-1.5">
                {score.risks.map((r, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                    <span className="text-red-400 mt-0.5 shrink-0 font-bold text-xs">!</span>
                    {r}
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
