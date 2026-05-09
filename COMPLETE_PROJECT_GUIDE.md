# HireCred-v1 Complete Project Guide

**Last updated:** 2026-05-09
**Status:** Active development — Phase 2 upgrade in progress

---

## 1. What This Project Is

HireCred is a trust-focused hiring platform. It helps clients find candidates using verified signals instead of only self-reported profile text.

The product centers on five ideas:

- Candidate profiles are richer than a normal resume, including an uploadable CV.
- AI (local Ollama Qwen 2.5 14B) creates a credibility score from profile evidence and CV content.
- AI converts written client feedback into structured appreciations.
- Search and leaderboard ranking prefer trust and proof with exact-match priority and semantic fallback.
- All data is validated for authenticity — dummy links, repeated entries, and placeholder content are blocked.

---

## 2. High-Level Architecture

The app is a monorepo:

- `client/` — React + Vite + TypeScript frontend
- `server/` — Python + FastAPI backend

```
f:/hireCred-v1/
├── client/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── index.css
│   │   ├── components/
│   │   │   ├── appreciation/
│   │   │   ├── profile/
│   │   │   ├── validation/          ← NEW: client-side authenticity validators
│   │   │   ├── ProtectedRoute.tsx
│   │   │   └── SkillsTagInput.tsx
│   │   ├── lib/
│   │   │   ├── api.ts
│   │   │   ├── queryClient.ts
│   │   │   ├── types.ts
│   │   │   ├── nanoid.ts
│   │   │   └── validators.ts        ← NEW: shared validation helpers
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Inbox.tsx
│   │   │   ├── Leaderboard.tsx
│   │   │   ├── Login.tsx
│   │   │   ├── ProfileEditor.tsx    ← UPDATED: CV upload + validation warnings
│   │   │   ├── ProfileView.tsx      ← UPDATED: CV viewer for hirers
│   │   │   ├── Register.tsx
│   │   │   └── SearchPage.tsx       ← UPDATED: improved semantic search UI
│   │   └── stores/
│   │       └── authStore.ts
└── server/
    ├── main.py
    ├── config.py                    ← UPDATED: ollama settings, removed gemini
    ├── database.py
    ├── requirements.txt             ← UPDATED: added httpx for ollama calls
    └── src/
        ├── ai/
        │   ├── ollama_client.py     ← NEW: single Ollama HTTP client
        │   ├── credibility_prompt.py ← REWRITTEN: uses Ollama
        │   ├── appreciation_prompt.py ← REWRITTEN: uses Ollama
        │   ├── search_prompt.py     ← REWRITTEN: uses Ollama + semantic matching
        │   ├── fraud_prompt.py      ← REWRITTEN: uses Ollama
        │   └── cv_prompt.py         ← NEW: CV analysis prompt
        ├── middleware/
        │   └── auth.py
        ├── models/
        │   ├── user.py
        │   ├── profile.py           ← UPDATED: cv_file_path field
        │   ├── proof_signal.py
        │   ├── credibility_score.py
        │   ├── appreciation.py
        │   └── message.py
        ├── routers/
        │   ├── auth.py
        │   ├── profile.py           ← UPDATED: CV upload endpoint
        │   ├── proof_signals.py
        │   ├── search.py            ← UPDATED: semantic + exact search logic
        │   ├── leaderboard.py       ← UPDATED: improved ranking formula
        │   ├── messages.py
        │   └── appreciation.py
        ├── schemas/
        │   ├── auth.py
        │   └── profile.py           ← UPDATED: cv_url in response
        └── services/
            ├── auth_service.py
            ├── credibility_service.py ← UPDATED: includes CV analysis
            ├── search_service.py    ← REWRITTEN: exact + semantic ranking
            ├── fraud_service.py
            └── validation_service.py ← NEW: authenticity checks
```

---

## 3. AI Layer — Ollama Qwen 2.5 14B (Replaces Gemini)

### 3.1 Why Ollama

The Gemini API is removed entirely. All AI processing now runs through a local Ollama instance with the `qwen2.5:14b` model. This means:

- No external API keys needed for AI
- No rate limits or cost per call
- Full control over context window (set to 8192 tokens)
- Privacy — profile data never leaves the machine

### 3.2 How Ollama Is Called

