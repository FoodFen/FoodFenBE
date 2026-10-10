"""Async engine, session factory, and the per-request session dependency."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.infrastructure.config import settings

engine = create_async_engine(settings.database_url, echo=settings.db_echo, pool_pre_ping=True)

SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """One session (= one unit of work) per endpoint call: commit on success, roll back on error.

    Commits when the endpoint function returns (see ``SessionDep``), not after the response.

    ponytail: per-endpoint transaction boundary. If a use case ever needs finer
    control (nested transactions, savepoints), give it an explicit UoW object instead.
    """
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
