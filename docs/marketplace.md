# Restaurant marketplace: business rules

> **Living document.** The single source of truth for *what* the restaurant/admin/recommendation
> side of FoodFen does and *why*. Update it in the same change as any decision or behaviour change.
> Design specs (`docs/superpowers/specs/`) record *how* one slice was built; this file records the
> rules that hold across slices. Status: **pieces 1–5 implemented**. Specs: pieces 1–2
> `docs/superpowers/specs/2026-10-08-restaurants-admin-design.md`, piece 3 `docs/superpowers/specs/2026-10-09-dish-tab-design.md`,
> piece 5 `docs/superpowers/specs/2026-10-12-paid-placement-design.md`.

## Vision

FoodFen grows from a personal nutrition tracker into a place to find food that fits your goals.
Five pieces, built in this order:

| # | Piece | Status |
|---|-------|--------|
| 1 | **Restaurants**: owners register for free, submit their profile and menu with nutrition | implemented |
| 2 | **Admin**: approves restaurants and dishes, sees basic platform data (transactions, users) | implemented |
| 3 | **Dish tab** (mobile): dishes that fit the user first, then the rest; tap a dish to see the restaurant and Google Maps | implemented |
| 4 | **Recommendation**: rules rank the dish tab by the day's macros; Fen recommends real dishes as cards in chat | implemented (`docs/superpowers/specs/2026-10-11-dish-recommendation-design.md`) |
| 5 | **Paid placement**: restaurants pay to appear in a separate "Được tài trợ" section above the dish list | implemented (`docs/superpowers/specs/2026-10-12-paid-placement-design.md`) |

## Decisions

| Date | Decision | Why |
|------|----------|-----|
| 2026-10-08 | Restaurants submit a profile **and** a menu, and every dish carries nutrition | Nutrition is what decides whether a restaurant belongs on FoodFen at all |
| 2026-10-08 | Nutrition is structured numbers per serving (kcal, protein, carbs, fat), never free text | Dishes will feed the recommender / AI later; it must be machine-readable |
| 2026-10-08 | Admin approves the restaurant once, and each dish separately | Editing one dish must not hide the whole restaurant |
| 2026-10-08 | Editing an approved dish sends it back to `pending`; it is hidden until re-approved | Simplest correct rule. Keeping the old version live needs a revision table: add it only if owners complain |
| 2026-10-08 | Admin scope is moderation + a cash-flow/growth dashboard + ad packages; no users table | The owner named what matters; the rest stays mock |
| 2026-10-08 | Ads (packages, purchase, featured section) are deferred to their own spec, together with the dish tab (done 2026-10-12, see below) | Packages nobody can buy are dead data; ads only pay off once the featured section and dish tab exist. The dashboard already returned `adRevenue` so its contract didn't change |
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
| 2026-10-12 | Money buys eligibility to be shown, never a place in front of a user the dish doesn't fit: a sponsored dish is shown only if it is in that user's suggested set (`fits`) **and** within the day's kcal tolerance (left x 1.1); the top-up dishes that keep the main list from being empty are never sponsored; nothing qualifies, or no goal, means no sponsored section | A paid ad for 1500 kcal to someone with 200 left would break trust in the whole tab. Health first is the product |
| 2026-10-12 | A package is N days for the **whole restaurant**, not per dish; per user the server picks the restaurant's best-ranked fitting dish | A healthier menu is shown more often: the incentive points the right way. Owners pick nothing per dish, so there is nothing to moderate |
| 2026-10-12 | Order and size of the sponsored section = the existing ranking, one dish per restaurant, the 3 best-ranked restaurants | Deterministic and testable; no bidding, so no auction rules |
| 2026-10-12 | The sponsored section is separate from the main list, which stays ranked purely by health and carries no sponsor label. A sponsored dish also appears at its natural rank in the main list (shown twice, the app does not de-duplicate) | Removing it from the main list would let money change the health ranking and shift the offset cursor |
| 2026-10-12 | The sponsored section appears on the first page only and honours search/filters (a search for "phở" only features phở) | Later pages are for browsing; a sponsored dish that ignores the search is noise |
| 2026-10-12 | Fen (chat) never sees sponsorship | Advice must stay neutral; sponsored dishes can still be recommended by Fen, but only on health merit |
| 2026-10-12 | Owners see daily impressions (one counter row per restaurant per Vietnam day, last 30 days) | Paying no longer guarantees exposure (the health gate), so the owner needs to see what they got. No click tracking |
| 2026-10-12 | Admin creates and edits packages (days, price, active) on the admin web; no delete (deactivate instead); the migration seeds one (7 days, 99 000 VND) | Payments snapshot the days and amount, so an edit never changes a pending order and history survives |
| 2026-10-12 | Buying while featured extends from the current end; no refund if the admin takes the restaurant down mid-package (its dishes just stop being public, the days keep running) | Simple and predictable; the takedown is the restaurant's own doing |
| 2026-10-12 | Only an approved restaurant can buy placement; payment goes through the existing PayOS / MoMo checkout (`plan_type = ad_package`), the return URL is FoodFenWeb's `/restaurant/ads` | Reuses the payment flow, status polling and webhooks as they are; ad payments count as `adRevenue`, never `premiumRevenue`, and grant no Premium |

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
3. **Ad packages**: create and edit the paid-placement packages restaurants can buy (`/admin/ad-packages`); the dashboard's `adRevenue` is the paid `ad_package` payments.

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