A single shared client lives at `server/src/ai/ollama_client.py`. All four prompt files import from it. It sends HTTP POST requests to `http://localhost:11434/api/generate` (or the configured `OLLAMA_HOST`) with:

```json
{
  "model": "qwen2.5:14b",
  "prompt": "...",
  "stream": false,
  "options": {
    "num_ctx": 8192,
    "temperature": 0.3,
    "num_predict": 1024
  }
}
```

The client extracts the `response` field, strips markdown fences, and parses JSON.

### 3.3 Setup Requirement

Ollama must be running before the backend starts:

```bash
ollama serve
ollama pull qwen2.5:14b
```

No API key is needed. The `OLLAMA_HOST` env var defaults to `http://localhost:11434`.

---

## 4. CV Upload and Analysis (Professional/Candidate Accounts)

### 4.1 What It Does

Candidates can upload a PDF or DOCX CV from their Profile Editor. The backend:

1. Saves the file to `server/uploads/cv/`
2. Extracts text from the CV (using `pdfplumber` for PDF, `python-docx` for DOCX)
3. Sends the text to Ollama via `server/src/ai/cv_prompt.py` for analysis
4. Stores the analysis result alongside the credibility score

When a hirer views a candidate's profile:

- A "View CV" button appears on `ProfileView.tsx` if a CV exists
- The button opens the CV file in a new browser tab (served as a static file by FastAPI)
- The CV analysis summary (extracted skills, experience summary, authenticity check) is shown in the profile sidebar

### 4.2 Files Involved

| File | Role |
|------|------|
| `client/src/pages/ProfileEditor.tsx` | CV file picker, upload button, progress state |
| `client/src/pages/ProfileView.tsx` | "View CV" button, CV analysis summary panel |
| `server/src/routers/profile.py` | `POST /api/profile/{user_id}/cv` upload endpoint |
| `server/src/ai/cv_prompt.py` | Ollama prompt to extract skills, experience, authenticity flag from CV text |
| `server/src/services/credibility_service.py` | Feeds CV analysis into credibility scoring |
| `server/src/models/profile.py` | `cv_file_path` and `cv_analysis` (JSON) columns |
| `server/src/schemas/profile.py` | `cv_url` and `cv_analysis` in response schema |

### 4.3 CV Authenticity Rules

The backend rejects CV uploads that:

- Are empty (zero text extracted)
- Contain only placeholder phrases (e.g., "Your Name Here", "Lorem ipsum", "Insert experience")
- Have fewer than 100 words of real content
- List only skills with no experience dates or roles

If the CV is rejected, the API returns HTTP 422 with a reason. The frontend shows this as a warning toast.

---

## 5. Data Validation and Authenticity System

This is the most critical new subsystem. Every piece of data entered by a candidate is validated for authenticity before it is accepted.

### 5.1 Two-Warning System

The frontend tracks a `warningCount` state per session (stored in component state, not persisted). When a user submits content that fails an authenticity check:

- Warning 1: A yellow banner explains what was wrong and what to fix. The save is blocked.
- Warning 2: A red banner appears with a stronger message. Save is still blocked.
- After 2 warnings the save button stays disabled until the offending field is corrected.

The backend also independently validates on every PUT/POST so warnings cannot be bypassed by API calls.

### 5.2 What Is Checked

#### URL Validation
Any URL field (portfolio URL, proof signal URL, GitHub link) is validated against:

- **Blocked domains**: `example.com`, `example.org`, `test.com`, `placeholder.com`, `yoursite.com`, `mywebsite.com`, `website.com`, `domain.com`, `sample.com`, `foo.bar`, `tempurl.com`, localhost
- **Format check**: must start with `https://` (HTTP allowed but flagged)
- **Pattern check**: must not be just an IP address
- **Real domain check**: the backend does a lightweight DNS existence check (not a full HTTP fetch)

Validation file (frontend): `client/src/lib/validators.ts`
Validation file (backend): `server/src/services/validation_service.py`

#### Duplicate / Repeated Entry Detection
- Skills: duplicate tags are silently removed
- Experience: if two entries share the same company name AND overlapping date ranges, the second is blocked
- Portfolio: if two items have identical URLs, the second is blocked
- Proof signals: duplicate URLs across any signal type are blocked

