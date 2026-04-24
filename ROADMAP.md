# HireCred-v1 — Build Roadmap

**Stack:** React + Vite + TypeScript | Python + FastAPI | Neon DB (PostgreSQL) | Claude API  
**Deadline:** 10 days from start (~2026-04-27)  
**Structure:** monorepo root `/` with `client/` and `server/` subfolders

---

## Phase 1 — Project Setup & Boilerplate (Day 1)

### 1.1 Root Setup
- Create root folder with a `README.md` and `.gitignore`
- `.gitignore` covers: `node_modules/`, `__pycache__/`, `.env`, `*.pyc`, `dist/`, `uploads/*`
- Init git repo: `git init`

### 1.2 Backend Scaffold (`server/`)
- Create `server/` folder
- Create Python virtual environment: `python -m venv venv`
- Install core packages:
  ```
  fastapi uvicorn[standard] python-dotenv
  sqlalchemy[asyncio] asyncpg alembic
  python-jose[cryptography] passlib[bcrypt]
  anthropic python-multipart pydantic
  ```
- Save to `requirements.txt`
- Create `server/.env.example`:
  ```
  DATABASE_URL=postgresql+asyncpg://...neon.tech/hirecred
  JWT_SECRET=your-secret-here
  ANTHROPIC_API_KEY=sk-ant-...
  ```
- Folder structure inside `server/`:
  ```
  server/
  ├── app/
  │   ├── main.py          # FastAPI app, routers registered here
  │   ├── database.py      # Async SQLAlchemy engine + session
  │   ├── models/          # SQLAlchemy ORM models (one file per model)
  │   ├── schemas/         # Pydantic request/response schemas
  │   ├── routers/         # Route files: auth, profile, search, etc.
  │   ├── services/        # Business logic (not in routers)
  │   ├── ai/              # All Claude prompt logic lives here
  │   └── middleware/      # JWT auth dependency
  ├── alembic/             # DB migrations
  ├── alembic.ini
  ├── requirements.txt
  └── .env
  ```

### 1.3 Frontend Scaffold (`client/`)
- Run: `npm create vite@latest client -- --template react-ts`
- Install packages:
  ```
  @tanstack/react-query axios
  react-router-dom zustand
  react-hot-toast
  tailwindcss @tailwindcss/vite (or postcss setup)
  ```
- Configure Tailwind
- Create `client/.env.example`:
  ```
  VITE_API_URL=http://localhost:8000
  ```
- Folder structure inside `client/src/`:
  ```
  src/
  ├── pages/               # One file per page/route
  ├── components/
  │   ├── ui/              # Reusable: Button, Input, Badge, Card, Modal
  │   ├── profile/         # ProfileCard, ProofSignals, ScoreWidget
  │   ├── search/          # SearchBar, CandidateResult
  │   ├── leaderboard/     # LeaderboardRow
  │   ├── appreciation/    # AppreciationForm, RatingBar
  │   └── messaging/       # MessageThread, MessageInput
  ├── hooks/               # useAuth, useProfile, useSearch, etc.
  ├── store/               # Zustand stores (authStore)
  ├── lib/                 # axios instance, query client
  └── types/               # Shared TypeScript types
  ```

---

## Phase 2 — Database Models & Migrations (Day 1–2)

### 2.1 Define SQLAlchemy Models
Create these models in `server/app/models/`:

**`user.py`**
```
User: id, email, password_hash, role (CANDIDATE|CLIENT), created_at
```

**`profile.py`**
```
Profile: id, user_id (FK), display_name, bio, skills (ARRAY), 
         experience (JSONB), portfolio (JSONB), avatar_url, view_count, updated_at
```

**`proof_signal.py`**
```
ProofSignal: id, profile_id (FK), type (GITHUB|SCREENSHOT|REFERENCE|URL),
             url, label, metadata (JSONB), created_at
```

**`credibility_score.py`**
```
CredibilityScore: id, profile_id (FK unique), score (int), 
                  strengths (ARRAY), risks (ARRAY),
                  fraud_risk (LOW|MEDIUM|HIGH), fraud_flags (ARRAY),
                  computed_at, updated_at
```

**`appreciation.py`**
```
Appreciation: id, from_user_id (FK), to_user_id (FK), raw_feedback (text),
              skill_rating (float), communication_rating (float), reliability_rating (float),
              summary (text), is_flagged (bool), created_at
```

