# Dish tab (public diner endpoints): design

Decided with the product owner on 2026-10-09. Piece 3 of `docs/marketplace.md`, plus the two decisions recorded
there on 2026-10-09 (`expectedUpdatedAt`, Cloudinary-only `imageUrl`). **Business rules live in
`docs/marketplace.md`**; this spec records only *how* the slice is built. Builds on the restaurants/admin slice
(`2026-10-08-restaurants-admin-design.md`).

Product decisions:

- **Free for every signed-in user.** Restaurants need views before they have a reason to join (and later buy ads).
  Signed in, because the ordering reads the user's goal and diary.
- **"Fits first" = a remaining-kcal rule**, not AI and not a weighted macro score. Recommendation (piece 4)
  replaces the ordering later if the rule is not enough.
- **No distance.** Lat/lng are returned only so the app can open Google Maps. No location permission.

Out of scope: pagination, search, distance filter/sort, AI recommendation, ads / featured section, a
"log this dish" endpoint (see below).

## Endpoints (`CurrentUserDep`, no Premium gate)

### `GET /dishes?date=YYYY-MM-DD`

`date` is the client's local day; omitted → today in Vietnam (UTC+7), like `POST /chat/messages`. No ±1 day
bound: it only changes the ordering of the caller's own view.

Response:

```json
{
  "remainingKcal": 820,            // null when the user has no goal in force on `date`
  "dishes": [
    {
      "id": "uuid", "name": "...", "description": null, "imageUrl": "https://res.cloudinary.com/...",
      "price": 45000, "servingG": 350, "kcal": 640, "proteinG": 32.0, "carbsG": 70.0, "fatG": 18.0,
      "fiberG": null,
      "fits": true,
      "restaurant": { "id": "uuid", "name": "...", "address": "...", "latitude": 10.77, "longitude": 106.70 }
    }
  ]
}
```

Only **public** dishes: `approved` dish of an `approved` restaurant. No `status`, `rejectionReason`,
`createdAt`/`updatedAt` or owner data on the wire.

### `GET /restaurants/{id}`

Public restaurant profile — `id, name, description, address, phone, openingHours, latitude, longitude,
imageUrl` — plus `dishes`: its approved dishes (same dish fields as above, without `fits`/`restaurant`),
oldest first. 404 (`RestaurantNotFoundException`) when the restaurant does not exist **or is not approved**.
Declared after `/restaurants/mine` in the router so `mine` never matches `{id}` (the path param is a `UUID`
anyway, so `mine` would be a 422, not a match).

## Ordering (`GET /dishes`)

- **Goal in force** on `date` = the user's `DailyGoal` with the latest `effective_date <= date` (same rule as
  `chat_context._goal`; one `max(...)` expression, not shared).
- **Eaten** = sum of `total_kcal` of the user's non-deleted food entries with `logged_on == date`
  (`FoodEntryRepository.list_by_date_range(user, date, date)`).
- `remainingKcal = goal.target_kcal - eaten` (may be ≤ 0).
- A dish **fits** when `kcal <= remainingKcal`.
- Order: fitting dishes first, **highest kcal first** (closest to filling what is left); then the rest,
  **lowest kcal first** (closest to fitting).
- No goal → `remainingKcal: null`, every `fits: false`, newest dish first (`dishes.created_at` desc).
- Ties keep a stable order by dish `id`, so the list does not shuffle between requests.

The ordering is a pure, stdlib-only function in `src/application/dish_fit.py`
(`rank_dishes(dishes, remaining_kcal) -> list[(dish, fits)]`), so it is unit-tested without fakes.
`# ponytail:` note there: every public dish is loaded and sorted in Python; when the payload gets heavy, add
pagination and push the ordering into SQL.

## Application

- Port `RestaurantRepositoryProtocol` gains `list_public_dishes() -> list[tuple[Dish, Restaurant]]`: one join,
  both `approved`. `get_by_id` and `list_dishes` already exist for `GET /restaurants/{id}` (filter `approved`
  in the use case).
