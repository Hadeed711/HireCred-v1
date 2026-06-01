# HireCred — Local Setup Guide

**Last updated: 2026-06-01**

---

## Prerequisites

1. **Ollama** — local AI engine (must be running with model downloaded)
2. **Python 3.11+** with venv
3. **Node.js 18+** with npm
4. **Neon PostgreSQL** — connection string in `.env`

---

## Step 1 — Ollama Setup

Pull the model (one-time, ~2 GB download):
```powershell
ollama pull qwen2.5:3b
```

Verify:
```powershell
ollama list
# Should show: qwen2.5:3b
```

> Ollama starts automatically on boot on Windows. Do NOT run `ollama serve` again if it's already running — it will fail with "address already in use."

---

## Step 2 — Backend Setup

```powershell
cd F:\hireCred-v1\server
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> `requirements.txt` includes `slowapi==0.1.9` for rate limiting on auth endpoints. If you see `ModuleNotFoundError: No module named 'slowapi'`, re-run pip install.

Create a `.env` file in `server/`:
```env
DATABASE_URL=postgresql+asyncpg://user:pass@host.neon.tech/hirecred
JWT_SECRET=your-secret-here
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b
SUPER_ADMIN_EMAILS=your@email.com
```

Run migrations:
```powershell
alembic upgrade head
```

Start the server:
```powershell
uvicorn main:app --reload --port 8000
```

You should see `Application startup complete.` with no errors.

> **Neon cold-start:** On startup the server automatically pings the database with exponential-backoff retries (up to 6 attempts) before accepting requests. This wakes the Neon free-tier database if it was sleeping. You will see log lines like `DB ping attempt 1/6 failed… retrying in 1s`. This is normal — the server is not broken; it is waiting for Neon to wake up. Within a few seconds you will see `Database connection established.` and the server becomes fully ready.
>
> If the database is still waking up when a request arrives, the API returns HTTP 503 ("Database temporarily unavailable — please try again in a few seconds") instead of a crash.

---

## Step 3 — Frontend Setup

```powershell
cd F:\hireCred-v1\client
npm install
npm run dev
```

Open **http://localhost:5173**

---

## Step 4 — Verify Everything

| Check | URL |
|-------|-----|
| Backend alive | http://localhost:8000/health |
| Ollama alive | http://localhost:8000/health/ai |
| Frontend | http://localhost:5173 |
| Swagger docs | http://localhost:8000/docs |

---

## Setting Up Admin Access

Admin portal uses a dedicated login URL (separate from regular user login):

- Regular login: http://localhost:5173/login
- Admin login: http://localhost:5173/admin/login

After registering your account, set it as admin directly in the DB (recommended bootstrap path):

```sql
UPDATE users SET is_admin = true WHERE email = 'your@email.com';
```

Then restart the backend. Admin users see an "Admin" link in the Dashboard nav.

**API-based promotion** (requires an existing admin JWT):
```
PUT /api/admin/users/{user_id}/set-admin?is_admin=true
Authorization: Bearer <admin_jwt>
```

This is restricted to emails listed in `SUPER_ADMIN_EMAILS` in `.env`.

---

## Scoring Behaviour

- Score computation is **always asynchronous** — profile saves, CV uploads, and proof signal changes return immediately (< 1s).
- The score updates in the background (typically 5–30s depending on Ollama speed). The ScoreWidget polls automatically.
- If Ollama is unavailable or times out (10s limit), a rule-based fallback runs instead.
- Profile owners can click **"Refresh"** on the HireCred Score widget to manually trigger recomputation via `POST /api/profile/{id}/rescore`.

---

## CV Upload

- PDF only, max 5 MB.
- The file is stored at `server/uploads/cv/{user_id}.pdf`.
- No text extraction or AI analysis runs on the CV — only the presence of a CV (yes/no) is passed to the scoring LLM as a binary signal contributing up to 12 pts.

---

## Key Config Files

| File | Purpose |
|------|---------|
| `server/.env` | DB URL, JWT secret, Ollama config, super admin emails |
| `server/src/config.py` | Pydantic settings (reads .env) |
| `server/src/database.py` | Async SQLAlchemy engine (pool_pre_ping, pool_recycle, pool_size=10, max_overflow=20) |
| `server/src/rate_limiter.py` | Shared slowapi Limiter instance (imported by routers) |
| `server/alembic.ini` | Alembic migration config |
| `client/.env` (optional) | `VITE_API_URL` if backend not on localhost:8000 |

---

## Running After a Code Pull

```powershell
# Always run migration after pulling
cd F:\hireCred-v1\server
.\.venv\Scripts\Activate.ps1
alembic upgrade head
uvicorn main:app --reload --port 8000
```
