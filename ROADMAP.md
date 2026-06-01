# HireCred-v1 — Build Roadmap & Status

**Last updated: 2026-06-01**  
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

## Phase 5 — Production Hardening (DONE — 2026-05-23)

### Search (Scalable to 1M+ profiles)
- [x] Replaced full-table Python scan with PostgreSQL full-text search (stored `search_tsv` tsvector column + plain GIN index; kept current by a DB trigger)
- [x] Added `pg_trgm` extension for typo-tolerant fuzzy fallback (trigram GIN index on `title`)
- [x] Three-stage SQL search chain: FTS → trigram fuzzy → ILIKE (each with hard LIMIT)
- [x] Never loads more than 200 rows into Python; all filtering happens in the database
- [x] Removed "return all candidates" last-resort fallback — returns empty + message instead
- [x] New Alembic migrations: `a1b2c3d4e5f6` (indexes), `b3c4d5e6f7a8` (pg_trgm + stored tsvector column + trigger + GIN indexes)

### Database Indexes (Critical missing FKs)
- [x] `appreciations.to_user_id` — was causing full table scan on every leaderboard + search ranking
- [x] `appreciations.from_user_id`
- [x] `credibility_scores.score` — leaderboard ORDER BY was a full scan
- [x] `credibility_scores.is_suspicious` — admin query speed
- [x] `proof_signals.profile_id` — scoring pipeline
- [x] `messages.sender_id`, `messages.receiver_id`, `messages.is_read`
- [x] `account_reports.reporter_id`, `account_reports.created_at`

### Backend Fixes
- [x] Leaderboard: fixed N+1 appreciation query (was N queries for N users → 1 batched query)
- [x] Leaderboard: added `asyncio.Lock` to prevent cache stampede
- [x] `database.py`: added `pool_size=10`, `max_overflow=20`, `pool_timeout=30`
- [x] `credibility_service.py`: added 10s timeout on Ollama AI call
- [x] `credibility_service.py`: added semaphore (max 5 concurrent URL checks)
- [x] `credibility_service.py`: replaced check-then-insert race with atomic PostgreSQL upsert
- [x] `profile.py`: `owner_email` now hidden from public profile views (only returned to profile owner)
- [x] `url_checker.py`: fixed `verify=False` SSL bypass → `verify=True` with proper error handling
- [x] `fraud_service.py`: AI failure now defaults to `medium` risk (was silently `low`)
- [x] `validation_service.py`: fixed date comparison bug (lexicographic "2024-9" > "2024-10")
- [x] `search.py`: added min/max query length validation (2–500 chars)
- [x] `main.py`: CORS hardened (whitelisted methods/headers instead of `*`)
- [x] `main.py`: added `slowapi` rate limiting (login: 10/min, register: 5/min)
- [x] `requirements.txt`: added `slowapi==0.1.9`

---

## Phase 6 — Reliability Fix (DONE — 2026-06-01)

- [x] **Neon cold-start fix**: `database.py` now exposes `ping_db(retries=6)` with exponential backoff (1 → 2 → 4 → 8 → 16 → 30s)
- [x] **Startup warmup**: `main.py` lifespan context calls `ping_db()` before the server accepts any requests — database is awake before first user hits the API
- [x] **Global exception handler**: `unhandled_exception_handler()` walks the full exception chain; asyncpg `InternalServerError` + `TimeoutError` now return HTTP 503 ("Database temporarily unavailable — please try again in a few seconds") instead of crashing the ASGI process with a 500

### Frontend Fixes
- [x] `api.ts`: added `getApiError()` unified error handler utility
- [x] `ProfileEditor.tsx`: file size (5 MB) + MIME type validation before upload
- [x] `ProfileEditor.tsx`: confirmation dialog before CV delete
- [x] `Inbox.tsx`: blob URL revoke on unmount (memory leak fix)
- [x] `Inbox.tsx`: polling pauses when browser tab not visible (`document.hidden`)
- [x] `SearchPage.tsx`: min 2-character validation on search query

---

## Phase 7 — Planned (Not Yet Started)

### 7.1 OAuth Proof Verification
- [ ] GitHub OAuth: verify ownership of GitHub account linked in proof signals
- [ ] Create-a-file proof of possession for custom portfolio domains

### 7.2 Duplicate Detection (Cross-Profile)
- [ ] Bio similarity fingerprinting across all profiles (difflib or embeddings)
- [ ] Flag copy-pasted bios from other users

### 7.3 Score Transparency
- [ ] Score breakdown UI: show per-criterion scores (completeness/alignment/portfolio/etc.)
- [ ] Score history chart (track improvement over time)

### 7.4 Hirer Features
- [ ] Saved candidates list
- [ ] Hirer-side review/rating of candidates post-hire
- [ ] Advanced search filters (experience level, location, score range)

### 7.5 Notifications
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
| `a1b2c3d4e5f6` | Add 10 missing indexes (appreciations FKs, credibility_scores.score, proof_signals.profile_id, messages FKs, reports FKs) |
| `b3c4d5e6f7a8` | Enable pg_trgm; add stored `search_tsv` tsvector column + DB trigger to keep it fresh + plain GIN index on `search_tsv` + trigram GIN index on `title` |