- `ListPublicDishesUseCase(restaurants, daily_goals, food_entries).execute(user_id, day) -> PublicDishListDTO`.
- `GetPublicRestaurantUseCase(restaurants).execute(restaurant_id) -> PublicRestaurantDTO`.
- DTOs (dataclasses, `application/dtos/restaurant.py`): `PublicRestaurantSummaryDTO`, `PublicDishDTO`
  (dish fields + `fits` + summary), `PublicDishListDTO(remaining_kcal, dishes)`, `PublicRestaurantDTO`.
- Providers in `di/use_cases.py` + `Annotated` aliases, re-exported from `di/__init__.py`.

## `expectedUpdatedAt` on reviews

- `ReviewRequest` (`admin_schemas.py`) gains `expected_updated_at: datetime | None = None`.
- `ReviewRestaurantUseCase` / `ReviewDishUseCase.execute(..., expected_updated_at: datetime | None)`: after
  loading the row, if `expected_updated_at is not None and expected_updated_at != row.updated_at` → raise
  `StaleReviewException` (new, `domain/exceptions.py`) → **409 `{message}`** via `EXCEPTION_STATUS`.
  Absent → today's behavior. Checked before `review()`, so a stale request changes nothing.
- The web client sends back the exact `updatedAt` string it received; Pydantic round-trips it to the same
  tz-aware microsecond `datetime`, so equality is exact.

## Cloudinary-only `imageUrl`

- `restaurant_schemas.py`: the four request models drop `pattern=_HTTPS` and share one `field_validator("image_url")`
  that accepts `None` or a URL starting with `https://res.cloudinary.com/<cloud_name>/image/upload/`; anything
  else → 422 `errors.imageUrl`.
- `<cloud_name>` = the host part of `settings.cloudinary_url` (`cloudinary://key:secret@<cloud_name>`), parsed
  the same way `CloudinaryImageStorage` does. **Unset → every non-null `imageUrl` is rejected** (fail closed;
  uploads cannot work without it either).
- Every URL the BE hands out already passes: `POST /restaurants/mine/images` (any signed-in user, before or after
  creating a restaurant; JPEG/PNG/WebP magic-byte checked, ≤ 5 MB) returns Cloudinary's `secure_url`.
  `/ai/food/analyze-image` uploads to the same cloud, so its URLs also pass; acceptable — same host, and a
  Cloudinary URL's content cannot be swapped by the owner.
- Rows already holding another host are untouched (none in prod: the restaurants slice is not deployed yet).

## Logging a dish to the diary

No endpoint. A dish's `kcal`/`proteinG`/`carbsG`/`fatG`/`servingG` names and types match `food_entries` on
purpose: the app copies them into a new local food entry and the existing sync uploads it.

## Testing (TDD)

- **Unit** `tests/unit/test_dish_fit.py`: no goal (newest first, none fit); some fit (fitting high→low kcal,
  then rest low→high); remaining ≤ 0 (none fit, all low→high); tie order stable by id.
- **Unit**: review use cases — stale `expected_updated_at` raises and leaves the row unchanged; matching or
  absent reviews normally.
- **API** `tests/api/test_dish_tab_endpoints.py`:
  - `GET /dishes` returns only approved dishes of approved restaurants (pending dish, rejected dish, approved
    dish of a pending restaurant all hidden); `remainingKcal` reflects a goal and a logged entry on `date`;
    no private fields on the wire; 401 without a token.
  - `GET /restaurants/{id}`: approved → profile + only approved dishes; pending / rejected / unknown → 404.
  - Review with a stale `expectedUpdatedAt` → 409 `{message}`; with the current one → 200.
  - Create/patch restaurant and dish with a non-Cloudinary `imageUrl` → 422 `errors.imageUrl`; a Cloudinary one
    → 2xx; `null` still clears. Tests set `CLOUDINARY_URL` to a fake `cloudinary://k:s@testcloud`.

## Docs

`docs/marketplace.md` in the same change: piece 3 → implemented; API section gains the two diner endpoints and
the `expectedUpdatedAt` / `imageUrl` rules; header status line. `CLAUDE.md` "Restaurants & admin": one line
for the diner endpoints (replacing "no public endpoint yet").