#### Dummy Screenshot Detection
When a proof signal screenshot is uploaded:

- File must be a real image (PNG/JPG/WEBP), max 10MB
- Image must be at least 400×300 pixels (tiny placeholder images fail)
- The backend runs a simple pixel variance check — a solid-color or near-solid image (common for blank placeholders) is rejected
- Images that contain obvious placeholder text patterns (detected via basic OCR if `pytesseract` is available, otherwise skipped) are flagged

#### Bio and Text Field Validation
- Bio must be at least 80 characters long
- Bio must not be a copy-paste of the job title repeated
- Bio must not contain placeholder phrases: "Lorem ipsum", "Write your bio here", "About me", "I am a professional", "Experienced professional"
- Experience descriptions must be at least 40 characters and specific to the role

#### Profile Completeness Gate
A profile must pass a minimum completeness threshold before the credibility scoring runs:
- At least 3 skills
- At least 1 experience entry
- Bio present and valid
- Title present

If the profile does not meet this threshold, scoring returns a low score with explicit feedback rather than running the full AI evaluation.

### 5.3 Validation Flow

```
Frontend form change
  → client-side validator (validators.ts) runs immediately
  → if fail: show inline field error (yellow border + message)
  → on Save click: all fields re-validated client-side
  → if fail: increment warningCount, show warning banner, block submit
  → if pass client-side: POST/PUT to backend
    → backend validation_service.py runs
    → if fail: HTTP 422 with { field, message } returned
    → frontend shows the returned error as a warning (counts toward 2-warning limit)
    → if pass: profile saved, credibility scoring triggered
```

---

## 6. Search — Exact Match Priority + Semantic Fallback

### 6.1 The Problem Being Solved

Previously a search for "doctor" could return software engineers if their credibility score was high. This is unacceptable. The new search has three tiers:

**Tier 1 — Exact profession/role match**
If the query clearly names a profession or role (doctor, lawyer, nurse, chef, teacher, engineer, designer, etc.), only candidates whose title or primary skills contain that profession are returned. If zero candidates match Tier 1, fall through to Tier 2.

**Tier 2 — Semantic skill match**
Skills and experience are matched semantically. This handles queries like:
- "Python backend engineer" → matches candidates with Django, FastAPI, Flask in skills even without "Python" in title
- "frontend with good communication" → matches React/Vue/Angular developers ranked by communication rating

If zero candidates match Tier 2, fall through to Tier 3.

**Tier 3 — Domain semantic search**
For queries that are not about a person role but about a field or domain (e.g., "foods with iron", "renewable energy consulting"), the search:
- Extracts the domain concept from the query
- Finds candidates whose bio, skills, or experience semantically overlaps with that domain
- Returns the closest matches with a note that no exact match was found

### 6.2 How Tier 1 Works

`server/src/ai/search_prompt.py` now returns an additional field:

```json
{
  "required_skills": ["react", "javascript"],
  "profession_keywords": ["doctor", "physician"],
  "trust_keywords": [],
  "experience_level": null,
  "trust_priority": false,
  "min_credibility_score": 0,
  "search_tier": "profession"
}
```

`search_tier` is one of `"profession"`, `"skill"`, or `"domain"`. The search service uses this to choose which filtering strategy to apply first.

`server/src/services/search_service.py` runs each tier in order and stops at the first tier that returns at least one result.

### 6.3 Ranking Formula

Within any tier, results are ranked by:

```
rank_score = (credibility_score × 0.40) + (skill_match_pct × 0.35) + (appreciation_avg × 0.15) + (profile_views_norm × 0.10)
```

For profession searches, candidates whose title exactly contains the profession keyword get a `+15` bonus before normalization.

### 6.4 Files Involved

| File | Role |
|------|------|
| `server/src/ai/search_prompt.py` | Ollama prompt that extracts intent, profession, tier |
| `server/src/services/search_service.py` | Tiered filtering + ranking logic |
| `server/src/routers/search.py` | HTTP endpoint, passes parsed intent to service |
| `client/src/pages/SearchPage.tsx` | Search input, results display, semantic fallback message |

---

## 7. Leaderboard — Trusted Ranking

### 7.1 Ranking Formula

