import { useState, FormEvent } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'
import toast from 'react-hot-toast'
import RatingBar from './RatingBar'

interface Props {
  toUserId: string
  toUserName: string
  onClose: () => void
}

interface AIResult {
  skill_rating: number
  communication_rating: number
  reliability_rating: number
  summary: string
}

interface SubmitResponse {
  appreciation: { id: string }
  ai_ratings: AIResult
}

export default function AppreciationModal({ toUserId, toUserName, onClose }: Props) {
  const [feedback, setFeedback] = useState('')
  const [aiResult, setAiResult] = useState<AIResult | null>(null)
  const queryClient = useQueryClient()

  const { mutate, isPending } = useMutation<SubmitResponse, Error, string>({
    mutationFn: (raw_feedback) =>
      api.post('/appreciation', { to_user_id: toUserId, raw_feedback }).then((r) => r.data),
    onSuccess: (data) => {
      setAiResult(data.ai_ratings)
      queryClient.invalidateQueries({ queryKey: ['appreciations', toUserId] })
      queryClient.invalidateQueries({ queryKey: ['score', toUserId] })
      toast.success('Appreciation submitted!')
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail ?? 'Failed to submit')
    },
  })

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (feedback.trim().length < 10) {
      toast.error('Please write at least 10 characters')
      return
    }
    mutate(feedback.trim())
  }

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center px-4" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6"
        onClick={(e) => e.stopPropagation()}
      >
        {!aiResult ? (
          <>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">Give Appreciation</h2>
              <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">×</button>
            </div>
            <p className="text-sm text-gray-500 mb-4">
              Describe your experience working with <span className="font-medium text-gray-700">{toUserName}</span>.
              Our AI will extract structured ratings from your words.
            </p>
            <form onSubmit={handleSubmit} className="space-y-4">
              <textarea
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                rows={5}
                placeholder="e.g. Great developer, delivered ahead of schedule and communicated clearly throughout the project…"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500"
                required
              />
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="flex-1 py-2 border border-gray-300 text-gray-700 text-sm rounded-lg hover:bg-gray-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isPending}
                  className="flex-1 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
                >
                  {isPending ? 'Analyzing…' : 'Submit'}
                </button>
              </div>
            </form>
          </>
        ) : (
          <>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">Here's what we understood</h2>
              <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">×</button>
            </div>
            <p className="text-sm text-gray-500 italic mb-5">"{aiResult.summary}"</p>
            <div className="space-y-3 mb-6">
              <RatingBar label="Skill" value={aiResult.skill_rating} />
              <RatingBar label="Communication" value={aiResult.communication_rating} />
              <RatingBar label="Reliability" value={aiResult.reliability_rating} />
            </div>
            <button
              onClick={onClose}
              className="w-full py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 transition-colors"
            >
              Done
            </button>
          </>
        )}
      </div>
    </div>
  )
}
