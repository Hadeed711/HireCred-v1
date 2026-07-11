import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from src.rate_limiter import limiter
from src.routers import auth, profile, proof_signals, appreciation, search, leaderboard, messages
from src.routers import validate
from src.routers.reports import reports_router, admin_router

logger = logging.getLogger(__name__)

UPLOADS_DIR = Path(__file__).parent / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)
(UPLOADS_DIR / "cv").mkdir(exist_ok=True)
(UPLOADS_DIR / "messages").mkdir(exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.database import ping_db, engine
    logger.info("Warming up database connection (Neon cold-start)...")
    ok = await ping_db(retries=6)
    if not ok:
        logger.warning("Database warmup failed — first requests may be slow or fail.")
    yield
    # Graceful shutdown: close shared HTTP pools and the DB engine so
    # in-flight sockets aren't abandoned.
    from src.services.url_checker import close_url_checker_client
    from src.ai.ollama_client import close_ollama_client
    await close_url_checker_client()
    await close_ollama_client()
    await engine.dispose()


app = FastAPI(title="HireCred API", version="1.0.0", lifespan=lifespan)


def _is_db_connection_error(exc: BaseException) -> bool:
    """Walk the exception chain looking for asyncpg or timeout errors."""
    seen = set()
    current = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        name = type(current).__name__
        module = type(current).__module__ or ""
        if "asyncpg" in module or name in ("TimeoutError", "ConnectionRefusedError"):
            return True
        current = current.__cause__ or current.__context__
    return False


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if _is_db_connection_error(exc):
        logger.warning("DB connection error on %s: %s", request.url.path, exc)
        return JSONResponse(
            status_code=503,
            content={"detail": "Database temporarily unavailable — please try again in a few seconds."},
        )
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

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


@app.get("/health/queue")
async def health_queue():
    """Background scoring queue stats — scheduled/coalesced/in-flight/failed."""
    from src.services.task_manager import queue_stats
    return queue_stats()
