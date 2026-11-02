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
- **Always** access the DB session through `SessionDep` (`get_db_session`, commit-on-success, rollback-on-error).
  It is `scope="function"`: the commit runs when the endpoint returns, *before* the response and
  BackgroundTasks (FastAPI's default yield scope would commit after both, so a slow email left a
  signed-up user invisible for seconds). Only a `StreamingResponse` whose generator writes after the
  endpoint returns (chat SSE) uses `StreamSessionDep` (`scope="request"`).
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

## Cross-cutting rules (wire, auth)

- **Wire format is camelCase** (`src/adapters/schemas/base.py::CamelModel`); Python stays snake_case.
  Endpoint/field names follow front-end contracts (`FoodFenFE/docs/backend-contracts/`), not our design.
- **Failure body** is `{"message"?, "error"?, "errors"?: {field: str}}`, never FastAPI's `{"detail": ...}`
  (`src/adapters/exception_handlers.py`). 409s that a client must tell apart carry an `error` code.
- **`User.id` is an int** (`IntPrimaryKey`, `None` until inserted); every other table has a UUID PK
  (exceptions: `mascots`, slug PK).
- Protected routes depend on `CurrentUserDep` / `CurrentAdminDep` (`src/infrastructure/di/security.py`);
  the admin role is read from the DB per request, never from the JWT.
- **Never** log, return, or persist a plaintext password; **never** raise `HTTPException` for auth
  failures (`InvalidCredentialsException`/`InvalidTokenException` → 401).
- App logs go through `configure_logging()` (`src/infrastructure/logging.py`).

## Feature notes — read before touching a feature

`docs/feature-notes.md` holds each feature's contract and invariants (moved out of this file to keep it
short). Read the matching section first, and update it in the same change as any rule it states:

- **Auth** (sign-up/in, refresh rotation, password reset, social sign-in, client IP, Swagger form)
- **AI chat** (SSE contract, persistence order, cursor, user context, dish cards)
- **Coins & quests** (balance, redeem idempotency, history, quests, mascots)
- **Quiz** (payout race, practice cap, content rules)
- **Food catalog** (`foods` table, slug id, derived `verified`, seed from the Mobile bundle)
- **Restaurants & admin** (moderation, owner routes, paid placement, dashboard) — also `docs/marketplace.md`

## Commands

    make dev            # uvicorn, restarted by watchfiles on src/ changes
    make test           # pytest (unit + integration + api)
    make lint-imports   # import-linter contracts
    make migrate        # alembic upgrade head
    make docker-up      # local postgres:16

`.env` is the local dev DB (docker postgres on localhost:5433). Prod's URL lives only on Render.
Startup (`main.lifespan` → `db/bootstrap.py`) ensures the `ADMIN_EMAIL` admin and, only with
`SEED_DEMO=true` (default off, keep it off on prod), seeds 3 demo restaurants (idempotent).

`unit` tests use an in-memory repo. `integration` and `api` tests run on in-memory SQLite — `tests/conftest.py`
forces `DATABASE_URL`, so `.env` is never touched, and shims the Postgres gaps (tz-aware datetimes,
the non-PK `payments.order_code` identity). No Docker needed; SQLite ignores `FOR UPDATE`, so row-lock
behaviour (e.g. coin redeem) is not exercised by tests.

## Adding a slice

See `ARCHITECTURE.md` → "Scaffolding a new slice". Mirror the User slice, layer by layer, inner to outer.
