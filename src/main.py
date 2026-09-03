"""Application factory: router, domain-exception handlers, lifespan DB check."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from src.adapters.controllers.auth_controller import router as auth_router
from src.adapters.controllers.user_controller import router as user_router
from src.domain.exceptions import (
    AuthenticationException,
    DomainException,
    EntityNotFoundException,
    InvalidAttributeException,
    UserAlreadyExistsException,
)
from src.infrastructure.config import DEV_JWT_SECRET, settings
from src.infrastructure.db.session import engine

_log = logging.getLogger("foodfenbe")

# Domain exception type -> HTTP status. Registration order is irrelevant: Starlette
# resolves a raised exception against the most specific registered base via its MRO.
_EXCEPTION_STATUS: list[tuple[type[DomainException], int]] = [
    (InvalidAttributeException, 400),  # + InvalidUserAttributeException, WeakPasswordException
    (UserAlreadyExistsException, 409),
    (AuthenticationException, 401),  # + InvalidCredentialsException, InvalidTokenException
    (EntityNotFoundException, 404),  # + UserNotFoundException
    (DomainException, 400),  # catch-all
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.jwt_secret == DEV_JWT_SECRET:
        _log.warning(
            "JWT_SECRET is the insecure development default — set a real one in production"
        )
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    yield
    await engine.dispose()


def _domain_exception_handler(status_code: int):
    headers = {"WWW-Authenticate": "Bearer"} if status_code == 401 else None

    async def handler(_: Request, exc: DomainException) -> JSONResponse:
        return JSONResponse(
            status_code=status_code, content={"detail": str(exc)}, headers=headers
        )

    return handler


def create_app() -> FastAPI:
    app = FastAPI(title="FoodFenBE", version="0.1.0", lifespan=lifespan)
    app.include_router(auth_router)
    app.include_router(user_router)

    for exc_type, status_code in _EXCEPTION_STATUS:
        app.add_exception_handler(exc_type, _domain_exception_handler(status_code))

    return app


app = create_app()
