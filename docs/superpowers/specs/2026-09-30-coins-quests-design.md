# Server-tracked coins & quests — design

Decided with the product owner (2026-09-30). Supersedes the FE's local-only coin shop.

## Decisions

- **Coins are server-authoritative.** Balance = `SUM(coin_transactions.amount)` (ledger already modelled).
  Users only earn coins online.
- **Quest progress is server-derived** from rows already synced (food entries, water, weight, goals). The client
  never reports completion.
- **Quest catalog is a DB table** (`quest_definitions`, seeded by migration). Evaluators stay in code; admin
  (later) edits target / reward / cadence / active. A brand-new *kind* of quest still needs a deploy.
- **Lazy evaluation.** `GET /quests?date=` issues missing quests, evaluates progress, and pays newly completed
  ones. No scheduler, no hooks on sync writes.
- **Redeem extends the single subscription row** by N days (`plan_type = coin_redeem`, price 0 if new), sets the
  user's tier to PREMIUM. Bundles are constants: 10 days / 600 coins, 30 days / 1500 coins.

## API (camelCase, `CurrentUserDep`)

- `GET /quests?date=YYYY-MM-DD` → `{balance, quests: [{id, questType, cadence, questDate, progress, target,
  rewardCoins, completed, completionRatio}]}`. `date` is the client's local day (same convention as `loggedOn`).
  `completionRatio` (0..1) is the fraction of `target` that counts as complete (0.9 for the calorie/protein goal quests,
  1 otherwise); `completed` stays the authority for done/not-done.
- `POST /coins/redeem {days: 10|30}` → `{balance, subscription}`. Unknown bundle 400, insufficient coins 409.

## Assumptions (defaults I picked — correct me)

| Quest | Progress unit | Seed target / ratio / reward | Cadence |
|---|---|---|---|
| log_breakfast | breakfast entries that day | 1 / 1 / 10 | daily |
| log_all_meals | distinct of breakfast, lunch, dinner | 3 / 1 / 20 | daily |
| hit_calorie_goal | % of goal kcal eaten, capped 100 | 100 / 0.9 / 20 | daily |
| hit_protein_goal | % of goal protein eaten, capped 100 | 100 / 0.9 / 20 | daily |
| drink_water | % of goal water drunk, capped 100 | 100 / 1 / 10 | daily |
| log_weight | weigh-ins that day | 1 / 1 / 10 | daily |
| stay_active_week | distinct days with a food entry in the ISO week | 5 / 1 / 50 | weekly (`questDate` = Monday) |

Rewards and targets are placeholders; they are data, so changing them is an UPDATE, not a deploy. A day with no
goal row scores 0 for goal quests. Soft-deleted rows don't count.

## Integrity

- Issuance: `INSERT … ON CONFLICT DO NOTHING` on `uq_quests_user_type_date`.
- Payout: `UPDATE quests SET completed … WHERE id=? AND completed=false RETURNING` — only the request that flips
  the flag writes the `QUEST_COMPLETED` ledger line, so concurrent reads can't double-pay.
- Redeem locks the user row (`FOR UPDATE`) before reading the balance, so concurrent redeems can't overdraw.
- Issued quests copy target/reward/ratio, so editing a definition never rewrites past quests.

## Out of scope

Streak bonuses, admin endpoints/role, redeem idempotency keys, a transaction-history endpoint.
