import { useQuery } from '@tanstack/react-query'
import { BadgeCheck, AlertTriangle, MessageSquareHeart } from 'lucide-react'
import api from '../../lib/api'
import RatingBar from './RatingBar'

interface AppreciationItem {
  id: string
  from_user_name: string
  summary: string
  skill_rating: number
  communication_rating: number
  reliability_rating: number
  created_at: string
}

interface AppreciationData {
  count: number
  avg_skill: number
  avg_communication: number
  avg_reliability: number
  items: AppreciationItem[]
}

interface Props {
  userId: string
  fraudRisk?: 'low' | 'medium' | 'high'
}

export default function AppreciationSection({ userId, fraudRisk }: Props) {
  const { data, isLoading } = useQuery<AppreciationData>({
    queryKey: ['appreciations', userId],
    queryFn: () => api.get(`/appreciation/${userId}`).then((r) => r.data),
    enabled: !!userId,
  })

  if (isLoading) return null

  if (!data || data.count === 0) {
    return (
      <div className="bg-white rounded-2xl border border-gray-200 p-6 animate-fade-up">
        <h2 className="text-base font-semibold text-gray-900 mb-1 flex items-center gap-2">
          <MessageSquareHeart className="h-4.5 w-4.5 text-indigo-600" /> Appreciations
        </h2>
        <p className="text-xs text-gray-400 mb-3">Feedback submitted by hiring clients who worked with this professional.</p>
        <p className="text-sm text-gray-400">No appreciations yet.</p>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-6 space-y-5">
      <div>
        <div className="flex items-center flex-wrap gap-2">
          <h2 className="text-base font-semibold text-gray-900">
            Appreciations
            <span className="ml-2 text-sm font-normal text-gray-400">({data.count})</span>
          </h2>
          {data.count >= 3 && fraudRisk === 'low' && (
            <span className="text-xs font-medium text-green-700 bg-green-50 border border-green-200 rounded-full px-2.5 py-0.5 inline-flex items-center gap-1">
              <BadgeCheck className="h-3.5 w-3.5" /> Verified Feedback
            </span>
          )}
          {fraudRisk === 'medium' && (
            <span className="text-xs font-medium text-amber-700 bg-amber-50 border border-amber-200 rounded-full px-2.5 py-0.5 inline-flex items-center gap-1">
              <AlertTriangle className="h-3 w-3" /> Under Review
            </span>
          )}
          {fraudRisk === 'high' && (
            <span className="text-xs font-medium text-red-700 bg-red-50 border border-red-200 rounded-full px-2.5 py-0.5 inline-flex items-center gap-1">
              <AlertTriangle className="h-3 w-3" /> Suspicious Reviews
            </span>
          )}
        </div>
        <p className="text-xs text-gray-400 mt-1">Feedback submitted by hiring clients who worked with this professional.</p>
      </div>

      {/* Aggregated bars */}
      <div className="space-y-3 pb-4 border-b border-gray-100">
        <RatingBar label="Skill" value={data.avg_skill} />
        <RatingBar label="Communication" value={data.avg_communication} />
        <RatingBar label="Reliability" value={data.avg_reliability} />
      </div>

      {/* Individual cards */}
      <div className="space-y-4">
        {data.items.map((item) => (
          <div key={item.id} className="bg-gray-50 rounded-xl p-4 border border-gray-100">
            <div className="flex items-start justify-between gap-2 mb-2">
              <div>
                <p className="text-sm font-medium text-gray-800">{item.from_user_name}</p>
                <p className="text-xs text-gray-400">
                  {new Date(item.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                </p>
              </div>
              <div className="flex gap-3 text-xs text-gray-500 shrink-0">
                <span>Skill <strong>{item.skill_rating.toFixed(1)}</strong></span>
                <span>Comm <strong>{item.communication_rating.toFixed(1)}</strong></span>
                <span>Rel <strong>{item.reliability_rating.toFixed(1)}</strong></span>
              </div>
            </div>
            <p className="text-sm text-gray-600 italic">"{item.summary}"</p>
          </div>
        ))}
      </div>
    </div>
  )
}
