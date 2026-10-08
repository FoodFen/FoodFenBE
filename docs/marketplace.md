# Restaurant marketplace: business rules

> **Living document.** The single source of truth for *what* the restaurant/admin/recommendation
> side of FoodFen does and *why*. Update it in the same change as any decision or behaviour change.
> Design specs (`docs/superpowers/specs/`) record *how* one slice was built; this file records the
> rules that hold across slices. Status: **designed, not implemented**. Spec for pieces 1–2:
> `docs/superpowers/specs/2026-10-08-restaurants-admin-design.md`.

## Vision

FoodFen grows from a personal nutrition tracker into a place to find food that fits your goals.
Five pieces, built in this order:

| # | Piece | Status |
|---|-------|--------|
| 1 | **Restaurants**: owners register for free, submit their profile and menu with nutrition | designing |
| 2 | **Admin**: approves restaurants and dishes, sees basic platform data (transactions, users) | designing |
| 3 | **Dish tab** (mobile): dishes that fit the user first, then the rest; tap a dish to see the restaurant and Google Maps | later |
| 4 | **Recommendation**: AI or rules over the user's stats pick suitable dishes | later, approach undecided |
| 5 | **Paid placement**: restaurants pay to appear in a separate "featured" section | later, needs research |

## Decisions

| Date | Decision | Why |
|------|----------|-----|
| 2026-10-08 | Restaurants submit a profile **and** a menu, and every dish carries nutrition | Nutrition is what decides whether a restaurant belongs on FoodFen at all |
| 2026-10-08 | Nutrition is structured numbers per serving (kcal, protein, carbs, fat), never free text | Dishes will feed the recommender / AI later; it must be machine-readable |
| 2026-10-08 | Admin approves the restaurant once, and each dish separately | Editing one dish must not hide the whole restaurant |
| 2026-10-08 | Editing an approved dish sends it back to `pending`; it is hidden until re-approved | Simplest correct rule. Keeping the old version live needs a revision table: add it only if owners complain |
| 2026-10-08 | Admin scope is moderation + a cash-flow/growth dashboard + ad packages; no users table | The owner named what matters; the rest stays mock |
| 2026-10-08 | Ads (packages, purchase, featured section) are deferred to their own spec, together with the dish tab | Packages nobody can buy are dead data; ads only pay off once the featured section and dish tab exist. The dashboard already returns `adRevenue` (0 for now) so its contract won't change |
| 2026-10-08 | Approved restaurant profile edits go live without re-review; admin can take a restaurant down any time | A profile carries no nutrition, so the risk is low; re-review would hide the whole restaurant over a phone-number change |
| 2026-10-08 | Moderation is status columns on each row, no review-history table | Nobody needs an audit trail yet; add a `moderation_reviews` table when someone does |
| 2026-10-08 | No separate restaurant account type. Any user can create a restaurant and becomes its owner; `role` is only `user` \| `admin` | One account system, one sign-up flow; an owner can still use the app as a diner; a role can never disagree with ownership data |

## Roles and permissions

- **user** (default): every account. Uses the app as a diner.
- **owner**: not a role. A user *is* the owner of a restaurant when `restaurants.user_id` (unique) points at them.
  Owner endpoints check ownership of the specific restaurant, never a role.
- **admin**: `users.role = 'admin'`. Moderates restaurants and dishes, sees platform data. The first
  admin is set with SQL; there is no self-service way to become one.

## Admin scope

The admin only needs these three things. Everything else in FoodFenWeb's `/admin` (old overview
KPIs, users table, quiz/quest content) stays on mock data until someone asks for it.

1. **Moderation**: approve or reject restaurants and dishes, checking the nutrition data.
2. **Dashboard**:
   - **Cash flow**: Premium revenue (real, from `payments` with status `paid`) + ad revenue.
   - **Growth**: new users and new restaurants per day.
3. **Ad packages**: manage the paid-placement packages restaurants can buy. *Deferred* (see Decisions).

## Data

- **Restaurant**: one per owner. Name, description, address, latitude/longitude (Google Maps, later
  distance filtering), phone, opening hours (free text), image.
- **Dish**: belongs to a restaurant. Name, description, image, price (VND), serving size in grams, and
  nutrition per serving: `kcal`, `protein_g`, `carbs_g`, `fat_g`, optional `fiber_g`. These names and
  types match `food_entries` on purpose, so logging a restaurant dish to the diary is a straight copy.