The leaderboard is not just "sort by credibility score." It uses a composite weighted score:

```
leaderboard_score =
  (credibility_score    × 0.40)  ← AI-evaluated trust
+ (avg_appreciation     × 0.25)  ← client-validated quality
+ (appreciation_count   × 0.10)  ← volume of feedback
+ (proof_signal_count   × 0.15)  ← evidence richness
+ (profile_view_norm    × 0.10)  ← organic interest
```

Candidates with `fraud_risk = high` are excluded. Candidates with `fraud_risk = medium` have their appreciation component halved.

### 7.2 Minimum Qualification

A candidate must have:
- At least 1 appreciation to appear in leaderboard
- Credibility score ≥ 10 (avoids empty profiles polluting the top)

If fewer than 5 qualified candidates exist, the leaderboard shows profiles sorted by completeness instead, with a "Not enough data yet" banner.

### 7.3 Files Involved

| File | Role |
|------|------|
| `server/src/routers/leaderboard.py` | Query, ranking computation, cache |
| `client/src/pages/Leaderboard.tsx` | Ranked list UI with rank badges and score breakdown |

---

## 8. How The Website Works End To End

### 8.1 Registration And Login

A new user opens the register page and chooses a role:

- **Candidate (Professional)**: builds a public profile, uploads a CV, receives credibility scores
- **Hirer (Client)**: searches for candidates and sends appreciations/messages

On registration or login:
- Frontend sends credentials to `POST /api/auth/register` or `POST /api/auth/login`
- Backend validates and returns a JWT
- JWT is stored in the browser via Zustand (`client/src/stores/authStore.ts`)
- All protected requests attach the JWT via Axios interceptors (`client/src/lib/api.ts`)

### 8.2 Candidate Profile Building

A candidate edits their profile in `ProfileEditor.tsx`:

- Bio, title, location
- Skills (tag input)
- Experience entries (with date validation)
- Portfolio items (with URL validation)
- Proof signals (GitHub, portfolio link, client reference, screenshot)
- CV upload (PDF or DOCX)

Every field is validated in real time by `client/src/lib/validators.ts`. On save:
- PUT to `server/src/routers/profile.py`
- Backend `server/src/services/validation_service.py` re-validates
- If valid: profile saved, credibility scoring triggered in background

### 8.3 CV Upload

From the Profile Editor, the candidate uploads a CV:
- File must be PDF or DOCX, max 5MB
- `POST /api/profile/{user_id}/cv` saves the file to `server/uploads/cv/`
- Backend extracts text, validates it is not blank or dummy
- CV analysis runs via `server/src/ai/cv_prompt.py`
- Analysis result stored in `profile.cv_analysis` JSON column

### 8.4 Proof Signals

Proof signals are evidence items: GitHub links, portfolio links, client references, work screenshots. They are stored separately and scored by the credibility AI. Screenshots have pixel-variance validation to reject blank or placeholder images.

### 8.5 Credibility Scoring

The backend sends the full profile context (including CV analysis if available) to Ollama `qwen2.5:14b` via `server/src/ai/credibility_prompt.py`.

Ollama evaluates:
- Profile completeness
- Skill and experience alignment
- Portfolio quality
- Writing clarity
- Proof signal quality
- CV content quality (if CV uploaded)

The result is stored in `credibility_scores` table and used in profile score widgets, search ranking, and leaderboard ranking.

### 8.6 Profile Viewing (Hirer)

The public profile page (`ProfileView.tsx`) shows:
- Candidate identity, title, location, view count
- Skills, experience, portfolio
- Proof signals
- HireCred score with strengths/risks
- Appreciations
- **"View CV" button** — visible only to authenticated hirers, opens the CV file

### 8.7 Client Search Flow

A hirer types a natural language request. The backend:
1. Parses intent with Ollama (profession, skills, trust level, search tier)
2. Runs Tier 1 (exact profession match) → if results, return them
3. Runs Tier 2 (semantic skill match) → if results, return them
4. Runs Tier 3 (domain semantic search) → returns closest matches with fallback note

Results are ranked by the composite formula (credibility × skills × appreciation × views).

### 8.8 Appreciation Flow

