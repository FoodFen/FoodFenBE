"""Request-scoped database session dependency."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.session import get_db_session

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