## Moderation lifecycle

Restaurants and dishes each have a status: `pending` → `approved` | `rejected` (with a reason).
Only the latest review is kept (status columns on each row); there is no review history.

- A new restaurant or dish starts `pending`. A `pending` restaurant can already add dishes, so the
  admin reviews the profile and menu together.
- **Dish**: editing an `approved` or `rejected` dish returns it to `pending` (resubmission).
- **Restaurant profile**: editing a `rejected` restaurant returns it to `pending`. Editing an
  `approved` one goes live immediately, with no re-review; in exchange the admin can take an approved
  restaurant down at any time (set it to `rejected` with a reason).
- Owners delete dishes outright (nothing references a dish yet).
- **Public** = an `approved` dish of an `approved` restaurant. Nothing else is ever shown to diners.

## API (planned)

Admin = `CurrentAdminDep` (403 otherwise). Role is read from the DB on every request, not from the
JWT, so promoting/demoting an admin with SQL takes effect immediately.

**Owner** (any signed-in user; ownership is implied by `/mine`, since one user has one restaurant):

- `POST /restaurants` (409 if the user already has one) · `GET|PATCH /restaurants/mine` (404 if none)
- `GET|POST /restaurants/mine/dishes` · `PATCH|DELETE /restaurants/mine/dishes/{id}` (404, not 403,
  for a dish of another restaurant)
- `POST /restaurants/mine/images` (multipart) → `{url}`, for both profile and dish images

**Admin**:

- `GET /admin/restaurants?needsReview=true|status=` · `GET /admin/restaurants/{id}` (profile + full menu)
- `POST /admin/restaurants/{id}/review` and `POST /admin/dishes/{id}/review`:
  `{decision: approved|rejected, reason?}` (reason required to reject; also used for takedowns).
  The review queue = `pending` restaurants **or** approved ones with `pending` dishes.
- `GET /admin/dashboard?from=&to=`: totals `premiumRevenue`, `adRevenue` (0 until ads exist),
  `newUsers`, `newRestaurants` + a daily series. Days are Vietnam days (UTC+7); default last 30 days.

`GET /auth/me` gains `role` and `restaurantId` (null when the user owns none).

**Contract details** (agreed with FoodFenWeb, 2026-10-08):

- Wire format is camelCase like the rest of the API: `servingG`, `proteinG`, `carbsG`, `fatG`,
  `fiberG`, `rejectionReason`, `restaurantId`, `latitude`, `longitude`, ... (snake_case above is DB/Python).
- Every write returns the full updated row (`POST /restaurants` returns the restaurant with its `id`;
  `PATCH` a dish returns it, already back at `pending`). Owner reads always include `status` +
  `rejectionReason`. Creates are 201; deleting a dish is 204.
- `PATCH` is partial (send only what changes). `null` clears `description`, `imageUrl`, `fiberG`; on any
  required field it is a 422 field error (`errors.<field>`).
- Latitude/longitude are plain numbers, range-checked (-90..90, -180..180) with a field error
  (`errors.latitude`). The BE never parses Google Maps links; the web client splits the
  `"10.7769, 106.7009"` string Google Maps copies.
- Admin list rows: `id`, `name`, `status`, `ownerName`, `ownerEmail`, `dishCount`, `pendingDishCount`,
  `updatedAt`, `rejectionReason`.
- Reviews are idempotent: reviewing again just sets the decision (and reason) again; 200 with the
  updated row, never 409.
- Images: JPEG/PNG/WebP (browser-renderable; no HEIC), max 5 MB, else 400 `{message}` like
  `/ai/food/analyze-image`. The returned `url` is absolute (Cloudinary `secure_url`).
- Dashboard: `daily` is zero-filled for every Vietnam day in `[from, to]` inclusive; dates are
  `YYYY-MM-DD`, money is integer VND, and each row also carries `adRevenue`. Range capped at 366 days.
- Role and status enums are exposed in the OpenAPI schema (the web client is generated from it).

Not yet: public diner endpoints (with the dish tab spec), bulk review, queue pagination.

## Open questions

- Recommendation approach (rules over macros vs. AI) and how dishes are fed to it.
- Paid placement: pricing, duration, how it is paid (PayOS / MoMo already integrated).
