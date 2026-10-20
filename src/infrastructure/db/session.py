"""Async engine, session factory, and the per-request session dependency."""

from __future__ import annotations

import time
from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.exc import DisconnectionError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from src.infrastructure.config import settings

_MAX_IDLE_SECONDS = 240


def _discard_idle_connections(engine: AsyncEngine) -> None:
    """Replace a pooled connection that sat idle longer than ``_MAX_IDLE_SECONDS`` on checkout.

    Instead of ``pool_pre_ping``, whose ``BEGIN; SELECT 1; ROLLBACK`` costs 3 round trips per request.

    ponytail: the limit sits under Neon free's 5-minute compute auto-suspend (which kills
    connections). A connection dropped for another reason within the window fails one request
    (SQLAlchemy then invalidates the pool); restore ``pool_pre_ping`` if that shows up in logs.
    """

    def stamp(_dbapi_conn, record, *_) -> None:
        record.info["idle_since"] = time.monotonic()

    def check(_dbapi_conn, record, _proxy) -> None:
        if time.monotonic() - record.info["idle_since"] > _MAX_IDLE_SECONDS:
            raise DisconnectionError("idle too long")

    event.listen(engine.sync_engine, "connect", stamp)
    event.listen(engine.sync_engine, "checkin", stamp)
    event.listen(engine.sync_engine, "checkout", check)


# Postgres only: the SQLite test engine is a StaticPool (no LIFO) whose one connection must never be replaced.
_is_pg = settings.database_url.startswith("postgresql")
# LIFO: reuse the warm connection (its prepared-statement cache is hot); extras age out.
engine = create_async_engine(
    settings.database_url, echo=settings.db_echo, **({"pool_use_lifo": True} if _is_pg else {})
)
if _is_pg:
    _discard_idle_connections(engine)

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
