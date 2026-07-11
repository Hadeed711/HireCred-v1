# HireCred-v1 — Complete Project Guide

**Last updated: 2026-07-11**

> Single source of truth for architecture, features, file locations, and data flows.
> For quick local setup see `LOCAL_SETUP.md`. For testing see `TESTING_GUIDE.md`.
> For scaling design, million-user rationale, and the production stack see `INFRASTRUCTURE.md`.

---

## Project Overview

HireCred is an AI-powered professional trust platform. Candidates build credibility-scored profiles. Hirers discover and evaluate them with confidence. The core differentiator is the **HireCred Score** — an AI-computed 0–100 trust metric grounded in real evidence (proof signals, URL verification, 16-point authenticity heuristics).

---

## Directory Structure

```
hireCred-v1/
├── client/                      # React + TypeScript frontend
│   └── src/
│       ├── pages/
│       │   ├── Login.tsx             # lucide icons: Mail, Lock, Award, Sparkles, BadgeCheck
│       │   ├── Register.tsx          # lucide icons: User, Mail, Lock, Briefcase, Building2
│       │   ├── Dashboard.tsx
│       │   ├── ProfileEditor.tsx     # Skills tag input (no validation warnings), "Skills" label
│       │   ├── ProfileView.tsx       # Report modal, suspicious banner, ScoreWidget
│       │   ├── SearchPage.tsx
│       │   ├── Leaderboard.tsx       # lucide icons: Trophy, Medal, Star, ShieldCheck, Sprout
│       │   ├── Inbox.tsx             # lucide icons: ArrowLeft, MessageCircle, ImageIcon, SendHorizonal, Trash2
│       │   ├── AdminPanel.tsx        # admin reports + users dashboard
│       │   └── AdminLogin.tsx        # dedicated admin login page
│       ├── components/
│       │   ├── profile/
│       │   │   └── ScoreWidget.tsx   # score ring + Refresh button + warning sections
│       │   ├── validation/
│       │   │   └── ValidationWarningBanner.tsx
│       │   └── appreciation/
│       ├── lib/
│       │   ├── api.ts                # axios client + JWT interceptor
│       │   ├── types.ts              # all TypeScript interfaces
│       │   └── queryClient.ts
│       └── stores/
│           └── authStore.ts          # Zustand auth (user includes is_admin)
│
└── server/                      # FastAPI backend
    ├── main.py                  # app entrypoint + lifespan DB warmup + 503 exception handler + all router registration
    ├── requirements.txt         # includes pdfplumber==0.11.4 (installed)
    ├── alembic/versions/        # 6 migration files (latest: f6g7h8i9j012)
    └── src/
        ├── config.py            # Settings (DB, JWT, Ollama host/model, super_admin_emails)
        ├── database.py          # async SQLAlchemy engine (pool_pre_ping, pool_recycle=1800, ping_db() cold-start warmup)
        ├── models/
        │   ├── user.py          # User — id, uid, email, role, is_admin
        │   ├── profile.py       # Profile — bio, skills, experience, portfolio, cv_file_path
        │   ├── credibility_score.py  # CredibilityScore — score, is_suspicious, url_warnings, authenticity_flags
        │   ├── proof_signal.py
        │   ├── appreciation.py
        │   ├── message.py       # soft-delete, image_path
        │   └── report.py        # AccountReport — reporter, reported, reason, status, admin_note
        ├── routers/
        │   ├── auth.py          # /api/auth
        │   ├── profile.py       # /api/profile (PDF upload only, rescore endpoint, background scoring)
        │   ├── proof_signals.py # background scoring on all signal changes
        │   ├── appreciation.py
        │   ├── search.py
        │   ├── leaderboard.py
        │   ├── messages.py
        │   ├── validate.py      # /api/validate (url, skills, consistency)
        │   └── reports.py       # /api/reports + /api/admin (two routers in one file)
        ├── services/
        │   ├── task_manager.py         # background job queue: debounce, dedup, semaphore, GC-safe refs
        │   ├── credibility_service.py  # main scoring pipeline (background tasks)
        │   ├── cv_extractor.py         # pdfplumber helpers (not called by pipeline)
        │   ├── authenticity_service.py # 16-point fake/duplicate/sci-fi heuristics
        │   ├── url_checker.py          # reachability + page title (4s timeout)
        │   ├── validation_service.py   # format checks (non-blocking)
        │   ├── skill_validator.py      # skill domain check (backend only, no UI warnings)
        │   ├── search_service.py
        │   ├── fraud_service.py
        │   └── auth_service.py
        ├── ai/
        │   ├── ollama_client.py        # call_ollama (120s timeout), extract_json, health
        │   ├── credibility_prompt.py   # scoring prompt with evidence context
        │   ├── cv_prompt.py            # CV analysis helpers (not used in pipeline)
        │   ├── appreciation_prompt.py
        │   ├── fraud_prompt.py
        │   └── search_prompt.py
        └── schemas/
            ├── auth.py          # UserResponse (is_admin), TokenResponse
            └── profile.py       # ProfileUpdate, ProfileResponse, ScoreResponse
```

