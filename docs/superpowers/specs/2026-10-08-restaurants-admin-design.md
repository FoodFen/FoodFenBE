# Restaurants, dishes & admin role: design

Decided with the product owner on 2026-10-08; the wire contract was agreed with the FoodFenWeb session.
**Business rules live in `docs/marketplace.md`** (roles, moderation lifecycle, what is public, contract
details). This spec records only *how* the slice is built. If the two disagree, fix whichever is wrong in
the same change.

Out of scope: public diner endpoints, the dish tab, recommendation, ads (packages / purchase / featured).

## Domain (`src/domain/`, stdlib only)

**Enums** (`enums.py`): `UserRole` (`user`, `admin`), `ModerationStatus` (`pending`, `approved`, `rejected`),
`ReviewDecision` (`approved`, `rejected`).

**`User`** gains `role: UserRole = UserRole.USER` and an `is_admin` property.

**`Restaurant`** (`entities/restaurant.py`), with a UUID minted in `.create()`:
`id, user_id (owner), name, description?, address, phone, opening_hours, latitude, longitude, image_url?,
status, rejection_reason?, created_at, updated_at, reviewed_at?`.

**`Dish`** (`entities/dish.py`), with a UUID minted in `.create()`:
`id, restaurant_id, name, description?, image_url?, price: Decimal, serving_g: int, kcal: int,
protein_g, carbs_g, fat_g: float, fiber_g: float | None, status, rejection_reason?, created_at,
updated_at, reviewed_at?`.

Invariants (`__post_init__`, via `domain/validation.py`'s `require_*` helpers, raising a new
`InvalidRestaurantAttributeException(InvalidAttributeException)` → 400):

- Non-blank `name`, `address`, `phone`, `opening_hours`; the strings are stripped.
- `-90 <= latitude <= 90`, `-180 <= longitude <= 180`.
- `price >= 0`, `serving_g > 0`, and `kcal`, `protein_g`, `carbs_g`, `fat_g`, `fiber_g` all `>= 0`.
- `status == rejected` ⇔ `rejection_reason` is set (non-blank).

Status changes go only through entity methods; a use case never assigns `status` directly:

| Method | Restaurant | Dish |
|---|---|---|
| `review(decision, reason, now)` | sets status, reason (cleared on approve), `reviewed_at`. Idempotent | same |
| `mark_edited(now)` | `rejected` → `pending` (reason cleared); `approved` stays `approved` | always → `pending` (reason cleared) |

`review` with `rejected` and a blank reason raises `InvalidRestaurantAttributeException`.

**Exceptions** (`exceptions.py`):

| Exception | HTTP |
|---|---|
| `RestaurantNotFoundException(EntityNotFoundException)` | 404 |
| `DishNotFoundException(EntityNotFoundException)` | 404 |
| `RestaurantAlreadyExistsException(DomainException)` | 409 |
| `AdminRequiredException(DomainException)` | 403 |
| `InvalidRestaurantAttributeException(InvalidAttributeException)` | 400 |

The two new status codes are added to `EXCEPTION_STATUS` in `adapters/exception_handlers.py`.

## Application (`src/application/`)

**Ports:**

- `RestaurantRepositoryProtocol` (`ports/restaurant_repository.py`). Restaurants and their dishes, one
  aggregate: `add`, `get_by_id`, `get_by_owner`, `update`, `list_for_admin(needs_review: bool,
  status: ModerationStatus | None) -> list[AdminRestaurantRowDTO]`, `add_dish`, `get_dish`, `update_dish`,
  `delete_dish`, `list_dishes(restaurant_id)`.
- `AdminStatsRepositoryProtocol` (`ports/admin_stats_repository.py`) returns raw rows in a UTC instant range:
  `paid_payments(start, end) -> list[tuple[datetime, Decimal]]` (`paid_at`, `amount` of `status = paid`),
  `user_signups(start, end) -> list[datetime]`, `restaurant_signups(start, end) -> list[datetime]`.

