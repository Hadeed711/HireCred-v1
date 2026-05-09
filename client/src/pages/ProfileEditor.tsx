import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import api from '../lib/api'
import { useAuthStore } from '../stores/authStore'
import SkillsTagInput from '../components/SkillsTagInput'
import ValidationWarningBanner from '../components/validation/ValidationWarningBanner'
import type { Profile, ExperienceItem, PortfolioItem, ProofSignal, SignalType } from '../lib/types'
import { nanoid } from '../lib/nanoid'
import {
  validateBio,
  validateUrl,
  validateExperienceDescription,
  findDuplicateExperience,
  findDuplicatePortfolioUrl,
  deduplicateSkills,
  validateProfileForSave,
} from '../lib/validators'

// ── helpers ──────────────────────────────────────────────────────────────────

const SIGNAL_LABELS: Record<SignalType, string> = {
  github: 'GitHub / Project Link',
  portfolio_link: 'Portfolio Link',
  client_reference: 'Client Reference',
  screenshot: 'Work Screenshot',
}

const SIGNAL_ICONS: Record<SignalType, string> = {
  github: '🔗',
  portfolio_link: '🌐',
  client_reference: '💬',
  screenshot: '🖼️',
}

// ── ExperienceForm ────────────────────────────────────────────────────────────

function ExperienceForm({
  item,
  index,
  allEntries,
  onChange,
  onRemove,
}: {
  item: ExperienceItem
  index: number
  allEntries: ExperienceItem[]
  onChange: (item: ExperienceItem) => void
  onRemove: () => void
}) {
  const thisMonth = new Date().toISOString().slice(0, 7)

  function field(key: keyof ExperienceItem) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      onChange({ ...item, [key]: e.target.value })
  }

  const startIsFuture = item.start_date && item.start_date > thisMonth
  const endIsFuture = !item.current && item.end_date && item.end_date > thisMonth
  const endBeforeStart = !item.current && item.start_date && item.end_date && item.end_date < item.start_date
  const descErr = validateExperienceDescription(item.description)
  const dupErr = item.company ? findDuplicateExperience(allEntries, index) : null

  return (
    <div className={`border rounded-xl p-4 space-y-3 bg-gray-50 ${dupErr ? 'border-red-300' : 'border-gray-200'}`}>
      {dupErr && <p className="text-xs text-red-600 font-medium">{dupErr}</p>}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label">Job Title</label>
          <input className="input" value={item.title} onChange={field('title')} placeholder="e.g. Senior Developer" />
        </div>
        <div>
          <label className="label">Company</label>
          <input className="input" value={item.company} onChange={field('company')} placeholder="e.g. Acme Corp" />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label">Start Date</label>
          <input
            className={`input ${startIsFuture ? 'border-amber-400' : ''}`}
            type="month"
            value={item.start_date}
            onChange={field('start_date')}
          />
          {startIsFuture && <p className="text-xs text-amber-600 mt-1">Start date is in the future</p>}
        </div>
        <div>
          <label className="label">End Date</label>
          <input
            className={`input ${endIsFuture || endBeforeStart ? 'border-amber-400' : ''}`}
            type="month"
            value={item.end_date ?? ''}
            onChange={field('end_date')}
            disabled={item.current}
          />
          {endIsFuture && <p className="text-xs text-amber-600 mt-1">End date is in the future</p>}
          {endBeforeStart && !endIsFuture && <p className="text-xs text-amber-600 mt-1">End date is before start date</p>}
          <label className="flex items-center gap-2 mt-1 text-sm text-gray-500 cursor-pointer">
            <input
              type="checkbox"
              checked={item.current}
              onChange={(e) => onChange({ ...item, current: e.target.checked, end_date: null })}
            />
            Current role
          </label>
        </div>
      </div>
      <div>
        <label className="label">Description</label>
        <textarea
          className={`input resize-none ${descErr ? 'border-amber-400' : ''}`}
          rows={2}
          value={item.description}
          onChange={field('description')}
          placeholder="What did you build / achieve? (min 40 chars if provided)"
        />
        {descErr && <p className="text-xs text-amber-600 mt-1">{descErr}</p>}
      </div>
      <button type="button" onClick={onRemove} className="text-red-500 text-sm hover:underline">
        Remove
      </button>
    </div>
  )
}

// ── PortfolioForm ─────────────────────────────────────────────────────────────