---

## Scoring Pipeline — Data Flow

```
Any write operation (profile save / CV upload / proof signal add or delete)
    ↓ data saved to DB
    ↓ HTTP response returned immediately (< 1s)
    ↓ task_manager.schedule_rescore(user_id)  ← managed background queue
      (2s debounce coalesces save bursts; max 2 concurrent pipelines;
       a save arriving mid-run queues exactly one follow-up run;
       strong task refs so runs can't be garbage-collected mid-flight)

Manual trigger: POST /api/profile/{id}/rescore  (rate-limited 5/min)
    ↓ task_manager.schedule_rescore(user_id)  ← same queue

Queue observability: GET /health/queue
    → {scheduled, coalesced, completed, failed, in_flight, dirty_pending}

compute_and_save_score():
    1. Load profile + proof signals from DB
    2. Check whether a CV file is uploaded (has_cv: bool) — no text extraction
    3. Authenticity heuristics (16 checks) → flags + penalty (0–60) + risk_level
    4. URL reachability checks (async parallel, 4s timeout) → URL warnings
    5. Build evidence context for LLM (profile data, has_cv, auth flags, URL warnings)
    6. Ollama scoring (120s timeout) → score (0–100) + strengths + risks + fraud_flags
       (fallback: rule_based_score if Ollama unavailable or returns bad JSON)
    7. Apply authenticity penalty (score − penalty, floor 0)
    8. Apply hard ceiling:
       - risk_level=high → score = min(score, 15)
       - risk_level=medium + penalty≥20 → score = min(score, 35)
    9. Apply URL warning penalty (−6 per warning, max −18)
   10. Upsert CredibilityScore row with all data
   11. Invalidate leaderboard cache
```

---

## HireCred Score Breakdown

**Ollama evaluates (6 criteria, 0–100):**
- Profile completeness: 0–18 pts
- Skill vs experience alignment: 0–22 pts
- Portfolio quality: 0–22 pts
- Writing clarity: 0–8 pts
- Proof signals: 0–18 pts
- CV quality: 0–12 pts (0 if no CV uploaded)

**AI instructions for low-scoring profiles:**
Any profile with sci-fi/fantasy content, fictional dates, joke skills, or impossible claims **must** score ≤ 15. Two such signals → must score ≤ 10 with fraud_flags.

**Post-LLM adjustments:**
- Authenticity penalty: −0 to −60 pts (16-point heuristic)
- Hard ceiling: high-risk → max 15; medium+penalty≥20 → max 35
- Dead URLs: −6 per warning, max −18
- Admin-approved report: −12 pts + is_suspicious = true

---

## CV Processing

- **Upload:** PDF stored at `server/uploads/cv/{user_id}.pdf`
- **No analysis runs:** pdfplumber, Ollama CV analysis, and CV↔profile matching are all removed from the scoring pipeline
- **Scoring signal:** LLM receives `"CV uploaded: Yes/No"` — presence still contributes to CV quality criterion

---

## URL Verification

