import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from src.config import settings

logger = logging.getLogger(__name__)


def _make_async_url(url: str) -> tuple[str, dict]:
    """Normalize any postgres URL to asyncpg dialect.
    Strips all query params (sslmode, channel_binding, etc.) and returns
    ssl setting via connect_args instead — asyncpg only accepts those.
    """
    ssl = "sslmode=require" in url or "sslmode=verify" in url

    # Strip everything after '?' — asyncpg handles none of these params
    base = url.split("?")[0]

    for prefix in ("postgres://", "postgresql://"):
        if base.startswith(prefix):
            base = "postgresql+asyncpg://" + base[len(prefix):]
            break

    return base, ({"ssl": True} if ssl else {})


_db_url, _connect_args = _make_async_url(settings.database_url)
engine = create_async_engine(
    _db_url,
    connect_args=_connect_args,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def ping_db(retries: int = 6) -> bool:
    """Ping DB with exponential backoff. Handles Neon free-tier cold-start delays."""
    for attempt in range(retries):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("Database connection established.")
            return True
        except Exception as exc:
            if attempt < retries - 1:
                wait = min(2 ** attempt, 30)
                logger.warning(
                    "DB ping attempt %d/%d failed (%s). Retrying in %ds...",
                    attempt + 1, retries, exc, wait,
                )
                await asyncio.sleep(wait)
            else:
                logger.error("DB unreachable after %d attempts: %s", retries, exc)
    return False


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
