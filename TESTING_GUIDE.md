# HireCred-v1 — Complete Testing Guide

**Last updated: 2026-05-18**

---

## 1. Start the Servers

### Backend (FastAPI)
```powershell
cd F:\hireCred-v1\server
.\.venv\Scripts\Activate.ps1
uvicorn main:app --reload --port 8000
```
Backend: **http://localhost:8000**  
Swagger docs: **http://localhost:8000/docs**

### Frontend (React + Vite)
```powershell
cd F:\hireCred-v1\client
npm run dev
```
Frontend: **http://localhost:5173**

### Ollama (AI engine)
```powershell
ollama list            # should show qwen2.5:3b
# If missing: ollama pull qwen2.5:3b
```
AI health check: **http://localhost:8000/health/ai**

---

## 2. Run Database Migration

After pulling new code, always run the migration:
```powershell
cd F:\hireCred-v1\server
.\.venv\Scripts\Activate.ps1
alembic upgrade head
```

---

## 3. Accounts You Need

| Account | Role | Purpose |
|---------|------|---------|
| Account A | Candidate | Build profile, receive appreciations/messages, upload CV |
| Account B | Client (Hirer) | Search candidates, give appreciations, test report feature |
| Account C (optional) | Admin | Login via admin URL and test report moderation |

Create at: **http://localhost:5173/register**  
Admin login: **http://localhost:5173/admin/login**

To make an account admin, set directly in DB:
```sql
UPDATE users SET is_admin = true WHERE email = 'your@email.com';
```

---

## 4. Feature-by-Feature Testing

### Feature 1 — Auth
1. Register candidate → redirected to Dashboard
2. Register client → different dashboard UI (no "Edit Profile" button)
3. Sign out → re-login → JWT token persists
4. `/api/auth/me` includes `is_admin: false` for regular users

---

### Feature 2 — Profile & Non-Blocking Validation
1. Log in as candidate → go to Profile Editor
2. Fill in bio (< 80 chars) → click Save → **profile should save** (no 422 error)
   - Check response: `_warnings` field contains a bio length warning
3. Frontend shows warning as a banner, not a blocking error
4. Add skills → type any skill and press Enter → no "not in skills list" warning
5. "Tech Stack" label in portfolio items is now labelled **"Skills"**

---

### Feature 3 — CV Upload (PDF Only)
1. Upload a valid PDF CV (candidate account)
2. Should succeed immediately — no AI analysis runs
3. Save button returns instantly ("Score updating in background…" toast)
4. Try uploading a `.docx` → should get "Only PDF files accepted" error
5. Max 5 MB — larger files rejected

---

### Feature 4 — HireCred Score & Background Scoring
1. Save profile → see "Score updating in background…" toast
2. Go to ProfileView → ScoreWidget shows loading ring, then score appears
3. Score polling: UI polls every 3s until score appears
4. **Refresh button**: click "Refresh" icon on ScoreWidget header → triggers manual rescore
5. If Ollama is down, rule-based fallback runs — score still appears, just simpler

---

### Feature 5 — Dummy / Fake Profile Detection
Create a candidate with clearly fake data and verify low score:

| Data Field | Fake Value | Expected Flag |
|------------|-----------|---------------|
| Title | "Ultra Creative Pixel Wizard" | Absurd title flag |
| Location | "Mars Colony Sector 9" | Fictional location flag |
| Bio | "Designer with 999 years of experience for alien startups across multiple galaxies" | Sci-fi content + absurd numeric |
| Skills | "Coffee Drinking, Meme Design, Fake Skill 101, Galactic UI" | Joke skills flag |
| Company | "Galaxy Banana Corp" | Fictional company flag |
| Dates | "3020 – Present" | Far-future date flag |

After saving, check score: **must be ≤ 15** (risk_level = high, score capped).
Check `authenticity_flags` in the score response — should list 6+ specific flags.

---

### Feature 6 — URL Dead-Link Detection
1. Add a portfolio item with URL `https://thisdoesnotexist123456.com`
2. Save profile → wait for background scoring
3. Check score: `url_warnings` should contain "Could not connect — domain may not exist"
4. Add URL to a parked/placeholder page → should detect suspicious page title
5. GitHub URLs skip HTTP check (trusted domain)

---

