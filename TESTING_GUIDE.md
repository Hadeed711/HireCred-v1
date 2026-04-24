# HireCred-v1 — Complete Testing Guide

## 1. Start the Servers

### Backend (FastAPI)
```bash
cd f:\hireCred-v1\server
.venv\Scripts\activate          # Windows
uvicorn main:app --reload --port 8000
```
Backend runs at: **http://localhost:8000**  
API docs (Swagger): **http://localhost:8000/docs**

### Frontend (React + Vite)
```bash
cd f:\hireCred-v1\client
npm run dev
```
Frontend runs at: **http://localhost:5173**

---

## 2. Accounts You Need

You will need **at least two accounts** to test the full flow:

| Account | Role | Purpose |
|---------|------|---------|
| Account A | Candidate | Build profile, receive messages & appreciations |
| Account B | Client | Search candidates, send messages, give appreciations |

Create them at: **http://localhost:5173/register**

---

## 3. Feature-by-Feature Testing

---

### Feature 1 — Auth (Register / Login)

**URL:** http://localhost:5173/register

**Steps:**
1. Open `/register`
2. Fill in: Full Name, Email, Password
3. Select role: **"I'm a Candidate"** → click Register
4. You should be redirected to `/dashboard`
5. Click **Sign out** (top right)
6. Register again with a different email → select **"I'm Hiring"** (Client role)
7. Verify you're on the client dashboard (shows "Find Candidates" in the nav)

**What to verify:**
- Both roles land on `/dashboard` after registration
- The nav shows different links depending on role (candidate sees "My Profile", client sees "Find Candidates")
- Refresh page — you should stay logged in (JWT persists in Zustand store)
- Visit `/login` and sign in with existing credentials

---

### Feature 2 — Candidate Profile Builder

**Login as:** Candidate (Account A)  
**URL:** http://localhost:5173/profile/edit

**Steps:**

#### 2a. Fill Basic Info
1. Go to `/profile/edit`
2. Fill in all fields:
   - **Title:** e.g. `Full-Stack Developer`
   - **Location:** e.g. `Lahore, Pakistan`
   - **Bio:** Write at least 2–3 sentences describing yourself professionally (be specific — vague bios score lower)
3. **Skills:** Type a skill name → press Enter to add (e.g. React, Node.js, PostgreSQL, TypeScript)
   - Add at least 3 skills for a better score

#### 2b. Add Experience
1. Click **"Add Experience"**
2. Fill: Job Title, Company, Start Date, check "Currently working here" or add End Date, Description
3. Add at least 1 experience entry

#### 2c. Add Portfolio
1. Click **"Add Portfolio Item"**
2. Fill: Project Title, Description (detailed!), URL (optional), Tech Stack
3. Add at least 1 portfolio item

#### 2d. Save Profile
1. Click **"Save Profile"**
2. You should see a success toast

**What to verify:**
- Profile saves without errors
- Navigating away and back to `/profile/edit` shows your saved data

---

### Feature 3 — Proof Signals

**Login as:** Candidate  
**URL:** http://localhost:5173/profile/edit → scroll down to Proof Signals section

**Steps:**
1. **GitHub / Project Link:**
   - Select type: `GitHub / Project Link`
   - Add title: `My GitHub Profile`
   - URL: `https://github.com/yourusername`
   - Click Add

2. **Screenshot (file upload):**
   - Select type: `Work Screenshot`
   - Add a title: `Dashboard Screenshot`
   - Choose an image file from your computer
   - Click Add

3. **Client Reference:**
   - Select type: `Client Reference`
   - Title: `Ahmed Khan - Previous Client`
   - Description: Name and contact of a past client
   - Click Add

**What to verify:**
- Each signal appears in the list after adding
- Clicking the × removes a signal
- After saving, signals persist on page reload

---

### Feature 4 — AI Credibility Score (HireCred Score)

**After saving your profile, this runs automatically in the background.**

**URL:** http://localhost:5173/profile/{your-user-id}  
(find your user ID from the URL when you click "View Public Profile" on the dashboard)

**What to verify:**
1. Open your public profile
2. The **Score Widget** section shows "Calculating…" initially
3. Within 5–10 seconds it refreshes and shows a score **0–100**
4. The ring color shows:
   - **Green** = 70–100 (high trust)
   - **Orange** = 40–69 (moderate)
   - **Red** = 0–39 (low trust)
5. Below the ring: **Strengths** (green) and **Risks** (red/orange) bullets listed
6. Go back, edit profile (add more content / proof signals), save again → score should update

