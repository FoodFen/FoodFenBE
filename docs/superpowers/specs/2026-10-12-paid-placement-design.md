# Paid placement (marketplace piece 5)

Status: approved in brainstorming 2026-10-12. Business rules go to `docs/marketplace.md` in the same change.

## Goal

Restaurants pay for a "Được tài trợ" (sponsored) section at the top of the dish tab, **without money ever buying
health advice**. Money buys *eligibility* to be shown, never a place in front of a user the dish doesn't fit.

Decisions:

- **Health gate.** A sponsored dish is shown to a user only if it is in that user's *suggested* set (`fits`:
  diet-compatible and within the day's kcal tolerance, the existing `dish_fit` rules). Nothing fits, or the user
  has no goal → no sponsored section.
- **A package is N days for the whole restaurant**, not per dish. For each user the server picks the restaurant's
  best-ranked fitting dish, so a healthier menu is shown more: the incentive points the right way.
- **Order = the existing ranking.** One dish per restaurant, the 3 best-ranked restaurants. Deterministic, testable.
- **Two separate sections, the main list is untouched.** The sponsored section sits above the main list; the
  main list stays ranked purely by health and carries no sponsor label. A sponsored dish also appears at its
  natural rank there (shown twice on purpose: removing it would let money change the health list, and would
  shift the offset cursor). The app does not de-duplicate either.
- **Fen is neutral.** The chat never sees sponsorship; no chat code changes.
- **Owners see daily impressions** (one counter row per restaurant per Vietnam day), since paying no longer
  guarantees exposure.
- **Admin creates and edits packages** on the admin web (no delete: payments snapshot them). Migration seeds one.
- **Buying while featured extends** from the current end. **No refund** if the admin takes the restaurant down
  mid-package; its dishes simply stop being public and the days keep running.

Out of scope: click tracking, per-dish campaigns, bidding/pay-per-impression, distance, sponsorship in chat.

## 1. Data (migration **0024**)

- **`ad_packages`** (`UUIDPrimaryKey`): `days int > 0`, `price_vnd Numeric > 0`, `active bool default true`,
  `created_at`. Seed one row: **7 days, 99 000 VND**. Domain `AdPackage` entity with `.create()` and an
  `update(days?, price_vnd?, active?)`; invariants (`days > 0`, `price_vnd > 0`) in `__post_init__`
  (`InvalidAdPackageException` → 422).
- **`restaurants.featured_until`** (tz-aware, nullable). `Restaurant.featured_until: datetime | None = None`,
  `Restaurant.is_featured(now) -> bool`, `Restaurant.extend_featured(days, now)`:
  `featured_until = max(now, featured_until or now) + days`. No campaign table: purchases are in `payments`.
- **`payments`**: `PlanType.AD_PACKAGE = "ad_package"`; new nullable `ad_days int`. `Payment.__post_init__`:
  `ad_days` is set (> 0) **iff** `plan_type is AD_PACKAGE` (plus a DB CHECK, bare name `ad_days`).
  Days are snapshotted at checkout, so an admin edit never changes a pending order. No `restaurant_id`: one
  restaurant per owner (`restaurants.user_id` unique), the payment's `user_id` finds it.
- **`ad_impressions`**: PK `(restaurant_id FK → restaurants, day date)`, `count int`. Incremented with an
  UPSERT (`on_conflict_do_update`, same pattern as `ai_trial_repository.py`).
- Register both new models in `db/models/__init__.py`. Verify `alembic upgrade head --sql` against the metadata.

## 2. Payment flow

- `apply_payment_result`: after the conditional `update_if_status` flip succeeds, branch on `plan_type`:
  `AD_PACKAGE` → load the owner's restaurant, `extend_featured(payment.ad_days, now)`, save; else the existing
  Premium renewal. Same "only the request that flips the payment applies it" guarantee.
  `ponytail:` two ad payments of one owner paid concurrently can race on `featured_until`; lock the restaurant
  row if that ever matters (same ceiling as the Subscription note already there).