**`message.py`**
```
Message: id, from_user_id (FK), to_user_id (FK), content (text), read_at, created_at
```

### 2.2 Database Connection (`database.py`)
- Async SQLAlchemy engine pointed at Neon DB URL
- `AsyncSession` dependency for FastAPI injection
- Neon requires SSL: add `?sslmode=require` to URL

### 2.3 Alembic Migrations
- `alembic init alembic`
- Point `alembic.ini` at `DATABASE_URL` from env
- `alembic revision --autogenerate -m "initial schema"`
- `alembic upgrade head`

---

## Phase 3 — Auth System (Day 2)

### 3.1 Backend Auth
- `POST /api/auth/register` — hash password with bcrypt, create User + empty Profile, return JWT
- `POST /api/auth/login` — verify password, return JWT
- `GET /api/auth/me` — protected, return current user
- JWT middleware: `get_current_user` FastAPI dependency (used in all protected routes)
- Token payload: `{ sub: user_id, role: CANDIDATE|CLIENT, exp: ... }`

### 3.2 Frontend Auth
- `authStore.ts` (Zustand): stores `{ user, token, setAuth, logout }`
- Axios instance in `lib/api.ts`: attaches `Authorization: Bearer <token>` header automatically
- `ProtectedRoute` component: redirects to `/login` if not authenticated
- Pages: `/login`, `/register` (with role selection: I'm a Candidate / I'm hiring)
- On login success → redirect to `/dashboard`

---

## Phase 4 — Smart Profile System (Day 3)

### 4.1 Backend Profile API
- `GET /api/profile/:user_id` — public, returns profile + score + proof signals + aggregated ratings
  - Also increments `view_count` on each fetch
- `PUT /api/profile` — protected (candidate only), updates bio/skills/experience/portfolio
- `POST /api/profile/proof-signals` — add a proof signal
- `DELETE /api/profile/proof-signals/:id` — remove a proof signal
- `POST /api/upload` — accepts image file, saves to `/uploads`, returns URL

### 4.2 Frontend Profile Pages
- `/profile/:userId` — public profile view
  - Shows: avatar, name, bio, skills tags, experience list, portfolio grid, proof signals, HireCred Score widget, appreciation list
  - "Send Message" button (client only), "Give Appreciation" button (client only)
- `/profile/edit` — candidate's own profile editor
  - Skills: tag input (type + enter to add, click to remove)
  - Experience: add/remove items with form fields
  - Portfolio: add/remove items with form fields
  - Proof Signals section: GitHub URL field, screenshot upload, reference text input
  - Save button → triggers score recomputation

---

## Phase 5 — AI Credibility Score (Day 4)

### 5.1 Prompt Design (`server/app/ai/credibility_prompt.py`)
- Build a detailed system prompt:
  ```
  You are HireCred's trust evaluator. Analyze the candidate profile below and return 
  a credibility score from 0 to 100 as valid JSON only.

  Scoring criteria:
  - Profile completeness (bio, skills count ≥3, experience ≥1 item, portfolio ≥1 item): 25 points
  - Skill vs experience alignment (do claimed skills appear in portfolio/experience?): 25 points
  - Portfolio quality (descriptions are detailed, links present, diverse projects): 20 points
  - Writing clarity (bio is professional, specific, not generic filler text): 15 points
  - Proof signals (GitHub = +8, screenshots = +5, references = +7 each, max 15): 15 points

  Return ONLY this JSON, no extra text:
  {
    "credibility_score": <integer 0-100>,
    "strengths": [<up to 4 specific strengths>],
    "risks": [<up to 4 specific risks or missing elements>]
  }
  ```
- Use Claude's `tool_use` (tool with defined JSON schema) to enforce structured output

### 5.2 Service (`server/app/services/credibility_service.py`)
- `async def compute_score(profile_data: dict) -> dict`
- Calls Claude API with the prompt
- Parses and validates response (fallback if malformed)
- Saves/updates `CredibilityScore` row in DB

### 5.3 Trigger
- Called automatically in the background after `PUT /api/profile` (use FastAPI `BackgroundTasks`)
- Endpoint `GET /api/profile/:user_id/score` returns latest stored score

### 5.4 Frontend Score Widget
- Circular progress ring showing 0–100
- Color: red (<40), orange (40–69), green (70+)
- Expandable section: "Strengths" and "Risks" listed below
- Shows "Calculating..." while score is being computed

---

## Phase 6 — AI Appreciation System (Day 5)

