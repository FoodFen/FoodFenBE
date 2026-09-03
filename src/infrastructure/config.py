"""Runtime settings, loaded from environment / .env."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

# Shipping this value to production is a critical misconfiguration; main.lifespan
# logs a warning if it is still in use at startup.
DEV_JWT_SECRET = "dev-insecure-secret-change-me-in-production-only"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5433/foodfen"
    db_echo: bool = False

    jwt_secret: str = DEV_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30


settings = Settings()
