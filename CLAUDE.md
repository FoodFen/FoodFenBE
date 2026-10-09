# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Clean Architecture. Python 3.11+, FastAPI, async SQLAlchemy 2.0, PostgreSQL, Pydantic v2, `uv`.
Dependency direction: `domain <- application <- adapters | infrastructure`. Never sideways, never inward-out.

## AI session tooling

> These assume `semble`, `ponytail`, and `superpowers` are available in your session (they're part
> of this repo owner's standard Claude Code setup). If a tool/skill named here isn't available to
> you, fall back to the plain equivalent (`Grep`/`Glob`, careful-by-hand review) rather than skipping
> the step it does.

- **Always** search with `mcp__semble__search` (CLI: `semble search "<query>" .`) to find where
  something is implemented, before reaching for `Grep`/`Glob`. Use `mcp__semble__find_related` to
  find similar code elsewhere in the repo. Reserve `Grep` for enumerating every literal occurrence
  of a known string (e.g. every caller of a renamed function) — not for first-pass discovery.
- **Always** apply `ponytail` discipline when writing or changing code here: climb the ladder (skip
  if speculative → reuse what's already in this repo → stdlib → native platform feature →
  already-installed dependency → one-liner → minimum code) before adding anything. No interfaces
  with one implementation, no config for a value that never changes, no scaffolding "for later" —
  this repo's Clean Architecture layers are already the intended structure, not a license to add
  more layers on top of them.
- **Model roles.** If you are running as an **Opus** model, you decide and review: brainstorming,
  specs, reviews (docs are fine to edit). **Never write or edit code yourself.** Every coding action
  is delegated to a subagent on a lower model (`model: "sonnet"`, or `"haiku"` for mechanical edits),
  which writes its own tests and code from the spec (TDD); then you review the diff.
- **Spec → code, no plan by default.** A slice gets a written spec (decisions, contract, files to
  touch, tests) and goes straight to the subagent. Write an implementation plan only when the work is
  split across several subagents, and then as a short task list (task, files, dependencies) —
  **never code in a plan**: a plan with full code is the implementation written twice, in Opus
  tokens. This overrides the `brainstorming` → `writing-plans` handoff.
- **Always** invoke the matching `superpowers` skill before starting non-trivial work:
  `brainstorming` before shaping a new feature or slice, `systematic-debugging` before proposing a
  bug fix, `test-driven-development` before implementation code, `verification-before-completion`
  before claiming something works or committing, `requesting-code-review` before opening a PR.

## Never

- **Never** import third-party packages in `src/domain/`. Standard library only (`dataclasses`, `typing`, `abc`, `re`, `uuid`, `datetime`).
- **Never** import `fastapi`, `sqlalchemy`, `pydantic`, `src.adapters`, or `src.infrastructure` from `src/application/`.
- **Never** define ports as `abc.ABC`. Ports are `typing.Protocol`.
- **Never** pass a Pydantic schema (or an ORM object) into a use case. Use cases take/return dataclass DTOs only.
- **Never** put business rules in controllers. They translate HTTP <-> DTO and nothing else.
- **Never** reuse a domain entity as an ORM model, or vice versa. They are separate classes with explicit `to_domain` / `from_domain`.
- **Never** raise `HTTPException` from application or domain. Raise a `DomainException` subclass;
  `src/adapters/exception_handlers.py` maps it to a status code (registered onto the app in `main.py`).
- **Never** catch domain exceptions in the controller. Let them propagate to the handlers.
- **Never** add a dependency for something a few lines of stdlib do.

## Always

- **Always** enforce entity invariants in the entity's `__post_init__` (or a factory), not in the use case or schema.
- **Always** construct new entities via the domain factory (`User.create(...)`), which sets
  timestamps / defaults (and, for `User` specifically, leaves `id=None` — see "Auth" below).
- **Always** access the DB session through the `get_db_session` dependency (commit-on-success, rollback-on-error per request).
- **Always** run `uv run lint-imports` after touching imports. It is the architecture's guardrail and CI must stay green.
- **Always** add an Alembic migration when you change an ORM model. Never edit the DB by hand.
- **Always** put a new use case's provider in `src/infrastructure/di/use_cases.py` (a `get_*_use_case`
  fn + an `Annotated[..., Depends(...)]` alias), re-exported from `src/infrastructure/di/__init__.py`.
  Repository providers go in `src/infrastructure/di/repositories.py`. All DI wiring lives in the
  `di/` package — controllers only ever import `from src.infrastructure.di import ...`, never define
  their own provider functions.