## Paid placement

Spec: `docs/superpowers/specs/2026-10-12-paid-placement-design.md`.

- A **package** (`ad_packages`: `days`, `priceVnd`, `active`) is N days of placement for a whole restaurant.
  The owner buys it through the normal checkout; once the payment flips to `paid` (webhook or status poll,
  applied exactly once) `restaurants.featured_until = max(now, featured_until) + days`.
- **Health gate**: `GET /dishes` computes `featured` from the ranked, filtered list: walking it in order, the
  first `fits` dish within kcal left x 1.1 of each currently featured restaurant, at most 3 restaurants
  (`pick_featured` in `application/dish_fit.py`). The top-up dishes (suggested only so the main list is
  never empty) are over that limit, so they are never sponsored: a user with nothing left sees no sponsored
  section. First page only (no cursor). No goal means `featured` is `[]`.
- **Impressions**: every restaurant in a returned `featured` list gets +1 on today's Vietnam day
  (`ad_impressions`, upsert). Zero when nothing is shown: no exposure, no count.
- Fen's chat context is untouched.

## Data

- **Restaurant**: one per owner. Name, description, address, latitude/longitude (Google Maps, later
  distance filtering), phone, opening hours (free text), image.
- `featured_until` (nullable) is when the restaurant's paid placement ends; see Paid placement.
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
- `GET /restaurants/mine/ads` → `{featuredUntil, packages: [{id, days, priceVnd}] (active, fewest days first),
  impressions: [{date, count}] (last 30 Vietnam days, oldest first, zero-filled)}`
- `POST /restaurants/mine/ads/checkout {packageId, provider}` → the same body as `/payments/checkout`
  (`planType: "ad_package"`); 409 `{error: "restaurant_not_approved"}` unless the restaurant is approved,
  404 for an unknown or inactive package. Status and cancel reuse `GET /payments/{orderCode}` and
  `POST /payments/{orderCode}/cancel`. `POST /payments/checkout` still only accepts `monthly | annual` (422).

**Diner** (any signed-in user, no Premium gate; public = approved dish of an approved restaurant):

- `GET /dishes?date=YYYY-MM-DD` → `{remainingKcal, dishes, featured}`; `date` is the client's local day (omitted:
  Vietnam day). `remainingKcal` is `null` with no goal in force. Each dish: `id, name, description,
  imageUrl, price, servingG, kcal, proteinG, carbsG, fatG, fiberG, dietTag, fits, reasons` + `restaurant
  {id, name, address, latitude, longitude}`. `fits` = suggested (see above), not "within the goal". No status,
  timestamps or owner data.
  The response also has `featured` (same dish shape, `fits` always true): the sponsored section, `[]` on
  later pages, with no goal, or when nothing sponsored fits.
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
- `GET /admin/ad-packages` (all, inactive included: `[{id, days, priceVnd, active, createdAt}]`) ·
  `POST /admin/ad-packages {days, priceVnd, active?}` (201) · `PATCH /admin/ad-packages/{id}`
  `{days?, priceVnd?, active?}` (404 unknown id). `days` and `priceVnd` are positive integers (422).
- `GET /admin/dashboard?from=&to=`: totals `premiumRevenue` (paid payments except ads), `adRevenue` (paid `ad_package` payments),
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
  `YYYY-MM-DD`, money is integer VND, and each row also carries `adRevenue`; `priceVnd` of ad packages is a JSON integer too. Range capped at 366 days.
- Role and status enums are exposed in the OpenAPI schema (the web client is generated from it).

Not yet: distance, bulk review, queue pagination.

## Open questions

None.