**DTOs** (`dtos/restaurant.py`, `dtos/admin.py`): input DTOs for create/update restaurant and dish (updates
are partial: `None` = unchanged, like `UpdateUserProfileDTO`), `AdminRestaurantRowDTO` (`id, name, status,
owner_name, owner_email, dish_count, pending_dish_count, updated_at, rejection_reason`),
`AdminRestaurantDetailDTO` (restaurant + dishes), `DashboardDTO` (totals + `daily: list[DashboardDayDTO]`).

**Use cases** (one per file, following the repo convention):

| File | Does |
|---|---|
| `get_me.py` | user + `restaurant_id` (owner lookup) for `/auth/me` |
| `create_restaurant.py` | 409 if the user already owns one; else `Restaurant.create` (pending) |
| `get_my_restaurant.py` | 404 if none |
| `update_my_restaurant.py` | apply the patch, `mark_edited`, re-validate (entity rebuilt or `__post_init__` re-run) |
| `list_my_dishes.py`, `create_dish.py`, `update_dish.py`, `delete_dish.py` | resolve the caller's restaurant first (404 if none); a dish whose `restaurant_id` differs is `DishNotFoundException` |
| `upload_restaurant_image.py` | `ImageStorageProtocol.upload` → absolute URL |
| `list_admin_restaurants.py`, `get_admin_restaurant.py` | queue / detail |
| `review_restaurant.py`, `review_dish.py` | load, `review(...)`, save, return the row |
| `get_admin_dashboard.py` | validates the range, fetches rows, buckets them into Vietnam days (UTC+7) and zero-fills |

Dashboard range: defaults to the last 30 Vietnam days ending today. `from > to` or a span over 366 days
raises `InvalidAttributeException` (400). Vietnam days are converted to a `[start, end)` UTC instant range
before querying. Bucketing is `(instant + 7h).date()`. Money is summed as `Decimal` and returned as `int`.
`ad_revenue` is `0` for every day and in the totals.

## Infrastructure

**Migration `0021_restaurants_and_roles.py`:**

- `users.role` VARCHAR, NOT NULL, `server_default 'user'`, CHECK `user_role` (bare name, per CLAUDE.md).
- `restaurants`: UUID PK, `user_id` INT FK `users.id` ON DELETE CASCADE **UNIQUE**, the columns above,
  `latitude`/`longitude` FLOAT, CHECK `moderation_status`, index on `status`.
- `dishes`: UUID PK, `restaurant_id` FK `restaurants.id` ON DELETE CASCADE (indexed), `price NUMERIC(12,0)`,
  nutrition columns typed exactly like `food_entries` (`kcal INTEGER`, `*_g FLOAT`, `fiber_g` nullable),
  CHECK `moderation_status`, index on `status`.

**ORM** (`models/restaurant_model.py`, `models/dish_model.py`), both registered in `models/__init__.py`:
`RestaurantORM(UUIDPrimaryKey, UserOwned, Base)` (reusing the mixin, so the owner column is `user_id`) and
`DishORM(UUIDPrimaryKey, Base)`, enums via `enum_column()`. `UserORM` gains `role`. There are no ORM
relationships: dishes are always queried explicitly, so there is no `MissingGreenlet` risk.