- **Always** use `Annotated` for router functions and other injected parameters that Python IDEs
  complain about (valid in FastAPI either way, but only `Annotated` type-checks cleanly). For example:

```python
async def create_user(
    body: CreateUserRequest,
    use_case: Annotated[CreateUserUseCase, Depends(get_create_user_use_case)],
    # Not: use_case: CreateUserUseCase = Depends(get_create_user_use_case)
) -> UserResponse:
```

  This applies to `di/use_cases.py` too — expose a named `Annotated[UseCase, Depends(provider)]`
  alias and use it in the route signature, rather than repeating `Annotated[...]` at each call site.

## Schema rules

- **Always** register a new ORM model in `src/infrastructure/db/models/__init__.py`. Alembic and
  `create_all` read `Base.metadata`; an unregistered model silently has no table.
- **Always** use `UUIDPrimaryKey` (not `IntPrimaryKey`) for a new table's own PK. `IntPrimaryKey`
  exists solely because the front-end contract types `User.id` as a number — `users` is the one
  deliberate exception. A UUID PK never needs a DB round-trip to know its own id.
- **Always** model a fixed set of strings as a `StrEnum` in `src/domain/enums.py` and map it with
  `enum_column()`. Never a bare `String`. `enum_column` sets `create_constraint=True` explicitly —
  SQLAlchemy has defaulted that to `False` since 1.4, so omitting it gives a VARCHAR with no CHECK.
- **Always** use `Decimal` / `Numeric` for money. Never `float`.
- **In migrations**, pass **bare** CHECK-constraint names (`"gender"`, not `"ck_users_gender"`) to
  `create_check_constraint` / `drop_constraint`. The metadata naming convention in
  `src/infrastructure/db/base.py` prefixes `ck_<table>_` itself; passing a full name yields
  `ck_users_ck_users_gender`. PK/FK/UNIQUE names are *not* composed this way — give those in full.
- **Always** set `lazy="selectin"` on a relationship whose `to_domain()` reads it. The async engine
  raises `MissingGreenlet` on a lazy load outside a greenlet context.
- **Always** verify a migration matches the models before committing: compare `alembic upgrade head
  --sql` against the DDL rendered from `Base.metadata`. Offline downgrade needs a range
  (`alembic downgrade 0002:0001 --sql`), not a single revision.

## Auth

> New to JWT auth? `docs/authentication.md` is a full beginner walk-through of the flow.
> The endpoint names, field names, and response shapes below follow a front-end API
> contract (a real client, not our own design) — see docs/authentication.md §0.

- **Endpoints**: `POST /auth/sign-up|sign-in|refresh|sign-out|social`, `POST /auth/password-reset`,
  `GET /auth/me`. `sign-up`/`sign-in`/`refresh`/`password-reset`/`social` need no bearer token;
  `sign-out` and `me` do. `verify-email` / `resend-verification` / `reset-password` are **extras**,
  not required by the contract.
- **Social sign-in** (`POST /auth/social`, Google/Apple): see `docs/social-sign-in.md`. Verifies the
  provider's identity token with PyJWT's `PyJWKClient` (no new heavyweight dependency), resolves via
  `social_identities` (migration 0006, unique on `(provider, provider_user_id)`), **auto-links** to
  an existing password account with the same verified email. A provider with no
  `GOOGLE_OAUTH_CLIENT_IDS`/`APPLE_CLIENT_IDS` configured fails closed (500), never open.
  `pyjwt[crypto]` (not bare `pyjwt`) is required — RS256 needs the `cryptography` package.
- **Wire format is camelCase**, not snake_case: `src/adapters/schemas/base.py::CamelModel`
  (`alias_generator=to_camel`). Python stays snake_case; the alias does the translation both ways.
