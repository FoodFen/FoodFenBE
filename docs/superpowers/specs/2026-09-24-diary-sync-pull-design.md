# Diary sync — pull endpoints (phase 1) — design

Date: 2026-09-24
Status: approved for implementation (phase 1 of 2 — see "Not in this phase")

## Goal

Serve the five `GET` endpoints `FoodFenFE/docs/backend-contracts/sync.md` documents as
"already shipped and calling real code paths client-side, just never had a backend":
`GET /daily-goals`, `GET /food-entries?from=&to=`, `GET /activity-logs?from=&to=`,
`GET /water-logs?from=&to=`, `GET /weight-logs?from=&to=`. `GET /users/me` needs no backend
work — it's a client-side pointer fix to the already-existing `GET /auth/me`.

This is phase 1 of the sync contract. **Push (`POST`/`PATCH`/`DELETE`, draining
`pendingChangeCount()`) is explicitly out of scope** — per the contract itself, no client
code calls it yet, so there's nothing concrete to build against; it comes back as its own
design once the client side exists. One exception: `POST /food-entries` (already shipped)
gets a small, additive fix in this phase — see below.

## Existing state this builds on

- `DailyGoal`, `ActivityLog`, `WaterLog`, `WeightLog` domain entities + ORM models already
  exist (`src/domain/entities/`, `src/infrastructure/db/models/`) from the original CalSnap
  ERD migration — **no application/adapter layer for any of them yet.** Same starting point
  `FoodEntry`/`Payment`/`Subscription` were in before their slices were built.
- `FoodEntry`'s application/adapter layer already exists (`POST`/`GET /food-entries/{id}`,
  this session) and is the template every new slice below mirrors exactly.
- The `sync.md` contract's field-for-field GET response shapes are the source of truth this
  spec implements against — not re-derived here; see that file for the exact JSON shapes.

## The `meal_type` / `logged_on` gap

`sync.md`'s `food-entries` response requires `mealType` (`breakfast|lunch|dinner|snack`) and
`loggedOn` (`yyyy-MM-dd`) on every entry — neither exists on `FoodEntry` today (confirmed:
`grep`ing the whole backend for `meal_type`/`logged_on` finds nothing). `activity-logs` and
`water-logs` also require `loggedOn`; `weight-logs`' `recordedAt` already **is** a date
column (`WeightLog.recorded_at`) and needs no change. `daily-goals`' response already matches
`DailyGoal` exactly as-is — no change needed there either.

`logged_on` is **not** derivable from `logged_at` server-side (`.date()` on a UTC instant)
— that would silently compute the wrong calendar day for an entry logged near midnight in
the user's actual timezone. It has to be a genuinely separate, client-supplied value, stored
as its own column, exactly mirroring why the client's own local schema keeps two columns
instead of one. This phase adds the columns; nothing populates them with real data until
push (phase 2) exists for `ActivityLog`/`WaterLog`/`DailyGoal` — they only have a creation
path via `FoodEntry`'s (see below), so their list endpoints return real data now only for
food entries. That's expected, not a bug in this phase.

## Domain layer

- `src/domain/enums.py`: add `MealType(StrEnum)`: `BREAKFAST/LUNCH/DINNER/SNACK`
  (`"breakfast"/"lunch"/"dinner"/"snack"`).
- `src/domain/entities/food_entry.py`: add required fields `meal_type: MealType` and
  `logged_on: date` to `FoodEntry` and its `.create()` factory (no default for `meal_type` —
  the caller must decide; `logged_on` defaults to `logged_at`'s date only as a fallback when
  not explicitly given, same pattern `WeightLog.create` already uses for `recorded_at`).
- `src/domain/entities/activity_log.py`, `src/domain/entities/water_log.py`: add
  `logged_on: date` the same way (default: `logged_at`'s date if omitted).

## Application layer

- `src/application/ports/daily_goal_repository.py` — `DailyGoalRepositoryProtocol`:
  `list_by_user(user_id) -> list[DailyGoal]` (all goals, no date filter — append-only,
  few rows; the client resolves "today's goal" itself).
- `src/application/ports/activity_log_repository.py`,
  `.../water_log_repository.py`, `.../weight_log_repository.py` — each:
  `list_by_date_range(user_id, from_date, to_date) -> list[...]` (inclusive), filtered on
  `logged_on` (`ActivityLog`/`WaterLog`) or `recorded_at` (`WeightLog`).
- `src/application/ports/food_entry_repository.py` — add
  `list_by_date_range(user_id, from_date, to_date) -> list[FoodEntry]` to the existing
  `FoodEntryRepositoryProtocol`, filtered on `logged_on`.
- DTOs: one output DTO per resource (`DailyGoalOutputDTO`, `ActivityLogOutputDTO`,
  `WaterLogOutputDTO`, `WeightLogOutputDTO`), each with a `from_entity` classmethod —
  mirrors `SubscriptionOutputDTO`'s shape exactly (plain frozen dataclass, no repo-shaped
  fields). `FoodEntryOutputDTO`/`CreateFoodEntryInputDTO` gain `meal_type`/`logged_on`.
