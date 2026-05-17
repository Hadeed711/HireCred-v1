# HireCred — Local Setup Guide

**Last updated: 2026-05-18**

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

> **Note:** The server uses `pool_pre_ping=True` and `pool_recycle=1800` on the DB connection pool — this prevents "connection is closed" errors on long-idle Neon connections.

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

- Score computation is **always asynchronous** — profile saves, CV uploads, and proof signal changes return immediately.
- The score updates in the background (typically 5–30s depending on Ollama speed).
- If Ollama is unavailable, a rule-based fallback runs instead.
- Profile owners can click **"Refresh"** on the HireCred Score widget to manually trigger recomputation.

---

## CV Upload

- PDF only, max 5 MB.
- The file is stored at `server/uploads/cv/{user_id}.pdf`.
- No text extraction or AI analysis runs on the CV — only the presence of a CV is passed to the scoring LLM.

---

## Key Config Files

| File | Purpose |
|------|---------|
| `server/.env` | DB URL, JWT secret, Ollama config, super admin emails |
| `server/src/config.py` | Pydantic settings (reads .env) |
| `server/src/database.py` | Async SQLAlchemy engine (pool_pre_ping, pool_recycle) |
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
