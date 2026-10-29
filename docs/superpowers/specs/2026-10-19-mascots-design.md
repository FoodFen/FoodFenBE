# Mascots (buy with coins, equip) — design

Requested by the FoodFenFE session; FE spec `FoodFenFE/docs/superpowers/specs/2026-10-19-mascot-design.md`
(Part 2). Same server-authoritative model as `POST /coins/redeem`. Artwork ships in the app keyed by id;
the server owns only ids, names, prices, ownership and the equipped id.

## Wire contract (camelCase, all `CurrentUserDep`)

- `GET /mascots` → `{ balance: int, equippedId: str, mascots: [{ id, name, coinCost, owned }] }`,
  mascots ordered by `coinCost` then `id`. The free mascot(s) (`coinCost == 0`) are `owned: true` for everyone.
- `POST /mascots/{id}/purchase` → same body as `GET /mascots` (after the purchase).
  404 unknown/inactive id · 409 `error: "mascot_already_owned"` (also for any free mascot) ·
  409 insufficient coins (existing `InsufficientCoinsException`, plain message, like redeem).
- `PUT /mascots/equipped {mascotId}` → `{ equippedId }`. 404 unknown/inactive id ·
  409 `error: "mascot_not_owned"`. Re-equipping the current one is a 200 no-op.

## Storage (migration 0026)

- `mascots` catalogue: `id String(32)` **PK — the slug itself** (deliberate exception to "UUID PK":
  the FE contract and the artwork registry key on the string id, a UUID + slug pair is pure
  indirection), `name String(40)`, `coin_cost Integer` (CHECK `>= 0`), `active Boolean` default true.
  Seeded: `default` "Fen" 0 · `sprout` "Sprout" 300 · `berry` "Berry" 600 · `chili` "Chili" 1000
  (bundles are 600 coins / 10 Premium days). Change prices/names with SQL; deactivate, never delete.
- `user_mascots`: `(user_id FK users ON DELETE CASCADE, mascot_id FK mascots)` composite PK,
  `purchased_at`. Free mascots get **no** row — owned is `coin_cost == 0 OR row exists`.
- `users.equipped_mascot_id String(32) NOT NULL server_default 'default'` FK `mascots.id`.
  Not on the `User` domain entity: only the mascot repository reads/writes it (UserORM gets the
  column so metadata matches the migration; `to_domain` ignores it).

## Rules

- Purchase: `coins.balance(user_id, for_update=True)` first (locks the user row, serialises a user's
  purchases), then: unknown → 404, owned → 409, short → 409, else insert `user_mascots` row +
  `CoinTransaction.create(user_id, -cost, CoinReason.SPEND)`. Doesn't auto-equip.
- An equipped mascot that is later deactivated: `GET /mascots` reports `equippedId: "default"`
  (no write). Inactive mascots are not listed.

## Shape

Domain: `Mascot` entity (id, name, coin_cost; invariant coin_cost >= 0), `MascotNotFoundException`
(EntityNotFound → 404), `MascotAlreadyOwnedException` / `MascotNotOwnedException` (409 + `error` code).
Application: `MascotRepositoryProtocol` (list_active, get_active(id), owned_ids(user_id), add_owned,
get_equipped(user_id), set_equipped), `MascotsOutputDTO`, use cases `GetMascots`, `PurchaseMascot`,
`EquipMascot`. Adapters: `mascot_controller.py`, `mascot_schemas.py`. Infra: ORM models, repo, DI.

## Tests

- api (`tests/api/test_mascot_endpoints.py`): GET for a fresh user (default owned + equipped,
  balance 0); purchase happy path (balance drops, owned flips, `spend` ledger row); 409 short; 409
  already owned (twice, and on `default`); 404 unknown; equip owned → 200 and GET reflects it; equip
  not-owned 409; equip unknown 404; 401 without a token.
- migration verified against `Base.metadata` (offline `--sql`), per CLAUDE.md.
