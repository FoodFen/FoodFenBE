# FoodFenBE — rules for AI sessions

Clean Architecture. Python 3.11+, FastAPI, async SQLAlchemy 2.0, PostgreSQL, Pydantic v2, `uv`.
Dependency direction: `domain <- application <- adapters | infrastructure`. Never sideways, never inward-out.

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
  (`password_reset`, short TTL) and updates the hash.
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

## Commands

    make dev            # uvicorn --reload
    make test           # pytest (unit + integration + api)
    make lint-imports   # import-linter contracts
    make migrate        # alembic upgrade head
    make docker-up      # local postgres:16

## Adding a slice

See `ARCHITECTURE.md` → "Scaffolding a new slice". Mirror the User slice, layer by layer, inner to outer.
