# Diary sync — phase 2: push

## Goal

Extend the diary resources that already support pull (phase 1: `daily-goals`,
`food-entries`, `activity-logs`, `weight-logs`, `water-logs`) plus the `User`
profile with push endpoints, per the frontend's wire contract:
`docs/backend-contracts/sync.md` (FoodFenFE repo). That document is the
source of truth for request/response shapes; this spec covers the backend
architecture decisions it leaves to us and the concrete plan of endpoints,
migrations, and layers to add.

**Explicitly out of scope**: `quests` and `coin-transactions`. Those have no
existing API surface at all (no pull, no controller/port/use case/schema —
only a domain entity and ORM model exist). They're a separate feature
(build a gamification API from scratch, pull and push both) and get their
own spec once this one ships.

## Three architecture decisions (confirmed)

### 1. Idempotency: DB unique constraint + catch-and-requery

Every pushable table gets a `client_id: str` column with a unique constraint
on `(user_id, client_id)`. `client_id` is the client's local row id
(`generateLocalId()`, e.g. `entry_xxx`) — never the row's real identity,
purely a dedup key so a retried request after a dropped response can't
create a duplicate.

Repository `create()` methods attempt the insert; on a unique-violation
(`sqlalchemy.exc.IntegrityError` wrapping asyncpg's `UniqueViolationError`),
catch it, re-query by `(user_id, client_id)`, and return the existing row
instead of raising. This is race-safe (two concurrent retries can't both
succeed in creating a duplicate) and keeps every repository's create method
in the same shape — no batch/upsert SQL, no Postgres-dialect-specific code,
consistent with the plain `select()`/`session.add()` style already used
throughout `src/infrastructure/db/repositories/`.

Rejected alternatives: check-then-insert (has a real race window — the
exact case `clientId` exists to prevent); `INSERT ... ON CONFLICT DO
NOTHING RETURNING` (fewer round trips, but introduces Postgres-dialect SQL
that's a style break from the rest of the repository layer for a marginal
win on a low-traffic path).

### 2. Soft delete: `food_entries` and `water_logs` only

Only these two resources have `DELETE` in the contract (`activity-logs`,
`daily-goals`, `weight-logs` don't — see sync.md's per-resource sections).
Both get a `deleted_at: datetime | None` column. `DELETE` sets it rather
than removing the row. Every existing read path for these two
(`list_by_date_range`, `get_by_id`) filters `deleted_at IS NULL`, so a
deleted row stops appearing in `GET` — matching the contract's statement
that pull "currently" (i.e. once this ships) returns no deleted rows.

What a *second* device does about a deletion it already pulled before is an
explicitly acknowledged gap in the contract itself, not something this spec
resolves.

### 3. PATCH semantics: full-replace for logs, partial for profile

- `PATCH /food-entries/{id}` and `PATCH /activity-logs/{id}`: **full
  replace**. The contract says "same body shape" as the matching `POST` —
  every field required, not a partial diff. Food entry `ingredients` are
  fully replaced (delete existing rows, insert the submitted set), mirroring
  how pull already treats ingredients as the complete authoritative set for
  an entry, so both directions stay symmetric.
- `PATCH /users/me`: **true partial patch**. Profile fields are filled in
  incrementally as onboarding/settings screens are used over time, so only
  fields present in the request body update; everything else is left alone.
  Implemented with Pydantic's `model_fields_set` (equivalent to
  `exclude_unset` on load) so an explicit `null` for a nullable field
  (clearing `weightGoal`) is distinguishable from the field being omitted
  entirely.