Per URL:
1. Check trusted domains (github.com, linkedin.com, etc.) → auto-pass, no HTTP check
2. HEAD request → if fails, try GET streaming
3. Extract `<title>` from first 10 KB of HTML
4. Match title against dead-page patterns: "domain for sale", "404 not found", "coming soon", "parked domain", "account suspended", "welcome to nginx", etc.

Timeout: 4 seconds per request, max 5 concurrent checks (semaphore). One shared
HTTP connection pool (no per-check client churn). Results cached in a bounded
LRU (512 entries, 5-minute TTL) so the cache can't grow into a memory leak.

---

## Authenticity Detection (16 Heuristics)

| Check | Penalty |
|-------|---------|
| Suspicious name (test/dummy/John Doe/admin) | −15 |
| Disposable email domain | −20 |
| Bio boilerplate phrases (guru, ninja, wizard, etc.) | −15 |
| Bio under 15 words | −8 |
| Sci-fi/fantasy phrases (holographic, alien startup, intergalactic, etc.) | −10 or −20 |
| Fictional location (Mars Colony, Moon Base, Sector N, planet names) | −15 |
| Absurd professional title (Pixel Wizard, Supreme Overlord, Galactic Designer) | −12 |
| Impossible numeric claims (999 years of experience, 5000% on Jupiter) | −15 |
| Far-future experience dates (year > current+2) | −18 per entry |
| Fictional company names (Galaxy Banana Corp, Moonlight Sandwich Studio) | −15 |
| Joke/non-professional skills (Coffee Drinking, Meme Design, Fake Skill 101) | −8 or −18 |
| Duplicate experience descriptions (copy-paste within same profile) | −12 |
| All portfolio URLs same domain | −12 |
| Identical portfolio descriptions | −12 |
| Skill list > 25 items | −8 |
| >60% generic non-technical skills | −8 |
| Tech title with no technical skills | −15 |

**Penalty cap:** 60. **Risk levels:** none (0) / low (1–10) / medium (11–28) / high (>28).  
Medium or high → `is_suspicious = true`. High → score hard-capped at 15.

---

## Report System

**Hirer reports candidate:**
- `POST /api/reports` with reason + optional evidence
- Cannot report yourself; no duplicate pending reports from same reporter

**Admin resolves:**
- `PUT /api/admin/reports/{id}/approve` → suspicious tag + −12 score (background task)
- `PUT /api/admin/reports/{id}/reject` → no effect

**Admin access:**
- User must have `is_admin = true`
- Login at `/admin/login`; panel at `/admin`
- Set via DB: `UPDATE users SET is_admin = true WHERE email = '...'`
- Or API (requires allowlisted super admin JWT): `PUT /api/admin/users/{id}/set-admin?is_admin=true`