Hirers submit free-text feedback. Ollama converts it to skill/communication/reliability ratings and a summary. After submission, fraud detection runs across all appreciations for that candidate.

### 8.9 Fraud Detection

Runs after every new appreciation. Ollama analyzes the full review set for:
- Generic/templated language
- Suspiciously perfect scores
- Repeated phrasing patterns
- Lack of specific project details

Fraud risk (low/medium/high) is stored and affects leaderboard ranking.

### 8.10 Leaderboard

Ranks candidates by composite score (credibility + appreciation + proof + views). Excludes fraud-flagged profiles. Requires minimum 1 appreciation to appear.

### 8.11 Messaging

Direct messages between hirers and candidates. Polling-based (no WebSocket). Inbox shows conversation list, unread counts, and thread view.

---

## 9. Frontend File Map

### 9.1 Root Setup
- [client/package.json](client/package.json) — frontend dependencies and scripts
- [client/vite.config.ts](client/vite.config.ts) — Vite configuration
- [client/tsconfig.json](client/tsconfig.json) — TypeScript config
- [client/index.html](client/index.html) — Vite HTML shell

### 9.2 Entrypoints
- [client/src/main.tsx](client/src/main.tsx) — mounts React, loads global CSS
- [client/src/App.tsx](client/src/App.tsx) — routes, protected routes, query client, toasts
- [client/src/index.css](client/src/index.css) — global styles and Tailwind foundation

### 9.3 API and Shared Utilities
- [client/src/lib/api.ts](client/src/lib/api.ts) — Axios client with JWT injection and 401 handling
- [client/src/lib/queryClient.ts](client/src/lib/queryClient.ts) — TanStack Query client
- [client/src/lib/types.ts](client/src/lib/types.ts) — TypeScript interfaces (includes CV fields)
- [client/src/lib/nanoid.ts](client/src/lib/nanoid.ts) — client-side ID generator for form items
- [client/src/lib/validators.ts](client/src/lib/validators.ts) — **NEW**: URL validation, duplicate detection, dummy text detection

### 9.4 Auth State
- [client/src/stores/authStore.ts](client/src/stores/authStore.ts) — Zustand store for user, token, login, logout

### 9.5 Components
- [client/src/components/ProtectedRoute.tsx](client/src/components/ProtectedRoute.tsx) — blocks unauthenticated access
- [client/src/components/SkillsTagInput.tsx](client/src/components/SkillsTagInput.tsx) — tag input with duplicate filtering
- [client/src/components/profile/ScoreWidget.tsx](client/src/components/profile/ScoreWidget.tsx) — score ring with strengths/risks
- [client/src/components/appreciation/AppreciationModal.tsx](client/src/components/appreciation/AppreciationModal.tsx) — feedback submission modal
- [client/src/components/appreciation/AppreciationSection.tsx](client/src/components/appreciation/AppreciationSection.tsx) — appreciation list and aggregates
- [client/src/components/appreciation/RatingBar.tsx](client/src/components/appreciation/RatingBar.tsx) — horizontal rating bar
- [client/src/components/validation/ValidationWarningBanner.tsx](client/src/components/validation/ValidationWarningBanner.tsx) — **NEW**: yellow/red warning banner for authenticity issues

### 9.6 Pages
- [client/src/pages/Login.tsx](client/src/pages/Login.tsx) — login form
- [client/src/pages/Register.tsx](client/src/pages/Register.tsx) — registration and role selection
- [client/src/pages/Dashboard.tsx](client/src/pages/Dashboard.tsx) — role-aware dashboard
- [client/src/pages/ProfileEditor.tsx](client/src/pages/ProfileEditor.tsx) — **UPDATED**: CV upload section, real-time validation, 2-warning system
- [client/src/pages/ProfileView.tsx](client/src/pages/ProfileView.tsx) — **UPDATED**: CV viewer button, CV analysis panel for hirers
- [client/src/pages/SearchPage.tsx](client/src/pages/SearchPage.tsx) — **UPDATED**: displays tier used, semantic fallback message
- [client/src/pages/Leaderboard.tsx](client/src/pages/Leaderboard.tsx) — **UPDATED**: improved ranking display with score breakdown
- [client/src/pages/Inbox.tsx](client/src/pages/Inbox.tsx) — conversation list and thread view

---

