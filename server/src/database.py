from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from src.config import settings


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
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