function PortfolioForm({
  item,
  index,
  allItems,
  onChange,
  onRemove,
}: {
  item: PortfolioItem
  index: number
  allItems: PortfolioItem[]
  onChange: (item: PortfolioItem) => void
  onRemove: () => void
}) {
  function field(key: keyof PortfolioItem) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      onChange({ ...item, [key]: e.target.value })
  }

  const urlErr = item.url ? validateUrl(item.url) : null
  const dupErr = item.url ? findDuplicatePortfolioUrl(allItems, index) : null
  const hasErr = urlErr || dupErr

  return (
    <div className={`border rounded-xl p-4 space-y-3 bg-gray-50 ${hasErr ? 'border-red-300' : 'border-gray-200'}`}>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label">Project Name</label>
          <input className="input" value={item.title} onChange={field('title')} placeholder="e.g. E-commerce App" />
        </div>
        <div>
          <label className="label">URL</label>
          <input
            className={`input ${hasErr ? 'border-red-300 focus:ring-red-300' : ''}`}
            value={item.url}
            onChange={field('url')}
            placeholder="https://..."
          />
          {urlErr && <p className="text-xs text-red-600 mt-1">{urlErr}</p>}
          {dupErr && <p className="text-xs text-red-600 mt-1">{dupErr}</p>}
        </div>
      </div>
      <div>
        <label className="label">Description</label>
        <textarea
          className="input resize-none"
          rows={2}
          value={item.description}
          onChange={field('description')}
          placeholder="What problem does it solve?"
        />
      </div>
      <div>
        <label className="label">Tech Stack</label>
        <SkillsTagInput
          skills={item.tech_stack}
          onChange={(tags) => onChange({ ...item, tech_stack: tags })}
        />
      </div>
      <button type="button" onClick={onRemove} className="text-red-500 text-sm hover:underline">
        Remove
      </button>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function ProfileEditor() {
  const { user } = useAuthStore()
  const navigate = useNavigate()
  const qc = useQueryClient()

  const { data: profile, isLoading } = useQuery<Profile>({
    queryKey: ['profile', user?.id],
    queryFn: () => api.get(`/profile/${user?.id}`).then((r) => r.data),
    enabled: !!user?.id,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  })

  // form state
  const [bio, setBio] = useState('')
  const [title, setTitle] = useState('')
  const [location, setLocation] = useState('')
  const [skills, setSkills] = useState<string[]>([])
  const [experience, setExperience] = useState<ExperienceItem[]>([])
  const [portfolio, setPortfolio] = useState<PortfolioItem[]>([])

  // validation state
  const [warningCount, setWarningCount] = useState(0)
  const [activeWarnings, setActiveWarnings] = useState<string[]>([])

  // proof signal state
  const [signalType, setSignalType] = useState<SignalType>('github')
  const [signalTitle, setSignalTitle] = useState('')
  const [signalUrl, setSignalUrl] = useState('')
  const [signalDesc, setSignalDesc] = useState('')
  const [signalFile, setSignalFile] = useState<File | null>(null)
  const [addingSignal, setAddingSignal] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  // CV upload state
  const [cvFile, setCvFile] = useState<File | null>(null)
  const [cvUploading, setCvUploading] = useState(false)
  const cvRef = useRef<HTMLInputElement>(null)

  const hasInitialized = useRef(false)

  useEffect(() => {
    if (profile && !hasInitialized.current) {
      hasInitialized.current = true
      setBio(profile.bio ?? '')
      setTitle(profile.title ?? '')
      setLocation(profile.location ?? '')
      setSkills(profile.skills ?? [])
      setExperience((profile.experience as ExperienceItem[]) ?? [])
      setPortfolio((profile.portfolio as PortfolioItem[]) ?? [])
    }
  }, [profile])

  const saveMutation = useMutation({
    mutationFn: (data: object) => api.put(`/profile/${user?.id}`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['profile', user?.id] })
      setActiveWarnings([])
      toast.success('Profile saved!')
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      if (msg) {
        const newCount = warningCount + 1
        setWarningCount(newCount)
        setActiveWarnings([msg])
        toast.error('Fix the issue before saving')
      } else {
        toast.error('Failed to save profile')
      }
    },
  })

  const deleteSignalMutation = useMutation({
    mutationFn: (signalId: string) => api.delete(`/profile/${user?.id}/signals/${signalId}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['profile', user?.id] })
      toast.success('Signal removed')
    },
    onError: () => toast.error('Failed to remove signal'),
  })

  function handleSkillsChange(newSkills: string[]) {
    setSkills(deduplicateSkills(newSkills))
  }

  function handleSave() {
    // Client-side validation
    const errors = validateProfileForSave({ bio, title, experience, portfolio, skills })
    if (errors.length > 0) {
      const newCount = warningCount + 1
      setWarningCount(newCount)
      setActiveWarnings(errors.map((e) => e.message))
      return
    }
    setActiveWarnings([])
    saveMutation.mutate({ bio, title, location, skills, experience, portfolio })
  }

  async function handleAddSignal() {
    if (!signalTitle.trim()) { toast.error('Title is required'); return }

    // Validate URL for non-screenshot signals
    if (signalType !== 'screenshot' && signalUrl) {
      const urlErr = validateUrl(signalUrl)
      if (urlErr) {
        toast.error(urlErr)
        return
      }
    }

    setAddingSignal(true)
    try {
      if (signalType === 'screenshot' && signalFile) {
        const fd = new FormData()
        fd.append('title', signalTitle)
        fd.append('description', signalDesc)
        fd.append('file', signalFile)
        await api.post(`/profile/${user?.id}/signals/upload`, fd, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
      } else {
        await api.post(`/profile/${user?.id}/signals`, {
          signal_type: signalType,
          title: signalTitle,
          url: signalUrl || null,
          description: signalDesc || null,
        })
      }
      qc.invalidateQueries({ queryKey: ['profile', user?.id] })
      toast.success('Proof signal added!')
      setSignalTitle(''); setSignalUrl(''); setSignalDesc(''); setSignalFile(null)
      if (fileRef.current) fileRef.current.value = ''
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(msg || 'Failed to add signal')
    } finally {
      setAddingSignal(false)
    }
  }

  async function handleCvRemove() {
    try {
      await api.delete(`/profile/${user?.id}/cv`)
      qc.invalidateQueries({ queryKey: ['profile', user?.id] })
      toast.success('CV removed')
    } catch {
      toast.error('Failed to remove CV')
    }
  }

  async function handleCvUpload() {
    if (!cvFile) return
    setCvUploading(true)
    try {
      const fd = new FormData()
      fd.append('file', cvFile)
      await api.post(`/profile/${user?.id}/cv`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      qc.invalidateQueries({ queryKey: ['profile', user?.id] })
      setCvFile(null)
      if (cvRef.current) cvRef.current.value = ''
      toast.success('CV uploaded and analyzed!')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      const newCount = warningCount + 1
      setWarningCount(newCount)
      setActiveWarnings([msg || 'CV upload failed — ensure it is a real, complete CV.'])
      toast.error(msg || 'CV upload failed')
    } finally {
      setCvUploading(false)
    }
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-400 text-sm">Loading profile…</div>
      </div>
    )
  }

  // Completion heuristic
  const completionPoints = [
    !!bio.trim(),
    !!title.trim(),
    !!location.trim(),
    skills.length >= 2,
    experience.length >= 1,
    portfolio.length >= 1,
    (profile?.proof_signals?.length ?? 0) >= 1,
    !!profile?.cv_url,
  ]
  const completionPct = Math.round((completionPoints.filter(Boolean).length / completionPoints.length) * 100)
  const completionColor = completionPct >= 80 ? 'bg-emerald-500' : completionPct >= 50 ? 'bg-amber-400' : 'bg-red-400'

  const saveBlocked = warningCount >= 2 && activeWarnings.length > 0

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Sticky header */}
      <header className="bg-white/90 backdrop-blur border-b border-gray-200 px-6 py-3.5 flex items-center justify-between sticky top-0 z-10 shadow-sm">
        <button onClick={() => navigate('/dashboard')} className="text-sm text-gray-500 hover:text-gray-700 flex items-center gap-1.5 hover:bg-gray-100 px-2 py-1.5 rounded-lg transition-colors">
          ← Dashboard
        </button>
        <div className="hidden sm:flex items-center gap-3">
          <div className="w-32 h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div className={`h-full rounded-full transition-all duration-500 ${completionColor}`} style={{ width: `${completionPct}%` }} />
          </div>
          <span className="text-xs font-medium text-gray-500">{completionPct}% complete</span>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => navigate(`/profile/${user?.uid ?? user?.id}`)}
            className="text-sm px-3 py-1.5 border border-gray-200 rounded-xl hover:bg-gray-50 transition-colors text-gray-600"
          >
            Preview
          </button>
          <button
            onClick={handleSave}
            disabled={saveMutation.isPending || saveBlocked}
            title={saveBlocked ? 'Fix all issues before saving' : undefined}
            className="text-sm px-4 py-1.5 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 disabled:opacity-50 transition-colors font-medium shadow-sm shadow-indigo-200"
          >
            {saveMutation.isPending ? (
              <span className="flex items-center gap-1.5">
                <svg className="animate-spin h-3.5 w-3.5" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Saving…
              </span>
            ) : saveBlocked ? '🚫 Fix Issues' : 'Save changes'}
          </button>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-8 space-y-6">

        {/* Validation warning banner */}
        <ValidationWarningBanner warnings={activeWarnings} warningCount={warningCount} />

        {/* Basic Info */}
        <Section title="Basic Info">
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Professional Title</label>
                <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Full-Stack Developer" />
              </div>
              <div>
                <label className="label">Location</label>
                <input className="input" value={location} onChange={(e) => setLocation(e.target.value)} placeholder="e.g. London, UK" />
              </div>
            </div>
            <div>
              <label className="label">Bio</label>
              <textarea
                className={`input resize-none ${bio.trim() && validateBio(bio) ? 'border-amber-400' : ''}`}
                rows={4}
                value={bio}
                onChange={(e) => setBio(e.target.value)}
                placeholder="Tell hiring clients about yourself, your expertise, and what makes you different… (min 80 characters)"
              />
              {bio.trim() && validateBio(bio) && (
                <p className="text-xs text-amber-600 mt-1">{validateBio(bio)}</p>
              )}
            </div>
          </div>
        </Section>

        {/* Skills */}
        <Section title="Skills">
          <SkillsTagInput skills={skills} onChange={handleSkillsChange} />
          <p className="mt-1.5 text-xs text-gray-400">Press Enter or comma to add. Duplicates are removed automatically.</p>
        </Section>

        {/* Experience */}
        <Section
          title="Experience"
          action={
            <button
              type="button"
              onClick={() => setExperience([...experience, { id: nanoid(), title: '', company: '', start_date: '', end_date: null, current: false, description: '' }])}
              className="text-sm text-indigo-600 hover:underline"
            >
              + Add
            </button>
          }
        >
          {experience.length === 0 && <p className="text-sm text-gray-400">No experience added yet.</p>}
          <div className="space-y-3">
            {experience.map((exp, i) => (
              <ExperienceForm
                key={exp.id}
                item={exp}
                index={i}
                allEntries={experience}
                onChange={(updated) => setExperience(experience.map((e, j) => (j === i ? updated : e)))}
                onRemove={() => setExperience(experience.filter((_, j) => j !== i))}
              />
            ))}
          </div>
        </Section>

        {/* Portfolio */}
        <Section
          title="Portfolio"
          action={
            <button
              type="button"
              onClick={() => setPortfolio([...portfolio, { id: nanoid(), title: '', description: '', url: '', tech_stack: [] }])}
              className="text-sm text-indigo-600 hover:underline"
            >
              + Add
            </button>
          }
        >
          {portfolio.length === 0 && <p className="text-sm text-gray-400">No portfolio items yet.</p>}
          <div className="space-y-3">
            {portfolio.map((item, i) => (
              <PortfolioForm
                key={item.id}
                item={item}
                index={i}
                allItems={portfolio}
                onChange={(updated) => setPortfolio(portfolio.map((p, j) => (j === i ? updated : p)))}
                onRemove={() => setPortfolio(portfolio.filter((_, j) => j !== i))}
              />
            ))}
          </div>
        </Section>

        {/* CV Upload */}
        <Section title="CV / Resume">
          <p className="text-sm text-gray-500 mb-4">
            Upload your CV to help hirers review your full background. Accepted formats: PDF, DOCX (max 5 MB).
            The CV is analyzed by AI and must be a real, complete document.
          </p>

          {profile?.cv_url && (
            <div className="flex items-center gap-3 p-3 bg-emerald-50 border border-emerald-200 rounded-xl mb-4">
              <span className="text-emerald-600 text-lg">✓</span>
              <div className="flex-1">
                <p className="text-sm font-medium text-emerald-800">CV uploaded</p>
                {profile.cv_analysis?.experience_summary && (
                  <p className="text-xs text-emerald-600 mt-0.5">{profile.cv_analysis.experience_summary}</p>
                )}
              </div>
              <a
                href={profile.cv_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs px-3 py-1 bg-emerald-100 text-emerald-700 rounded-lg hover:bg-emerald-200 transition-colors font-medium"
              >
                View CV
              </a>
              <button
                type="button"
                onClick={handleCvRemove}
                title="Remove CV"
                className="w-6 h-6 flex items-center justify-center rounded-full text-emerald-400 hover:text-red-500 hover:bg-red-50 transition-colors text-base font-bold leading-none"
              >
                ×
              </button>
            </div>
          )}

          <div className="border border-dashed border-gray-300 rounded-xl p-4 bg-white space-y-3">
            <div>
              <label className="label">{profile?.cv_url ? 'Replace CV' : 'Upload CV'}</label>
              <input
                ref={cvRef}
                type="file"
                accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                onChange={(e) => setCvFile(e.target.files?.[0] ?? null)}
                className="input text-sm"
              />
            </div>
            {cvFile && (
              <button
                type="button"
                onClick={handleCvUpload}
                disabled={cvUploading}
                className="text-sm px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
              >
                {cvUploading ? 'Uploading & analyzing…' : 'Upload CV'}
              </button>
            )}
          </div>
        </Section>

        {/* Proof Signals */}
        <Section title="Proof Signals">
          <p className="text-sm text-gray-500 mb-4">
            Proof signals verify your claims. Add GitHub links, portfolio links, client references, or work screenshots.
            Only real, working URLs are accepted.
          </p>

          {profile?.proof_signals && profile.proof_signals.length > 0 && (
            <div className="space-y-2 mb-6">
              {profile.proof_signals.map((s: ProofSignal) => (
                <div key={s.id} className="flex items-start justify-between p-3 bg-white border border-gray-200 rounded-lg">
                  <div className="flex items-start gap-3">
                    <span className="text-xl mt-0.5">{SIGNAL_ICONS[s.signal_type]}</span>
                    <div>
                      <p className="text-sm font-medium text-gray-800">{s.title}</p>
                      <p className="text-xs text-gray-400 capitalize">{SIGNAL_LABELS[s.signal_type]}</p>
                      {s.url && (
                        <a href={s.url} target="_blank" rel="noopener noreferrer" className="text-xs text-indigo-500 hover:underline break-all">
                          {s.url}
                        </a>
                      )}
                      {s.file_path && (
                        <a href={`/uploads/${s.file_path}`} target="_blank" rel="noopener noreferrer" className="text-xs text-indigo-500 hover:underline">
                          View file
                        </a>
                      )}
                      {s.description && <p className="text-xs text-gray-500 mt-0.5">{s.description}</p>}
                    </div>
                  </div>
                  <button
                    onClick={() => deleteSignalMutation.mutate(s.id)}
                    className="text-gray-300 hover:text-red-400 text-lg leading-none ml-2 shrink-0"
                    title="Remove"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}

          <div className="border border-dashed border-gray-300 rounded-xl p-4 space-y-3 bg-white">
            <p className="text-sm font-medium text-gray-700">Add a new proof signal</p>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label">Type</label>
                <select className="input" value={signalType} onChange={(e) => setSignalType(e.target.value as SignalType)}>
                  {(Object.keys(SIGNAL_LABELS) as SignalType[]).map((t) => (
                    <option key={t} value={t}>{SIGNAL_LABELS[t]}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">Title</label>
                <input className="input" value={signalTitle} onChange={(e) => setSignalTitle(e.target.value)} placeholder="e.g. My GitHub Profile" />
              </div>
            </div>

            {signalType === 'screenshot' ? (
              <div>
                <label className="label">Upload File (image or PDF, max 5 MB)</label>
                <input
                  ref={fileRef}
                  type="file"
                  accept="image/*,application/pdf"
                  onChange={(e) => setSignalFile(e.target.files?.[0] ?? null)}
                  className="input text-sm"
                />
              </div>
            ) : (
              <div>
                <label className="label">URL</label>
                <input
                  className={`input ${signalUrl && validateUrl(signalUrl) ? 'border-red-300' : ''}`}
                  value={signalUrl}
                  onChange={(e) => setSignalUrl(e.target.value)}
                  placeholder="https://..."
                />
                {signalUrl && validateUrl(signalUrl) && (
                  <p className="text-xs text-red-600 mt-1">{validateUrl(signalUrl)}</p>
                )}
              </div>
            )}

            <div>
              <label className="label">Description (optional)</label>
              <input className="input" value={signalDesc} onChange={(e) => setSignalDesc(e.target.value)} placeholder="Brief context…" />
            </div>

            <button
              type="button"
              onClick={handleAddSignal}
              disabled={addingSignal}
              className="text-sm px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
            >
              {addingSignal ? 'Adding…' : 'Add signal'}
            </button>
          </div>
        </Section>

      </main>
    </div>
  )
}

// ── Section wrapper ───────────────────────────────────────────────────────────

function Section({ title, children, action }: { title: string; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-base font-semibold text-gray-900">{title}</h2>
        {action}
      </div>
      {children}
    </div>
  )
}
