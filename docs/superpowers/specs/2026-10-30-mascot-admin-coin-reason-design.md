# Mascot artwork from the server, admin mascot CRUD, mascot purchases in coin history — design

Date: 2026-10-30 · Status: implemented (BE) 2026-10-30 · Follows `2026-10-19-mascots-design.md` and `2026-10-14-coin-history-design.md`.
Plan: `docs/superpowers/plans/2026-10-30-mascot-admin-coin-reason.md`.

## Why

1. `GET /coins/transactions` can't tell a mascot purchase from a Premium redeem: both write `CoinReason.SPEND`.
2. Mascot artwork is drawn in app code (`FoodFenFE/src/components/mascot/visuals.tsx`), so a new mascot needs an
   app release, and the paid ones are recolours of Fen. The user wants the artwork to live on the server: admin
   manages it, the app downloads it.
3. The catalogue is edited with hand-written SQL. Admin must be able to create, edit, hide and delete mascots
   from the web admin, **as easily as possible** (owner's explicit priority).

The four hand-drawn mascots (`default`, `sprout`, `berry`, `chili`) stay as they are, for testing. Uploading art
for one of them later makes the server art win over the hand-drawn one.

## Part A — `mascot_purchase` coin reason

- `CoinReason.MASCOT_PURCHASE = "mascot_purchase"`. `PurchaseMascotUseCase` writes it; Premium redeem keeps `SPEND`.
- Migration `0029`: widen the `coin_reason` CHECK (bare name `"coin_reason"`, mirror how `0016` added the quiz
  reasons; widen the VARCHAR if its width comes from the longest value) and **backfill**: a `spend` row becomes
  `mascot_purchase` when a `user_mascots` row has the same `user_id`, `amount = -mascots.coin_cost` and
  `|created_at - purchased_at| < 5 s` (same request). Downgrade reverses both.
- Wire: no shape change, `reason` gains a value. Out of scope: *which* mascot was bought.

## Part B — mascot artwork (data + public API)

- **Model**: each mascot has up to one image per *state*. States = new `MascotState` StrEnum in
  `src/domain/enums.py`, exactly the app's actions: `idle, hungry, thirsty, eating, drinking, exercising,
  thinking, happy, confused`. `idle` is the base image; the app uses it for any state without its own image.
- **Storage**: migration `0030`, table `mascot_images`: `mascot_id String(32)` FK `mascots.id` **ON DELETE CASCADE**,
  `state` (`enum_column(MascotState, ...)`), `url String(2048)`, PK `(mascot_id, state)`. `MascotORM` gets a
  `lazy="selectin"` relationship (`cascade="all, delete-orphan"` too: tests run on SQLite, where the FK
`ON DELETE` isn't enforced); `Mascot` entity gets `images: dict[MascotState, str]`.
- **Files**: PNG or WebP (transparent; animated WebP allowed, the app's `expo-image` plays it), max 5 MB, on our
  Cloudinary. URLs are validated with the existing `CloudinaryImageUrl` (`restaurant_schemas.py`) — move it to a
  shared schema module if importing it from there reads wrong.
- **Upload**: `POST /admin/images` (admin, multipart `image`) → `{ url }`. Same checks and same
  `UploadRestaurantImageUseCase` / `ImageStorageProtocol` as `POST /restaurants/mine/images` (share the
  content-type / size / magic-byte check, don't copy it), but **without** the 20/min per-user limiter: dropping
  9 state images plus a few retries must never hit a 429.
- **Public**: `GET /mascots` (and the purchase response) items gain `images: { [state]: url }` — only states
  that have one; `{}` for the hand-drawn four today.

## Part C — admin mascot CRUD

All under the admin router (`get_current_admin`, 403). Item shape everywhere:
`{ id, name, coinCost, active, images: { [state]: url }, ownerCount, equippedCount }`
(`ownerCount` = `user_mascots` rows, `equippedCount` = users with it equipped; the web uses them to warn).

- `GET /admin/mascots` → every mascot incl. inactive, ordered `coinCost`, `id`.
- `POST /admin/mascots { id, name, coinCost, active = false, images = {} }` → 201. One request creates the whole
  mascot, art included. `id`: slug `^[a-z0-9_-]{1,32}$`, immutable; taken → 409 `mascot_id_taken`.
  New mascots default to **inactive** (a draft the admin can finish before users see it).
- `PATCH /admin/mascots/{id} { name?, coinCost?, active?, images? }` → 200. `images` merges per state:
  a url sets it, `null` removes it, an absent state is untouched. Unknown id → 404.
- `DELETE /admin/mascots/{id}` → 204 when nobody owns or equips it (typos, abandoned drafts); otherwise 409
  `mascot_in_use` (the message says to hide it instead). Images go with it (cascade).
- Validation: `name` trimmed, 1..40; `coinCost` int 0..1_000_000; `state` keys must be `MascotState` values (422).
- **Invariants** (entity `create` / `update`, never the use case):
  - `default` is locked: can't be deactivated, priced > 0 or deleted → 409 `mascot_default_locked`.
  - An **active** mascot must have an `idle` image → 409 `mascot_missing_idle_image` (activating without one,
    creating active without one, or removing `idle` from an active one). Exception: the four hand-drawn ids,
    which the app draws itself (`# ponytail:` comment on that set — drop an id once it has server art).
- Price changes are not retroactive: buyers keep their row; a free mascot made paid stops being owned by
  users without a row (they stay equipped). Documented, not prevented.
- Exceptions: `MascotIdTakenException`, `MascotDefaultLockedException`, `MascotMissingIdleImageException`,
  `MascotInUseException` (409 + `error` code, like `MascotAlreadyOwnedException`). Use cases in
  `src/application/use_cases/admin_mascots.py`. Repository port gains `list_all` (with the two counts),
  `get` (any status), `add`, `update`, `delete`.

## Part D — body colour (added 2026-11-01, asked by the mobile session)

Server art is the character only; the app fills a body circle behind it. Admin picks that circle's colour.

- `mascots.body_color`: nullable `String(7)`, `#RRGGBB` (migration `0031`, existing rows NULL). **NULL = the app's
  theme green** (light/dark differ, so no default hex is stored).
- Entity `Mascot.body_color: str | None = None`, checked in `__post_init__` against `^#[0-9A-Fa-f]{6}$`
  (`InvalidMascotException`), stored as given. Request schemas repeat the pattern so bad input is a plain 422.
- Wire: `bodyColor: string | null` on `MascotResponse` (`GET /mascots`, purchase) and `AdminMascotResponse`.
  `POST /admin/mascots` takes optional `bodyColor` (default null). `PATCH`: absent = unchanged, explicit `null` =
  back to default. Pydantic can't tell those apart by value, so the controller passes `...` (Ellipsis, "keep")
  unless `"body_color" in body.model_fields_set`; `Mascot.update(body_color=...)` defaults to `...` as well.

## Web admin UX (FoodFenWeb) — "as easy as possible"

Mirrors `features/admin/ad-packages-*`, plus:

- **Table**: idle-image thumbnail, name, id, price, owners / equipped, an **inline active switch** (no dialog;
  disabled with a tooltip when there's no idle image), edit and delete actions. Delete is offered only when
  `ownerCount == 0 && equippedCount == 0`; otherwise the action reads "Hide" and does the switch.
- **One dialog for create and edit**: name, price, id (pre-filled as a slug of the name on create, editable;
  read-only on edit), and a **9-tile state grid**. Each tile: click to pick or drag-and-drop a file, uploads at
  once with a spinner, shows the preview, remove button; empty tiles show the idle image greyed out ("uses idle").
- **Bulk drop**: dropping several files anywhere on the grid assigns each by filename (`happy.png` → happy,
  `idle.webp` → idle); unmatched files are listed so the admin can drag them onto a tile.
- **Preview** strip: the mascot on a light and a dark background, cycling through states, so the admin sees what
  users will see.
- **Confirmations** only where it hurts: hiding a mascot with `equippedCount > 0` ("N users use it; they'll
  switch to Fen"); repricing a free mascot to paid; deleting (irreversible, one-step confirm). Server errors land inline on the field they concern
  (existing `{message, error, errors}` body).
- `default`'s price and active controls are disabled with a short reason.

## Mobile (FoodFenFE)

- Schemas: `images` on catalogue items; coin reasons add `mascot_purchase` **and the already-missing
  `quiz_daily`, `quiz_practice`** (strict `z.enum` currently rejects real history rows).
- Rendering order for a mascot + state: server image for that state → server `idle` → hand-drawn visual (the
  four ids) → Fen. With `expo-image` (disk cache), sized via a Cloudinary transformation in the URL if that helps.
- The equipped mascot must render offline at cold start: persist its `images` with the equipped id
  (`equippedStore`) rather than relying on the catalogue query being cached. The shop uses the `idle` image.
- Keep the existing hop animation. Contract note in `docs/backend-contracts/premium-entitlements.md`.

## Tests (TDD, by each implementer)

- A: purchase → newest transaction `mascot_purchase`; redeem still `spend`; backfill exercised in the
  migration check.
- B/C unit: entity invariants (slug, name, cost, default lock, idle-required-when-active incl. the hand-drawn
  exception, images merge).
- B/C api: list with counts; create 201 (with images) / 409 taken / 422 bad slug or state; patch merge
  (set, remove, untouched) / 404 / 409 locked / 409 missing idle; delete 204 / 409 in use; non-admin 403;
  `GET /mascots` returns `images`; inactive mascot disappears from `GET /mascots` and can't be bought;
  `POST /admin/images` rejects non-images and isn't rate-limited.
- Before done: `make test`, `uv run lint-imports`, migration-vs-metadata DDL check (0029, 0030).

## Docs (same change)

`docs/feature-notes.md` "Coins & quests" Mascots bullet (art from the server, admin endpoints, new reason), and the
2026-10-19 mascots spec's "Change prices/names with SQL" line.
