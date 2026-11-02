"""Runtime settings, loaded from environment / .env."""

from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Shipping this value to production is a critical misconfiguration; main.lifespan
# logs a warning if it is still in use at startup.
DEV_JWT_SECRET = "dev-insecure-secret-change-me-in-production-only"

# Default persona for the AI chat; override via GEMINI_SYSTEM_PROMPT to tune tone
# without a code change.
DEFAULT_GEMINI_SYSTEM_PROMPT = """\
You are Fen, the friendly nutrition buddy inside FoodFen. You help people—especially
teens and young adults—understand what they eat and build better habits, without ever
sounding like a textbook or a diet influencer.

VOICE
- Talk like a smart, supportive friend, not a doctor or a lecture. Casual, warm, upbeat.
- Keep it short. 2-4 sentences per reply unless the user clearly wants depth (recipes,
  meal plans, breakdowns) — then use clear headers/bullets instead of walls of text.
- Emoji are fine in moderation (1-3 per message) to add warmth, never spam.
- Use plain language over jargon. If you use a term like "glycemic index" or "macros,"
  explain it in one short clause the first time.
- Be encouraging, never preachy or guilt-trippy. No fear-mongering about "bad foods."
  Food is not moral — nothing is "good" or "bad," some choices just fuel you better.

WHAT YOU DO
- Explain nutrition facts, ingredients, and how food affects energy, mood, and health
  in relatable terms (e.g. "this is basically your body's fast-charge fuel").
- Help log meals, estimate calories/macros, and read nutrition labels.
- Suggest budget-friendly, easy-to-make swaps and recipes for students/young people
  (dorm-friendly, quick, minimal cooking skill assumed unless told otherwise).
- Answer "is X healthy" questions with balanced, non-judgmental context, not a verdict.
- Celebrate small wins ("adding veggies to your ramen? that's a win") to keep motivation up.

USING THE USER'S DATA
- When a "DATA ABOUT THIS USER" section follows, ground your advice in it: compare what
  they ate with their daily goal and point out patterns across the last 7 days.
- Never invent numbers that aren't in that data. If something is missing, say so and
  suggest logging it in the app.
- "not logged" means unknown, not that they ate nothing.
- If the user's age is under 18, don't push calorie deficits or weight-loss targets even
  if a goal is set; focus on balanced, regular meals.

WHAT YOU DON'T DO
- No medical diagnoses, no prescribing supplements/medication, no treating eating
  disorders — for red flags (disordered eating patterns, extreme restriction, mentions
  of self-harm), gently encourage talking to a doctor, school counselor, or trusted
  adult, and provide a helpline if appropriate. Never shame or interrogate.
- No extreme diets, detoxes, fasting protocols for minors, or weight-loss pressure.
- Don't assume a goal (weight loss, bulking, etc.) — use the one in the user's data if present; otherwise ask, or stay neutral until told.
- No long disclaimers or "I am an AI" hedging in every message — say it once if truly
  relevant, otherwise just help.

FORMAT
- Default to conversational prose. Use bullet points/tables only for structured data
  like meal plans, nutrient breakdowns, or comparisons.
- When citing nutrition numbers, keep them approximate and easy to scan
  (e.g. "~250 kcal, 8g protein") rather than clinical precision.
"""

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

    # Reverse proxies in front of the app that each append to X-Forwarded-For (Render: 1).
    # The client IP is the Nth entry from the right; anything left of it is client-controlled.
    # 0 = no proxy, use the socket peer.
    trusted_proxy_hops: int = 1

    # Comma-separated allowed origins for browser clients, or "*" for any origin
    # (safe here since auth is a Bearer header, not cookies, so allow_credentials
    # stays False).
    cors_allow_origins: str = "*"

    # "console" logs the link; "brevo" sends via Brevo's HTTP API. Anything else fails at startup.
    email_backend: Literal["console", "brevo"] = "console"
    # Must be a sender (address or domain) verified in Brevo (the local default only works for "console").
    email_from: str = "no-reply@foodfen.local"
    brevo_api_key: str = ""

    # Startup bootstrap (db/bootstrap.py): with both set, that account is created / promoted to admin
    # (an existing account keeps its password). SEED_DEMO adds fictional restaurants; keep it off in prod.
    admin_email: str = ""
    admin_password: str = ""
    seed_demo: bool = False

    # Comma-separated (an app usually has more than one client id). Empty
    # fails that provider's sign-in closed rather than accepting any audience.
    google_oauth_client_ids: str = ""
    apple_client_ids: str = ""

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3-flash-preview"
    gemini_system_prompt: str = DEFAULT_GEMINI_SYSTEM_PROMPT
    chat_history_limit: int = 10
    # Kill switch (env FOOD_ANALYSIS_GROUNDING): off = the old ungrounded prompt and the new
    # response fields null/false, no deploy needed.
    food_analysis_grounding: bool = True

    # "cloudinary://<api_key>:<api_secret>@<cloud_name>" — the SDK's own URL shape.
    cloudinary_url: str = ""

    # PayOS (payos.vn) — VietQR / bank-transfer checkout for Premium purchases.
    # No default: empty must fail closed, same as the OAuth client ids.
    payos_client_id: str = ""
    payos_api_key: str = ""
    payos_checksum_key: str = ""
    # Frontend/deep-link URLs the user is redirected to after paying — not backend routes.
    payos_return_url: str = ""
    payos_cancel_url: str = ""
    payos_monthly_price_vnd: int = 49_000
    payos_annual_price_vnd: int = 499_000
    # MoMo (v2 gateway, captureWallet). Offered only when partner code, both keys and the IPN URL are set.
    momo_partner_code: str = ""
    momo_access_key: str = ""
    momo_secret_key: str = ""
    momo_endpoint: str = "https://test-payment.momo.vn"
    # Where MoMo sends the user after paying: the app's deep link (or an HTTPS bounce to it).
    momo_redirect_url: str = "foodfen://premium/return"
    # Public URL of POST /payments/webhook/momo.
    momo_ipn_url: str = ""
    # Quiz rewards (coins). Passed into the use cases by DI, so changing one is an env edit.
    quiz_daily_coins_per_correct: int = 4
    quiz_practice_coins_per_correct: int = 1
    quiz_practice_daily_cap: int = 10


settings = Settings()
