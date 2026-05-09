# HireCred — Local Setup Guide

## What you need running

1. **Ollama** (AI engine) — must be running with the model downloaded
2. **Backend** (FastAPI on port 8000)
3. **Frontend** (Vite on port 5173)

---

## Step 1 — Fix Ollama (do this first)

Your Ollama server is already running but has **no models installed**.
Run this in any terminal — it downloads ~9 GB, takes 5–15 min depending on your connection:

```powershell
ollama pull qwen2.5:3b
```

Wait until it says `success`. Verify with:

```powershell
ollama list
# Should show: qwen2.5:3b
```

> **Do NOT run `ollama serve` again** — it is already running in the background.
> If you ever reboot your PC, Ollama starts automatically. Just pull the model once.

---

## Step 2 — Start the backend

Open a new terminal:

```powershell
cd F:\hireCred-v1\server
.\.venv\Scripts\Activate.ps1
uvicorn main:app --reload --port 8000
```

You should see `Application startup complete.` with no errors.

---

## Step 3 — Start the frontend

Open another terminal:

```powershell
cd F:\hireCred-v1\client
npm run dev
```

Open **http://localhost:5173** in your browser.

---

## Verify Ollama is working

After pulling the model, test it directly:

```powershell
ollama run qwen2.5:3b "Reply with: OK"
# Should print: OK
```

If it prints `OK`, the model is ready. The backend will then use it for all AI features.

---

## Common errors and fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `404 Not Found` on `/api/generate` | Model not downloaded | Run `ollama pull qwen2.5:3b` |
| `bind: Only one usage of each socket address` | Ollama already running | Do nothing — it's fine, don't run `ollama serve` again |
| `ollama list` shows empty | Model not pulled | Run `ollama pull qwen2.5:3b` |
| Backend starts but AI returns fallback scores | Ollama model not ready | Wait for pull to finish, restart backend |
| `ValidationError` on profile save | Dummy/placeholder data entered | Use real URLs, real bio text (min 80 chars) |

---

## Environment variables

The backend reads from `server/.env`. Required variables:

```env
DATABASE_URL=postgresql+asyncpg://...neon.tech/hirecred?sslmode=require
JWT_SECRET=your_secret_here
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b
OLLAMA_CTX=8192
```

`OLLAMA_HOST`, `OLLAMA_MODEL`, and `OLLAMA_CTX` have those defaults built in — you only need them in `.env` if you want to override.

---

## Quick start (once Ollama model is pulled)

```powershell
# Terminal 1 — Backend
cd F:\hireCred-v1\server
.\.venv\Scripts\Activate.ps1
uvicorn main:app --reload --port 8000

# Terminal 2 — Frontend
cd F:\hireCred-v1\client
npm run dev
```

Then open http://localhost:5173