**Score boosters to test:**
| Action | Expected Effect |
|--------|----------------|
| Add bio with specific details | Score goes up |
| Add 3+ skills | Score goes up |
| Add experience with description | Score goes up |
| Add GitHub proof signal | +8 pts contribution |
| Add portfolio with detailed description | Score goes up |
| Empty bio, no skills | Score stays low (0–30) |

---

### Feature 5 — Smart Intent Search

**Login as:** Client (Account B)  
**URL:** http://localhost:5173/search

**Steps:**
1. Type a natural language query in the search box, e.g.:
   - `"Looking for a reliable React developer with real project experience"`
   - `"Need a senior backend engineer I can trust with deadlines"`
   - `"Experienced UI/UX designer with a strong portfolio"`
2. Click **Search** (or press Enter)
3. Wait for **"AI is analyzing your request…"** animation to complete

**What to verify:**
- Results show candidate cards with: name, HireCred Score badge, top 3 skills, avg appreciation, "View Profile" button
- Results are ranked by trust score — higher credibility scores appear first
- Clicking "View Profile" opens that candidate's public profile
- Searching for unrelated skills (e.g. "carpenter") returns no results or low-match candidates
- Searching with trust words like "reliable", "verified", "trustworthy" boosts weight on HireCred Score

---

### Feature 6 — Public Profile View

**URL:** http://localhost:5173/profile/{candidate-user-id}

**Can be viewed by anyone (no login required for the page itself).**

**Steps:**
1. Navigate to any candidate's profile
2. Check all sections render: Hero card (name, title, location, views), Skills, Experience, Portfolio, Proof Signals, HireCred Score widget, Appreciations

