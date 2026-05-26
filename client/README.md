# HireCred — Frontend

**Last updated: 2026-05-27**

React 18 + TypeScript + Vite + TailwindCSS v4 frontend for the HireCred trust platform.

---

## Stack

| Tool | Purpose |
|------|---------|
| React 18 | UI framework |
| TypeScript | Type safety |
| Vite | Dev server + bundler |
| TailwindCSS v4 | Styling |
| Zustand | Auth state (`authStore`) |
| TanStack Query | Server state, caching, polling |
| Axios | HTTP client with JWT interceptor |
| lucide-react | All icons (no inline SVGs) |
| react-hot-toast | Toast notifications |
| react-router-dom v6 | Routing |

---

## Pages

| Route | File | Access |
|-------|------|--------|
| `/login` | `Login.tsx` | Public |
| `/register` | `Register.tsx` | Public |
| `/dashboard` | `Dashboard.tsx` | Auth |
| `/profile/edit` | `ProfileEditor.tsx` | Candidate only |
| `/profile/:userId` | `ProfileView.tsx` | Public |
| `/search` | `SearchPage.tsx` | Client only |
| `/leaderboard` | `Leaderboard.tsx` | Public |
| `/inbox` | `Inbox.tsx` | Auth |
| `/inbox/:userId` | `Inbox.tsx` | Auth |
| `/admin/login` | `AdminLogin.tsx` | Public |
| `/admin` | `AdminPanel.tsx` | Admin only |

---

## Key Components

| Component | Purpose |
|-----------|---------|
| `ScoreWidget` | HireCred score ring + refresh button + strengths/risks/flags |
| `SkillsTagInput` | Tag-style skill input (no validation warnings) |
| `ValidationWarningBanner` | Non-blocking profile save warnings |
| `AppreciationModal` | Client appreciation submission |
| `AppreciationSection` | Appreciation list with fraud-risk context |

---

## Dev Commands

```bash
npm install       # install dependencies
npm run dev       # start dev server (http://localhost:5173)
npm run build     # production build
npm run preview   # preview production build
```

---

## Environment

Optional: create `client/.env` to override the API base URL:
```env
VITE_API_URL=http://localhost:8000
```

Default: `http://localhost:8000` (hardcoded in `src/lib/api.ts`).

---

## Design Notes

- All icons use **lucide-react** — no raw SVG tags in JSX
- Password inputs suppress browser native eye toggle via CSS (`::-ms-reveal`, `::-webkit-credentials-auto-fill-button`)
- Score polling: `refetchInterval: 3000` until score appears, then stops
- Background scoring: all saves show "Score updating in background…" toast; score appears automatically via TanStack Query polling
- Portfolio "tech_stack" field is labelled "Skills" in both editor and profile view
- Register endpoint now returns `{access_token, user}` — user is logged in immediately after registration (no separate login needed)
- Search requires minimum 2 characters; validated client-side (toast) and server-side (400)
