"""Application factory: router registration, lifespan DB check.

Domain-exception -> HTTP-status mapping lives in ``src/adapters/exception_handlers.py``.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from src.adapters.controllers.activity_log_controller import router as activity_log_router
from src.adapters.controllers.auth_controller import router as auth_router
from src.adapters.controllers.chat_controller import router as chat_router
from src.adapters.controllers.daily_goal_controller import router as daily_goal_router
from src.adapters.controllers.food_analysis_controller import router as food_analysis_router
from src.adapters.controllers.food_entry_controller import router as food_entry_router
from src.adapters.controllers.payment_controller import router as payment_router
from src.adapters.controllers.subscription_controller import router as subscription_router
from src.adapters.controllers.user_controller import router as user_router
from src.adapters.controllers.water_log_controller import router as water_log_router
from src.adapters.controllers.weight_log_controller import router as weight_log_router
from src.adapters.exception_handlers import register_exception_handlers
from src.infrastructure.config import DEV_JWT_SECRET, settings
from src.infrastructure.db.session import engine
from src.infrastructure.logging import configure_logging

_log = configure_logging()


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


def create_app() -> FastAPI:
    app = FastAPI(title="FoodFenBE", version="0.1.0", lifespan=lifespan)
    app.include_router(auth_router)
    app.include_router(user_router)
    app.include_router(chat_router)
    app.include_router(food_analysis_router)
    app.include_router(food_entry_router)
    app.include_router(payment_router)
    app.include_router(subscription_router)
    app.include_router(daily_goal_router)
    app.include_router(activity_log_router)
    app.include_router(water_log_router)
    app.include_router(weight_log_router)
    register_exception_handlers(app)
    return app


app = create_app()