### Feature 7 — Authenticity Detection (Edge Cases)
| Test | Expected |
|------|---------|
| Register with name "Test User" | authenticity_flags: suspicious name |
| Bio contains "highly motivated team player" | authenticity_flags: boilerplate phrase |
| Two experience entries with identical descriptions | flag: copy-paste detected |
| Experience start_date "2027-01" (just future) | flag: start date in future |
| Experience start_date "3020" (far future) | flag: far-future fictional date |
| 2+ portfolio items all linking to example.com | flag: all portfolio same domain |

---

### Feature 8 — Report Account System
1. Log in as client (Account B)
2. Go to any candidate's profile view
3. Click "⚑ Report" button (top right, next to Send Message)
4. Select reason from dropdown + optional evidence text
5. Submit → "Report submitted" toast
6. Check `/api/reports/my` to confirm report created
7. Try submitting the same report again → "You already have a pending report" error

---

### Feature 9 — Admin Panel
1. Set yourself as admin (via DB `UPDATE users SET is_admin = true WHERE email = '...'`)
2. Restart backend
3. Log in via **http://localhost:5173/admin/login**
4. Dashboard shows "Admin" link in nav
5. Go to `/admin`:
   - **Reports tab**: filter by status (pending / approved / rejected)
   - Approve a report → score −12 pts, suspicious tag applied to candidate
   - Reject a report → no score change
6. **Users tab**: see all users with score and suspicious status

---

### Feature 10 — Suspicious Account Display
1. After an admin approves a report against a candidate:
   - Candidate's ScoreWidget shows "⚠ Suspicious" badge in header
   - ProfileView shows amber warning banner: "Suspicious Account — engage with caution"
   - Score mini-ring in hero card also shows Suspicious badge
2. Candidate's score is reduced by 12 points

---

### Feature 11 — Appreciation System
1. As client, go to candidate's profile → "Give Appreciation" button
2. Write freeform feedback ("Great React developer, delivered on time and communicated well")
3. Submit → Ollama extracts ratings + summary (background)
4. Check `/api/appreciation/{uid}` for structured ratings
5. Score recalculated in background after appreciation

---

### Feature 12 — Search
1. As client, go to `/search`
2. Try: "Looking for a reliable React developer"
3. Results ranked by trust score + skill match
4. Try: "Need an experienced Python backend engineer" — skill-based matching

---

### Feature 13 — Leaderboard
1. Go to `/leaderboard` (public page)
2. See top candidates ranked with lucide icons (Star, ShieldCheck, Medal)
3. Candidates with `fraud_risk = high` are excluded
4. Suspicion alone doesn't exclude (needs `fraud_risk = high`)

---

### Feature 14 — Messaging
1. As client, go to candidate's profile → "Send Message"
2. Type message → press Enter to send (or click SendHorizonal icon)
3. Attach an image using ImageIcon button
4. Hover over your own message → Trash2 delete icon appears
5. Deleted messages show "Message deleted" placeholder text

---

## 5. Score API Response Fields

```json
{
  "score": 74,
  "strengths": ["Has detailed work experience", "GitHub proof signal added"],
  "risks": ["Bio is short", "URL for portfolio item is not reachable"],
  "fraud_risk": "low",
  "computed_at": "2026-05-18T10:00:00",
  "is_suspicious": false,
  "authenticity_flags": [],
  "cv_match_score": null,
  "cv_match_warnings": [],
  "url_warnings": []
}
```

> `cv_match_score` and `cv_match_warnings` are always `null` / `[]` — CV analysis was removed. The CV presence (yes/no) is still factored into the LLM score.

---

## 6. Common Issues

| Issue | Fix |
|-------|-----|
| Score not updating | Ollama may be slow. Click "Refresh" icon on ScoreWidget. Check `/health/ai`. |
| CV upload fails | Must be PDF (not DOCX). Max 5 MB. |
| DB "connection is closed" error | Restart the server. Pool recycles after 30 min idle. |
| Report button not visible | Must be logged in and NOT the profile owner |
| Admin panel shows 403 | User's `is_admin` must be true. Restart server after DB change. |
| Two eye icons in password field | Fixed via CSS `::-ms-reveal` suppression. Clear browser cache if still seeing it. |
| Score seems too high for fake profile | Check that Ollama is responding — rule-based fallback gives completeness points but authenticity penalty subtracts them. Penalty cap is 60 pts. |
| URL warnings showing for GitHub | GitHub is on the trusted-domain list — skips HTTP check intentionally. |
