import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../lib/api'
import { useAuthStore } from '../stores/authStore'
import toast from 'react-hot-toast'

interface Conversation {
  conversation_id: string
  other_user_id: string
  other_user_name: string
  last_message: string
  last_message_at: string
  unread_count: number
}

interface MessageItem {
  id: string
  sender_id: string
  sender_name: string
  content: string
  is_read: boolean
  created_at: string
}

export default function Inbox() {
  const { userId: otherUserId } = useParams<{ userId?: string }>()
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const qc = useQueryClient()
  const [draft, setDraft] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  // Conversation list
  const { data: conversations, isLoading: convsLoading } = useQuery<Conversation[]>({
    queryKey: ['conversations'],
    queryFn: () => api.get('/messages/conversations').then((r) => r.data),
    refetchInterval: otherUserId ? false : 5000,
  })

  // Thread
  const { data: thread } = useQuery<MessageItem[]>({
    queryKey: ['thread', otherUserId],
    queryFn: () => api.get(`/messages/conversation/${otherUserId}`).then((r) => r.data),
    enabled: !!otherUserId,
    refetchInterval: 5000,
  })

  // Mark as read when opening a thread
  useEffect(() => {
    if (otherUserId) {
      api.patch(`/messages/read/${otherUserId}`).catch(() => null)
      qc.invalidateQueries({ queryKey: ['conversations'] })
    }
  }, [otherUserId, qc])

  // Scroll to bottom when thread updates
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [thread])

  const sendMutation = useMutation({
    mutationFn: (content: string) =>
      api.post('/messages', { to_user_id: otherUserId, content }),
    onSuccess: () => {
      setDraft('')
      qc.invalidateQueries({ queryKey: ['thread', otherUserId] })
      qc.invalidateQueries({ queryKey: ['conversations'] })
    },
    onError: () => toast.error('Failed to send message'),
  })

  const handleSend = () => {
    const trimmed = draft.trim()
    if (!trimmed) return
    sendMutation.mutate(trimmed)
  }

  const activeConv = conversations?.find((c) => c.other_user_id === otherUserId)

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center gap-4">
        <button
          onClick={() => (otherUserId ? navigate('/inbox') : navigate('/dashboard'))}
          className="text-sm text-gray-500 hover:text-gray-700"
        >
          ← {otherUserId ? 'Inbox' : 'Back'}
        </button>
        <h1 className="text-base font-semibold text-gray-900">
          {otherUserId && activeConv ? activeConv.other_user_name : 'Inbox'}
        </h1>
      </header>

      <div className="flex flex-1 max-w-4xl mx-auto w-full">
        {/* ── Conversation list (sidebar) ── */}
        <aside className={`w-72 border-r border-gray-200 bg-white flex-shrink-0 ${otherUserId ? 'hidden md:flex flex-col' : 'flex flex-col w-full md:w-72'}`}>
          <div className="px-4 py-3 border-b border-gray-100">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Conversations</p>
          </div>

          {convsLoading && (
            <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">
              Loading…
            </div>
          )}

          {!convsLoading && (!conversations || conversations.length === 0) && (
            <div className="flex-1 flex items-center justify-center text-gray-400 text-sm px-6 text-center">
              No conversations yet. Visit a profile to send a message.
            </div>
          )}

          <div className="flex-1 overflow-y-auto">
            {conversations?.map((conv) => (
              <button
                key={conv.conversation_id}
                onClick={() => navigate(`/inbox/${conv.other_user_id}`)}
                className={`w-full px-4 py-3 flex items-start gap-3 text-left border-b border-gray-50 hover:bg-gray-50 transition-colors ${
                  conv.other_user_id === otherUserId ? 'bg-indigo-50' : ''
                }`}
              >
                <div className="w-9 h-9 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 font-bold text-sm shrink-0">
                  {conv.other_user_name.charAt(0).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-1">
                    <p className="text-sm font-medium text-gray-900 truncate">{conv.other_user_name}</p>
                    {conv.unread_count > 0 && (
                      <span className="bg-indigo-600 text-white text-xs rounded-full px-1.5 py-0.5 shrink-0">
                        {conv.unread_count}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-400 truncate mt-0.5">{conv.last_message}</p>
                </div>
              </button>
            ))}
          </div>
        </aside>

        {/* ── Thread panel ── */}
        {otherUserId ? (
          <div className="flex-1 flex flex-col">
            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-4 py-6 space-y-3">
              {thread?.length === 0 && (
                <p className="text-center text-sm text-gray-400">No messages yet. Say hello!</p>
              )}
              {thread?.map((msg) => {
                const isMe = msg.sender_id === user?.id
                return (
                  <div
                    key={msg.id}
                    className={`flex ${isMe ? 'justify-end' : 'justify-start'}`}
                  >
                    <div
                      className={`max-w-xs md:max-w-md px-4 py-2.5 rounded-2xl text-sm leading-relaxed ${
                        isMe
                          ? 'bg-indigo-600 text-white rounded-br-sm'
                          : 'bg-white border border-gray-200 text-gray-800 rounded-bl-sm'
                      }`}
                    >
                      {msg.content}
                      <p className={`text-xs mt-1 ${isMe ? 'text-indigo-200' : 'text-gray-400'}`}>
                        {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </p>
                    </div>
                  </div>
                )
              })}
              <div ref={bottomRef} />
            </div>

            {/* Input */}
            <div className="bg-white border-t border-gray-200 px-4 py-3 flex items-end gap-3">
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    handleSend()
                  }
                }}
                placeholder="Type a message… (Enter to send)"
                rows={1}
                className="flex-1 resize-none rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <button
                onClick={handleSend}
                disabled={!draft.trim() || sendMutation.isPending}
                className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-xl hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Send
              </button>
            </div>
          </div>
        ) : (
          <div className="hidden md:flex flex-1 items-center justify-center text-gray-400 text-sm">
            Select a conversation to start messaging.
          </div>
        )}
      </div>
    </div>
  )
}
