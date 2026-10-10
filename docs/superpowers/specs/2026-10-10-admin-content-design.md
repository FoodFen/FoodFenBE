# Admin: real data for overview, users, quiz and quest screens

Asked by FoodFenWeb on 2026-10-10 to replace the web admin's mock "Tổng quan", "Người dùng" and
"Nội dung" screens. All read-only, admin-only (the `/admin` router already depends on
`get_current_admin`), camelCase. No edit / toggle / export / ban actions.

## Decisions

- **No `/admin/overview` endpoint.** `GET /admin/dashboard` already returns daily `newUsers`; the
  web gets "today vs yesterday" from `GET /admin/dashboard?from=<yesterday>&to=<today>`. The two
  missing numbers go into the dashboard instead:
  - `foodEntries`: per day in `daily[]` and summed in `totals`. Counts non-deleted `food_entries`
    (`deleted_at IS NULL`) by `logged_on` (the user's own day; no instant to convert).
  - `premiumUsers`: one **current** count in `totals` (not per day; there is no history of tier).
- **No `aiScans`.** `ai_trial_usage` only counts the free trial, so Premium scans are not recorded.
- **Premium "effective today"** (dashboard count and the users table) uses the same rule as
  `di/security.py::_reconcile_premium`, read-only (never writes the reconciliation):
  `user.is_premium and (subscription is None or subscription.covers(today))`, `today` = Vietnam day.
  Put that rule in one place in `application/` and use it from both.
- **Streak shown** = `streak.current_streak` if `last_active_date` is today or yesterday (Vietnam
  day), else 0 (a missed day breaks it); no streak row → 0.
- **Search** reuses `application/dish_fit.py::fold` (case- and diacritic-insensitive). Paging reuses
  the `GET /dishes` offset cursor: decimal string, `pattern=r"^\d{1,9}$"`, opaque to the client.

## Endpoints

### `GET /admin/dashboard` (changed, additive)
`totals` gains `foodEntries: int` and `premiumUsers: int`; each `daily[]` item gains `foodEntries: int`.

### `GET /admin/users?q=&tier=free|premium&limit=&cursor=`
- `q` ≤100 chars, blank = none, matches `name` or `email` via `fold`. `tier` filters on the effective
  tier. `limit` 1..50, default 20.
- Order: `createdAt` desc, then `id` desc. Filter, then page.
- Response `{ users: [...], total: int, nextCursor: string|null }`, `total` = matches after filters.
- Row: `id (int), displayName (users.name, nullable), email, role (user|admin), tier (free|premium),
  streak (int), createdAt, isActive`.
- `# ponytail:` comment: every user + subscription + streak loaded and filtered in memory; move to
  SQL when the user count makes it slow (same ceiling as `/dishes`).

### `GET /admin/quizzes`
List of every quiz question, active or not: `{ id, question (quiz_questions.text), topic (the
topic's label), active }`. Order: topic label, then question text.

### `GET /admin/quests`
List of every quest definition, active or not: `{ id, title (title_vi), target, rewardCoins,
cadence, active }`. Order: cadence, then title.

## Layering
New use cases `ListAdminUsersUseCase`, `ListAdminQuizQuestionsUseCase`,
`ListAdminQuestDefinitionsUseCase` (+ providers in `di/use_cases.py`, re-exported). Read methods go on
existing ports where they fit (`AdminStatsRepositoryProtocol` for counts and user rows,
`QuizRepositoryProtocol` / `QuestRepositoryProtocol` for "all, including inactive"). No new
migration. Routes go in `admin_controller.py`.

## Tests
- Unit: the effective-premium rule (premium + covering sub, premium + lapsed sub, premium + no sub,
  free); the streak rule (today, yesterday, older, none); dashboard `foodEntries` bucketing and
  totals; users filter (`q` on name and on email with diacritics, `tier`) and paging (`total`,
  `nextCursor`, last page null).
- API: each new route 403 for a non-admin, 200 for admin with the expected shape; dashboard has the
  new fields; bad `limit`/`cursor` → 422.
