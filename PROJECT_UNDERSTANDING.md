# HireCred-v1 — Project Understanding

## The Core Problem

Current job platforms (Rozgar, Fiverr, Upwork) still ask a fundamental unanswered question:
> **"How do we trust a candidate online?"**

Anyone can write "5 years of React experience" on a profile. There's no mechanism to verify that claim, assess the quality of their work, or distinguish a genuinely skilled person from someone who just filled in all the right fields.

HireCred-v1 solves this by making **credibility measurable** — through AI analysis of proof signals, not just self-reported data.

---

## What Makes This Different

| Traditional Platforms | HireCred-v1 |
|---|---|
| Star ratings (easily faked) | AI-structured appreciation → skill/comm/reliability ratings |
| Filter-based search | Intent-based natural language search |
| Self-reported skills | Proof signals (GitHub, screenshots, references) |
| No trust indicator | HireCred Score (0–100) with AI-explained strengths/risks |
| Passive profiles | Trust Leaderboard based on verified data |

---

## The 6 Core Features Explained

### 1. Smart Profile System
A candidate's profile is more than a resume. It has two layers:

**Layer 1 — Standard Info:**
- Skills (stored as tags, e.g., `["React", "Node.js", "PostgreSQL"]`)
- Experience (list of jobs with title, company, duration, description)
- Portfolio (list of projects with title, description, tech stack)

**Layer 2 — Proof Signals (the key differentiator):**
- GitHub link (verifiable public activity)
- Work screenshots (uploaded images of real deliverables)
- Client references (text-based testimonials with contact)
- Live project URLs

Without proof signals, the AI score will be low — this incentivizes candidates to provide evidence, not just claims.

---

### 2. AI Credibility Score (HireCred Score)
This is the heart of the product. When a profile is saved/updated, the backend sends the full profile data to Claude AI with a carefully designed prompt.

**What Claude evaluates:**
- **Profile completeness** — Did they fill everything? Empty bio = penalized.
- **Skill vs experience alignment** — Claims React expert but no React projects? Flagged.
- **Portfolio quality** — Are descriptions detailed? Are links present?
- **Writing clarity** — Is the bio professional and coherent?
- **Missing proof signals** — GitHub missing for a developer = risk.

**Output (strict JSON):**
```json
{
  "credibility_score": 78,
  "strengths": ["Strong GitHub presence", "Skills align with portfolio"],
  "risks": ["No client references", "Bio is too generic"]
}
```

This score is stored in DB, shown on profile, and used in search ranking.

---

### 3. AI-Based Appreciation System
Instead of "⭐⭐⭐⭐⭐", clients write what they actually think:

> "Ali delivered the dashboard on time, communicated well, but the code needed some cleanup."

Claude reads this and extracts:
```json
{
  "skill_rating": 7.5,
  "communication_rating": 9.0,
  "reliability_rating": 8.5,
  "summary": "Timely delivery with good communication; code quality could improve."
}
```

This makes feedback **harder to fake** — it's harder to game a paragraph than to click 5 stars. It also surfaces more nuanced information for hiring decisions.

---

### 4. Smart Intent-Based Search
No dropdowns. No filters. Just a text box:

> "Looking for a reliable React developer who has real project experience"

The backend does two things:
1. **AI parse** — Claude extracts from the query: required skills, intent signals (reliability, experience level, trust priority)
2. **Ranked DB query** — Candidates are fetched and scored:
   - 40% weight: credibility score match
   - 40% weight: skill overlap with extracted skills
   - 20% weight: appreciation quality (avg ratings)

The results feel intelligent — a candidate with a 90 HireCred Score and strong reliability ratings ranks above someone with matching skills but low trust indicators.

---

### 5. Trust Leaderboard
A ranked list of top professionals. Not based on who paid more or who has more connections, but on:
- AI credibility score
- Number and quality of verified appreciations
- Profile view activity (signals real demand)

This creates a fair, merit-based visibility system.

---

### 6. Basic Hiring Flow
Simple but complete:
- Client views a candidate profile
- Client sends a message (simple threading, no real-time needed)
- After working together, client gives appreciation (structured feedback)

---

## Bonus Features (Differentiation)

### Fake Review Detection
When a new appreciation is submitted, Claude analyzes the full set of appreciations for that candidate:
- Are they all generic ("great work!")?
- Are all ratings suspiciously perfect (10/10/10)?
- Same writing style across multiple reviewers?

Output: `{ "fraud_risk": "medium", "flags": ["Generic language detected", "Unusual rating pattern"] }`

This gets stored on the credibility score and lowers it if fraud is detected. It makes the trust system **self-defending**.

---

## Data Flow Summary

```
Candidate fills profile
        ↓
Backend sends profile to Claude AI
        ↓
Claude returns HireCred Score JSON
        ↓
Score stored in DB, shown on profile
        ↓
Client searches "need reliable React dev"
        ↓
Backend AI-parses query → DB ranked query
        ↓
Client views candidate profile
        ↓
Client writes appreciation text
        ↓
Claude converts text → structured ratings
        ↓
Fraud detection runs on all appreciations
        ↓
Score updated, leaderboard recalculates
```

---

## Key Design Decisions

1. **Why Python backend?** Clean, fast to write AI integration with Anthropic SDK, great for prompt engineering logic.
2. **Why Neon DB (serverless PostgreSQL)?** No local setup, free tier, scales to zero, works perfectly with Python + asyncpg/psycopg2.
3. **Why Claude API?** Structured outputs via tool_use, high-quality reasoning for nuanced tasks like fraud detection.
4. **Why no real-time messaging?** Out of scope — the trust/credibility system is the product. Messaging is just a utility.
5. **Why no star ratings?** They're gameable and low-signal. Text + AI conversion is higher quality and harder to fake.

---

## User Roles

| Role | Can Do |
|---|---|
| **Candidate** | Create/edit profile, add proof signals, receive appreciations, send/receive messages |
| **Client** | Browse candidates, search, view profiles, send messages, give appreciations |

Authentication: JWT (access token). Both roles register with role selection.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite + TypeScript |
| Styling | Tailwind CSS |
| State | Zustand (auth) + TanStack Query (server state) |
| Routing | React Router v6 |
| Backend | Python + FastAPI |
| AI | Anthropic Claude API (`claude-sonnet-4-6`) |
| ORM | SQLAlchemy (async) + Alembic (migrations) |
| Database | Neon DB (serverless PostgreSQL) |
| Auth | JWT (python-jose + passlib) |
| File Upload | FastAPI UploadFile → local `/uploads` or Cloudinary |
| Deployment | Railway (backend) + Vercel (frontend) |
