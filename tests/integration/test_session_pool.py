"""_discard_idle_connections: a pooled connection is reused while fresh, replaced once it sat idle too long."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import create_async_engine

from src.infrastructure.db.session import _MAX_IDLE_SECONDS, _discard_idle_connections


async def _checkout(engine):
    """(driver connection, the pool record's ``info`` dict, which outlives the checkout)"""
    async with engine.connect() as conn:
        raw = await conn.get_raw_connection()
        return raw.driver_connection, raw.info


async def test_idle_connection_is_replaced_and_fresh_one_is_reused(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'pool.db'}")  # file DB: a real pool
    _discard_idle_connections(engine)

    first, info = await _checkout(engine)
    assert (await _checkout(engine))[0] is first  # fresh: reused

    info["idle_since"] -= _MAX_IDLE_SECONDS + 1  # it "sat in the pool" too long
    replaced, _ = await _checkout(engine)

    assert replaced is not first
    await engine.dispose()
