"""Application factory: router, domain-exception handlers, lifespan DB check."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from src.adapters.controllers.user_controller import router as user_router
from src.domain.exceptions import (
    DomainException,
    EntityNotFoundException,
    InvalidUserAttributeException,
    UserAlreadyExistsException,
)
from src.infrastructure.db.session import engine

# Domain exception type -> HTTP status. Order matters: most specific first.
_EXCEPTION_STATUS: list[tuple[type[DomainException], int]] = [
    (InvalidUserAttributeException, 400),
    (UserAlreadyExistsException, 409),
    (EntityNotFoundException, 404),  # covers UserNotFoundException
    (DomainException, 400),  # catch-all
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    yield
    await engine.dispose()


def _domain_exception_handler(status_code: int):
    async def handler(_: Request, exc: DomainException) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    return handler


def create_app() -> FastAPI:
    app = FastAPI(title="FoodFenBE", version="0.1.0", lifespan=lifespan)
    app.include_router(user_router)

    for exc_type, status_code in _EXCEPTION_STATUS:
        app.add_exception_handler(exc_type, _domain_exception_handler(status_code))

    return app


app = create_app()
