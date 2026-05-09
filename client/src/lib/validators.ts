export interface ValidationError {
  field: string
  message: string
}

// Domains that are obviously fake/placeholder
const BLOCKED_DOMAINS = new Set([
  'example.com', 'example.org', 'example.net',
  'test.com', 'test.org', 'test.net',
  'placeholder.com', 'yoursite.com', 'mywebsite.com',
  'website.com', 'domain.com', 'sample.com',
  'foo.bar', 'tempurl.com', 'dummysite.com',
  'fakesite.com', 'abc.com', 'xyz.com',
  'localhost', '127.0.0.1', '0.0.0.0',
])

const PLACEHOLDER_BIO_PHRASES = [
  'lorem ipsum', 'write your bio here', 'about me section',
  'experienced professional', 'i am a professional', 'insert bio',
  'your bio here', 'add your description', 'click to edit',
]

export function validateUrl(url: string): string | null {
  if (!url) return null
  const trimmed = url.trim()
  if (!trimmed.startsWith('http://') && !trimmed.startsWith('https://')) {
    return 'URL must start with http:// or https://'
  }
  try {
    const parsed = new URL(trimmed)
    const host = parsed.hostname.toLowerCase()
    // check exact match and subdomain match
    for (const blocked of BLOCKED_DOMAINS) {
      if (host === blocked || host.endsWith('.' + blocked)) {
        return `"${host}" is not a valid real URL. Please use your actual project or profile link.`
      }
    }
  } catch {
    return 'Invalid URL format.'
  }
  return null
}

export function validateBio(bio: string): string | null {
  const trimmed = bio.trim()
  if (trimmed.length < 80) {
    return `Bio must be at least 80 characters (currently ${trimmed.length}).`
  }
  const lower = trimmed.toLowerCase()
  for (const phrase of PLACEHOLDER_BIO_PHRASES) {
    if (lower.includes(phrase)) {
      return `Bio contains placeholder text ("${phrase}"). Please write about your real background.`
    }
  }
  return null
}

export function validateExperienceDescription(desc: string): string | null {
  if (desc.trim().length > 0 && desc.trim().length < 40) {
    return 'Experience description must be at least 40 characters or left empty.'
  }
  return null
}

export function findDuplicateExperience(
  entries: { company: string; start_date: string; end_date: string | null; current: boolean }[],
  currentIndex: number
): string | null {
  const current = entries[currentIndex]
  if (!current.company) return null
  for (let i = 0; i < entries.length; i++) {
    if (i === currentIndex) continue
    const other = entries[i]
    if (other.company.trim().toLowerCase() === current.company.trim().toLowerCase()) {
      // Check for overlapping date ranges
      const cStart = current.start_date
      const cEnd = current.current ? '9999-99' : (current.end_date ?? '9999-99')
      const oStart = other.start_date
      const oEnd = other.current ? '9999-99' : (other.end_date ?? '9999-99')
      if (cStart <= oEnd && oStart <= cEnd) {
        return `Duplicate entry: you already have overlapping experience at "${current.company}".`
      }
    }
  }
  return null
}

export function findDuplicatePortfolioUrl(
  items: { url: string }[],
  currentIndex: number
): string | null {
  const url = items[currentIndex]?.url?.trim()
  if (!url) return null
  for (let i = 0; i < items.length; i++) {
    if (i === currentIndex) continue
    if (items[i].url?.trim() === url) {
      return 'This portfolio URL is already listed.'
    }
  }
  return null
}

export function deduplicateSkills(skills: string[]): string[] {
  const seen = new Set<string>()
  return skills.filter((s) => {
    const key = s.trim().toLowerCase()
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

// Run all validations for the full profile save; returns list of errors
export function validateProfileForSave(data: {
  bio: string
  title: string
  experience: { company: string; start_date: string; end_date: string | null; current: boolean; description: string }[]
  portfolio: { url: string; title: string }[]
  skills: string[]
}): ValidationError[] {
  const errors: ValidationError[] = []

  if (data.bio.trim()) {
    const bioErr = validateBio(data.bio)
    if (bioErr) errors.push({ field: 'bio', message: bioErr })
  }

  data.experience.forEach((exp, i) => {
    const descErr = validateExperienceDescription(exp.description)
    if (descErr) errors.push({ field: `experience[${i}].description`, message: descErr })
    const dupErr = findDuplicateExperience(data.experience, i)
    if (dupErr) errors.push({ field: `experience[${i}]`, message: dupErr })
  })

  data.portfolio.forEach((item, i) => {
    if (item.url) {
      const urlErr = validateUrl(item.url)
      if (urlErr) errors.push({ field: `portfolio[${i}].url`, message: urlErr })
    }
    const dupErr = findDuplicatePortfolioUrl(data.portfolio, i)
    if (dupErr) errors.push({ field: `portfolio[${i}].url`, message: dupErr })
  })

  return errors
}
