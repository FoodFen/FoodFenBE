# Coin history + idempotent redeem — design

Date: 2026-10-14 · Status: implemented (2026-10-29) · Follows
`2026-09-30-coins-quests-design.md` ("Out of scope: a transaction-history endpoint, redeem idempotency keys").
Wire contract (owned by the mobile repo): `FoodFenFE/docs/backend-contracts/premium-entitlements.md`.

## Goal

1. A user can see where their coins came from and went: `GET /coins/transactions`, newest first, paged.
2. A retried `POST /coins/redeem` (dropped response, double tap) never spends twice.

For every user, no Premium gate.

## `GET /coins/transactions?before=&limit=` (`CurrentUserDep`)

- Same paging shape as `GET /chat/messages`: `before` = the opaque cursor from the previous page,
  `limit` 1..50 (default 20, out of range → 422).
- Response `200`: `{ "transactions": [{ "id": "uuid", "amount": 120, "reason": "quest_completed",
  "createdAt": "iso-datetime" }], "nextCursor": "string | null" }`. `amount` signed (credit > 0,
  debit < 0); `reason` is `CoinReason` (`quest_completed | streak_bonus | purchase | spend | adjustment |
  quiz_daily | quiz_practice`) and is in the OpenAPI enum. `nextCursor: null` = last page. Only the
  caller's own rows. A malformed cursor → 422 per the mobile contract (chat returns 400 for the same case; left as is). Checked at the HTTP boundary (`CursorQuery` in `coin_schemas.py`), `decode_cursor` unchanged.
- Ordering newest first by `(created_at, id)` descending; the cursor is `created_at|id`.
- **Reuse `src/application/chat_cursor.py`**: widen `encode_cursor` to accept any object with
  `created_at` and `id` (a small `Protocol` in that module) instead of only `ChatMessage`; keep the module
  name and `decode_cursor` unchanged. No second codec.
- Port: `CoinRepositoryProtocol.list_page(user_id, before: str | None, limit: int) -> list[CoinTransaction]`.
  Use case `ListCoinTransactionsUseCase` asks for `limit + 1` rows to know whether there is a next page
  (mirror `ListChatMessagesUseCase`). The `(user_id, created_at)` index already exists.

## Idempotent redeem

- `POST /coins/redeem` body gains optional `clientId: string` (1..64 chars), the repo's existing
  idempotency convention (diary push uses `clientId` + a `(user_id, client_id)` unique constraint).
  Absent → today's behaviour exactly.
- `coin_transactions.client_id` nullable `String(64)`, `UniqueConstraint("user_id", "client_id")`
  (NULLs never conflict). Domain `CoinTransaction` gains `client_id: str | None = None`; `create(...)`
  takes it optionally. Migration `0027` (0025/0026 were taken on main) (bare names per CLAUDE.md, verify `--sql` against metadata).
- Flow in `RedeemCoinsUseCase`, after the existing user-row lock (`balance(..., for_update=True)`):
  if `client_id` is given and a row `(user_id, client_id)` already exists → **replay**: return `200` with the
  current balance and current subscription, spend nothing, grant nothing. Otherwise spend as today, storing
  `client_id` on the `SPEND` row. The unique constraint is the backstop for a race the lock does not cover.
- Same `clientId` with different `days`: still a replay (the key identifies the request; documented).
- New port method `CoinRepositoryProtocol.get_by_client_id(user_id, client_id) -> CoinTransaction | None`.

## Tests (TDD)

- Unit: cursor encode/decode with a coin transaction; use case paging (limit+1, next cursor, last page).
- Repository/integration: `list_page` ordering + tie on `created_at`, only own rows; `get_by_client_id`.
- API: paging across 2 pages with no duplicates; 422 on bad limit/cursor; 401 without token; redeem twice
  with the same `clientId` → one `SPEND` row, same balance, 200 both times; redeem without `clientId`
  unchanged; two different `clientId`s spend twice.
- Before commit: `make test`, `uv run lint-imports`, migration-vs-metadata DDL check.

## Docs

- `CLAUDE.md` → "Coins & quests": add the endpoint and the `clientId` replay rule.
- Mobile contract (`premium-entitlements.md`) is updated in the mobile branch.
