from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from atlas.config import get_settings
from atlas.errors import AppError


@lru_cache
def get_engine() -> AsyncEngine | None:
    settings = get_settings()
    if not settings.database_url:
        return None
    connect_args: dict[str, object] = {}
    if ":6543/" in settings.database_url:
        connect_args["statement_cache_size"] = 0
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        connect_args=connect_args,
    )


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession] | None:
    engine = get_engine()
    if engine is None:
        return None
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    if factory is None:
        raise AppError(
            "service_not_configured",
            "The database connection has not been configured.",
            status_code=503,
        )
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def close_database() -> None:
    engine = get_engine()
    if engine is not None:
        await engine.dispose()
    get_session_factory.cache_clear()
    get_engine.cache_clear()