## 10. Backend File Map

### 10.1 Root Files
- [server/main.py](server/main.py) — FastAPI app, CORS, static file mounts, router registration
- [server/config.py](server/config.py) — settings from `.env` (UPDATED: `ollama_host`, removed gemini key)
- [server/database.py](server/database.py) — async SQLAlchemy engine and session factory
- [server/requirements.txt](server/requirements.txt) — Python dependencies (UPDATED: added `httpx`, `pdfplumber`, `python-docx`)

### 10.2 AI Layer
- [server/src/ai/ollama_client.py](server/src/ai/ollama_client.py) — **NEW**: shared async HTTP client for Ollama API calls
- [server/src/ai/credibility_prompt.py](server/src/ai/credibility_prompt.py) — **REWRITTEN**: Ollama prompt for credibility scoring, includes CV analysis input
- [server/src/ai/appreciation_prompt.py](server/src/ai/appreciation_prompt.py) — **REWRITTEN**: Ollama prompt for feedback → structured ratings
- [server/src/ai/search_prompt.py](server/src/ai/search_prompt.py) — **REWRITTEN**: Ollama prompt with profession extraction, search_tier output
- [server/src/ai/fraud_prompt.py](server/src/ai/fraud_prompt.py) — **REWRITTEN**: Ollama prompt for fake review detection
- [server/src/ai/cv_prompt.py](server/src/ai/cv_prompt.py) — **NEW**: Ollama prompt to analyze CV text for skills, experience, authenticity

### 10.3 Middleware
- [server/src/middleware/auth.py](server/src/middleware/auth.py) — JWT auth helpers and `current_user` dependency

### 10.4 ORM Models
- [server/src/models/user.py](server/src/models/user.py) — user accounts, roles, relationships
- [server/src/models/profile.py](server/src/models/profile.py) — **UPDATED**: `cv_file_path`, `cv_analysis` JSON columns
- [server/src/models/proof_signal.py](server/src/models/proof_signal.py) — proof signal records and signal type enum
- [server/src/models/credibility_score.py](server/src/models/credibility_score.py) — score, strengths, risks, fraud fields
- [server/src/models/appreciation.py](server/src/models/appreciation.py) — structured ratings and raw feedback
- [server/src/models/message.py](server/src/models/message.py) — message records and conversation data

### 10.5 Pydantic Schemas
- [server/src/schemas/auth.py](server/src/schemas/auth.py) — register, login, token, user response
- [server/src/schemas/profile.py](server/src/schemas/profile.py) — **UPDATED**: `cv_url`, `cv_analysis` in profile response

### 10.6 Routers
- [server/src/routers/auth.py](server/src/routers/auth.py) — `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`
- [server/src/routers/profile.py](server/src/routers/profile.py) — **UPDATED**: `GET/PUT /api/profile/{id}`, `POST /api/profile/{id}/cv`
- [server/src/routers/proof_signals.py](server/src/routers/proof_signals.py) — create/delete/upload proof signals with validation
- [server/src/routers/search.py](server/src/routers/search.py) — **UPDATED**: tiered search flow, profession + semantic matching
- [server/src/routers/leaderboard.py](server/src/routers/leaderboard.py) — **UPDATED**: composite ranking formula
- [server/src/routers/messages.py](server/src/routers/messages.py) — send, list, fetch, mark-read messages
- [server/src/routers/appreciation.py](server/src/routers/appreciation.py) — submit appreciation, load aggregates

### 10.7 Services
- [server/src/services/auth_service.py](server/src/services/auth_service.py) — password hashing and JWT creation
- [server/src/services/credibility_service.py](server/src/services/credibility_service.py) — **UPDATED**: feeds CV analysis to scoring, validation gate
- [server/src/services/search_service.py](server/src/services/search_service.py) — **REWRITTEN**: Tier 1/2/3 filtering, composite ranking
- [server/src/services/fraud_service.py](server/src/services/fraud_service.py) — appreciation fraud analysis, score penalty
- [server/src/services/validation_service.py](server/src/services/validation_service.py) — **NEW**: URL validation, duplicate detection, dummy content detection, image variance check

---

## 11. Main Data Flows

