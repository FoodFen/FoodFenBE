# Restaurant marketplace: business rules

> **Living document.** The single source of truth for *what* the restaurant/admin/recommendation
> side of FoodFen does and *why*. Update it in the same change as any decision or behaviour change.
> Design specs (`docs/superpowers/specs/`) record *how* one slice was built; this file records the
> rules that hold across slices. Status: **pieces 1–3 implemented** (on main). Specs: pieces 1–2
> `docs/superpowers/specs/2026-10-08-restaurants-admin-design.md`, piece 3 `docs/superpowers/specs/2026-10-09-dish-tab-design.md`.

## Vision

FoodFen grows from a personal nutrition tracker into a place to find food that fits your goals.
Five pieces, built in this order:

| # | Piece | Status |
|---|-------|--------|
| 1 | **Restaurants**: owners register for free, submit their profile and menu with nutrition | implemented |
| 2 | **Admin**: approves restaurants and dishes, sees basic platform data (transactions, users) | implemented |
| 3 | **Dish tab** (mobile): dishes that fit the user first, then the rest; tap a dish to see the restaurant and Google Maps | implemented |
| 4 | **Recommendation**: rules rank the dish tab by the day's macros; Fen recommends real dishes as cards in chat | implemented (ranking); Fen cards pending (`docs/superpowers/specs/2026-10-11-dish-recommendation-design.md`) |
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
| 2026-10-09 | Both review endpoints take an optional `expectedUpdatedAt`; if it differs from the row's `updated_at` → 409 `{message}`. Absent = no check. Ships with the dish tab | An owner edit between the admin opening a row and approving it would otherwise be approved unseen. Optional so old clients keep working; web sends the on-screen `updatedAt` and asks for a reload on 409 |
| 2026-10-09 | `imageUrl` (restaurant and dish, create and patch) only accepts our own Cloudinary delivery URLs; image changes are not re-reviewed. Ships with the dish tab | Any https host lets an owner swap the file behind an already-approved URL and lets a third party see every viewer's IP. The upload endpoint already returns Cloudinary URLs. A bad image is handled by the admin takedown; revisit re-review only if abuse shows up |
| 2026-10-10 | `GET /dishes` gets search (`q`), filters and a cursor; filters apply after ranking and never change `remainingKcal` | The diner needs to find a dish by name or budget without losing the fits-first order. In memory and offset-based until the dish count makes it slow |
| 2026-10-11 | Recommendation = deterministic ranking for the dish tab + Fen picking from that ranking in chat. No LLM in the list, no per-meal split, no RAG | The list must be instant, page-stable and testable, and an LLM compares numbers badly; Fen adds what numbers miss (variety, "đồ nước, không cay"). Users log at the end of the day, so meals can't be inferred. The whole catalog fits the prompt; retrieval waits until it doesn't (200 dishes) |
| 2026-10-11 | Dish-tab rank: diet first, then fits the day's kcal (10% tolerance), ordered by how close the dish's macro split is to what is left; always at least 3 suggestions, flagged with `exceeds_*` reasons. `fits` now means "suggested" | Never too strict: a user near the goal still gets options, told what they would exceed. The app only sends `fits=true`, so tolerance and top-up dishes must count as `fits` |
| 2026-10-11 | Dishes carry `dietTag` (`none`/`vegetarian`/`vegan`), declared by the owner, checked by the admin; a vegetarian/vegan user is never suggested or offered by Fen a non-matching dish | Suggesting cơm gà to a vegan user with "fills your protein" would break trust; the owner knows the recipe, an AI guess from the name does not |
| 2026-10-10 | Admin gets read-only users (`GET /admin/users`), quiz questions and quest definitions; the dashboard gains `foodEntries` and `premiumUsers`. No overview endpoint, no AI-scan count | The web admin's mock screens needed real data. The dashboard already had the daily series, so KPIs reuse it; Premium AI scans are not recorded anywhere, so the number would be invented |

## Roles and permissions

- **user** (default): every account. Uses the app as a diner.
- **owner**: not a role. A user *is* the owner of a restaurant when `restaurants.user_id` (unique) points at them.
  Owner endpoints check ownership of the specific restaurant, never a role.
