export type SignalType = 'github' | 'screenshot' | 'client_reference' | 'portfolio_link'

export interface ProofSignal {
  id: string
  signal_type: SignalType
  title: string
  url: string | null
  description: string | null
  file_path: string | null
  created_at: string
}

export interface ExperienceItem {
  id: string
  title: string
  company: string
  start_date: string
  end_date: string | null
  current: boolean
  description: string
}

export interface PortfolioItem {
  id: string
  title: string
  description: string
  url: string
  tech_stack: string[]
}

export interface AppreciationItem {
  id: string
  from_user_id: string
  from_user_name: string
  raw_feedback: string
  skill_rating: number
  communication_rating: number
  reliability_rating: number
  summary: string
  created_at: string
}

export interface AppreciationAggregates {
  count: number
  avg_skill: number
  avg_communication: number
  avg_reliability: number
  items: AppreciationItem[]
}

export interface CredibilityScore {
  score: number
  strengths: string[]
  risks: string[]
  fraud_risk: 'low' | 'medium' | 'high'
  computed_at: string
}

export interface CvAnalysis {
  extracted_skills: string[]
  experience_summary: string
  is_authentic: boolean
  rejection_reason: string
}

export interface Profile {
  id: string
  user_id: string
  bio: string | null
  title: string | null
  location: string | null
  skills: string[]
  experience: ExperienceItem[]
  portfolio: PortfolioItem[]
  profile_views: number
  avatar_url: string | null
  cv_url: string | null
  cv_analysis: CvAnalysis | null
  proof_signals: ProofSignal[]
  created_at: string
  updated_at: string
  owner_name: string
  owner_email: string
  owner_role: string
  owner_uid: number | null
}
