# HireCred-v1 — Project Understanding

**Last updated: 2026-06-01**

## The Core Problem

Current job platforms ask an unanswered question: **"How do we trust a candidate online?"**

Anyone can write "5 years of React experience." There's no mechanism to verify that claim, assess work quality, or distinguish a real professional from someone who filled in all the right fields.

HireCred-v1 solves this by making **credibility measurable** — through AI analysis of proof signals, authenticity heuristics, URL verification, and real content checks — not just self-reported data.

---

## What Makes This Different

| Traditional Platforms | HireCred-v1 |
|---|---|
| Star ratings (easily faked) | AI-structured appreciation → skill/comm/reliability ratings |
| Filter-based search | Intent-based natural language search |
| Self-reported skills | Proof signals + background scoring |
| No trust indicator | HireCred Score (0–100) with AI-explained strengths/risks/flags |
| Passive profiles | Trust Leaderboard based on verified data |
| No fake detection | 16-point authenticity heuristics + admin-reviewed reports |
| Any URL accepted | Dead-link and parked-page detection via page title extraction |

---

## System Architecture

### Stack
| Layer | Tech |
|-------|------|
| Frontend | React 18, TypeScript, Vite, TailwindCSS v4, Zustand, TanStack Query |
| Backend | Python, FastAPI, SQLAlchemy (async), Alembic |
| Database | Neon PostgreSQL (serverless), asyncpg |
| AI / LLM | Ollama (local), `qwen2.5:3b` |
| Auth | JWT (python-jose), bcrypt |

---

## Core Features

### 1. Smart Profile System
A candidate's profile contains:
- Bio, title, location, skills (tag input — no validation warnings)
- Work experience entries (title, company, dates, description)
- Portfolio items (title, description, URL, skills used)
- Proof signals (GitHub links, screenshots, client references, portfolio links)
- CV upload (PDF only, max 5 MB — stored as file, no AI analysis)

**Non-blocking validation:** Profile saves are never blocked. Any validity issues are returned as warnings that affect the HireCred Score, not as hard errors.

**Background scoring:** All score computation runs asynchronously after saves — profile/signal/CV operations return immediately (< 1 second). Score updates appear automatically via polling.

### 2. HireCred Score (0–100)
The central trust metric. Computed in background by an Ollama LLM fed with:

**Evidence sources:**
- Full profile data (bio, skills, experience, portfolio, proof signals)
- Whether a CV file has been uploaded (yes/no — no content analysis)
- Authenticity flags (16-point heuristic fake/duplicate detection)
- URL warnings (dead links, parked pages detected via page title)

**Scoring criteria (AI-weighted):**
1. Profile completeness (18 pts)
2. Skill vs experience alignment (22 pts)
3. Portfolio quality (22 pts)
4. Writing clarity (8 pts)
5. Proof signals (18 pts)
6. CV quality (12 pts — 0 if no CV uploaded)

**Post-LLM score adjustments:**
- Authenticity penalty: −0 to −60 pts (heuristic fake detection, cap increased)
- Dead URL penalty: −6 pts per unreachable/parked link (max −18)
- Admin-approved report: −12 pts + `is_suspicious = true`

**Hard score ceilings:**
- `risk_level == high` → score capped at 15
- `risk_level == medium` + penalty ≥ 20 → score capped at 35

**Manual refresh:** Profile owner can click "Refresh" on the ScoreWidget to trigger recomputation via `POST /api/profile/{id}/rescore`.

### 3. CV Upload (File Storage Only)
- PDF only, max 5 MB
- Stored as a file at `server/uploads/cv/{user_id}.pdf`
- No text extraction, no Ollama analysis
- Presence of a CV file is passed to the LLM as a binary signal ("CV uploaded: Yes/No")
- CV contributes up to 12 pts in the LLM scoring criteria

### 4. URL Verification
For each portfolio URL and proof signal URL:
1. **Trusted domains** (github.com, linkedin.com, etc.) — skip HTTP check, auto-pass
2. **HEAD + GET request** — check if URL is reachable (4s timeout)
3. **Page title extraction** — fetch HTML, extract `<title>` tag
4. **Dead-page detection** — title containing "domain for sale", "404 not found", "coming soon", "parked domain", etc. → flagged suspicious even if HTTP 200

