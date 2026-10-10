"""Database session dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.session import get_db_session

# scope="function": commit/rollback when the endpoint returns, i.e. before the response is sent and
# before BackgroundTasks run (the default "request" scope would commit after both).
SessionDep = Annotated[AsyncSession, Depends(get_db_session, scope="function")]
# Only for a route whose StreamingResponse generator keeps using the session after the endpoint returns.
StreamSessionDep = Annotated[AsyncSession, Depends(get_db_session, scope="request")]