**Repositories**: `SQLAlchemyRestaurantRepository`. `list_for_admin` is one query: restaurants joined to
`users` (owner name/email), with `COUNT(dishes)` and `COUNT(dishes) FILTER/CASE status = pending`
grouped by restaurant. `needs_review` = `status = pending OR (status = approved AND pending_dish_count > 0)` (HAVING; a
rejected restaurant's pending dishes wait until the restaurant is resubmitted),
ordered by `updated_at` asc (oldest first). `SQLAlchemyAdminStatsRepository` runs three plain range selects.

> `ponytail:` dashboard rows are fetched and bucketed in Python, which is O(rows in range) and portable
> across Postgres/SQLite. Move it to SQL `GROUP BY` when a 30-day window holds more than ~100k payments or signups.

**DI** (`di/repositories.py`, `di/use_cases.py`, re-exported from `di/__init__.py`): one provider and an
`Annotated` alias per repository and use case.

**Security** (`di/security.py`):

- `get_current_admin(user: CurrentUserDep) -> User` raises `AdminRequiredException` unless `user.is_admin`.
  The `CurrentAdminDep` alias is used on every `/admin/*` route.
- The role is read from the user row that `get_current_user` already loads, so it is not stored in the JWT.
- `limit_upload_by_user`: a new `SlidingWindowLimiter(limit=20, window_seconds=60)` on the image endpoint
  (Cloudinary costs money, and any signed-in user may upload).

## Adapters

**Schemas** (`schemas/restaurant_schemas.py`, `schemas/admin_schemas.py`, all `CamelModel`):

- Request models bound fields with Pydantic (`latitude: float = Field(ge=-90, le=90)`, `kcal: int =
  Field(ge=0)`, `price: Decimal = Field(ge=0, max_digits=12, decimal_places=0)`, string `min_length`/`max_length`),
  so bad input is a 422 with `errors.<field>`. The entity re-checks as the last line of defence.
- The `ReviewRequest` schema is `{decision: ReviewDecision, reason: str | None}` and carries a model validator
  requiring a reason when `decision = rejected` (→ `errors.reason`).
- Responses use the enum types, so `role`/`status`/`decision` appear as enums in OpenAPI.

**`/auth/me`** returns `MeResponse(UserResponse)` + `restaurant_id: UUID | None`. `UserResponse` itself
gains `role`, so every session payload (sign-in, sign-up, refresh, social) carries it. `restaurantId` is
on `/auth/me` only, which the web client already calls after sign-in.

**Controllers**: `restaurant_controller.py` (`/restaurants`, owner endpoints, `CurrentUserDep`) and
`admin_controller.py` (`/admin`, `CurrentAdminDep`), both registered in `main.py`. The image endpoint
reuses the same check pattern as `food_analysis_controller.py`, with its own constants: allowed
`image/jpeg`, `image/png`, `image/webp`; max 5 MB; violations raise `UnreadableImageException` (400).

Endpoint list and per-field contract: `docs/marketplace.md` → "API" and "Contract details".

## Testing (TDD)

- **Unit** (`tests/unit/test_restaurant_entities.py`): invariants (lat/lng bounds, negative nutrition,
  blank fields); `review` sets/clears the reason, is idempotent, and rejects a blank reason; `mark_edited`
  (dish approved→pending, restaurant approved stays approved, restaurant rejected→pending).
- **Unit** (`tests/unit/test_admin_dashboard.py`): Vietnam-day bucketing at the 17:00 UTC boundary,
  zero-fill across the range, the default range, and range-validation errors.
- **API** (`tests/api/test_restaurant_endpoints.py`, `tests/api/test_admin_endpoints.py`):
  - Owner: create → 201 with `id`; second create → 409; `GET /mine` with no restaurant → 404; editing
    another restaurant's dish → 404; `PATCH` an approved dish returns `pending`; lat out of range → 422
    `errors.latitude`.
  - Admin: a non-admin on `/admin/*` → 403; review reject without reason → 422; repeat review → 200; the
    queue includes an approved restaurant with a pending dish and excludes a fully approved one; the
    list row counts.
  - Dashboard: only `paid` payments are summed; the series is zero-filled; `adRevenue` is 0; `/auth/me`
    carries `role` and `restaurantId`.
  - Image upload: bad type → 400; oversized → 400; OK → `{url}`, with `ImageStorage` overridden like the
    analyze-image tests.
  - Admins in tests: create a user, then set `role` through the repository.
- Before commit: `uv run lint-imports`, `make test`, and the migration-vs-metadata DDL comparison.

## Follow-ups (not in this slice)

Public diner endpoints and the dish tab · recommendation input · ads · review history / `reviewed_by` ·
admin queue pagination and bulk review · FoodFenWeb wiring (its own session, from `docs/marketplace.md`).
