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
    verification_token_expire_hours: int = 24
    # Shorter than verification: a leaked reset link is more damaging.
    password_reset_token_expire_minutes: int = 60

    app_base_url: str = "http://localhost:8000"

    email_backend: str = "console"  # "console" logs the link; "smtp" actually sends
    email_from: str = "no-reply@foodfen.local"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = True

    # Comma-separated (an app usually has more than one client id). Empty
    # fails that provider's sign-in closed rather than accepting any audience.
    google_oauth_client_ids: str = ""
    apple_client_ids: str = ""


settings = Settings()
