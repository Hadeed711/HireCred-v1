# HireCred-v1 — Functionality Pipeline Reference

**Last updated: 2026-06-01**

Every feature documented end-to-end: frontend → API → router → service → model/DB → response.
File names are exact paths relative to repo root. Purpose of each step is explained inline.

---

## Plain English Guide — What This App Actually Does

> Read this section if you're non-technical or want the big picture before diving into details.

**HireCred is a trust platform for hiring.** Think of it like a verified LinkedIn — but instead of just taking candidates at their word, the system actually checks whether their profile holds up.

Here's what happens when you use it:

---

### "I'm a candidate — what does HireCred do for me?"

1. **You create a profile** — your bio, skills, job history, portfolio links, and proof signals (GitHub, screenshots, client references). You can also upload your CV as a PDF.

2. **The system scores you automatically** — a number from 0 to 100 called the **HireCred Score**. This score is not based on your word; it's based on:
   - Does your profile look real, complete, and consistent?
   - Do your links actually work?
   - Does your claimed experience match your listed skills?
   - Have clients written you genuine appreciations?

3. **Scoring happens in the background** — you save your profile and it responds in under a second. The score is computed behind the scenes (usually within 5–30 seconds) and appears automatically on your profile.

4. **Clients leave appreciations** — when a client writes feedback, an AI reads it and extracts structured ratings for skill, communication, and reliability. These feed into your score.

5. **Your score updates when things change** — if you add a proof signal, upload a CV, or get a new appreciation, the score is recomputed automatically.

---

### "I'm a hirer — how do I find good candidates?"

1. **Search in plain English** — type something like "reliable React developer with startup experience." The system understands what you mean, extracts the skills and role you're looking for, and runs an intelligent database search.

2. **Results are ranked by trust** — candidates with higher HireCred Scores, better appreciation ratings, and more proof signals appear first. Not just whoever filled in the most fields.

3. **You can see what the AI found suspicious** — each profile shows authenticity flags (e.g., "bio under 15 words", "dead portfolio link") and URL warnings so you know the score is honest.

4. **You can report a profile** — if something looks wrong, you can report it. Admins review reports and can mark a profile as suspicious, which caps its score.

5. **Trust Leaderboard** — the top 20 most trustworthy candidates are ranked on a leaderboard updated every 2 minutes.

---

### "What checks does the system do automatically?"

Every time a profile is saved, the system runs **16 authenticity checks** in the background:

| What it looks for | Example that triggers it |
|-------------------|--------------------------|
| Fake-looking name | "Test User", "Admin123", "John Doe" |
| Throwaway email address | mailinator.com, guerrillamail.com |
| Generic bio buzzwords | "guru", "ninja", "rockstar", "unicorn" |
| Bio that's too short | Less than 15 words |
| Science fiction content | "Alien startup", "intergalactic marketing firm" |
| Fictional location | "Mars Colony", "Moon Base Alpha", "Sector 9" |
| Absurd job title | "Supreme Overlord of Code", "Ultra Creative Pixel Wizard" |
| Impossible numbers | "999 years of experience", "5000% sales increase" |
| Future experience dates | End year listed as 3020, 2099, etc. |
| Made-up company names | "Galaxy Banana Corp", "Moonlight Sandwich Studio" |
| Joke skills | "Coffee Drinking", "Meme Design", "Nap Champion" |
| Copy-pasted job descriptions | Same text used for multiple roles |
| All portfolio links on one domain | Suggests self-hosting fake projects |
| Portfolio descriptions are identical | Copy-paste detected |
| Too many skills listed | More than 25 is suspicious |
| Mostly non-technical skills | "Breathing", "Walking", "Looking busy" |
| Tech title but no tech skills | Says "developer" but lists no coding skills |

Each check applies a penalty. High penalty → score is capped low, profile is marked suspicious.

---

### "What happens when I click a portfolio link in my profile?"

The system automatically checks every URL you add:

1. **Well-known sites** (GitHub, LinkedIn, etc.) are trusted and not checked — no network request needed.
2. **Unknown URLs** get a 4-second HTTP request. If the page doesn't respond → flagged.
3. **Even if the page loads**, the system reads the page title. If it says things like "Domain for Sale", "404 Not Found", "Coming Soon", or "Parked Domain" → flagged as dead/fake.
4. **Each bad URL** costs 6 points off your score (max −18 total).

---

### "What is the database and why does the app sometimes take a second to start?"

The database is hosted on **Neon** — a serverless PostgreSQL service. On the free plan, the database **goes to sleep** after a period of inactivity to save resources.

When you restart the server, the app now **wakes the database up before accepting requests** — it sends a test query and retries up to 6 times with increasing delays. This means the first few seconds after startup may show warmup logs, but by the time any real user hits the API, the database is ready.

If the database is still waking up and a request arrives anyway, the API returns a clear **"503 — Database temporarily unavailable"** message instead of a confusing 500 crash.

---

## Table of Contents