### 5. Profile Authenticity Detection (16 Heuristics)
All checks run on every profile save in the background:

| Check | Penalty |
|-------|---------|
| Suspicious name (test/dummy/John Doe/admin) | −15 |
| Disposable email domain | −20 |
| Bio boilerplate phrases (guru, ninja, wizard, etc.) | −15 |
| Bio under 15 words | −8 |
| Sci-fi/fantasy content (alien startups, holographic billboards, intergalactic) | −10–20 |
| Fictional location (Mars Colony, Moon Base, Sector 9, planet names) | −15 |
| Absurd professional title (Ultra Creative Pixel Wizard, Supreme Overlord) | −12 |
| Impossible numeric claims (999 years of experience, 5000% increase) | −15 |
| Far-future experience dates (year > current+2, e.g. 3020) | −18 per entry |
| Fictional company names (Galaxy Banana Corp, Moonlight Sandwich Studio) | −15 |
| Joke/non-professional skills (Coffee Drinking, Meme Design, Fake Skill 101) | −8–18 |
| Duplicate experience descriptions (copy-paste within same profile) | −12 |
| All portfolio URLs same domain | −12 |
| Identical portfolio descriptions | −12 |
| Skill list > 25 items | −8 |
| >60% generic non-technical skills | −8 |
| Tech title with no technical skills | −15 |

Max total penalty: −60. Medium/high risk → `is_suspicious = true`.

### 6. AI-Powered Appreciation
Clients write freeform feedback. Ollama extracts:
- `skill_rating` (0–10)
- `communication_rating` (0–10)
- `reliability_rating` (0–10)
- One-sentence summary

Fraud detection runs on the full set of appreciations — flags suspiciously generic, uniform, or templated reviews.

### 7. Intent-Based Search (Scalable to 1M+ profiles)
Natural language queries ("reliable React developer with startup experience") parsed by Ollama or local heuristics.

**Architecture:** SQL-first, Python-rank
- All filtering happens inside PostgreSQL using a stored `search_tsv` `TSVECTOR` column on `profiles` (populated from `title + bio + skills`), kept up-to-date by the `profiles_search_tsv_trigger` DB trigger, and indexed with a plain GIN index (`ix_profiles_fts`)
- `pg_trgm` extension + trigram GIN index on `title` enable fuzzy matching (handles typos like "develoer" → "developer")
- Three SQL search stages: FTS on `search_tsv` → trigram fuzzy → ILIKE (each with hard LIMIT)
- Never loads more than 200 rows into Python; Python ranks the pre-filtered set
- Returns empty results with a message when nothing matches — no random fallback

**Ranking formula:** 40% credibility score + 35% skill match + 15% appreciation ratings + 10% profile views.

**No results:** Returns empty list + `"message"` field explaining no candidates were found. No random unrelated profiles returned.

### 8. Trust Leaderboard
Top 20 candidates ranked by a combined metric. High fraud risk → excluded. Medium fraud risk → appreciation weight halved. Cached 2 minutes.

### 9. Report Account System
Authenticated users can report any profile they don't own:
- Reason: fake account / impersonation / fake credentials / inappropriate content / spam / other
- Optional evidence text
- Duplicate pending reports from same reporter prevented

### 10. Admin Panel
Admin users (`is_admin = true` on User model) have access to:
- **Reports dashboard** — filter by status (pending / approved / rejected)
- **Approve report** → applies suspicious tag + −12 score penalty
- **Reject report** → no effect on score
- **Users table** — see all users with score, role, suspicious status

Admin login at `/admin/login`. Admin panel at `/admin`. Set admin via DB or API.

### 11. Messaging
Simple conversation threads between any two authenticated users. Supports text and image attachments. Soft-delete (`is_deleted` flag).

---

## Database Schema (7 tables)