`email` is included in `PATCH /users/me` per the literal contract text
(every `User` field except `id`/`createdAt`/`subscriptionTier`), with no
new reverification step — this matches the existing signup flow, which
also doesn't gate on email verification. A changed email that collides with
another account reuses the existing `UserAlreadyExistsException` path
(`RegisterUserUseCase`'s `get_by_email` check is the precedent).
`subscriptionTier` sent in the body is a `422` (schema doesn't accept the
field at all — Pydantic's default `extra="ignore"` would otherwise silently
drop it, which is the wrong failure mode for "client tried to grant itself
Premium"; the profile schema sets `extra="forbid"` to make that loud).

## Endpoints

| Resource | Endpoint | Behavior |
|---|---|---|
| User | `PATCH /users/me` | Partial update; full `User` response |
| Daily goals | `POST /daily-goals` | Create-only (goals are append-only, never edited/deleted) |
| Food entries | `POST /food-entries` (extend) | Add `clientId` idempotency to the existing endpoint |
| Food entries | `PATCH /food-entries/{id}` | Full replace incl. ingredients; 404 if not found or not owned |
| Food entries | `DELETE /food-entries/{id}` | Soft delete; 404 if not found/not owned |
| Activity logs | `POST /activity-logs` | Create, with `clientId` idempotency |
| Activity logs | `PATCH /activity-logs/{id}` | Full replace; 404 if not found/not owned |
| Weight logs | `POST /weight-logs` | Create, with `clientId` idempotency |
| Water logs | `POST /water-logs` | Create, with `clientId` idempotency |
| Water logs | `DELETE /water-logs/{id}` | Soft delete; 404 if not found/not owned |

Every endpoint: `userId` inferred from `CurrentUserDep`, never a request
field. `404` for "doesn't exist" and "exists but belongs to another user"
are identical responses (existence isn't leaked), matching
`GetFoodEntryUseCase`'s existing pattern.

## New domain-layer pieces

- `FoodEntryNotFoundException` already exists (reused for PATCH/DELETE).
  New: `ActivityLogNotFoundException`, `WaterLogNotFoundException`
  (`src/domain/exceptions.py`).
- Entities gain no new methods beyond what a plain mutable `@dataclass`
  already supports: an update use case builds the new field values onto the
  existing entity instance and re-invokes `__post_init__()` to re-run
  validation (same instance, not a new one — preserves `id`/`user_id`).
- `User` gains no new method either — `UserRepositoryProtocol.update()` and
  its SQLAlchemy implementation already exist (used by email verification)
  and are reused as-is.

## Migration

One Alembic migration (`0011_diary_sync_push_fields`):
- `client_id: String, nullable=False` + unique constraint on
  `(user_id, client_id)` for `daily_goals`, `food_entries`, `activity_logs`,
  `weight_logs`, `water_logs`.
- `deleted_at: DateTime(timezone=True), nullable=True` for `food_entries`,
  `water_logs`.

`client_id` is `nullable=False` with no default — existing rows created
before this migration (from phase 1 testing / the current demo session)
have no client-generated id to backfill honestly, and adding a `NOT NULL`
column to a non-empty table fails outright without one. Rather than invent
a synthetic backfill value for disposable test data, `upgrade()` truncates
`food_entries`, `daily_goals`, `activity_logs`, `weight_logs`, `water_logs`
(cascading to `ingredients`) before adding the column — safe only because
this is local dev data with no real users yet (confirmed earlier this
session). `downgrade()` drops the columns and constraints, bare-name
convention per `CLAUDE.md`; it does not restore truncated rows.

## Testing

Same layering as phase 1: unit tests for each new/changed use case
(including the idempotency re-query path — assert a second `create()` call
with the same `client_id` returns the *same* row, not a new one, verified
by breaking the catch-and-requery logic and watching the test fail before
trusting it), integration tests for repository methods against the real DB
(soft-delete filtering, unique-constraint conflict handling), API tests for
each endpoint (403/404 ownership checks, partial-patch `exclude_unset`
behavior on `PATCH /users/me`, `subscriptionTier` rejection).

## Out of scope (per sync.md's own "left to the backend session" list)

- Whether/how a pulled list surfaces a row deleted on another device.
- Multi-device conflict resolution beyond last-push-wins (nothing here
  needs to *detect* a conflict — there's no concurrent-edit signal to act
  on, so there's genuinely nothing to build for this).
- Real batching (one call covering many dirty rows) — current contract is
  one row per request.
- Rate limiting on push endpoints.
- `quests` / `coin-transactions` — separate spec.