1. [Authentication (Register / Login / Me)](#1-authentication)
2. [Profile — View](#2-profile-view)
3. [Profile — Edit](#3-profile-edit)
4. [CV Upload & Delete](#4-cv-upload--delete)
5. [Proof Signals (Add / Remove)](#5-proof-signals)
6. [HireCred Score — Background Computation](#6-hirecred-score-background-computation)
7. [HireCred Score — Manual Refresh](#7-hirecred-score-manual-refresh)
8. [Authenticity Heuristic Detection (16-point)](#8-authenticity-heuristic-detection)
9. [URL Verification (Dead-link & Parked-page)](#9-url-verification)
10. [Intent-Based Search (SQL-first, scales to 1M+)](#10-intent-based-search)
11. [Trust Leaderboard](#11-trust-leaderboard)
12. [Appreciations + Fraud Detection](#12-appreciations--fraud-detection)
13. [Messaging (Inbox / Conversation Threads)](#13-messaging)
14. [Report Account](#14-report-account)
15. [Admin Panel (Reports + User Management)](#15-admin-panel)
16. [File Serving (CV + Message Images)](#16-file-serving)
17. [Validation Utilities (URL / Skills / Consistency)](#17-validation-utilities)
18. [Supporting Infrastructure](#18-supporting-infrastructure)

---

## 1. Authentication

### Register

| Step | File | What It Does |
|------|------|-------------|
| Form UI | `client/src/pages/Register.tsx` | Collects email, password, role (candidate/client). Submits via `api.post('/api/auth/register')` |
| HTTP client | `client/src/lib/api.ts` | Axios instance. `getApiError()` normalizes error messages from `detail` field |
| Rate limiter | `server/src/rate_limiter.py` → `server/src/routers/auth.py` | `@limiter.limit("5/minute")` blocks abuse before the endpoint body runs |
| Router | `server/src/routers/auth.py → register()` | Validates request body, calls `auth_service.create_user()` |
| Service | `server/src/services/auth_service.py → create_user()` | Checks email uniqueness, bcrypt-hashes password (`bcrypt.hashpw`), creates `User` + empty `Profile` row |
| Model | `server/src/models/user.py` (User), `server/src/models/profile.py` (Profile) | SQLAlchemy ORM — `User.email`, `User.hashed_password`, `User.role`, `User.uid` (auto-sequence) |
| DB write | Neon PostgreSQL — `users` + `profiles` tables | Transactional insert; uid sequence assigned |
| Response | `{access_token, user: {id, email, role, uid, is_admin}}` | JWT returned immediately — user is logged in after register without a separate login call |

### Login

| Step | File | What It Does |
|------|------|-------------|
| Form UI | `client/src/pages/Login.tsx` | Email + password form. On success stores JWT in `authStore` |
| Auth state | `client/src/stores/authStore.ts` | Zustand store. `setToken(jwt)` saves to `localStorage`. `useAuth()` hook exposes `token`, `user`, `logout()` |
| Rate limiter | `server/src/rate_limiter.py` → `server/src/routers/auth.py` | `@limiter.limit("10/minute")` — stricter limit than register |
| Router | `server/src/routers/auth.py → login()` | Calls `auth_service.authenticate_user()`, generates JWT |
| Service | `server/src/services/auth_service.py → authenticate_user()` | `bcrypt.checkpw` comparison; raises 401 on mismatch |
| JWT | `server/src/routers/auth.py` | `python-jose` HS256 token, 7-day expiry, sub = `user.id` |
| Response | `{access_token, token_type}` | Stored in localStorage via authStore |

### Me (current user)

| Step | File | What It Does |
|------|------|-------------|
| Called on app load | `client/src/stores/authStore.ts` | On startup: `api.get('/api/auth/me')` with stored JWT to rehydrate user state |
| Router | `server/src/routers/auth.py → get_me()` | Decodes JWT, loads User from DB, returns `{id, email, role, uid, is_admin}` |
| Route guards | `client/src/components/ProtectedRoute.tsx`, `client/src/components/AdminRoute.tsx` | `ProtectedRoute` blocks unauthenticated. `AdminRoute` additionally checks `user.is_admin` |

---

## 2. Profile — View

| Step | File | What It Does |
|------|------|-------------|
| Page | `client/src/pages/ProfileView.tsx` | Public profile page. URL: `/profile/:uid`. Fetches profile, score, appreciations |
| API calls | `client/src/lib/api.ts` | `GET /api/profile/{uid}` + `GET /api/profile/{id}/score` + `GET /api/appreciation/{id}` |
| Router | `server/src/routers/profile.py → get_profile()` | Loads User by uid, loads Profile with joined User. Calls `_build_profile_response()` |
| Email guard | `server/src/routers/profile.py → _build_profile_response()` | `owner_email` only returned if `is_owner=True`; null for all other viewers — prevents email enumeration |
| Suspicious badge | `client/src/pages/ProfileView.tsx` | If `score.is_suspicious == true`, renders "⚠ Suspicious Account" warning badge |
| Score display | `client/src/components/profile/ScoreWidget.tsx` | Shows score 0–100, strengths, risks, authenticity flags, URL warnings. Refresh button for owner |
| Appreciation section | `client/src/components/appreciation/AppreciationSection.tsx` | Renders skill/comm/reliability ratings. `AppreciationModal.tsx` opens submit form for clients |
| Report button | `client/src/pages/ProfileView.tsx` | Shown to authenticated non-owners. Opens modal → `POST /api/reports` |
| DB | `users`, `profiles`, `credibility_scores`, `appreciations` tables | All reads. No writes on view |

---

## 3. Profile — Edit

| Step | File | What It Does |
|------|------|-------------|
| Page | `client/src/pages/ProfileEditor.tsx` | Full editor: bio, title, location, skills tag input, experience entries, portfolio items |
| Skills UI | `client/src/components/SkillsTagInput.tsx` | Tag-style input. No validation warnings shown — any skill accepted |
| Validation banner | `client/src/components/validation/ValidationWarningBanner.tsx` | Shows server-returned `warnings[]` as non-blocking alerts (never prevents save) |
| API call | `client/src/lib/api.ts` | `PUT /api/profile/{id}` with full profile body |
| Router | `server/src/routers/profile.py → update_profile()` | Validates ownership (JWT user must own profile). Updates profile fields. Launches background score task |
| Background task | `server/src/routers/profile.py` | `asyncio.create_task(compute_score_background(profile_id, db_session))` — does NOT await it; HTTP response returns immediately |
| Validation service | `server/src/services/validation_service.py` | Checks date overlaps (`_normalize_date` pads months with `zfill(2)` for correct lexicographic sort), URL format, skills consistency. Returns `warnings[]` only — never raises 422 |
| Score trigger | `server/src/services/credibility_service.py` | Background task runs full pipeline: authenticity → URL checks → LLM scoring → DB upsert |
| DB write | `profiles` table | SQLAlchemy `session.merge()` on Profile model |
| Response | `{profile, warnings[]}` | Returns immediately (< 1s). Score updates asynchronously in background |

---

## 4. CV Upload & Delete

### Upload

| Step | File | What It Does |
|------|------|-------------|
| Client validation | `client/src/pages/ProfileEditor.tsx → handleCvUpload()` | Checks `file.size > 5MB` and `file.type !== 'application/pdf'` BEFORE sending. Shows toast error and aborts if invalid |
| API call | `client/src/lib/api.ts` | `POST /api/profile/{id}/cv` — multipart form-data |
| Router | `server/src/routers/profile.py → upload_cv()` | Validates ownership, MIME type (`application/pdf`), size (< 5 MB). Saves file, triggers background rescore |
| File storage | `server/uploads/cv/{user_id}.pdf` | Simple filesystem write. One file per user (overwrites previous) |
| Score signal | `server/src/services/credibility_service.py` | CV presence passed to LLM as binary string "CV uploaded: Yes/No". Contributes up to 12 pts |
| DB write | `profiles.cv_file_path` | Stores path string. `cv_analysis` field exists but is always null (no text extraction) |

### Delete

| Step | File | What It Does |
|------|------|-------------|
| Confirmation | `client/src/pages/ProfileEditor.tsx → handleCvRemove()` | `window.confirm()` dialog before proceeding — prevents accidental deletion |
| API call | `client/src/lib/api.ts` | `DELETE /api/profile/{id}/cv` |
| Router | `server/src/routers/profile.py → delete_cv()` | Deletes file from disk, clears `cv_file_path` in DB, triggers background rescore |

---

## 5. Proof Signals

Proof signals are verifiable links or screenshots: GitHub repos, portfolio links, client reference URLs, screenshot images.

### Add Signal

| Step | File | What It Does |
|------|------|-------------|
| UI | `client/src/pages/ProfileEditor.tsx` | Signal type selector + URL/file input. Screenshot uploads validated: size < 5 MB, MIME must be `image/*` |
| API call | `client/src/lib/api.ts` | `POST /api/profile/{id}/signals` — multipart if file, JSON if URL |
| Router | `server/src/routers/proof_signals.py → add_signal()` | Validates ownership, saves signal record, triggers background rescore |
| Model | `server/src/models/proof_signal.py` | `ProofSignal(profile_id, signal_type, title, url, file_path)` |
| URL check (background) | `server/src/services/url_checker.py` | If URL provided, reachability + page title check runs during next score computation |
| DB write | `proof_signals` table | Indexed on `profile_id` (added in migration `a1b2c3d4e5f6`) |

### Remove Signal

| Step | File | What It Does |
|------|------|-------------|
| API call | `client/src/lib/api.ts` | `DELETE /api/profile/{id}/signals/{signal_id}` |
| Router | `server/src/routers/proof_signals.py → remove_signal()` | Ownership check, deletes record + file if screenshot, triggers background rescore |

---

## 6. HireCred Score — Background Computation

This pipeline runs every time a profile is saved, a CV is uploaded/deleted, or a proof signal changes. It always runs asynchronously — the HTTP response is already returned to the client before this starts.

```
Profile save / CV change / Signal change
        ↓
asyncio.create_task(compute_score_background())
        ↓
credibility_service.py → compute_and_save_score()
        ↓
  ┌─────────────────────────────────────────┐
  │ 1. Load profile + signals from DB       │
  │ 2. Run authenticity_service (sync)      │
  │ 3. Run URL checks (concurrent, capped)  │
  │ 4. Build LLM prompt                     │
  │ 5. Call Ollama LLM (timeout 10s)        │
  │ 6. Parse LLM output                     │
  │ 7. Apply post-LLM adjustments           │
  │ 8. Atomic upsert to DB                  │
  └─────────────────────────────────────────┘
```

### Detailed Steps

| Step | File | Logic |
|------|------|-------|
| Entry point | `server/src/services/credibility_service.py → compute_and_save_score()` | Orchestrates all sub-steps |
| Load data | `server/src/services/credibility_service.py` | Async DB query: Profile + ProofSignals joined |
| Authenticity | `server/src/services/authenticity_service.py → run_all_checks()` | 16 heuristic checks (see §8). Returns `penalty` and `flags[]` |
| URL checks | `server/src/services/url_checker.py → check_url()` | Semaphore `_URL_CHECK_SEM = Semaphore(5)` caps concurrent checks at 5. `verify=True` enforces SSL. 4s timeout per URL |
| LLM prompt | `server/src/ai/credibility_prompt.py → build_prompt()` | Injects: bio, title, skills, experience, portfolio, proof signals, CV present (yes/no), authenticity flags, URL warnings. Instructs LLM to score 6 criteria |
| LLM call | `server/src/ai/ollama_client.py → generate()` | `asyncio.wait_for(…, timeout=10.0)` — falls back to rule-based if Ollama times out or is unavailable |
| Rule-based fallback | `server/src/services/credibility_service.py → _fallback_score()` | Heuristic scoring when LLM unavailable: counts fields, signals, skills |
| Parse output | `server/src/services/credibility_service.py` | Extracts JSON from LLM response text; ignores surrounding prose |
| Post-LLM adjustments | `server/src/services/credibility_service.py` | Authenticity penalty (−0 to −60), URL dead-link penalty (−6/link, max −18), admin report penalty (−12 if `is_suspicious`) |
| Score ceilings | `server/src/services/credibility_service.py` | `risk_level == high` → max 15; `risk_level == medium` + penalty ≥ 20 → max 35 |
| Atomic upsert | `server/src/services/credibility_service.py` | `pg_insert(CredibilityScore).on_conflict_do_update(index_elements=["user_id"])` — no race condition |
| Model | `server/src/models/credibility_score.py` | `CredibilityScore(user_id, score, strengths, risks, fraud_risk, is_suspicious, authenticity_flags, url_warnings)` |
| DB | `credibility_scores` table | Indexed on `score` and `is_suspicious` (migration `a1b2c3d4e5f6`) |

### Scoring Criteria (LLM-weighted)

| Criterion | Max Points |
|-----------|-----------|
| Profile completeness | 18 |
| Skill vs experience alignment | 22 |
| Portfolio quality | 22 |
| Writing clarity | 8 |
| Proof signals | 18 |
| CV quality (0 if no CV) | 12 |
| **Total** | **100** |

---

## 7. HireCred Score — Manual Refresh

| Step | File | What It Does |
|------|------|-------------|
| UI | `client/src/components/profile/ScoreWidget.tsx` | "Refresh Score" button, shown only to profile owner |
| API call | `client/src/lib/api.ts` | `POST /api/profile/{id}/rescore` |
| Router | `server/src/routers/profile.py → rescore_profile()` | Ownership check, launches `asyncio.create_task(compute_score_background(...))` |
| Response | `{message: "Score recomputation started"}` | Returns instantly. ScoreWidget polls `GET /api/profile/{id}/score` every few seconds via TanStack Query |

---

## 8. Authenticity Heuristic Detection

Runs synchronously inside the background score computation. No separate API call. All 16 checks run on every score computation.

| File | `server/src/services/authenticity_service.py` |
|------|------|

| Check | Trigger | Penalty |
|-------|---------|---------|
| Suspicious name | name contains "test", "dummy", "john doe", "admin" | −15 |
| Disposable email | domain in blocklist (mailinator, guerrilla, temp-mail, etc.) | −20 |
| Bio boilerplate | "guru", "ninja", "wizard", "rockstar", "unicorn" in bio | −15 |
| Short bio | bio word count < 15 | −8 |
| Sci-fi/fantasy content | "alien", "intergalactic", "holographic", "galactic empire" in any field | −10 to −20 |
| Fictional location | "Mars Colony", "Moon Base", "Sector 9", planet names | −15 |
| Absurd title | "Ultra Creative Pixel Wizard", "Supreme Overlord" | −12 |
| Impossible numbers | "999 years of experience", "5000% increase" | −15 |
| Far-future dates | experience end year > current year + 2 | −18 per entry |
| Fictional companies | "Galaxy Banana Corp", "Moonlight Sandwich Studio" | −15 |
| Joke skills | "Coffee Drinking", "Meme Design", "Fake Skill 101" | −8 to −18 |
| Duplicate experience | copy-pasted description across entries | −12 |
| Same-domain portfolio | all portfolio URLs share one domain | −12 |
| Identical portfolio descriptions | description text duplicated | −12 |
| Skill list bloat | > 25 skills listed | −8 |
| Generic skill ratio | > 60% non-technical skills | −8 |
| Tech title / no tech skills | title says "developer/engineer" but skills list has none | −15 |

**Total cap:** −60. `risk_level` computed: penalty 0–19 = low, 20–39 = medium, 40+ = high. Medium/high → `is_suspicious = true`.

**Output:** `{"penalty": int, "flags": ["flag description", ...], "risk_level": "low|medium|high"}`

---

## 9. URL Verification

Runs as part of background score computation. Also available standalone via `POST /api/validate/url`.

| Step | File | Logic |
|------|------|-------|
| Entry | `server/src/services/credibility_service.py` | Collects all portfolio URLs + proof signal URLs. Passes to URL checker with semaphore |
| Trusted domain skip | `server/src/services/url_checker.py` | `github.com`, `linkedin.com`, `stackoverflow.com`, etc. → auto-pass, no HTTP request |
| HTTP check | `server/src/services/url_checker.py → check_url()` | `httpx.AsyncClient(verify=True, max_redirects=10)`. HEAD then GET. 4s timeout |
| Title extraction | `server/src/services/url_checker.py` | Parses `<title>` tag from HTML response body |
| Dead-page detection | `server/src/services/url_checker.py` | Title containing "domain for sale", "404", "coming soon", "parked domain", "buy this domain" → flagged even if HTTP 200 |
| SSL errors | `server/src/services/url_checker.py` | `httpx.ConnectError`, `httpx.ConnectTimeout`, `httpx.RemoteProtocolError` caught → returns `{reachable: false, reason: "SSL/connection error"}` |
| Score impact | `server/src/services/credibility_service.py` | −6 pts per dead/parked URL, max −18 total |
| Standalone API | `server/src/routers/validate.py → validate_url()` | Returns `{reachable, title, is_suspicious, reason}` |

---

## 10. Intent-Based Search

SQL-first architecture. Never loads more than 200 rows into Python memory. Scales to 1M+ profiles.

### Complete Pipeline

```
User types query
        ↓
client/src/pages/SearchPage.tsx
  → validates min 2 chars (toast error if too short)
  → POST /api/search  {query: "reliable React developer"}
        ↓
server/src/routers/search.py → search()
  → validates: len(q) < 2 → 400, len(q) > 500 → 400
  → calls search_service.search_candidates(query, db)
        ↓
server/src/services/search_service.py → search_candidates()
  → parse_search_intent() → extracts roles, skills, attributes
  → build tsquery terms from parsed intent + expansions
        ↓
  Stage 1: _fts_query()
    → queries Profile.search_tsv (stored TSVECTOR column)
    → WHERE search_tsv @@ tsquery  (uses plain GIN index ix_profiles_fts — O(log n))
    → ORDER BY ts_rank DESC
    → LIMIT 200
        ↓
  If 0 results: Stage 2: _fuzzy_query()
    → pg_trgm: similarity(Profile.title, query) > 0.15
    → handles typos: "develoer" → "developer"
    → LIMIT 50
        ↓
  If 0 results: Stage 3: _ilike_query()
    → ILIKE on title/bio for each search term
    → LIMIT 100
        ↓
  If still 0: return {results: [], message: "No candidates found..."}
  NO random fallback — empty means empty
        ↓
  _load_appreciation_map(candidate_ids)
    → single batched query: WHERE to_user_id IN (...) GROUP BY to_user_id
    → builds dict {user_id: {count, avg_skill, avg_comm, avg_reliability}}
        ↓
  Precision gate (loose/unrecognized queries only):
    → triggers when the query yielded NO profession and NO recognized skill,
      so the words were extracted as a last resort (e.g. "a space explorer")
    → the FTS AND-filter can match scattered, coincidental bio words, so a
      candidate is kept ONLY if a loose term appears in its title/skills,
      or the full query phrase appears intact in its bio
    → drops the "matched only on prose coincidence" false positives
    → if the gate empties the set → return the same "No candidates found" message
        ↓
  Python ranking on ≤200 pre-filtered rows:
    → 40% credibility score
    → 35% skill match (overlap between parsed skills + profile skills)
    → 15% appreciation average
    → 10% profile views
    → + up to 12 pts textual-relevance bonus (per-batch normalized ts_rank)
      so a genuinely on-topic profile out-ranks one that only shares a score
    → slice to top 20 (or 10 for domain tier)
        ↓
Response: {parsed, results[], search_tier_used, message?}
```

### Key Files

| File | Role |
|------|------|
| `client/src/pages/SearchPage.tsx` | Search form, result cards, min-length validation |
| `client/src/lib/api.ts` | `POST /api/search` call |
| `server/src/routers/search.py` | Length validation, calls service |
| `server/src/services/search_service.py` | Full search logic: parse → SQL → rank |
| `server/src/ai/search_prompt.py` | Ollama prompt for intent parsing (role/skills/attributes extraction) |
| `server/src/ai/ollama_client.py` | Ollama HTTP client wrapper |
| `server/alembic/versions/b3c4d5e6f7a8_add_fulltext_search.py` | Enables pg_trgm; adds `search_tsv` stored column, `profiles_search_tsv_trigger`, plain GIN index on `search_tsv`, trigram GIN on `title` |
| `server/src/models/profile.py` | `Profile.search_tsv` mapped as `TSVECTOR` column |

### Database Indexes Used

| Index | Type | Supports |
|-------|------|----------|
| `ix_profiles_fts` | Plain GIN on `search_tsv` column | Full-text search `search_tsv @@ tsquery` |
| `ix_profiles_title_trgm` | GIN (gin_trgm_ops) on `title` | Fuzzy `similarity()` queries |
| `ix_appreciations_to_user_id` | BTree | Appreciation batch aggregation |
| `ix_credibility_scores_score` | BTree | Score ordering in ranking |

---

## 11. Trust Leaderboard

Top 20 candidates ranked by combined metric. Cached 2 minutes with stampede protection.

| Step | File | Logic |
|------|------|-------|
| Page | `client/src/pages/Leaderboard.tsx` | Fetches `GET /api/leaderboard`. Renders ranked cards |
| Router | `server/src/routers/leaderboard.py → get_leaderboard()` | Checks `_cache` (module-level dict). Returns cached if fresh |
| Cache lock | `server/src/routers/leaderboard.py` | `_cache_lock = asyncio.Lock()`. Double-check after acquiring lock (prevents stampede: only one request rebuilds cache) |
| DB query | `server/src/routers/leaderboard.py` | `SELECT users JOIN profiles JOIN credibility_scores WHERE role=candidate AND is_active AND NOT is_suspicious (or halved weight for medium risk) ORDER BY score DESC` |
| Appreciation batch | `server/src/routers/leaderboard.py` | Single query: `WHERE to_user_id IN (all_ids) GROUP BY to_user_id` → builds `appr_map` dict. O(1) lookup per user in ranking loop |
| Ranking formula | `server/src/routers/leaderboard.py` | `0.5 * score + 0.3 * avg_appreciation + 0.2 * proof_signal_count` |
| Fraud exclusion | `server/src/routers/leaderboard.py` | `risk_level == high` → excluded entirely. `risk_level == medium` → appreciation weight halved |
| Cache TTL | `server/src/routers/leaderboard.py` | `_cache_ttl = 120` seconds. Stale cache is rebuilt atomically |

---

## 12. Appreciations + Fraud Detection

### Submit Appreciation

| Step | File | Logic |
|------|------|-------|
| UI | `client/src/components/appreciation/AppreciationModal.tsx` | Open from profile. Freeform text input |
| Auth guard | `client/src/components/appreciation/AppreciationSection.tsx` | Only shown to authenticated `client` role users; not own profile |
| API call | `client/src/lib/api.ts` | `POST /api/appreciation` with `{to_user_id, content}` |
| Router | `server/src/routers/appreciation.py → submit_appreciation()` | Validates not self-appreciation, creates record, triggers AI extraction |
| AI extraction | `server/src/ai/appreciation_prompt.py → build_prompt()` | Prompt asks LLM to extract `skill_rating`, `communication_rating`, `reliability_rating` (0–10) + one-sentence summary |
| LLM call | `server/src/ai/ollama_client.py` | Ollama call with qwen2.5:3b. Timeout handled |
| Model | `server/src/models/appreciation.py` | `Appreciation(to_user_id, from_user_id, skill_rating, communication_rating, reliability_rating, summary, raw_content)` |
| Fraud trigger | `server/src/routers/appreciation.py` | After save, triggers `fraud_service.analyze_appreciations(to_user_id, db)` as background task |

### Fraud Detection

| Step | File | Logic |
|------|------|-------|
| Entry | `server/src/services/fraud_service.py → analyze_appreciations()` | Loads all appreciations for that user |
| AI prompt | `server/src/ai/fraud_prompt.py → build_prompt()` | Feeds all appreciation texts to LLM: "Are these suspiciously generic, uniform, or templated?" |
| LLM call | `server/src/ai/ollama_client.py` | Returns `{fraud_risk: "low|medium|high", flags: [...]}` |
| Failure default | `server/src/services/fraud_service.py` | On any exception: defaults to `medium` risk + flag "AI analysis unavailable — manual review recommended" (conservative, not silently safe) |
| Score impact | `server/src/services/credibility_service.py` | Fraud risk feeds into `risk_level` which controls score ceiling (high → max 15, medium+penalty → max 35) |
| Suspicious flag | `server/src/models/credibility_score.py` | `is_suspicious = True` when medium/high fraud risk |

---

## 13. Messaging

Simple conversation threads between any two authenticated users. Supports text and image attachments.

### Send Message

| Step | File | Logic |
|------|------|-------|
| UI | `client/src/pages/Inbox.tsx` | Conversation list (left panel) + message thread (right panel). Polling every 3–5s (paused when tab hidden) |
| Tab-aware polling | `client/src/pages/Inbox.tsx` | `refetchInterval: () => document.hidden ? false : 3000` — zero CPU on background tabs |
| Image pick | `client/src/pages/Inbox.tsx → handleImagePick()` | Validates: `file.size > 5MB` → error toast. `!file.type.startsWith('image/')` → error toast |
| Blob URL cleanup | `client/src/pages/Inbox.tsx` | `useEffect(() => () => { if (imagePreview) URL.revokeObjectURL(imagePreview) }, [imagePreview])` — prevents memory leak |
| API call | `client/src/lib/api.ts` | `POST /api/messages` — multipart if image attached |
| Router | `server/src/routers/messages.py → send_message()` | Auth check, saves message, triggers read-receipt logic |
| Model | `server/src/models/message.py` | `Message(sender_id, receiver_id, conversation_id, content, image_path, is_deleted, is_read)` |
| DB indexes | `messages` table | Indexed on `sender_id`, `receiver_id`, `is_read` (migration `a1b2c3d4e5f6`) |

### Soft Delete

| Step | File | Logic |
|------|------|-------|
| API call | `client/src/lib/api.ts` | `DELETE /api/messages/{id}` |
| Router | `server/src/routers/messages.py` | Sets `is_deleted = True` — message stays in DB, hidden from UI |

---

## 14. Report Account

Any authenticated user can report a profile they don't own.

| Step | File | Logic |
|------|------|-------|
| UI | `client/src/pages/ProfileView.tsx` | "Report Account" button, visible to authenticated non-owners |
| Form | `client/src/pages/ProfileView.tsx` | Reason dropdown (fake account / impersonation / fake credentials / inappropriate content / spam / other) + optional evidence text |
| API call | `client/src/lib/api.ts` | `POST /api/reports` |
| Router | `server/src/routers/reports.py → submit_report()` | Auth check, self-report prevention, duplicate pending report prevention |
| Model | `server/src/models/report.py` | `AccountReport(reporter_id, reported_user_id, reason, evidence_text, status, admin_note)` |
| DB indexes | `account_reports` table | Indexed on `reporter_id`, `created_at` |
| My reports | `client/src/lib/api.ts` | `GET /api/reports/my` → reporter sees their submitted reports and status |

---

## 15. Admin Panel

Admin users (`is_admin = true`) access reports and user management.

### Access

| File | Logic |
|------|-------|
| `client/src/pages/AdminLogin.tsx` | Dedicated login page at `/admin/login` — same JWT auth but sets admin session |
| `client/src/components/AdminRoute.tsx` | Route guard: redirects non-admins to `/` |
| `client/src/pages/AdminPanel.tsx` | Two tabs: Reports, Users |

### Reports Management

| Step | File | Logic |
|------|------|-------|
| Load reports | `client/src/pages/AdminPanel.tsx` | `GET /api/admin/reports?status=pending` |
| Router | `server/src/routers/reports.py → list_reports()` | Admin-only (checks `current_user.is_admin`). Returns paginated reports |
| Approve report | `client/src/pages/AdminPanel.tsx` → `PUT /api/admin/reports/{id}/approve` | Sets `status = approved`. Triggers score penalty: `score -= 12`, `is_suspicious = True` |
| Reject report | `PUT /api/admin/reports/{id}/reject` | Sets `status = rejected`. No score effect |
| Score penalty | `server/src/routers/reports.py` | Atomic update on `credibility_scores` for reported user |

### User Management

| Step | File | Logic |
|------|------|-------|
| Load users | `GET /api/admin/users` | Returns all users with score, role, suspicious status, is_admin |
| Promote admin | `PUT /api/admin/users/{id}/set-admin?is_admin=true` | Restricted: caller must be in `SUPER_ADMIN_EMAILS` env var (set in `server/.env`) |

---

## 16. File Serving

### CV Files

| Step | File | Logic |
|------|------|-------|
| Storage path | `server/uploads/cv/{user_id}.pdf` | Created on upload. Overwritten on re-upload |
| Serving | `server/main.py` | `app.mount("/uploads", StaticFiles(directory="uploads"))` — served directly by FastAPI |
| Download link | `client/src/pages/ProfileEditor.tsx` | Links to `/uploads/cv/{user_id}.pdf` |

### Message Images

| Step | File | Logic |
|------|------|-------|
| Storage path | `server/uploads/messages/{message_id}.{ext}` | Saved on send |
| Serving | `server/main.py` | Same static mount — `/uploads/messages/...` |
| Display | `client/src/pages/Inbox.tsx` | `<img src={...}>` with blob URL preview before send, static URL after |
| Cleanup | `client/src/pages/Inbox.tsx` | `URL.revokeObjectURL(imagePreview)` on unmount — prevents memory leak |

---

## 17. Validation Utilities

Standalone endpoints used by the frontend before/after profile edits. All return warnings only — never block saves.

| Endpoint | Router | Service | Purpose |
|----------|--------|---------|---------|
| `POST /api/validate/url` | `server/src/routers/validate.py` | `server/src/services/url_checker.py` | Check URL reachability + title; returns `{reachable, is_suspicious, reason}` |
| `POST /api/validate/skills` | `server/src/routers/validate.py` | `server/src/services/skill_validator.py` | Domain classification of skills. No UI warning shown (silently used for scoring signal) |
| `POST /api/validate/consistency` | `server/src/routers/validate.py` | `server/src/services/validation_service.py` | Title vs skills consistency; experience date overlap check using `_normalize_date()` |

**Date normalization detail** (`server/src/services/validation_service.py → _normalize_date()`):
Splits date string on `-`, pads month with `zfill(2)`: `"2024-9"` → `"2024-09"`. Fixes lexicographic comparison bug where `"2024-9" > "2024-10"` (September appearing after October).

---

## 18. Supporting Infrastructure

### Rate Limiting

| File | Logic |
|------|-------|
| `server/src/rate_limiter.py` | `Limiter(key_func=get_remote_address)` — shared slowapi instance |
| `server/src/routers/auth.py` | `@limiter.limit("5/minute")` on register; `@limiter.limit("10/minute")` on login |
| `server/main.py` | `app.state.limiter = limiter` + `SlowAPIMiddleware` + `RateLimitExceeded` handler |
| Storage | In-memory (no Redis required). Free. Resets on server restart |

### Database Connection Pool & Cold-Start Handling

| File | Setting / Mechanism | Purpose |
|------|---------------------|---------|
| `server/src/database.py` | `pool_size=10` | Max 10 persistent connections |
| `server/src/database.py` | `max_overflow=20` | Up to 20 additional connections under burst load |
| `server/src/database.py` | `pool_timeout=30` | Wait up to 30s for a connection before raising error |
| `server/src/database.py` | `pool_pre_ping=True` | Tests connection before use (fixes Neon idle-timeout drops) |
| `server/src/database.py` | `pool_recycle=1800` | Recycles connections every 30 min (prevents "connection closed" errors) |
| `server/src/database.py` | `ping_db(retries=6)` | Exponential-backoff warmup for Neon free-tier cold start (1s, 2s, 4s, 8s, 16s, 30s) |
| `server/main.py` | `lifespan()` context manager | Calls `ping_db()` on every server startup before accepting requests |
| `server/main.py` | `unhandled_exception_handler()` | Catches asyncpg `InternalServerError` / `TimeoutError` anywhere in the chain; returns HTTP 503 instead of crashing the ASGI process |

### Authentication & Security

| File | Mechanism |
|------|-----------|
| `server/src/routers/auth.py` | `python-jose` HS256 JWT, 7-day expiry. Sub = `user.id` |
| `server/src/services/auth_service.py` | bcrypt password hashing + `checkpw` verification |
| `server/src/routers/profile.py` | `owner_email` hidden from non-owner responses (email enumeration prevention) |
| `server/src/services/url_checker.py` | `verify=True` (SSL enforcement). No `verify=False` bypass |
| `server/main.py` | CORS: whitelisted origins, methods (`GET/POST/PUT/DELETE/OPTIONS`), headers (`Content-Type, Authorization`). No `*` |
| `server/src/config.py` | Pydantic `BaseSettings` — reads all secrets from `.env`. Never hardcoded |

### Ollama AI Client

| File | Logic |
|------|-------|
| `server/src/ai/ollama_client.py` | Shared async HTTP client wrapping Ollama REST API |
| Model | `qwen2.5:3b` — 3B parameter model, 8k context window, runs fully local |
| Timeout | 10s on credibility scoring; 120s overall Ollama connection timeout |
| Fallback | All LLM-dependent features have non-LLM fallbacks: rule-based scoring, conservative fraud risk (`medium`), empty search intent |
| Health | `GET /health/ai` endpoint checks Ollama reachability + model availability |

### Config & Settings

| File | Purpose |
|------|---------|
| `server/.env` | `DATABASE_URL`, `JWT_SECRET`, `OLLAMA_HOST`, `OLLAMA_MODEL`, `SUPER_ADMIN_EMAILS` |
| `server/src/config.py` | Pydantic `Settings` class — single source of truth for all config values |
| `server/alembic.ini` | Alembic migration config — points to `server/src/alembic/versions/` |
| `client/.env` (optional) | `VITE_API_URL` override if backend not on `localhost:8000` |

### Frontend State Management

| File | Purpose |
|------|---------|
| `client/src/stores/authStore.ts` | Zustand store for JWT token + user object. Persists to localStorage |
| `client/src/lib/queryClient.ts` | TanStack Query client config — stale times, retry behavior |
| `client/src/lib/api.ts` | Axios instance with base URL + auth interceptor (injects `Authorization: Bearer <token>`). `getApiError()` utility |
| `client/src/lib/types.ts` | Shared TypeScript interfaces for API response shapes |
| `client/src/lib/validators.ts` | Client-side field validators (email format, password strength) |

### Database Migration Chain

| Migration ID | File | Change |
|-------------|------|--------|
| `4a99fc87d523` | `..._initial.py` | Initial schema: users, profiles, proof_signals, appreciations, messages, credibility_scores |
| `b2c3d4e5f678` | `..._uid_sequence.py` | Add uid auto-sequence to users |
| `c3d4e5f6a789` | `..._fix_uid.py` | Fix uid sequence |
| `d4e5f6a7b890` | `..._cv_fields.py` | Add cv_file_path + cv_analysis to profiles |
| `e5f6a7b8c901` | `..._message_fields.py` | Add image_path + is_deleted to messages |
| `f6g7h8i9j012` | `..._admin_reports.py` | Add is_admin to users; is_suspicious, url_warnings to credibility_scores; account_reports table |
| `a1b2c3d4e5f6` | `..._add_missing_indexes.py` | 10 critical missing indexes (FKs, score ordering, admin queries) |
| `b3c4d5e6f7a8` | `..._add_fulltext_search.py` | Enable pg_trgm; add stored `search_tsv` tsvector column + `profiles_search_tsv_trigger` + plain GIN index on `search_tsv` + trigram GIN index on `title` |

---

## Data Flow Summary

```
Browser (React + Zustand + TanStack Query)
    ↕  Axios (client/src/lib/api.ts)
FastAPI (server/main.py)
    ↕  Rate limiting (slowapi middleware)
    ↕  JWT auth (python-jose)
Routers (server/src/routers/*.py)
    ↕  Pydantic schemas (server/src/schemas/*.py)
Services (server/src/services/*.py)
    ↕  SQLAlchemy async (server/src/database.py)
Neon PostgreSQL
    → GIN indexes (FTS + trgm)
    → BTree indexes (FKs, ordering)
    → Atomic upserts (ON CONFLICT DO UPDATE)

AI Path (async, non-blocking):
Services → server/src/ai/ollama_client.py → Ollama (localhost:11434) → qwen2.5:3b
```
