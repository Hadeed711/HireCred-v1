import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, MessageCircle, ImageIcon, SendHorizonal, Trash2, X } from 'lucide-react'
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
  image_url: string | null
  is_read: boolean
  is_deleted: boolean
  created_at: string
}

const AVATAR_COLORS = [
  'bg-indigo-500', 'bg-violet-500', 'bg-blue-500',
  'bg-emerald-500', 'bg-amber-500', 'bg-rose-500', 'bg-teal-500',
]
function avatarColor(name: string) { return AVATAR_COLORS[name.charCodeAt(0) % AVATAR_COLORS.length] }
function initial(name: string) { return name.charAt(0).toUpperCase() }

function convTime(dateStr: string) {
  const d = new Date(dateStr)
  const today = new Date()
  if (d.toDateString() === today.toDateString())
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' })
}

function dayLabel(dateStr: string) {
  const d = new Date(dateStr)
  const today = new Date()
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)
  if (d.toDateString() === today.toDateString()) return 'Today'
  if (d.toDateString() === yesterday.toDateString()) return 'Yesterday'
  return d.toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' })
}

export default function Inbox() {
  const { userId: otherUserId } = useParams<{ userId?: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const navName = (location.state as { name?: string } | null)?.name
  const { user } = useAuthStore()
  const qc = useQueryClient()

  const [draft, setDraft] = useState('')
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [imagePreview, setImagePreview] = useState<string | null>(null)
  const [uploadingImg, setUploadingImg] = useState(false)
  const [pendingImageUrl, setPendingImageUrl] = useState<string | null>(null)
  const [hoveredMsg, setHoveredMsg] = useState<string | null>(null)
  const [lightbox, setLightbox] = useState<string | null>(null)

  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const imgInputRef = useRef<HTMLInputElement>(null)

  const { data: conversations, isLoading: convsLoading } = useQuery<Conversation[]>({
    queryKey: ['conversations'],
    queryFn: () => api.get('/messages/conversations').then((r) => r.data),
    refetchInterval: () => document.hidden ? false : 5000,
  })

  const { data: thread } = useQuery<MessageItem[]>({
    queryKey: ['thread', otherUserId],
    queryFn: () => api.get(`/messages/conversation/${otherUserId}`).then((r) => r.data),
    enabled: !!otherUserId,
    refetchInterval: () => document.hidden ? false : 3000,
  })

  useEffect(() => {
    if (otherUserId) {
      api.patch(`/messages/read/${otherUserId}`).catch(() => null)
      qc.invalidateQueries({ queryKey: ['conversations'] })
    }
  }, [otherUserId, qc])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [thread])

  // Revoke blob URL when it changes or component unmounts to prevent memory leak
  useEffect(() => {
    return () => {
      if (imagePreview) URL.revokeObjectURL(imagePreview)
    }
  }, [imagePreview])

  // When user picks an image — upload immediately and store URL
  async function handleImagePick(file: File) {
    const MAX_SIZE = 5 * 1024 * 1024
    if (file.size > MAX_SIZE) { toast.error('Image must be under 5 MB'); return }
    if (!file.type.startsWith('image/')) { toast.error('Only image files are allowed'); return }

    setImageFile(file)
    setImagePreview(URL.createObjectURL(file))
    setUploadingImg(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const res = await api.post('/messages/upload-image', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setPendingImageUrl(res.data.image_url)
    } catch {
      toast.error('Image upload failed')
      clearImage()
    } finally {
      setUploadingImg(false)
    }
  }

  function clearImage() {
    setImageFile(null)
    setImagePreview(null)
    setPendingImageUrl(null)
    if (imgInputRef.current) imgInputRef.current.value = ''
  }

  const sendMutation = useMutation({
    mutationFn: (payload: { content: string; image_url?: string }) =>
      api.post('/messages', { to_user_id: otherUserId, ...payload }),
    onSuccess: () => {
      setDraft('')
      clearImage()
      if (textareaRef.current) {
        textareaRef.current.style.height = '22px'
        textareaRef.current.focus()
      }
      qc.invalidateQueries({ queryKey: ['thread', otherUserId] })
      qc.invalidateQueries({ queryKey: ['conversations'] })
    },
    onError: () => toast.error('Failed to send message'),
  })

  const deleteMutation = useMutation({
    mutationFn: (msgId: string) => api.delete(`/messages/${msgId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['thread', otherUserId] }),
    onError: () => toast.error('Failed to delete message'),
  })

  function handleSend() {
    const trimmed = draft.trim()
    if ((!trimmed && !pendingImageUrl) || sendMutation.isPending || uploadingImg) return
    sendMutation.mutate({ content: trimmed, image_url: pendingImageUrl ?? undefined })
  }

  const activeConv = conversations?.find((c) => c.other_user_id === otherUserId)
  const contactName = activeConv?.other_user_name ?? navName ?? null

  // Group messages by day
  const grouped: { label: string; msgs: MessageItem[] }[] = []
  if (thread) {
    for (const msg of thread) {
      const label = dayLabel(msg.created_at)
      const last = grouped[grouped.length - 1]
      if (last && last.label === label) last.msgs.push(msg)
      else grouped.push({ label, msgs: [msg] })
    }
  }

  return (
    <div className="h-screen bg-gray-50 flex flex-col overflow-hidden">
      {/* Lightbox */}
      {lightbox && (
        <div
          className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center"
          onClick={() => setLightbox(null)}
        >
          <button className="absolute top-4 right-4 text-white p-2 rounded-full hover:bg-white/10 transition-colors" onClick={() => setLightbox(null)}>
            <X className="h-6 w-6" />
          </button>
          <img src={lightbox} className="max-w-full max-h-full rounded-xl" alt="Full size" onClick={(e) => e.stopPropagation()} />
        </div>
      )}

      {/* Page header */}
      <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center gap-3 shrink-0 shadow-sm">
        <button
          onClick={() => (otherUserId ? navigate('/inbox') : navigate('/dashboard'))}
          className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500 hover:text-gray-700 transition-colors shrink-0"
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        {otherUserId && contactName ? (
          <div className="flex items-center gap-2.5 min-w-0">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-white text-sm font-bold shrink-0 ${avatarColor(contactName)}`}>
              {initial(contactName)}
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-gray-900 truncate leading-none">{contactName}</p>
              <p className="text-xs text-gray-400 mt-0.5">Direct message</p>
            </div>
          </div>
        ) : (
          <h1 className="text-sm font-semibold text-gray-900">{otherUserId ? 'Conversation' : 'Inbox'}</h1>
        )}
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside className={`border-r border-gray-200 bg-white flex flex-col shrink-0 ${otherUserId ? 'hidden md:flex md:w-72' : 'flex w-full md:w-72'}`}>
          <div className="px-4 py-3 border-b border-gray-100">
            <h2 className="text-xs font-bold text-gray-400 uppercase tracking-widest">Messages</h2>
          </div>
          <div className="flex-1 overflow-y-auto">
            {convsLoading && (
              <div className="space-y-1 p-2">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="flex items-center gap-3 p-3 rounded-xl animate-pulse">
                    <div className="w-10 h-10 rounded-full bg-gray-200 shrink-0" />
                    <div className="flex-1 space-y-1.5">
                      <div className="h-3.5 bg-gray-200 rounded w-1/2" />
                      <div className="h-3 bg-gray-100 rounded w-3/4" />
                    </div>
                  </div>
                ))}
              </div>
            )}
            {!convsLoading && (!conversations || conversations.length === 0) && (
              <div className="flex flex-col items-center justify-center h-full py-12 px-6 text-center">
                <div className="w-12 h-12 rounded-2xl bg-indigo-50 flex items-center justify-center mb-3">
                <MessageCircle className="h-6 w-6 text-indigo-400" />
              </div>
                <p className="text-sm font-medium text-gray-700">No conversations yet</p>
                <p className="text-xs text-gray-400 mt-1">Visit a profile to send the first message.</p>
              </div>
            )}
            <div className="p-2 space-y-0.5">
              {conversations?.map((conv) => {
                const isActive = conv.other_user_id === otherUserId
                return (
                  <button
                    key={conv.conversation_id}
                    onClick={() => navigate(`/inbox/${conv.other_user_id}`)}
                    className={`w-full p-3 flex items-center gap-3 text-left rounded-xl transition-colors ${isActive ? 'bg-indigo-50' : 'hover:bg-gray-50'}`}
                  >
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center text-white text-sm font-bold shrink-0 ${avatarColor(conv.other_user_name)}`}>
                      {initial(conv.other_user_name)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-1 mb-0.5">
                        <p className={`text-sm truncate ${conv.unread_count > 0 ? 'font-semibold text-gray-900' : 'font-medium text-gray-700'}`}>
                          {conv.other_user_name}
                        </p>
                        <span className="text-xs text-gray-400 shrink-0">{convTime(conv.last_message_at)}</span>
                      </div>
                      <div className="flex items-center justify-between gap-1">
                        <p className={`text-xs truncate ${conv.unread_count > 0 ? 'text-gray-700' : 'text-gray-400'}`}>
                          {conv.last_message}
                        </p>
                        {conv.unread_count > 0 && (
                          <span className="bg-indigo-600 text-white text-xs rounded-full min-w-4.5 h-4.5 flex items-center justify-center px-1 shrink-0 font-semibold">
                            {conv.unread_count}
                          </span>
                        )}
                      </div>
                    </div>
                  </button>
                )
              })}
            </div>
          </div>
        </aside>

        {/* Thread panel */}
        {otherUserId ? (
          <div className="flex-1 flex flex-col min-w-0">
            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-4 py-5 bg-gray-50">
              {thread?.length === 0 && (
                <div className="flex flex-col items-center justify-center h-full gap-3 py-16">
                  <div className={`w-14 h-14 rounded-2xl flex items-center justify-center text-white text-xl font-bold shadow-sm ${contactName ? avatarColor(contactName) : 'bg-indigo-400'}`}>
                    {contactName ? initial(contactName) : <MessageCircle className="h-6 w-6" />}
                  </div>
                  <div className="text-center">
                    <p className="text-sm font-semibold text-gray-700">
                      {contactName ? `Start a conversation with ${contactName}` : 'Start a conversation'}
                    </p>
                    <p className="text-xs text-gray-400 mt-1">Your messages will appear here.</p>
                  </div>
                </div>
              )}

              {grouped.map(({ label, msgs }) => (
                <div key={label} className="mb-2">
                  <div className="flex items-center gap-3 py-3">
                    <div className="flex-1 h-px bg-gray-200" />
                    <span className="text-xs text-gray-400 font-medium shrink-0">{label}</span>
                    <div className="flex-1 h-px bg-gray-200" />
                  </div>
                  <div className="space-y-1">
                    {msgs.map((msg, idx) => {
                      const isMe = msg.sender_id === user?.id
                      const isLastInGroup = !msgs[idx + 1] || msgs[idx + 1].sender_id !== msg.sender_id
                      const isHovered = hoveredMsg === msg.id

                      return (
                        <div
                          key={msg.id}
                          className={`flex items-end gap-2 group ${isMe ? 'flex-row-reverse' : 'flex-row'}`}
                          onMouseEnter={() => setHoveredMsg(msg.id)}
                          onMouseLeave={() => setHoveredMsg(null)}
                        >
                          {/* Avatar slot */}
                          <div className="w-7 shrink-0">
                            {!isMe && isLastInGroup && contactName && (
                              <div className={`w-7 h-7 rounded-full flex items-center justify-center text-white text-xs font-bold ${avatarColor(contactName)}`}>
                                {initial(contactName)}
                              </div>
                            )}
                          </div>

                          <div className={`flex flex-col max-w-xs md:max-w-md ${isMe ? 'items-end' : 'items-start'}`}>
                            {/* Deleted message */}
                            {msg.is_deleted ? (
                              <p className="text-xs text-gray-400 italic px-3 py-2">Message deleted</p>
                            ) : (
                              <>
                                {/* Image */}
                                {msg.image_url && (
                                  <img
                                    src={msg.image_url}
                                    alt="Shared image"
                                    className="max-w-55 rounded-xl mb-1 cursor-pointer hover:opacity-90 transition-opacity"
                                    onClick={() => setLightbox(msg.image_url!)}
                                  />
                                )}
                                {/* Text bubble */}
                                {msg.content && (
                                  <div className={`px-3.5 py-2.5 text-sm leading-relaxed animate-scale-in ${
                                    isMe
                                      ? 'bg-linear-to-br from-indigo-600 to-violet-600 text-white rounded-2xl rounded-br-md shadow-sm shadow-indigo-200/60'
                                      : 'bg-white border border-gray-200 text-gray-800 rounded-2xl rounded-bl-md shadow-sm'
                                  }`}>
                                    {msg.content}
                                  </div>
                                )}
                              </>
                            )}

                            {isLastInGroup && (
                              <div className={`flex items-center gap-2 mt-1 px-1 ${isMe ? 'flex-row-reverse' : ''}`}>
                                <p className="text-xs text-gray-400">
                                  {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                </p>
                                {/* Delete button — own messages only */}
                                {isMe && !msg.is_deleted && isHovered && (
                                  <button
                                    onClick={() => deleteMutation.mutate(msg.id)}
                                    className="text-gray-300 hover:text-red-400 transition-colors"
                                    title="Delete message"
                                  >
                                    <Trash2 className="h-3.5 w-3.5" />
                                  </button>
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              ))}
              <div ref={bottomRef} />
            </div>

            {/* Image preview strip */}
            {imagePreview && (
              <div className="bg-white border-t border-gray-100 px-4 pt-2 pb-1 flex items-center gap-3 shrink-0">
                <div className="relative">
                  <img src={imagePreview} alt="Preview" className="h-16 rounded-lg object-cover" />
                  {uploadingImg && (
                    <div className="absolute inset-0 bg-white/60 flex items-center justify-center rounded-lg">
                      <span className="text-xs text-gray-500">Uploading…</span>
                    </div>
                  )}
                  <button
                    onClick={clearImage}
                    className="absolute -top-1.5 -right-1.5 w-5 h-5 bg-gray-700 text-white rounded-full flex items-center justify-center hover:bg-red-500 transition-colors"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </div>
                <span className="text-xs text-gray-400">{imageFile?.name}</span>
              </div>
            )}

            {/* Compose bar */}
            <div className="bg-white border-t border-gray-200 px-4 py-3 shrink-0">
              <div className="flex items-end gap-2 bg-gray-50 rounded-2xl border border-gray-200 px-3 py-2 focus-within:border-indigo-400 focus-within:ring-2 focus-within:ring-indigo-100 transition-all">
                {/* Image attach button */}
                <button
                  type="button"
                  onClick={() => imgInputRef.current?.click()}
                  className="p-1.5 text-gray-400 hover:text-indigo-500 transition-colors shrink-0 mb-0.5"
                  title="Attach image"
                >
                  <ImageIcon className="w-4 h-4" />
                </button>
                <input
                  ref={imgInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/gif,image/webp"
                  className="hidden"
                  onChange={(e) => { const f = e.target.files?.[0]; if (f) handleImagePick(f) }}
                />

                <textarea
                  ref={textareaRef}
                  value={draft}
                  onChange={(e) => {
                    setDraft(e.target.value)
                    e.target.style.height = 'auto'
                    e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px'
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      handleSend()
                    }
                  }}
                  placeholder={imagePreview ? 'Add a caption…' : 'Type a message… (Enter to send)'}
                  rows={1}
                  className="flex-1 resize-none bg-transparent text-sm text-gray-800 placeholder-gray-400 focus:outline-none py-0.5 max-h-30"
                  style={{ height: '22px' }}
                />
                <button
                  onClick={handleSend}
                  disabled={(!draft.trim() && !pendingImageUrl) || sendMutation.isPending || uploadingImg}
                  className="p-1.5 rounded-xl bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shrink-0 mb-0.5"
                  title="Send"
                >
                  <SendHorizonal className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="hidden md:flex flex-1 flex-col items-center justify-center bg-gray-50 gap-4">
            <div className="w-16 h-16 rounded-3xl bg-white border border-gray-200 flex items-center justify-center shadow-sm">
              <MessageCircle className="h-7 w-7 text-indigo-400" />
            </div>
            <div className="text-center">
              <p className="text-sm font-semibold text-gray-700">Select a conversation</p>
              <p className="text-xs text-gray-400 mt-1">Choose from your messages to start chatting.</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