- Use cases, each a one-method class exactly like the existing ones:
  `ListDailyGoalsUseCase.execute(user_id) -> list[DailyGoalOutputDTO]`,
  `ListFoodEntriesUseCase.execute(user_id, from_date, to_date) -> list[FoodEntryOutputDTO]`,
  `ListActivityLogsUseCase`, `ListWaterLogsUseCase`, `ListWeightLogsUseCase` (same shape).
  `CreateFoodEntryUseCase` gains no new logic — the new fields just flow through like every
  other field already does.

## Infrastructure layer

- ORM models: `FoodEntryORM` gains `meal_type` (`enum_column(MealType, "meal_type")`) and
  `logged_on` (`Date`, indexed alongside the existing `(user_id, logged_at)` index — add
  `(user_id, logged_on)` too, since that's what the new list query filters on).
  `ActivityLogORM`/`WaterLogORM` gain `logged_on` (`Date`) the same way, same new index
  pattern. `to_domain`/`from_domain` updated for all three.
- Migration `alembic/versions/0010_diary_sync_fields.py`: adds the three `logged_on` columns
  + `food_entries.meal_type`, with the `meal_type` CHECK constraint, and the two new
  `(user_id, logged_on)` indexes. `logged_on`/`meal_type` are `NOT NULL` — this repo has no
  data yet on `main` beyond what this session's own tests created (dropped per-test), so no
  backfill step is needed; if that stops being true before this ships, revisit before adding
  the constraint as a single migration.
- New repositories: `SQLAlchemyDailyGoalRepository`, `SQLAlchemyActivityLogRepository`,
  `SQLAlchemyWaterLogRepository`, `SQLAlchemyWeightLogRepository` — each a thin `select`
  wrapper, same shape as every existing repository. `SQLAlchemyFoodEntryRepository` gains
  `list_by_date_range`.
- DI: one repository provider + one use-case provider (+ `Annotated` alias) per resource in
  `di/repositories.py` / `di/use_cases.py`, re-exported from `di/__init__.py` — same pattern
  as every existing entry there.

## Adapters layer

- New schemas: `daily_goal_schemas.py` (`DailyGoalResponse`), `activity_log_schemas.py`
  (`ActivityLogResponse`), `water_log_schemas.py` (`WaterLogResponse`), `weight_log_schemas.py`
  (`WeightLogResponse`) — each a `CamelModel` mirroring its `GET` shape in `sync.md` exactly.
  `food_entry_schemas.py`: `CreateFoodEntryRequest`/`FoodEntryResponse` gain `meal_type`/
  `logged_on`.
- New controllers/routes, `CurrentUserDep`-protected like everything else:
  - `GET /daily-goals` (new `daily_goal_controller.py`)
  - `GET /food-entries?from=&to=` — **added to the existing** `food_entry_controller.py`,
    alongside `POST /food-entries` and `GET /food-entries/{entry_id}` (no path collision:
    one has a path segment, one doesn't). `from`/`to` are required query params, `date`-typed
    (FastAPI parses `yyyy-MM-dd` natively); `from` is a Python keyword, so the parameter is
    named `from_` with `Query(alias="from")` so the wire name still matches the contract.
  - `GET /activity-logs?from=&to=` (new `activity_log_controller.py`)
  - `GET /water-logs?from=&to=` (new `water_log_controller.py`)
  - `GET /weight-logs?from=&to=` (new `weight_log_controller.py`, response's `recordedAt`
    is a bare date, not a datetime)
- `src/main.py`: register the four new routers.
- No new exception types or `exception_handlers.py` changes — nothing here raises a new
  domain exception (a list endpoint returning `[]` for "no rows" needs no not-found case).

## Testing

- Unit tests per new use case (in-memory fake repo, same shape as every existing use-case
  test file) — the interesting case per resource is just "returns what the repo returns,
  mapped to DTOs"; `ListFoodEntriesUseCase`/`ListActivityLogsUseCase`/`ListWaterLogsUseCase`
  additionally get a case proving the date-range filter is passed through to the repo call.
- One integration test per new repository (real DB) proving `list_by_date_range`/
  `list_by_user` actually filters correctly (a row outside the range is excluded; a
  different user's row is excluded) — mirrors `test_payment_repository.py`'s shape.
- API tests: extend `test_food_entry_endpoints.py` for the new `GET /food-entries?from=&to=`
  route (including `mealType`/`loggedOn` round-tripping through `POST` then back out of the
  list), plus one new API test file per resource proving `CurrentUserDep` is enforced and the
  response shape matches `sync.md` field names exactly (camelCase). Since `daily-goals`/
  `activity-logs`/`water-logs`/`weight-logs` have no create path yet, these tests seed rows
  directly via the repository (not through the API) before asserting the `GET` response —
  same "insert via repo, assert via API" pattern already used in this codebase's other tests
  wherever only the read side exists.

## Not in this phase (explicitly deferred)

- Push (`POST`/`PATCH`/`DELETE` for every resource, `clientId` idempotency, the User profile
  `PATCH`) — no client code to build against yet, per `sync.md` itself. Comes back as its own
  design once the client-side push scheduler exists.
- Quests, coin-transactions — new resources the FE session flagged as needed eventually;
  `sync.md` scopes them under push, which this phase doesn't touch.
- Any resolution for "pull never sees a remote deletion" or cross-device conflict handling —
  `sync.md` explicitly leaves both open; nothing in phase 1 needs either since nothing writes
  through these new endpoints yet.
