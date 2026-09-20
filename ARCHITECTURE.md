# FoodFenBE Architecture

Clean Architecture with four layers. Dependencies point **inward only**:

```
adapters ─┐
          ├─▶ application ─▶ domain
infrastructure ─┘
```

`import-linter` (`.importlinter`, run via `make lint-imports`) enforces this at CI time.

## Layers

### `src/domain/` — enterprise rules

- Pure standard library. Zero third-party imports (no Pydantic, SQLAlchemy, FastAPI).
- Entities are `@dataclass`. Invariants are enforced on construction (`__post_init__`) or in a
  classmethod factory (`User.create`). An entity that exists is always valid.
- Domain errors: `DomainException` and subclasses. Raised here and in the application layer.

### `src/application/` — use cases

- Imports the standard library and `src/domain/` only. **No frameworks.**
- **Ports** (`ports/`) are `typing.Protocol` classes — the interfaces the outside world must satisfy
  (e.g. `UserRepositoryProtocol`). Defined here, implemented in `infrastructure`.
- **DTOs** (`dtos/`) are frozen dataclasses. Use cases take an input DTO and return an output DTO —
  never an entity, never a Pydantic model, never an ORM row.
- **Use cases** (`use_cases/`) are small classes with one `execute` method. They receive their ports
  by constructor injection (`@dataclass` field typed as the Protocol). They orchestrate; they hold no
  I/O code themselves.

### `src/adapters/` — delivery mechanism (HTTP)

- FastAPI routers (`controllers/`) and Pydantic v2 models (`schemas/`).
- Controllers do exactly three things: parse the request into an input DTO, call `use_case.execute`,
  serialize the output DTO into a response model. No branching on domain state, no validation beyond
  what Pydantic gives for free.
- Pydantic schemas never travel deeper than this layer.

### `src/infrastructure/` — frameworks & drivers

- Concrete implementations of the application ports (`db/repositories/`).
- ORM models (`db/models/`) are **separate classes** from domain entities, with `to_domain()` and
  `from_domain()` for explicit mapping. `Base` (the declarative metadata) lives in `db/base.py`.
- Engine / session wiring in `db/session.py`. Settings in `config.py` (pydantic-settings).
- `di/` is the **composition root**, and the only place that wires anything: `di/database.py`
  (session), `di/repositories.py` (one factory + alias per table), `di/security.py` (hasher, token
  service, `get_current_user`), `di/notifications.py` (outbound email), `di/use_cases.py` (every
  `get_*_use_case` provider, for every slice — kept in one file rather than split per controller).
  `di/__init__.py` re-exports all of it; controllers only ever `from src.infrastructure.di import ...`.
- `src/adapters/exception_handlers.py` maps `DomainException` subclasses to HTTP status codes
  (`EXCEPTION_STATUS`) and registers the handlers onto the app.
- `src/main.py` is the outermost shell: app factory, router registration, calling
  `register_exception_handlers`, lifespan DB check. It holds no policy of its own.

## Dependency inversion, concretely

The use case depends on `UserRepositoryProtocol` (an abstraction it owns). `SQLAlchemyUserRepository`
(infrastructure) depends on that same abstraction by implementing it. Neither the use case nor the
domain knows SQLAlchemy exists. Swapping PostgreSQL for anything else touches only `infrastructure`
and the `di/` package. Tests swap in a hand-written in-memory class — no mocking library needed.

Exception flow: use case raises `UserAlreadyExistsException` → propagates untouched through the
controller → a handler registered by `src/adapters/exception_handlers.py` maps the type to HTTP 409.
Adding a new mapping is one tuple in `EXCEPTION_STATUS` there.

## Current schema

The full CalSnap ERD is implemented at the two innermost persistence layers: a domain entity in
`src/domain/entities/` and an ORM model in `src/infrastructure/db/models/` for each of

`User`, `DailyGoal`, `FoodEntry`, `Ingredient`, `ActivityLog`, `WeightLog`, `WaterLog`, `Streak`,
`Quest`, `CoinTransaction`, `Subscription`

Full vertical slices exist for **auth** (`POST /auth/sign-up|sign-in|refresh|sign-out|social`,
`POST /auth/password-reset`, `GET /auth/me` — endpoint names and shapes follow a front-end API
contract, see `docs/authentication.md` and `docs/social-sign-in.md`) and for reading a `User` by id
(`GET /users/{id}`, token-protected, not part of that contract). Auth added six application ports —
`PasswordHasherProtocol`, `TokenServiceProtocol`, `RefreshTokenRepositoryProtocol`,
`EmailVerificationNotifierProtocol`, `SocialIdentityVerifierProtocol`,
`SocialIdentityRepositoryProtocol` — implemented in `src/infrastructure/security/`,
`src/infrastructure/notifications/`, and `src/infrastructure/db/repositories/`. `User` is also the
one table with an integer PK (see `docs/authentication.md`); every other entity — including
`SocialIdentity` — has just its domain entity + ORM model with a UUID PK,
so a new slice starts at step 2 below.

`FoodEntry` is the one aggregate root with children; it owns its `Ingredient` list, and the ORM
relationship is `lazy="selectin"` so `to_domain()` can read it under the async engine.

## Scaffolding a new slice (e.g. `Food`, `Meal`)

Work inside-out. Each step compiles and `make lint-imports` stays green.

1. **Domain**
   - `src/domain/entities/food.py` — `@dataclass Food` with invariants in `__post_init__`, a
     `Food.create(...)` factory, and any value objects it needs.
   - Add `FoodNotFoundException` / `InvalidFoodAttributeException` to `src/domain/exceptions.py`.
2. **Application**
   - `src/application/dtos/food.py` — `CreateFoodInputDTO`, `FoodOutputDTO` (frozen dataclasses,
     `from_entity` helper on the output).
   - `src/application/ports/food_repository.py` — `FoodRepositoryProtocol(Protocol)` with the async
     methods the use cases need.
   - `src/application/use_cases/create_food.py`, `get_food.py` — one class each, `execute` method,
     port injected as a `@dataclass` field.
3. **Infrastructure**
   - `src/infrastructure/db/models/food_model.py` — `FoodORM(Base)` + `to_domain` / `from_domain`.
   - `src/infrastructure/db/repositories/food_repository.py` — `SQLAlchemyFoodRepository`
     implementing the protocol.
   - `alembic revision -m "create foods table"` then hand-write / check the migration; `make migrate`.
   - Add `get_food_repository` + `FoodRepositoryDep` to `src/infrastructure/di/repositories.py`.
   - Add `get_*_food_use_case` + their `Annotated` aliases to `src/infrastructure/di/use_cases.py`,
     and re-export them from `src/infrastructure/di/__init__.py`.
4. **Adapters**
   - `src/adapters/schemas/food_schemas.py` — `CreateFoodRequest`, `FoodResponse` (Pydantic v2).
   - `src/adapters/controllers/food_controller.py` — `APIRouter(prefix="/foods")`, thin routes,
     importing its use-case deps from `src.infrastructure.di`.
   - Register the router in `src/main.py`; add a tuple to `EXCEPTION_STATUS` in
     `src/adapters/exception_handlers.py` if new domain errors need distinct status codes.
5. **Tests**
   - `tests/unit/test_food_use_cases.py` — in-memory repo, no DB.
   - `tests/integration/test_food_repository.py` — real DB, schema per test.
   - `tests/api/test_food_endpoints.py` — `httpx.AsyncClient` against the app.

Rule of thumb: if you are writing an `if` about domain state in a controller, or importing SQLAlchemy
in a use case, stop — it belongs one layer over.
