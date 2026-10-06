"""Database session dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.session import get_db_session

# Committed when the endpoint function returns, i.e. before the response and background tasks.
SessionDep = Annotated[AsyncSession, Depends(get_db_session, scope="function")]
# Same session factory, but lives until the response body is fully sent (SSE writes mid-stream).
# FastAPI's dependency cache is keyed on (callable, scope), so this is a separate session from
# SessionDep's even within one request.
StreamSessionDep = Annotated[AsyncSession, Depends(get_db_session, scope="request")]
