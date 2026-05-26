from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from src.rate_limiter import limiter
from src.routers import auth, profile, proof_signals, appreciation, search, leaderboard, messages
from src.routers import validate
from src.routers.reports import reports_router, admin_router

UPLOADS_DIR = Path(__file__).parent / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)
(UPLOADS_DIR / "cv").mkdir(exist_ok=True)
(UPLOADS_DIR / "messages").mkdir(exist_ok=True)

app = FastAPI(title="HireCred API", version="1.0.0")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(proof_signals.router)
app.include_router(appreciation.router)
app.include_router(search.router)
app.include_router(leaderboard.router)
app.include_router(messages.router)
app.include_router(validate.router)
app.include_router(reports_router)
app.include_router(admin_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/health/ai")
async def health_ai():
    from src.ai.ollama_client import check_ollama_health
    return await check_ollama_health()