### 6.1 Prompt Design (`server/app/ai/appreciation_prompt.py`)
- System prompt:
  ```
  You are analyzing a client's written feedback about a freelancer.
  Extract and rate the following dimensions from 0.0 to 10.0 based on what is implied 
  or stated in the text. Do not invent information not present in the feedback.

  Return ONLY this JSON:
  {
    "skill_rating": <float 0-10>,
    "communication_rating": <float 0-10>,
    "reliability_rating": <float 0-10>,
    "summary": "<one sentence neutral summary>"
  }
  ```

### 6.2 Backend
- `POST /api/appreciation` — protected (client only)
  - Accepts `{ to_user_id, raw_feedback }`
  - Runs AI conversion → saves structured appreciation
  - Triggers fraud detection (background task)
  - Triggers credibility score recomputation for the recipient
- `GET /api/appreciation/:user_id` — returns list + aggregates `{ avg_skill, avg_comm, avg_reliability, count }`

### 6.3 Frontend
- Appreciation form modal: single textarea "Describe your experience working with this person"
- After submission: shows the AI-generated ratings to the submitter ("Here's what we understood from your feedback")
- On profile: rating bars for skill / communication / reliability
- Individual appreciation cards showing summary + ratings

---

## Phase 7 — Smart Intent Search (Day 6)

### 7.1 AI Query Parsing (`server/app/ai/search_prompt.py`)
- System prompt:
  ```
  Parse the following job search query into structured intent.
  Return ONLY this JSON:
  {
    "required_skills": [<list of skill names extracted>],
    "trust_keywords": [<words like: reliable, verified, experienced, fast>],
    "experience_level": "junior" | "mid" | "senior" | null,
    "trust_priority": <true if query emphasizes trust/reliability>
  }
  ```

### 7.2 Search Service (`server/app/services/search_service.py`)
- AI parse the raw query → get `required_skills`, `trust_priority`
- DB query:
  - Filter candidates whose `profile.skills` overlap with `required_skills`
  - JOIN with `credibility_score`
- Rank each result:
  ```python
  rank = (credibility_score * 0.4) + (skill_overlap_pct * 40) + (avg_appreciation * 2)
  if trust_priority: rank += credibility_score * 0.2  # boost trust weight
  ```
- Return top 20 sorted by rank

### 7.3 Frontend Search Page (`/search`)
- Single large search input: `"Describe who you're looking for..."`
- Loading state: "AI is analyzing your request..." with pulse animation
- Result cards: name, HireCred Score badge, top 3 skills, avg appreciation, "View Profile" button
- No filters, no dropdowns

---

## Phase 8 — Trust Leaderboard (Day 6–7) ✅ COMPLETED

### 8.1 Backend
- `GET /api/leaderboard` — returns top 20 candidates
- Ranking formula:
  ```python
  leaderboard_rank = (credibility_score * 0.5) + (appreciation_count * 2) + (avg_ratings * 3) + (view_count * 0.1)
  ```
- Cached in memory for 10 minutes (simple dict cache or Redis if time permits)

### 8.2 Frontend (`/leaderboard`)
- Rank badges: #1 gold, #2 silver, #3 bronze, rest numbered
- Each row: rank, avatar, name, skills, HireCred Score, appreciation count
- Clicking a row opens profile

---

## Phase 9 — Messaging (Day 7) ✅ COMPLETED

### 9.1 Backend
- `POST /api/messages` — send a message `{ to_user_id, content }`
- `GET /api/messages/conversations` — list of unique conversations for current user
- `GET /api/messages/conversation/:other_user_id` — full thread between two users
- `PATCH /api/messages/read/:other_user_id` — mark messages as read

### 9.2 Frontend
- `/inbox` — list of conversations with unread indicator
- `/inbox/:userId` — message thread, poll every 5 seconds (no real-time needed)
- "Send Message" button on profile page → redirects to `/inbox/:userId`

---

## Phase 10 — Fake Review Detection (Day 8, Bonus) ✅ COMPLETED

### 10.1 Fraud Detection Prompt (`server/app/ai/fraud_prompt.py`)
```
You are analyzing a set of client appreciations for a single freelancer to detect fake or manipulated reviews.

Look for:
- Generic, templated language (e.g. "great work, highly recommend")
- Suspiciously perfect scores (all 10s with no nuance)
- Reviews that are too short to contain real information
- Uniform writing style across multiple reviewers

Return ONLY this JSON:
{
  "fraud_risk": "low" | "medium" | "high",
  "flags": [<list of specific concerns found, empty if none>]
}
```

