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
- **Never** raise `HTTPException` from application or domain. Raise a `DomainException` subclass; `src/main.py` maps it to a status code.
- **Never** catch domain exceptions in the controller. Let them propagate to the handlers.
- **Never** add a dependency for something a few lines of stdlib do.

## Always

- **Always** enforce entity invariants in the entity's `__post_init__` (or a factory), not in the use case or schema.
- **Always** construct new entities via the domain factory (`User.create(...)`), which sets id / timestamps / defaults.
- **Always** access the DB session through the `get_db_session` dependency (commit-on-success, rollback-on-error per request).
- **Always** run `uv run lint-imports` after touching imports. It is the architecture's guardrail and CI must stay green.
- **Always** add an Alembic migration when you change an ORM model. Never edit the DB by hand.
- **Always** put a new use case's provider in its slice's `src/adapters/controllers/<slice>_deps.py`
  (a `get_*_use_case` fn + an `Annotated[..., Depends(...)]` alias). Repository providers go in
  `src/infrastructure/di/repositories.py`; shared primitives in `src/infrastructure/di/`.
- **Always** use `Annotated` for router functions and other injected parameters that Python IDEs
  complain about (valid in FastAPI either way, but only `Annotated` type-checks cleanly). For example:

```python
async def create_user(
    body: CreateUserRequest,
    use_case: Annotated[CreateUserUseCase, Depends(get_create_user_use_case)],
    # Not: use_case: CreateUserUseCase = Depends(get_create_user_use_case)
) -> UserResponse:
```

  This applies to the `di/` package and the `*_deps.py` modules too — expose a named
  `Annotated[UseCase, Depends(provider)]` alias and use it in the route signature, rather than
  repeating `Annotated[...]` at each call site.

## Schema rules

- **Always** register a new ORM model in `src/infrastructure/db/models/__init__.py`. Alembic and
  `create_all` read `Base.metadata`; an unregistered model silently has no table.
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

- **Three JWT types**, distinguished by a `type` claim (checked on decode): `access` (~30 min,
  stateless), `refresh` (30 d, carries a `jti`), `email_verification` (24 h). One `JwtTokenService`.
- **Refresh token**: every issued one gets a `refresh_tokens` row (`jti` unique, `expires_at`,
  `revoked_at`). Accepted only if a matching **unrevoked, unexpired** row exists, so logout and
  rotation take effect immediately. Rotated on every `/auth/refresh` — single-use.
- **Email verification**: `User.email_verified_at` (nullable, migration 0004). Register creates the
  user with it `None` and returns **no tokens** — just a 201 message; `LoginUseCase` raises
  `EmailNotVerifiedException` (→ **403**) until it is set. `GET /auth/verify-email?token=` and
  `POST /auth/resend-verification` (always 202). The email itself is sent from the **controller** via
  `BackgroundTasks` (a use case can't reach it) — the use case returns a `VerificationDispatchDTO`.
- **Protected routes**: depend on `CurrentUserDep` (or `dependencies=[Depends(get_current_user)]` when
  the handler doesn't need the user). `get_current_user` lives in `src/infrastructure/di/security.py`.
- **Never** log, return, or persist a plaintext password. Hashing is `PasswordHasherProtocol`
  (bcrypt, cost 12) — the domain never sees bcrypt. No JWT is stored; only the refresh token's `jti` is.
- **Never** raise `HTTPException` for auth failures. Raise a `DomainException` subclass
  (`InvalidCredentialsException`/`InvalidTokenException` → 401, `EmailNotVerifiedException` → 403);
  `src/main.py` maps the type to a status. 401s also carry `WWW-Authenticate: Bearer`.
- Password policy (`>= 8` chars, `<= 72` bytes) is `User.validate_password_strength`, called by
  `RegisterUserUseCase`. `bcrypt` truncates past 72 bytes — the schema caps it too.
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