### 11.1 Registration and Authentication
1. User registers/logs in from frontend
2. `authStore.ts` calls auth endpoints
3. `routers/auth.py` creates or verifies the user
4. `services/auth_service.py` creates a JWT
5. Token stored in browser, attached to all requests by `api.ts`

### 11.2 Profile Editing with Validation
1. `ProfileEditor.tsx` collects fields
2. `validators.ts` runs real-time checks on each field change
3. On save: client validates all fields, increments warning count on failure
4. If client passes: `PUT /api/profile/{user_id}` sent
5. `routers/profile.py` calls `validation_service.py`
6. Backend validation failure → HTTP 422 → frontend warning banner
7. Backend validation pass → profile saved → credibility scoring triggered

### 11.3 CV Upload
1. Candidate selects PDF/DOCX in `ProfileEditor.tsx`
2. `POST /api/profile/{user_id}/cv` uploads file
3. Backend extracts text, validates content is not blank or dummy
4. `cv_prompt.py` sends text to Ollama for analysis
5. Analysis stored in `profile.cv_analysis`
6. CV is now visible to hirers on `ProfileView.tsx`

### 11.4 Proof Signal Upload
1. Editor uploads proof signal or screenshot
2. `routers/proof_signals.py` validates URL (if link) or image (if screenshot)
3. Image screenshot goes through pixel-variance check
4. Valid signals stored in database, served from `server/uploads/`

### 11.5 Public Profile View (Hirer)
1. `ProfileView.tsx` loads profile by user ID
2. Requests score from `/api/profile/{user_id}/score`
3. `ScoreWidget.tsx` renders score ring and summary
4. `AppreciationSection.tsx` loads appreciations
5. If candidate has a CV and viewer is a hirer: "View CV" button shown

### 11.6 Search (Three-Tier)
1. `SearchPage.tsx` sends query to `POST /api/search`
2. `routers/search.py` forwards to `search_service.py`
3. `search_prompt.py` sends query to Ollama → returns parsed intent + `search_tier`
4. Tier 1: filter by profession keywords in title/skills → if results, return
5. Tier 2: filter by semantic skill overlap → if results, return
6. Tier 3: semantic domain search → return closest with fallback note
7. Results ranked by composite formula, returned to frontend

### 11.7 Appreciation and Fraud Detection
1. Hirer submits text feedback from profile page
2. `routers/appreciation.py` sends text to `appreciation_prompt.py` → Ollama
3. Structured appreciation stored in database
4. `credibility_service.py` recomputes recipient score
5. `fraud_service.py` runs analysis on all appreciations for the candidate

### 11.8 Leaderboard
1. `routers/leaderboard.py` queries candidates with profiles, scores, appreciations
2. Excludes `fraud_risk = high` candidates
3. Computes composite leaderboard score
4. Returns top 20 sorted descending
5. `Leaderboard.tsx` renders with rank badges and score breakdown

### 11.9 Messaging
1. Profile page opens conversation
2. `routers/messages.py` stores messages, returns threads
3. `Inbox.tsx` polls for updates, shows unread badges

---

## 12. Validation Service Reference

**File:** `server/src/services/validation_service.py`

**Functions:**

| Function | What It Checks |
|----------|----------------|
| `validate_url(url)` | Blocked domains, format, real domain existence |
| `validate_no_duplicates(items, key)` | Repeated entries in lists |
| `validate_bio(bio)` | Min length, placeholder phrases |
| `validate_experience_entry(entry, existing)` | Overlapping dates, same company |
| `validate_image_content(file_bytes)` | Pixel variance, image size, placeholder detection |
| `validate_cv_content(text)` | Min word count, dummy phrases |
| `validate_full_profile(profile_data)` | Runs all checks, returns list of ValidationError |

**Blocked URL Domains (complete list):**
`example.com`, `example.org`, `example.net`, `test.com`, `placeholder.com`, `yoursite.com`, `mywebsite.com`, `website.com`, `domain.com`, `sample.com`, `foo.bar`, `tempurl.com`, `dummysite.com`, `fakesite.com`, `abc.com`, `xyz.com` (and their subdomains)

---

## 13. Config Reference

`server/src/config.py` reads from `.env`:

