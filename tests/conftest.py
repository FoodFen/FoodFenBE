"""Tests run on in-memory SQLite, never on the DATABASE_URL from .env.

The env vars must be set before ``src`` is imported: ``settings`` and the module-level engine
read them at import. The shims below paper over where SQLite differs from the Postgres prod DB.
"""

import itertools
import os
from datetime import timezone

os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from sqlalchemy import event, types  # noqa: E402
from sqlalchemy.dialects.sqlite import DATETIME  # noqa: E402
from sqlalchemy.dialects.sqlite.aiosqlite import SQLiteDialect_aiosqlite  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402

from src.infrastructure.db.models.payment_model import PaymentORM  # noqa: E402


@event.listens_for(Engine, "connect")
def _enable_foreign_keys(dbapi_connection, _record) -> None:
    # SQLite ignores FKs (and so ON DELETE CASCADE) unless asked, per connection.
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


class _UTCDateTime(DATETIME):
    """SQLite drops tzinfo; Postgres returns aware datetimes, and the domain compares against those."""

    def result_processor(self, dialect, coltype):
        parse = super().result_processor(dialect, coltype)
        return lambda v: (d := parse(v)) and d.replace(tzinfo=timezone.utc)


SQLiteDialect_aiosqlite.colspecs = {**SQLiteDialect_aiosqlite.colspecs, types.DateTime: _UTCDateTime}

_order_codes = itertools.count(1)


@event.listens_for(PaymentORM, "before_insert")
def _fake_identity(_mapper, _conn, row: PaymentORM) -> None:
    # `order_code` is a non-PK IDENTITY column on Postgres; SQLite has no equivalent.
    if row.order_code is None:
        row.order_code = next(_order_codes)