---

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/auth/register` | — | Register |
| POST | `/api/auth/login` | — | Login → JWT |
| GET | `/api/auth/me` | JWT | Current user + is_admin |
| GET | `/api/profile/{uid}` | optional | View profile |
| PUT | `/api/profile/{id}` | JWT | Update profile (non-blocking, background scoring) |
| GET | `/api/profile/{id}/score` | — | Full score + all warning fields |
| POST | `/api/profile/{id}/cv` | JWT | Upload CV (PDF only, max 5MB, no analysis) |
| DELETE | `/api/profile/{id}/cv` | JWT | Delete CV |
| POST | `/api/profile/{id}/rescore` | JWT | Manually trigger score recomputation |
| POST | `/api/profile/{id}/signals` | JWT | Add proof signal (background scoring) |
| DELETE | `/api/profile/{id}/signals/{id}` | JWT | Remove signal (background scoring) |
| POST | `/api/profile/{id}/signals/upload` | JWT | Upload screenshot signal |
| POST | `/api/appreciation` | JWT | Submit appreciation |
| GET | `/api/appreciation/{id}` | — | Get appreciations |
| POST | `/api/search` | JWT | Intent-based search |
| GET | `/api/leaderboard` | — | Ranked candidates (cached 2 min) |
| POST | `/api/validate/url` | — | URL reachability + title |
| POST | `/api/validate/skills` | — | Skill domain check |
| POST | `/api/validate/consistency` | — | Title vs skills check |
| POST | `/api/reports` | JWT | Submit report |
| GET | `/api/reports/my` | JWT | My submitted reports |
| GET | `/api/admin/reports` | JWT+Admin | All reports |
| PUT | `/api/admin/reports/{id}/approve` | JWT+Admin | Approve report |
| PUT | `/api/admin/reports/{id}/reject` | JWT+Admin | Reject report |
| GET | `/api/admin/users` | JWT+Admin | All users |
| PUT | `/api/admin/users/{id}/set-admin` | JWT+Admin | Promote/demote admin |
| GET | `/health` | — | Server health |
| GET | `/health/ai` | — | Ollama health |

---

## Score API Response

```json
{
  "score": 74,
  "strengths": ["Has detailed work experience", "GitHub proof signal added"],
  "risks": ["Bio is short", "URL for portfolio item not reachable"],
  "fraud_risk": "low",
  "computed_at": "2026-05-18T10:00:00",
  "is_suspicious": false,
  "authenticity_flags": [],
  "cv_match_score": null,
  "cv_match_warnings": [],
  "url_warnings": []
}
```

> `cv_match_score` and `cv_match_warnings` are always `null` / `[]` — CV text analysis removed. The LLM still scores CV quality based on whether a file is uploaded.

---

## Non-Blocking Validation

`PUT /api/profile/{id}` **never returns 422**.  
Warnings are in the response body as `_warnings: string[]`.  
Frontend displays them as toasts/banners. Score is penalized by the same issues independently.

---

## Database Schema

| Table | Key Columns |
|-------|-------------|
| `users` | id, uid, email, hashed_password, role, is_admin, is_active |
| `profiles` | user_id, bio, title, location, skills (JSONB), experience (JSONB), portfolio (JSONB), cv_file_path, cv_analysis (JSONB, unused) |
| `credibility_scores` | user_id, score, strengths, risks, fraud_risk, fraud_flags, is_suspicious, authenticity_flags, cv_match_score (null), cv_match_warnings ([]), url_warnings |
| `proof_signals` | profile_id, signal_type, title, url, file_path, description |
| `appreciations` | to_user_id, from_user_id, skill_rating, communication_rating, reliability_rating, summary, fraud_flagged |
| `messages` | sender_id, receiver_id, conversation_id, content, image_path, is_deleted, is_read |
| `account_reports` | reporter_id, reported_user_id, reason, evidence_text, status, admin_note, resolved_at |

---

## Performance Notes

| Setting | Value | Reason |
|---------|-------|--------|
| DB `pool_pre_ping` | True | Prevents "connection is closed" on Neon serverless |
| DB `pool_recycle` | 1800s | Refreshes idle connections every 30 min |
| Ollama timeout | 120s | Enough for qwen2.5:3b on CPU (1–3 tok/s × 200 tokens); rule-based fallback if exceeded |
| Ollama HTTP client | shared pool | One persistent connection instead of a handshake per LLM call |
| URL check timeout | 4s | Faster failure detection per URL |
| URL check cache | LRU 512 / 5 min | Bounded — cannot leak memory on a long-running server |
| Score tasks | `task_manager.schedule_rescore()` | Debounced + deduplicated + semaphore(2); never blocks HTTP response; GC-safe |
| Appreciation follow-ups | background | Rescore + fraud analysis (2 LLM pipelines) no longer run inside the POST request |
| Leaderboard | SQL-ranked, `LIMIT 20` | Ranking computed in PostgreSQL; only 20 rows ever cross the wire (was: all candidates loaded into Python) |
| Leaderboard cache | 2 min + lock | Avoids repeated heavy query and cache-stampede |
| Profile views | atomic SQL increment | `SET views = views + 1` — no read-modify-write race |
| Rate limits | search 30/min, rescore 5/min, appreciation 10/min | Protects the LLM tier from being a DoS vector |

> Deep-dive on every one of these decisions, the 1M-user scaling path, and
> production stack recommendations: see **`INFRASTRUCTURE.md`**.