### 10.2 Integration
- Triggered as a background task after each new appreciation is submitted
- Updates `fraud_risk` and `fraud_flags` on `CredibilityScore`
- If `fraud_risk = "high"`: subtract 15 from credibility score
- If `fraud_risk = "medium"`: subtract 7 from credibility score
- Show "Verified Feedback" green badge on profiles with `fraud_risk = "low"` and ≥3 appreciations

---

## Phase 11 — Polish & Deploy (Day 9–10)

### 11.1 Frontend Polish
- Error boundaries and fallback UI
- Empty state components (no profile yet, no search results, no messages)
- Loading skeletons for profile and search results
- Toast notifications (success/error) using react-hot-toast
- Mobile-responsive layout check

### 11.2 Seed Data Script
- Create a `server/seed.py` script
- Generates 10–15 fake candidates with varied profiles, proof signals, and appreciations
- Covers edge cases: high-score vs low-score, fraud-flagged, new with no appreciations
- Run before demo to make leaderboard and search feel alive

### 11.3 Environment & Deploy
- Backend: deploy to Railway
  - Set environment variables (DATABASE_URL, JWT_SECRET, ANTHROPIC_API_KEY)
  - Neon DB connection already cloud-hosted
- Frontend: deploy to Vercel
  - Set `VITE_API_URL` to Railway backend URL
- Test full flow on deployed URLs before recording demo

### 11.4 Demo Video Plan (2–5 min)
1. Register as candidate → fill profile → add proof signals → show HireCred Score generated
2. Register as client → search "looking for reliable React developer" → show ranked results
3. Open a candidate profile → send message → give appreciation → show AI-converted ratings
4. Show leaderboard → explain ranking logic
5. Show fraud detection: add 3 generic reviews → show badge change

---

## File/Folder Reference

```
hireCred-v1/
├── client/                    # React + Vite frontend
│   ├── src/
│   │   ├── pages/
│   │   │   ├── LoginPage.tsx
│   │   │   ├── RegisterPage.tsx
│   │   │   ├── DashboardPage.tsx
│   │   │   ├── ProfileViewPage.tsx
│   │   │   ├── ProfileEditPage.tsx
│   │   │   ├── SearchPage.tsx
│   │   │   ├── LeaderboardPage.tsx
│   │   │   └── InboxPage.tsx
│   │   ├── components/
│   │   │   ├── ui/            # Button, Input, Badge, Card, Modal, Skeleton
│   │   │   ├── profile/       # ScoreWidget, ProofSignalList, AppreciationList
│   │   │   ├── search/        # SearchBar, CandidateCard
│   │   │   └── appreciation/  # AppreciationForm, RatingBars
│   │   ├── store/authStore.ts
│   │   ├── lib/api.ts         # Axios instance
│   │   └── types/index.ts
│   └── package.json
│
├── server/                    # Python + FastAPI backend
│   ├── app/
│   │   ├── main.py
│   │   ├── database.py
│   │   ├── models/            # user, profile, proof_signal, credibility_score, appreciation, message
│   │   ├── schemas/           # Pydantic schemas matching each model
│   │   ├── routers/           # auth, profile, search, appreciation, message, leaderboard
│   │   ├── services/          # credibility_service, search_service, fraud_service
│   │   ├── ai/                # credibility_prompt, appreciation_prompt, search_prompt, fraud_prompt
│   │   └── middleware/        # auth dependency (get_current_user)
│   ├── alembic/
│   ├── requirements.txt
│   └── .env
│
├── PROJECT_UNDERSTANDING.md   # ← this project's logic explained
└── ROADMAP.md                 # ← this file
```

---

## Day-by-Day Summary

| Day | Focus |
|-----|-------|
| 1 | Boilerplate setup, folder structure, DB connection |
| 2 | DB models, migrations, auth backend + frontend |
| 3 | Profile system: edit, view, proof signals, upload |
| 4 | AI Credibility Score: prompt, service, score widget |
| 5 | AI Appreciation: prompt, form, ratings display |
| 6 | Smart Search + Trust Leaderboard ✅ |
| 7 | Messaging flow + end-to-end hiring flow ✅ |
| 8 | Fake review detection (bonus) ✅ |
| 9 | Polish, seed data, deploy |
| 10 | Buffer, final testing, demo video |