| Variable | Purpose | Default |
|----------|---------|---------|
| `DATABASE_URL` | Neon PostgreSQL connection string | required |
| `JWT_SECRET` | JWT signing key | required |
| `JWT_ALGORITHM` | JWT algorithm | `HS256` |
| `JWT_EXPIRE_MINUTES` | Token TTL | `10080` (7 days) |
| `OLLAMA_HOST` | Ollama API base URL | `http://localhost:11434` |
| `OLLAMA_MODEL` | Model name | `qwen2.5:14b` |
| `OLLAMA_CTX` | Context window tokens | `8192` |
| `ENVIRONMENT` | `development` or `production` | `development` |

The `GEMINI_API_KEY` and `ANTHROPIC_API_KEY` variables are removed. The `AI_PROVIDER` variable is removed (Ollama is the only provider).

---

## 14. Runtime Notes

- Frontend uses TanStack Query for server state and cache invalidation
- Frontend uses Zustand for persistent auth state
- Backend uses async SQLAlchemy with FastAPI
- **Ollama must be running** before the backend starts — if Ollama is unavailable, AI scoring falls back to rule-based scoring (credibility service has a fallback)
- File uploads are saved locally under `server/uploads/` (split into `server/uploads/screenshots/` and `server/uploads/cv/`) and served as static files by FastAPI
- Search uses three tiers to ensure profession-specific queries never return unrelated professions

---

## 15. Helpful Commands

**Frontend:**
```bash
cd client
npm run dev
npm run build
npm run lint
```

**Backend:**
```bash
cd server
uvicorn main:app --reload --port 8000
```

**Ollama (must run before backend):**
```bash
ollama serve
# First time only:
ollama pull qwen2.5:14b
```

**Database migrations:**
```bash
cd server
alembic revision --autogenerate -m "add cv fields"
alembic upgrade head
```

---

## 16. Feature Completeness Map

| Feature | Status | Key Files |
|---------|--------|-----------|
| Registration & login | Done | `routers/auth.py`, `Login.tsx`, `Register.tsx` |
| Candidate profile editing | Done | `ProfileEditor.tsx`, `routers/profile.py` |
| Skills tag input | Done | `SkillsTagInput.tsx` |
| Proof signals (link + screenshot) | Done | `routers/proof_signals.py` |
| Screenshot image validation | **NEW** | `validation_service.py`, `proof_signals.py` |
| URL authenticity validation | **NEW** | `validators.ts`, `validation_service.py` |
| Duplicate entry detection | **NEW** | `validators.ts`, `validation_service.py` |
| Two-warning system | **NEW** | `ProfileEditor.tsx`, `ValidationWarningBanner.tsx` |
| CV upload (candidate) | **NEW** | `routers/profile.py`, `ProfileEditor.tsx` |
| CV analysis via AI | **NEW** | `cv_prompt.py`, `credibility_service.py` |
| CV viewer (hirer on profile) | **NEW** | `ProfileView.tsx` |
| Credibility scoring (Ollama) | **UPDATED** | `credibility_prompt.py`, `ollama_client.py` |
| Appreciation system (Ollama) | **UPDATED** | `appreciation_prompt.py` |
| Fraud detection (Ollama) | **UPDATED** | `fraud_prompt.py` |
| Search — exact profession match | **NEW** | `search_service.py`, `search_prompt.py` |
| Search — semantic skill match | **UPDATED** | `search_service.py` |
| Search — domain semantic fallback | **NEW** | `search_service.py` |
| Leaderboard composite ranking | **UPDATED** | `leaderboard.py` |
| Leaderboard fraud exclusion | **NEW** | `leaderboard.py` |
| Messaging / inbox | Done | `routers/messages.py`, `Inbox.tsx` |
| Public profile view | Done | `ProfileView.tsx` |
| HireCred score widget | Done | `ScoreWidget.tsx` |

---

## 17. Summary

HireCred is a trust-based hiring platform built with React + FastAPI + PostgreSQL. AI runs entirely locally via Ollama (Qwen 2.5 14B, 8k context). The platform ensures data authenticity through a layered validation system, enables CV upload and analysis for professional candidates, surfaces CVs to hirers, and delivers precise search results by prioritizing exact profession matches before falling back to semantic similarity. The leaderboard reflects genuine, fraud-resistant trust signals rather than raw activity.