- **admin**: `users.role = 'admin'`. Moderates restaurants and dishes, sees platform data. The admin
  account comes from `ADMIN_EMAIL`/`ADMIN_PASSWORD`, ensured at every startup; there is no self-service way to become one.

## Admin scope

The admin needs these three things, plus read-only views of users and quiz/quest content
(asked for on 2026-10-10, spec `docs/superpowers/specs/2026-10-10-admin-content-design.md`). Nothing
in the admin edits users or content: no ban, toggle, export or edit actions.

1. **Moderation**: approve or reject restaurants and dishes, checking the nutrition data.
2. **Dashboard**:
   - **Cash flow**: Premium revenue (real, from `payments` with status `paid`) + ad revenue.
   - **Growth**: new users and new restaurants per day.
   - **Activity**: meals logged per day (`foodEntries`) and the current Premium user count. Today vs
     yesterday is the same endpoint with `from=<yesterday>&to=<today>`, not a separate overview.
3. **Ad packages**: manage the paid-placement packages restaurants can buy. *Deferred* (see Decisions).

## Dish tab (diner view)

Free for every signed-in user (restaurants need views before they have a reason to join). The order is a
rule, not AI: `remaining` is the goal in force on the day minus that day's diary (kcal, protein, carbs, fat),
each clamped at 0. Per dish, in tiers: (1) diet-compatible and `kcal` <= remaining kcal, (2) diet-compatible
and `kcal` <= remaining x 1.1, both ordered by a macro score (how far the dish's energy split P/C/F is from the
split of what is left: protein short, carbs or fat over; ties lower kcal, then id); (3) the other
diet-compatible dishes, lowest kcal first; (4) diet-incompatible dishes, lowest kcal first. Tiers 1-2 are
**suggested** (`fits`); if they hold fewer than 3 dishes the lowest-kcal tier-3 dishes are suggested until there
are 3 (also when nothing is left), never tier 4. Diet: a `vegan` user only gets `vegan` dishes, a `vegetarian`
user `vegetarian` or `vegan`, any other or unset diet every dish. With no goal: newest first (diet-compatible
before the rest), nothing suggested. `reasons` (suggested dishes only): `fills_protein` (the dish has at least
the protein per kcal that is left), `exceeds_kcal` / `exceeds_carbs` / `exceeds_fat` (more than what is left;
protein over is never flagged). No distance: coordinates are returned only so the app can open Google Maps.
Logging a dish to the diary has no endpoint: the app copies the dish's nutrition into a local food entry and the
existing sync uploads it.

Search and filters (2026-10-10) narrow the ranked list, they never reorder it: rank first, then filter, then
page. `q` matches the dish **or** restaurant name, case- and Vietnamese-diacritic-insensitive ("pho" finds
"Phở", "dong" finds "Đông"). `remainingKcal` ignores filters. All filtering and paging happen in memory over
every public dish (`application/dish_fit.py`); move to SQL with a keyset cursor once that gets slow.

## Data

- **Restaurant**: one per owner. Name, description, address, latitude/longitude (Google Maps, later
  distance filtering), phone, opening hours (free text), image.
- **Dish**: belongs to a restaurant. Name, description, image, price (VND), serving size in grams, `dietTag`
  (`none` | `vegetarian` | `vegan`, default `none`, declared by the owner and checked by the admin like
  nutrition; changing it is an edit, so it goes back to review), and
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

## API

Admin = `CurrentAdminDep` (403 otherwise). Role is read from the DB on every request, not from the
JWT, so promoting/demoting an admin with SQL takes effect immediately.

**Owner** (any signed-in user; ownership is implied by `/mine`, since one user has one restaurant):

- `POST /restaurants` (409 if the user already has one) · `GET|PATCH /restaurants/mine` (404 if none)
- `GET|POST /restaurants/mine/dishes` · `PATCH|DELETE /restaurants/mine/dishes/{id}` (404, not 403,
  for a dish of another restaurant)
- `POST /restaurants/mine/images` (multipart) → `{url}`, for both profile and dish images

**Diner** (any signed-in user, no Premium gate; public = approved dish of an approved restaurant):