- Return URL: `{APP_BASE_URL}/restaurant/ads` (FoodFenWeb) for both PayOS return/cancel. `MomoProvider` currently
  ignores `return_url` and always uses `momo_redirect_url`; make it use the passed `return_url` when non-empty
  (Premium keeps passing its current value, so its behaviour is unchanged).
- `POST /payments/checkout` keeps accepting only `monthly | annual`.
- Status / cancel reuse `GET /payments/{orderCode}` and `POST /payments/{orderCode}/cancel` unchanged
  (`planType` reads `ad_package`).

## 3. Featured selection (`application/dish_fit.py`, stdlib only)

`pick_featured(ranked: list[RankedDish], featured_restaurant_ids: set[UUID], limit=3) -> list[RankedDish]`:
walk the ranked list in order, keep `fits` dishes whose restaurant is featured, first dish per restaurant,
stop at `limit`. Pure, unit-tested.

`ListPublicDishesUseCase`: on the **first page only** (no cursor), compute `featured` from the **filtered,
ranked** list (so a search for "phở" only features phở), then increment impressions for each featured
restaurant on today's Vietnam day. Later pages: `featured = []`. No goal → nothing `fits` → `[]`.

## 4. API

Wire is camelCase; errors use the standard `{message, error?}` body.

**Diner (Mobile)** — `GET /dishes`: response gains `featured: Dish[]` (same `PublicFitDishResponse` shape as
`dishes`, `fits` always true). `[]` on later pages, with no goal, or when nothing sponsored fits.

**Owner (Web)**, `CurrentUserDep`, ownership implied like every `/restaurants/mine` route (no restaurant → 404):

- `GET /restaurants/mine/ads` →
  `{featuredUntil: datetime | null, packages: [{id, days, priceVnd}] (active only, by days),
  impressions: [{date, count}] (last 30 Vietnam days, oldest first, zero-filled)}`.
- `POST /restaurants/mine/ads/checkout {packageId, provider}` → the same `CheckoutResponse` as
  `/payments/checkout` (`planType: "ad_package"`). Restaurant not approved → 409
  `{error: "restaurant_not_approved"}`; package missing or inactive → 404.

**Admin (Web)**, router-level admin guard (403):

- `GET /admin/ad-packages` → all packages incl. inactive: `[{id, days, priceVnd, active, createdAt}]`.
- `POST /admin/ad-packages {days, priceVnd, active?}` → 201, the package.
- `PATCH /admin/ad-packages/{id} {days?, priceVnd?, active?}` → the package; unknown id → 404.
- `GET /admin/dashboard`: `adRevenue` (daily + total) = paid `ad_package` payments; `premiumRevenue` now
  excludes them.

## 5. Tests

- Unit: `pick_featured` (only `fits`, one per restaurant, cap 3, order kept, non-featured excluded);
  `Restaurant.extend_featured` (active → extends from end, expired/None → from now); `Payment` `ad_days`
  invariant; `AdPackage` invariants.
- API: owner checkout → webhook paid → restaurant appears in page-1 `featured`, page 2 `featured == []`,
  impressions counted; not-approved 409; inactive package 404; non-fitting sponsored dish not featured; admin
  CRUD + non-admin 403; dashboard splits `adRevenue` / `premiumRevenue`; `/payments/checkout` rejects
  `ad_package` (422).

## 6. Work split

| Session | Work |
|---|---|
| BE (this repo) | Everything above + `docs/marketplace.md` (status, decisions, API) + `CLAUDE.md` |
| Web (FoodFenWeb) | Regenerate the SDK. Owner page `/restaurant/ads`: featured-until, packages, buy (PayOS/MoMo), return + poll `GET /payments/{orderCode}`, 30-day impressions chart. Admin: packages CRUD screen; dashboard shows `adRevenue` |
| Mobile (FoodFenFE) | "Được tài trợ" section above the dish list, hidden when `featured` is empty, clearly labelled; tap opens the existing dish/restaurant detail. Update `docs/backend-contracts/dishes.md` |