| Table | Key Fields |
|-------|-----------|
| `users` | id, uid, email, role, is_admin, is_active |
| `profiles` | user_id, bio, title, skills, experience, portfolio, cv_file_path, cv_analysis (null — not used), search_tsv (tsvector — maintained by trigger) |
| `credibility_scores` | user_id, score, strengths, risks, fraud_risk, is_suspicious, authenticity_flags, cv_match_score (null), cv_match_warnings (empty), url_warnings |
| `proof_signals` | profile_id, signal_type, title, url, file_path |
| `appreciations` | to_user_id, from_user_id, skill_rating, communication_rating, reliability_rating |
| `messages` | sender_id, receiver_id, conversation_id, content, image_path, is_deleted |
| `account_reports` | reporter_id, reported_user_id, reason, evidence_text, status, admin_note |

---

## API Endpoints Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register (candidate/client) → returns `{access_token, user}` immediately |
| POST | `/api/auth/login` | Login → JWT |
| GET | `/api/auth/me` | Current user (includes is_admin) |
| GET | `/api/profile/{uid}` | View profile |
| PUT | `/api/profile/{id}` | Update profile (non-blocking, background scoring) |
| GET | `/api/profile/{id}/score` | Get full credibility score |
| POST | `/api/profile/{id}/cv` | Upload CV (PDF only, no analysis) |
| DELETE | `/api/profile/{id}/cv` | Delete CV |
| POST | `/api/profile/{id}/rescore` | Manually trigger score recomputation |
| POST | `/api/profile/{id}/signals` | Add proof signal |
| DELETE | `/api/profile/{id}/signals/{id}` | Remove proof signal |
| POST | `/api/appreciation` | Submit appreciation |
| GET | `/api/appreciation/{id}` | Get appreciations for user |
| POST | `/api/search` | Intent-based candidate search |
| GET | `/api/leaderboard` | Ranked candidates |
| POST | `/api/validate/url` | Check URL reachability + title |
| POST | `/api/validate/skills` | Skill domain check (no warning in UI) |
| POST | `/api/validate/consistency` | Title vs skills consistency |
| POST | `/api/reports` | Submit account report |
| GET | `/api/reports/my` | My submitted reports |
| GET | `/api/admin/reports` | All reports (admin) |
| PUT | `/api/admin/reports/{id}/approve` | Approve report (admin) |
| PUT | `/api/admin/reports/{id}/reject` | Reject report (admin) |
| GET | `/api/admin/users` | All users (admin) |
| PUT | `/api/admin/users/{id}/set-admin` | Promote/demote admin |
| GET | `/health` | Server health |
| GET | `/health/ai` | Ollama health |

---

## Key File Locations

| Purpose | File |
|---------|------|
| Main scoring pipeline | `server/src/services/credibility_service.py` |
| LLM prompt (with evidence context) | `server/src/ai/credibility_prompt.py` |
| 16-point authenticity detection | `server/src/services/authenticity_service.py` |
| URL checker + title extraction | `server/src/services/url_checker.py` |
| Report + admin endpoints | `server/src/routers/reports.py` |
| Admin frontend | `client/src/pages/AdminPanel.tsx` |
| Score display + refresh button | `client/src/components/profile/ScoreWidget.tsx` |
| Profile view + report button | `client/src/pages/ProfileView.tsx` |
| DB connection pool config | `server/src/database.py` |
| Scalable search service | `server/src/services/search_service.py` |
| Rate limiter (shared) | `server/src/rate_limiter.py` |
| Search router | `server/src/routers/search.py` |

---

## Security & Production Notes

| Concern | How It's Handled |
|---------|-----------------|
| SQL injection | SQLAlchemy parameterized queries throughout |
| Passwords | bcrypt hashing |
| Auth | JWT (HS256), 7-day expiry |
| Rate limiting | slowapi on `/auth/login` (10/min) and `/auth/register` (5/min) |
| CORS | Whitelisted origins + specific methods/headers (no `*`) |
| Email enumeration | `owner_email` hidden from public profile responses |
| File upload safety | MIME type + size validation on server and client |
| URL verification | SSL enforced (`verify=True`); trusted domain skip list |
| Fraud detection | AI analysis of appreciation patterns; conservative default on AI failure |
| Concurrency | Atomic PostgreSQL upsert for credibility scores; asyncio.Lock on leaderboard cache |
| Neon cold-start | `ping_db()` warmup on startup (6 retries, exponential backoff); asyncpg errors return HTTP 503 instead of crashing |