**What to verify (as Client):**
- The header shows **"Give Appreciation"** and **"Send Message"** buttons (only if logged in as client, and it's not your own profile)
- **"Edit Profile"** button appears only when viewing your own profile as a candidate
- Profile view count increments each time the profile is loaded (check the "👁 X views" counter)

---

### Feature 7 — Messaging

**Login as:** Client  
**URL:** http://localhost:5173/profile/{candidate-user-id}

**Steps:**
1. Open a candidate's public profile
2. Click **"Send Message"** button in the header
3. You are redirected to `/inbox/{candidate-user-id}`
4. Type a message and press **Enter** or click **Send**
5. Message appears as a bubble on the right side

**Switch to Candidate account:**
1. Log out, log in as the candidate
2. Go to **Inbox** (nav link or http://localhost:5173/inbox)
3. You should see the conversation with an unread count badge
4. Click the conversation → thread opens
5. Type a reply and send it

**Switch back to Client:**
1. Go to Inbox → new message appears (polling refreshes every 5 seconds — wait a moment)

**What to verify:**
- Conversation list shows: other person's name, last message preview, unread count badge
- Unread badge clears after opening the conversation
- Messages show your sent messages on the right (indigo), received on the left (white)
- Timestamps appear below each message
- Pressing Enter sends; Shift+Enter adds a new line

---

### Feature 8 — AI Appreciation System

**Login as:** Client  
**URL:** http://localhost:5173/profile/{candidate-user-id}

**Steps:**
1. Open a candidate's public profile
2. Click **"Give Appreciation"** button
3. The appreciation modal opens — write a paragraph of feedback, e.g.:
   > "Ali delivered the project on time and communicated clearly throughout. The code quality was solid and he was responsive to feedback. Would definitely hire again."
4. Click **"Submit Appreciation"**
5. Wait a moment — the modal shows what Claude extracted:
   - Skill rating (0–10)
   - Communication rating (0–10)
   - Reliability rating (0–10)
   - One-sentence AI summary

**What to verify:**
- The ratings shown reflect what you wrote:
  - Mention deadlines → high reliability
  - Mention communication → high communication
  - Mention buggy code → lower skill rating
- After closing the modal, scroll to the **"Client Appreciations"** section on the profile
- Your appreciation appears as a card with ratings and summary
- The aggregated rating bars (Skill / Communication / Reliability) update

**Test different feedback types:**
| Feedback | Expected Ratings |
|----------|-----------------|
| "Fantastic work, delivered fast, zero issues" | All high (8–10) |
| "Code was messy but he communicated well" | Skill low, Communication high |
| "Very slow, took 3x longer than expected" | Reliability low |
| "Great work!" (very short) | Gets minimal AI ratings, ~5/10 neutral |

---

### Feature 9 — Trust Leaderboard

**URL:** http://localhost:5173/leaderboard (public, no login needed)

**Steps:**
1. Navigate to `/leaderboard`
2. Browse the ranked list of top candidates

**What to verify:**
- **#1 gets a gold badge**, #2 silver, #3 bronze, rest show #4, #5, etc.
- Each row shows: rank badge, avatar initial, name, top 3 skills, HireCred score (color-coded), appreciation count
- Clicking a row navigates to that candidate's public profile
- The leaderboard is cached for 10 minutes — adding a new candidate won't appear instantly

**Ranking formula used:**
```
rank = (credibility_score × 0.5) + (appreciation_count × 2) + (avg_ratings × 3) + (view_count × 0.1)
```

---

### Feature 10 — Fake Review Detection

**This is a background feature — you won't trigger it manually, but you can observe its effect.**

**To test it:**

1. As Client, submit **3+ appreciations** for the same candidate using **generic, identical-sounding text:**
   - `"Great work, highly recommend!"`
   - `"Amazing freelancer, would hire again!"`
   - `"Perfect work, 10/10, great communication!"`
2. After the 3rd appreciation, wait 10–15 seconds
3. Reload the candidate's profile

**What to verify:**
- If fraud is detected (high risk):
  - The **HireCred Score decreases** (by 7 for medium, by 15 for high)
  - The **Appreciations section header** shows a red **"⚠ Suspicious Reviews"** badge
- If reviews look genuine:
  - After 3+ real appreciations, a green **"✓ Verified Feedback"** badge appears in the Appreciations header
  - This badge only shows when: `count ≥ 3 AND fraud_risk = "low"`

---

## 4. Full End-to-End Hiring Flow (Demo Script)

Follow this sequence to test everything connected together:

```
1. Register as Candidate → fill profile completely (bio, 3+ skills, experience, portfolio, proof signals)
2. Save profile → wait for HireCred Score to compute → note the score
3. Register as Client → go to Search
4. Search "reliable React developer with portfolio" → find the candidate in results
5. Click "View Profile" from search results → inspect the score widget
6. Click "Send Message" → send a message in the inbox
7. Switch to Candidate → check Inbox → reply to the message
8. Switch to Client → give Appreciation with a detailed paragraph
9. Observe AI-extracted ratings in the modal
10. Reload candidate profile → see appreciation in list + rating bars updated
11. Go to Leaderboard → candidate appears (score updates within 10 min cache cycle)
12. Submit 3 generic appreciations → observe fraud badge / score drop
```

---

## 5. API Testing (Optional — via Swagger)

All endpoints are documented at: **http://localhost:8000/docs**

To test authenticated endpoints in Swagger:
1. Call `POST /api/auth/login` → copy the `access_token` from the response
2. Click **"Authorize"** (top right of Swagger UI)
3. Enter: `Bearer <your-token>`
4. Now all protected endpoints work

**Key endpoints to verify manually:**
| Endpoint | Method | Auth | Test |
|----------|--------|------|------|
| `/api/auth/register` | POST | None | Register user |
| `/api/auth/login` | POST | None | Get JWT token |
| `/api/auth/me` | GET | Yes | Returns current user |
| `/api/profile/{user_id}` | GET | None | Returns full profile |
| `/api/profile/{user_id}/score` | GET | None | Returns credibility score |
| `/api/leaderboard` | GET | None | Returns top 20 candidates |
| `/api/appreciation/{user_id}` | GET | None | Returns appreciation list |
| `/api/messages/conversations` | GET | Yes | Returns conversation list |
| `/api/messages/conversation/{id}` | GET | Yes | Returns message thread |

---

## 6. Common Issues & Fixes

| Problem | Likely Cause | Fix |
|---------|-------------|-----|
| Score shows "—" and never loads | Background task failed (Claude API key invalid or profile empty) | Check `.env` for `ANTHROPIC_API_KEY`, fill profile before saving |
| Search returns no results | No candidates in DB or skills don't overlap | Register a candidate, fill skills, then search for those exact skills |
| "Only clients can submit appreciations" error | Logged in as a candidate | Log in as a client account |
| Leaderboard empty | No candidates have credibility scores yet | Save a filled candidate profile first to trigger scoring |
| Messages not appearing | Polling delay | Wait 5 seconds or manually refresh the page |
| File upload fails for screenshot | Server uploads folder missing or wrong content-type | Ensure `server/uploads/` folder exists; upload only images (jpg, png) |
| 401 Unauthorized on API calls | JWT expired or not set | Log out and log in again |