- `GET /dishes?date=YYYY-MM-DD` → `{remainingKcal, dishes}`; `date` is the client's local day (omitted:
  Vietnam day). `remainingKcal` is `null` with no goal in force. Each dish: `id, name, description,
  imageUrl, price, servingG, kcal, proteinG, carbsG, fatG, fiberG, dietTag, fits, reasons` + `restaurant
  {id, name, address, latitude, longitude}`. `fits` = suggested (see above), not "within the goal". No status,
  timestamps or owner data.
  Optional query params, all combinable: `q` (≤100 chars, blank = none), `fits` (`true` = only suggested
  dishes, `false` = only the others; omit for both), `kcalMin`/`kcalMax`, `priceMin`/`priceMax` (VND),
  `proteinMin` (g), bounds inclusive and ≥ 0; `limit` 1..50 (default 20), `cursor`. Response adds
  `nextCursor: string | null`: pass it back as `cursor` for the next page; `null` = last page. The cursor
  is opaque (today an offset, so a diary change mid-scroll can shift rows: dedupe by `id`). Bad values → 422.
- `GET /restaurants/{id}`: public profile (`id, name, description, address, phone, openingHours,
  latitude, longitude, imageUrl`) + `dishes` (its approved dishes, oldest first). 404 when the
  restaurant does not exist or is not approved.

**Admin**:

- `GET /admin/restaurants?needsReview=true|status=` · `GET /admin/restaurants/{id}` (profile + full menu)
- `POST /admin/restaurants/{id}/review` and `POST /admin/dishes/{id}/review`:
  `{decision: approved|rejected, reason?}` (reason required to reject; also used for takedowns).
  The review queue = `pending` restaurants **or** approved ones with `pending` dishes.
  Optional `expectedUpdatedAt` (the `updatedAt` the admin saw, sent back verbatim): if the row has
  changed since, 409 `{message}` and nothing is reviewed. Absent: no check.
- `GET /admin/dashboard?from=&to=`: totals `premiumRevenue`, `adRevenue` (0 until ads exist),
  `newUsers`, `newRestaurants` + a daily series. Days are Vietnam days (UTC+7); default last 30 days.

`GET /auth/me` gains `role` and `restaurantId` (null when the user owns none).

**Contract details** (agreed with FoodFenWeb, 2026-10-08):

- Wire format is camelCase like the rest of the API: `servingG`, `proteinG`, `carbsG`, `fatG`,
  `fiberG`, `rejectionReason`, `restaurantId`, `latitude`, `longitude`, ... (snake_case above is DB/Python).
- Every write returns the full updated row (`POST /restaurants` returns the restaurant with its `id`;
  `PATCH` a dish returns it, already back at `pending`). Owner reads always include `status` +
  `rejectionReason`. Creates are 201; deleting a dish is 204.
- `PATCH` with an empty body is a no-op (no status change).
- `PATCH` is partial (send only what changes). `null` clears `description`, `imageUrl`, `fiberG`; on any
  required field it is a 422 field error (`errors.<field>`).
- Latitude/longitude are plain numbers, range-checked (-90..90, -180..180) with a field error
  (`errors.latitude`). The BE never parses Google Maps links; the web client splits the
  `"10.7769, 106.7009"` string Google Maps copies.
- Admin list rows: `id`, `name`, `status`, `ownerName`, `ownerEmail`, `dishCount`, `pendingDishCount`,
  `updatedAt`, `rejectionReason`.
- Reviews are idempotent: reviewing again just sets the decision (and reason) again; 200 with the
  updated row. The only 409 is a stale `expectedUpdatedAt`.
- Images: JPEG/PNG/WebP (browser-renderable; no HEIC), max 5 MB, else 400 `{message}` like
  `/ai/food/analyze-image`. The returned `url` is absolute (Cloudinary `secure_url`).
- `imageUrl` on create/patch (restaurant and dish) must start with
  `https://res.cloudinary.com/<our cloud>/image/upload/`, else 422 `errors.imageUrl`; `null` still
  clears. With no `CLOUDINARY_URL` configured every non-null `imageUrl` is rejected.
- Dashboard: `daily` is zero-filled for every Vietnam day in `[from, to]` inclusive; dates are
  `YYYY-MM-DD`, money is integer VND, and each row also carries `adRevenue`. Range capped at 366 days.
- Role and status enums are exposed in the OpenAPI schema (the web client is generated from it).

Not yet: distance, bulk review, queue pagination.

## Open questions

- Paid placement: pricing, duration, how it is paid (PayOS / MoMo already integrated).
