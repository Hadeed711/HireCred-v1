import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import api from '../lib/api'
import { useAuthStore } from '../stores/authStore'
import type { AccountReport, AdminUser } from '../lib/types'

type Tab = 'reports' | 'users'
type ReportFilter = 'all' | 'pending' | 'approved' | 'reconsidered' | 'rejected'

const REASON_LABELS: Record<string, string> = {
  fake_account: 'Fake / bot account',
  impersonation: 'Impersonation',
  fake_credentials: 'Fake credentials',
  inappropriate_content: 'Inappropriate content',
  spam: 'Spam',
  other: 'Other',
}

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-amber-100 text-amber-700 border-amber-200',
  approved: 'bg-red-100 text-red-700 border-red-200',
  rejected: 'bg-gray-100 text-gray-600 border-gray-200',
  reconsidered: 'bg-emerald-100 text-emerald-700 border-emerald-200',
}

export default function AdminPanel() {
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const qc = useQueryClient()
  const [tab, setTab] = useState<Tab>('reports')
  const [reportFilter, setReportFilter] = useState<ReportFilter>('pending')
  const [resolveNote, setResolveNote] = useState<Record<string, string>>({})

  const { data: reports = [], isLoading: reportsLoading } = useQuery<AccountReport[]>({
    queryKey: ['admin-reports', reportFilter],
    queryFn: () =>
      api.get(`/admin/reports${reportFilter !== 'all' ? `?status=${reportFilter}` : ''}`).then((r) => r.data),
    enabled: tab === 'reports',
  })

  const { data: users = [], isLoading: usersLoading } = useQuery<AdminUser[]>({
    queryKey: ['admin-users'],
    queryFn: () => api.get('/admin/users').then((r) => r.data),
    enabled: tab === 'users',
  })

  const approveMutation = useMutation({
    mutationFn: ({ id, note }: { id: string; note: string }) =>
      api.put(`/admin/reports/${id}/approve`, { admin_note: note || null }),
    onSuccess: () => {
      toast.success('Report approved — suspicious tag applied.')
      qc.invalidateQueries({ queryKey: ['admin-reports'] })
    },
    onError: (err: any) => toast.error(err?.response?.data?.detail || 'Failed to approve.'),
  })

  const rejectMutation = useMutation({
    mutationFn: ({ id, note }: { id: string; note: string }) =>
      api.put(`/admin/reports/${id}/reject`, { admin_note: note || null }),
    onSuccess: () => {
      toast.success('Report rejected.')
      qc.invalidateQueries({ queryKey: ['admin-reports'] })
    },
    onError: (err: any) => toast.error(err?.response?.data?.detail || 'Failed to reject.'),
  })

  const reconsiderMutation = useMutation({
    mutationFn: ({ id, note }: { id: string; note: string }) =>
      api.put(`/admin/reports/${id}/reconsider`, { admin_note: note || null }),
    onSuccess: () => {
      toast.success('Report reconsidered. Account restored to normal.')
      qc.invalidateQueries({ queryKey: ['admin-reports'] })
      qc.invalidateQueries({ queryKey: ['admin-users'] })
    },
    onError: (err: any) => toast.error(err?.response?.data?.detail || 'Failed to reconsider.'),
  })

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between sticky top-0 z-10">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/dashboard')}
            className="text-sm text-gray-500 hover:text-gray-700 flex items-center gap-1 hover:bg-gray-100 px-2.5 py-1.5 rounded-lg"
          >
            ← Back
          </button>
          <span className="text-sm font-bold text-gray-900">HireCred Admin</span>
          <span className="text-xs bg-red-100 text-red-600 px-2 py-0.5 rounded-full font-semibold border border-red-200">ADMIN</span>
        </div>
        <span className="text-xs text-gray-400">{user?.email}</span>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8">
        {/* Tab bar */}
        <div className="flex gap-1 mb-6 bg-white border border-gray-200 rounded-xl p-1 w-fit">
          {(['reports', 'users'] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`text-sm px-5 py-2 rounded-lg font-medium transition-colors capitalize ${
                tab === t
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              {t === 'reports' ? `Reports` : 'Users'}
            </button>
          ))}
        </div>

        {/* ── Reports tab ── */}
        {tab === 'reports' && (
          <div className="space-y-4">
            {/* Filter */}
            <div className="flex gap-2 flex-wrap">
              {(['pending', 'all', 'approved', 'reconsidered', 'rejected'] as ReportFilter[]).map((f) => (
                <button
                  key={f}
                  onClick={() => setReportFilter(f)}
                  className={`text-xs px-3 py-1.5 rounded-lg font-medium capitalize transition-colors border ${
                    reportFilter === f
                      ? 'bg-indigo-600 text-white border-indigo-600'
                      : 'bg-white text-gray-600 border-gray-200 hover:border-gray-300'
                  }`}
                >
                  {f}
                </button>
              ))}
            </div>

            {reportsLoading ? (
              <p className="text-sm text-gray-400 text-center py-12">Loading reports…</p>
            ) : reports.length === 0 ? (
              <div className="bg-white rounded-2xl border border-gray-100 p-12 text-center">
                <p className="text-4xl mb-3">📭</p>
                <p className="text-gray-500 font-medium">No reports found</p>
              </div>
            ) : (
              <div className="space-y-3">
                {reports.map((r) => (
                  <div key={r.id} className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm">
                    <div className="flex items-start justify-between gap-4 flex-wrap">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-2 flex-wrap">
                          <span className={`text-xs px-2 py-0.5 rounded-full font-semibold border capitalize ${STATUS_COLORS[r.status]}`}>
                            {r.status}
                          </span>
                          <span className="text-xs font-semibold text-gray-700 bg-gray-100 px-2 py-0.5 rounded-md">
                            {REASON_LABELS[r.reason] || r.reason}
                          </span>
                          <span className="text-xs text-gray-400">
                            {new Date(r.created_at).toLocaleDateString()}
                          </span>
                        </div>

                        <p className="text-sm text-gray-700 mb-0.5">
                          <span className="font-semibold">Reporter:</span>{' '}
                          {r.reporter_name || r.reporter_id.slice(0, 8)}
                        </p>
                        <p className="text-sm text-gray-700 mb-2">
                          <span className="font-semibold">Reported:</span>{' '}
                          <button
                            onClick={() => navigate(`/profile/${r.reported_user_id}`, { state: { from: '/admin' } })}
                            className="text-indigo-600 hover:underline"
                          >
                            {r.reported_user_name || r.reported_user_id.slice(0, 8)} ↗
                          </button>
                        </p>

                        {r.evidence_text && (
                          <div className="bg-gray-50 rounded-xl px-3 py-2 text-xs text-gray-600 mb-2 border border-gray-100">
                            <span className="font-semibold text-gray-700">Evidence:</span> {r.evidence_text}
                          </div>
                        )}

                        {r.admin_note && (
                          <p className="text-xs text-gray-500 italic">Admin note: {r.admin_note}</p>
                        )}
                      </div>

                      {r.status === 'pending' && (
                        <div className="flex flex-col gap-2 shrink-0 min-w-50">
                          <textarea
                            placeholder="Admin note (optional)"
                            value={resolveNote[r.id] || ''}
                            onChange={(e) => setResolveNote((prev) => ({ ...prev, [r.id]: e.target.value }))}
                            rows={2}
                            className="w-full text-xs border border-gray-200 rounded-xl px-2.5 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-indigo-200"
                          />
                          <div className="flex gap-2">
                            <button
                              onClick={() => approveMutation.mutate({ id: r.id, note: resolveNote[r.id] || '' })}
                              disabled={approveMutation.isPending}
                              className="flex-1 text-xs py-2 bg-red-500 text-white rounded-xl hover:bg-red-600 disabled:opacity-60 font-semibold transition-colors"
                            >
                              Approve
                            </button>
                            <button
                              onClick={() => rejectMutation.mutate({ id: r.id, note: resolveNote[r.id] || '' })}
                              disabled={rejectMutation.isPending}
                              className="flex-1 text-xs py-2 bg-gray-200 text-gray-700 rounded-xl hover:bg-gray-300 disabled:opacity-60 font-semibold transition-colors"
                            >
                              Reject
                            </button>
                          </div>
                        </div>
                      )}

                      {r.status === 'approved' && (
                        <div className="flex flex-col gap-2 shrink-0 min-w-50">
                          <textarea
                            placeholder="Admin note (optional)"
                            value={resolveNote[r.id] || ''}
                            onChange={(e) => setResolveNote((prev) => ({ ...prev, [r.id]: e.target.value }))}
                            rows={2}
                            className="w-full text-xs border border-gray-200 rounded-xl px-2.5 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-indigo-200"
                          />
                          <button
                            onClick={() => reconsiderMutation.mutate({ id: r.id, note: resolveNote[r.id] || '' })}
                            disabled={reconsiderMutation.isPending}
                            className="w-full text-xs py-2 bg-emerald-600 text-white rounded-xl hover:bg-emerald-700 disabled:opacity-60 font-semibold transition-colors"
                          >
                            Reconsider
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ── Users tab ── */}
        {tab === 'users' && (
          <div>
            {usersLoading ? (
              <p className="text-sm text-gray-400 text-center py-12">Loading users…</p>
            ) : (
              <div className="bg-white rounded-2xl border border-gray-100 overflow-hidden shadow-sm">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-100 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                      <th className="px-4 py-3 text-left">User</th>
                      <th className="px-4 py-3 text-left">Role</th>
                      <th className="px-4 py-3 text-left">Score</th>
                      <th className="px-4 py-3 text-left">Status</th>
                      <th className="px-4 py-3 text-left">Joined</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {users.map((u) => (
                      <tr key={u.id} className="hover:bg-gray-50 transition-colors">
                        <td className="px-4 py-3">
                          <button
                            onClick={() => navigate(`/profile/${u.id}`, { state: { from: '/admin' } })}
                            className="text-left"
                          >
                            <p className="font-medium text-gray-900 hover:text-indigo-600 transition-colors">
                              {u.full_name}
                            </p>
                            <p className="text-xs text-gray-400">{u.email}</p>
                          </button>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize border ${
                            u.role === 'client'
                              ? 'bg-blue-50 text-blue-700 border-blue-100'
                              : 'bg-violet-50 text-violet-700 border-violet-100'
                          }`}>
                            {u.role}
                          </span>
                          {u.is_admin && (
                            <span className="ml-1 text-xs px-2 py-0.5 rounded-full font-medium bg-red-50 text-red-600 border border-red-100">
                              admin
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <span className={`font-semibold ${
                            u.score === null ? 'text-gray-400' :
                            u.score >= 70 ? 'text-emerald-600' :
                            u.score >= 40 ? 'text-amber-600' : 'text-red-500'
                          }`}>
                            {u.score ?? '—'}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            {u.is_suspicious && (
                              <span className="text-xs px-2 py-0.5 rounded-full font-semibold bg-amber-100 text-amber-700 border border-amber-200">
                                ⚠ Suspicious
                              </span>
                            )}
                            {!u.is_active && (
                              <span className="text-xs px-2 py-0.5 rounded-full font-semibold bg-gray-100 text-gray-600 border border-gray-200">
                                Inactive
                              </span>
                            )}
                            {u.is_active && !u.is_suspicious && (
                              <span className="text-xs text-gray-400">Active</span>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-xs text-gray-400">
                          {new Date(u.created_at).toLocaleDateString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  )
}