- **`User.id` is an integer**, not a UUID — the contract types it as a number. Only `users` has an
  int PK (`IntPrimaryKey` mixin, autoincrement); every other table keeps a UUID PK. `User.id` is
  `None` until the row is inserted (an autoincrement id doesn't exist before that), unlike every
  other entity, which mints its own UUID up front in `.create()`.
- **Sign-up returns a live session immediately** — `RegisterResultDTO{session: AuthSessionDTO,
  verification_token}`. Email verification does **not** gate login; it's sent (via
  `BackgroundTasks`, since a use case can't reach it) but purely informational. Sign-in and refresh
  also return a full `AuthSessionDTO` (tokens + the `user`), via the shared
  `use_cases/token_pair.py::issue_session` helper.
- **Refresh token**: JWT (`type: "refresh"`, carries a `jti`); every issued one gets a
  `refresh_tokens` row (`jti` unique, `expires_at`, `revoked_at`). Accepted only if a matching
  **unrevoked, unexpired** row exists, so sign-out and rotation take effect immediately. Rotated on
  every `/auth/refresh` — single-use.
- **Password reset**: `POST /auth/password-reset {email}` always 2xx, enumeration-safe (mirrors
  `resend-verification`'s pattern). `POST /auth/reset-password {token, newPassword}` (extra, not in
  the contract — there is no "confirm" endpoint documented client-side) verifies a fourth JWT type
  (`password_reset`, short TTL) and updates the hash. The token carries a `stamp` claim
  (`User.password_stamp`) so it works once, and a successful reset revokes all the user's refresh tokens.
- **Client IP** (rate limits): the Nth entry from the right of `X-Forwarded-For`, N =
  `TRUSTED_PROXY_HOPS` (default 1, Render). uvicorn runs with `--no-proxy-headers`; never trust
  leftmost entries, they are client-supplied. Set `TRUSTED_PROXY_HOPS=0` with no proxy in front.
- **Failure body shape**: `{"message"?: str, "error"?: str, "errors"?: {field: str}}` — **not**
  FastAPI's default `{"detail": ...}`. `src/adapters/exception_handlers.py` overrides both domain
  exceptions and Pydantic's `RequestValidationError` to this shape. `UserAlreadyExistsException`
  (duplicate email at sign-up) gets its own handler: `errors.email`, not just a message.
- **Protected routes**: depend on `CurrentUserDep` (or `dependencies=[Depends(get_current_user)]`
  when the handler doesn't need the user, e.g. `sign-out`). `get_current_user` lives in
  `src/infrastructure/di/security.py`.
- **Swagger UI**: `get_current_user` depends on `OAuth2PasswordBearer(tokenUrl="auth/token")`, not
  `HTTPBearer` — same header extraction at runtime, but it makes `/docs`' Authorize button render a
  username/password form instead of a bare token field. `POST /auth/token` (form-encoded, per the
  OAuth2 spec) exists only as that form's target; it's `include_in_schema=False` and calls the same
  `LoginUseCase` as the real, JSON `POST /auth/sign-in`. Requires `python-multipart`.
- **Never** log, return, or persist a plaintext password. Hashing is `PasswordHasherProtocol`
  (bcrypt, cost 12) — the domain never sees bcrypt. No JWT is stored; only the refresh token's `jti` is.
- **Never** raise `HTTPException` for auth failures. Raise a `DomainException` subclass
  (`InvalidCredentialsException`/`InvalidTokenException` → 401); `src/adapters/exception_handlers.py`
  maps the type to a status. 401s also carry `WWW-Authenticate: Bearer`.
- Password policy (`>= 8` chars, `<= 72` bytes) is `User.validate_password_strength`, called by
  `RegisterUserUseCase` and `ResetPasswordUseCase`. `bcrypt` truncates past 72 bytes — the schema
  caps it too.
- App logs go through `configure_logging()` (`src/infrastructure/logging.py`) — a bare
  `getLogger("foodfenbe")` produces no output under uvicorn.
- `JWT_SECRET` has an insecure dev default; `main.lifespan` warns if it's still in use. Set a real one
  (`openssl rand -hex 32`) via env for anything shared.

## AI chat

- **Endpoints** (`src/adapters/controllers/chat_controller.py`, all `CurrentUserDep`-protected):
  `GET /chat/messages?before=&limit=` returns a page of history; `POST /chat/messages` streams the
  assistant's reply as SSE (`text/event-stream`), not JSON.
- **SSE contract**: `event: token` per delta (`{"delta": str}`), then either `event: done`
  (`{"message": ChatMessageResponse}`) or `event: error` (`{"message": str}`). A failure *before*
  streaming starts (auth, validation) is a normal 401/422; only a failure *after* the stream opens
  becomes an `event: error` frame, since headers are already committed at that point.
- **Persistence order** (`use_cases/send_chat_message.py`): the user's message is saved *before* the
  provider is called, so it's already in history if generation then fails. The assistant's reply is
  only persisted once fully generated — a failed or empty generation is discarded, not saved
  partially, and yields `event: error` instead.
- **Pagination cursor**: opaque `"{created_at.isoformat()}|{id}"`, encoded/decoded only by
  `src/application/chat_cursor.py` (stdlib-only, shared by the use case and the repository so they
  can't drift out of sync). The `id` tiebreaks same-timestamp rows at a page boundary.
- **Provider port**: `AiChatProviderProtocol` (`application/ports/ai_chat_provider.py`), implemented
  by `GeminiChatProvider` (`infrastructure/ai/gemini_chat_provider.py`) using `google-genai`.
  Gemini's role vocabulary (`user`/`model`) is translated from the domain `ChatRole` enum
  (`user`/`assistant`) only inside that class.
- **User context** (spec `docs/superpowers/specs/2026-10-05-chat-user-context-design.md`): every
  turn, `SendChatMessageUseCase._build_context` renders profile, goal in force, today's meals and
  7-day totals (`application/chat_context.py`, stdlib-only) and passes it as `stream_reply(...,
  context)`; Gemini appends it after the system prompt. Rebuilt per turn, never persisted.
  `POST /chat/messages` takes an optional `date` (client-local day; omitted → the Vietnam, UTC+7, day). A new source (food catalog,
  RAG retriever) adds one section in `_build_context`; the provider doesn't change.
- **System prompt is config, not code**: `settings.gemini_system_prompt` (default in
  `DEFAULT_GEMINI_SYSTEM_PROMPT`, `infrastructure/config.py`), overridable via
  `GEMINI_SYSTEM_PROMPT` without touching `gemini_chat_provider.py`. `settings.chat_history_limit`
  caps how many prior messages are sent to the model per turn.
- Tests never call the real Gemini API — `tests/api/conftest.py::FakeAiChatProvider` overrides
  `get_ai_chat_provider` with a scripted reply.

## Coins & quests

Design + defaults: `docs/superpowers/specs/2026-09-30-coins-quests-design.md`.

- **Endpoints** (`coin_controller.py`, `CurrentUserDep`): `GET /quests?date=` (client's local day),
  `POST /coins/redeem {days}`, `GET /coins/bundles` (public; the `coin_bundles` table, seeded in migration 0019:
  10 days / 600 coins, 30 days / 1500 coins; redeem prices from the same rows). `GET /payments/plans` (public) lists the
  monthly/annual prices from settings. `GET /quests` also takes `language=vi|en` and returns each quest's
  `unit` (`count`|`percent`, derived in `Quest.unit`), `completionRatio`, `title` and `description` (the
  `title_*`/`description_*` columns of `quest_definitions`: static text, edit it with SQL together with any
  target/ratio change).
- **Balance is `SUM(coin_transactions.amount)`**, never a stored field. Redeem takes the user row
  `FOR UPDATE` before checking it; insufficient coins → `InsufficientCoinsException` (409).
- **Quests are evaluated lazily** inside `GET /quests` from synced diary rows — the client never reports
  completion. Payout happens only for the request whose `QuestRepository.record()` flips `completed`
  (conditional UPDATE), so concurrent reads can't pay twice.
- **The catalog is the `quest_definitions` table** (seeded in migration 0012). What each `QuestType`
  *measures* lives in `SQLAlchemyQuestRepository.measure()`; a new type needs an evaluator there.
- **`PlanType.COIN_REDEEM` is not purchasable** — `CreateCheckoutRequest` only accepts monthly/annual.

## Quiz

Spec: `docs/superpowers/specs/2026-10-03-quiz-design.md`. Wire contract (owned by the FE repo):
`FoodFenFE/docs/backend-contracts/quiz.md`.

- **Endpoints** (`quiz_controller.py`, `CurrentUserDep` except the public `GET /quizzes/topics`): `GET /quizzes/topics`, `GET /quizzes/daily?date=`,
  `POST /quizzes/practice {topic, date}`, `GET /quizzes/{id}`, `POST /quizzes/{id}/submit`.
- **The client never reports a score.** Correct answers and explanations live in `quiz_questions` and
  appear only in the submit response / a completed quiz — never in a question payload.
- **Payout** only happens for the request whose `QuizRepository.mark_submitted()` (conditional UPDATE on
  `submitted_at IS NULL`) succeeds; a loser gets 409 with `error: "quiz_already_submitted"`. Practice also
  takes the user row `FOR UPDATE` first, so the daily cap can't be overshot by concurrent submits.
- **Practice cap** is per the quiz's own `quiz_date` (client-local day, must be within ±1 day of server UTC),
  summed from `quizzes.coins_earned`. Past the cap a submit still returns 200 with `coinsEarned: 0` and no
  ledger row.
- **Rewards** are settings, not data: `QUIZ_DAILY_COINS_PER_CORRECT` (4), `QUIZ_PRACTICE_COINS_PER_CORRECT` (1),
  `QUIZ_PRACTICE_DAILY_CAP` (10).
- **Content** is Vietnamese, seeded by migration 0017; add or fix questions with SQL. Deactivate
  (`active = false`), never delete: issued quizzes reference questions by id.

## Restaurants & admin

Business rules (roles, moderation, what is public, open questions) live in `docs/marketplace.md`,
a **living document**: read it before touching restaurants, dishes, admin or recommendation, and
update it in the same change as any decision.

- **Admin** = `users.role = 'admin'`, set with SQL. `CurrentAdminDep` / router-level
  `Depends(get_current_admin)` (403); the role is read from the DB per request, never from the JWT.
- **Owner** is not a role: `restaurants.user_id` (unique). Owner routes are `/restaurants/mine/...`;
  ownership is implied, and another owner's dish is a 404 (`use_cases/restaurant_support.py`).
- Moderation transitions live only in `Restaurant`/`Dish` `.review()` / `.mark_edited()`; a use case
  never assigns `status`. Public = approved dish of an approved restaurant.
- **Diner endpoints** (`CurrentUserDep`, free): `GET /dishes?date=` (fits-first by remaining kcal, ordering in
  `application/dish_fit.py`) and `GET /restaurants/{id}` (404 unless approved). Spec:
  `docs/superpowers/specs/2026-10-09-dish-tab-design.md`. Reviews take an optional `expectedUpdatedAt`
  (stale → 409); `imageUrl` must be a Cloudinary upload on our cloud (`restaurant_schemas.py`).
- Dashboard buckets rows into Vietnam days in `get_admin_dashboard.py` (Python, not SQL; see its
  `ponytail:` note).

## Commands

    make dev            # uvicorn --reload
    make test           # pytest (unit + integration + api)
    make lint-imports   # import-linter contracts
    make migrate        # alembic upgrade head
    make docker-up      # local postgres:16

`unit` tests use an in-memory repo. `integration` and `api` tests run on in-memory SQLite — `tests/conftest.py`
forces `DATABASE_URL`, so `.env` (prod) is never touched, and shims the Postgres gaps (tz-aware datetimes,
the non-PK `payments.order_code` identity). No Docker needed; SQLite ignores `FOR UPDATE`, so row-lock
behaviour (e.g. coin redeem) is not exercised by tests.

## Adding a slice

See `ARCHITECTURE.md` → "Scaffolding a new slice". Mirror the User slice, layer by layer, inner to outer.
