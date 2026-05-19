# HireCred-v1 — Build Roadmap & Status

**Last updated: 2026-05-18**  
**Stack:** React + Vite + TypeScript | Python + FastAPI | Neon PostgreSQL | Ollama (qwen2.5:3b local LLM)

---

## Phase 1 — Core Platform (DONE)

- [x] Auth: register / login / JWT / roles (candidate | client)
- [x] Profile CRUD: bio, title, location, skills, experience, portfolio
- [x] Proof signals: GitHub links, screenshots, client references, portfolio links
- [x] Messaging: conversation threads with image attachments, soft-delete
- [x] Appreciation: freeform → AI-structured ratings (skill / comm / reliability)
- [x] HireCred Score: Ollama LLM scoring (0–100) with rule-based fallback
- [x] Fraud detection: AI analysis of appreciation patterns
- [x] Intent-based search: 3-tier Ollama query parser + ranking formula
- [x] Trust Leaderboard: ranked by score + appreciations + proof signals

---

## Phase 2 — AI Upgrade (DONE)

- [x] Switch from Gemini API to local Ollama (qwen2.5:3b, 8k context)
- [x] CV upload (PDF only — file stored, presence used as scoring signal)
- [x] Non-blocking validation: profile saves never return 422; issues become score warnings
- [x] Background scoring: all score computation via `asyncio.create_task()` — HTTP responses return instantly
- [x] Manual score refresh: `POST /api/profile/{id}/rescore` endpoint + Refresh button in ScoreWidget

---

## Phase 3 — Authenticity & Trust (DONE)

- [x] 16-point authenticity heuristic detector:
  - Suspicious name, disposable email, bio boilerplate
  - Sci-fi/fantasy content (alien companies, intergalactic markets, holographic billboards)
  - Fictional location (Mars Colony, Moon Base, planet names, Sector numbers)
  - Absurd professional title (Ultra Creative Pixel Wizard, Supreme Overlord)
  - Impossible numeric claims (999 years of experience, 5000% on Jupiter)
  - Far-future experience dates (year > current+2 e.g. 3018, 3020)
  - Fictional company names (Galaxy Banana Corp, Moonlight Sandwich Studio)
  - Joke/non-professional skills (Coffee Drinking, Meme Design, Fake Skill 101)
  - Duplicate experience descriptions, same-domain portfolio, identical descriptions
  - Large/generic skill list, tech title with no tech skills
- [x] Hard score ceiling: risk_level=high → max 15 pts; medium+penalty≥20 → max 35 pts
- [x] Penalty cap raised: 50 → 60 pts
- [x] URL dead-link detection: HEAD + GET + page title extraction (4s timeout)
- [x] `is_suspicious` flag on CredibilityScore with "⚠ Suspicious" badge on profile
- [x] Authenticity flags and URL warnings shown in ScoreWidget
- [x] Report Account: authenticated users can report any profile
- [x] Admin Panel (`/admin`): list/approve/reject reports; approve → suspicious + −12 score
- [x] Admin user management: all users table, promote/demote admin role
- [x] Dedicated admin login at `/admin/login`

---

## Phase 4 — Polish & UX (DONE)

- [x] Professional icons throughout: lucide-react in Login, Register, Leaderboard, Inbox, ProfileView
- [x] Skills tag input: removed validation warnings (no more "not in skills list" messages)
- [x] Portfolio "Tech Stack" label renamed to "Skills"
- [x] Browser native password eye icon suppressed (CSS `::-ms-reveal` + `::-webkit-credentials-auto-fill-button`)
- [x] DB connection pool: `pool_pre_ping=True` + `pool_recycle=1800` (fixes connection closed errors)
- [x] Ollama timeout: set to 120s (qwen2.5:3b on CPU needs 65–200s for 200-token output; 120s gives the model time while still falling back if truly hung)
- [x] URL checker timeout: 8s → 4s
- [x] pdfplumber installed (was missing from venv despite being in requirements.txt)
- [x] CV analysis pipeline removed: upload stores file only; no pdfplumber extraction, no Ollama CV analysis, no CV↔profile match

---

## Phase 5 — Planned (Not Yet Started)

### 5.1 OAuth Proof Verification
- [ ] GitHub OAuth: verify ownership of GitHub account linked in proof signals
- [ ] Create-a-file proof of possession for custom portfolio domains

### 5.2 Duplicate Detection (Cross-Profile)
- [ ] Bio similarity fingerprinting across all profiles (difflib or embeddings)
- [ ] Flag copy-pasted bios from other users

### 5.3 Score Transparency
- [ ] Score breakdown UI: show per-criterion scores (completeness/alignment/portfolio/etc.)
- [ ] Score history chart (track improvement over time)

### 5.4 Hirer Features
- [ ] Saved candidates list
- [ ] Hirer-side review/rating of candidates post-hire
- [ ] Advanced search filters (experience level, location, score range)

### 5.5 Notifications
- [ ] In-app notifications: new appreciation, new message, score change
- [ ] Email digest (weekly summary)

---

## DB Migration History

| Migration ID | Change |
|-------------|--------|
| `4a99fc87d523` | Initial schema (users, profiles, proof_signals, appreciations, messages, credibility_scores) |
| `b2c3d4e5f678` | Add uid auto-sequence to users |
| `c3d4e5f6a789` | Fix uid sequence |
| `d4e5f6a7b890` | Add cv_file_path and cv_analysis to profiles |
| `e5f6a7b8c901` | Add image_path and is_deleted to messages |
| `f6g7h8i9j012` | Add is_admin to users; add is_suspicious, cv_match_*, url_warnings to credibility_scores; add account_reports table |
