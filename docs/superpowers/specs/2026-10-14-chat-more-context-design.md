# Chat context: water, activity, weight, streak — design

Date: 2026-10-14 · Status: approved for implementation · Extends
`2026-10-05-chat-user-context-design.md` (whose "Out of scope" listed exactly these sources).

## Goal

Fen (`POST /chat/messages`) already sees the profile, the goal in force, today's meals and 7-day food
totals. Add the user's own **water**, **activity / exercise**, **weight** and **streak** data so answers
like "hôm nay tôi uống đủ nước chưa?", "tuần này tôi tập thế nào?", "tôi có đang giảm cân không?" are
grounded. For every user (chat is not Premium-gated today; a gate, if wanted later, is one check in
`_build_context`, not part of this slice).

## Decisions

- **One new pure renderer**, `render_activity_context(goals, water, activities, weights, streak, today) -> str`
  in `src/application/chat_context.py` (stdlib only, like `render_user_context`). It returns four sections
  joined by a blank line. `render_user_context` is unchanged.
- `SendChatMessageUseCase._build_context` reads the new data and appends that section right after the
  user context (before `DISHES`). Windows, all inclusive and keyed on the client day `today`:
  - water logs and activity logs: `today - (WINDOW_DAYS - 1) .. today` (the existing 7-day window);
  - weight logs: `today - (WEIGHT_WINDOW_DAYS - 1) .. today`, `WEIGHT_WINDOW_DAYS = 30`;
  - streak: the user's single row.
- **Streak read**: add `get_by_user(user_id) -> Streak | None` to `StreakRepositoryProtocol` and
  `SQLAlchemyStreakRepository`. Show it with `account_status.shown_streak(streak, today)` (a streak whose
  last active day is before yesterday is broken → 0), plus `longest_streak`.
- New use-case dependencies (`water_logs`, `activity_logs`, `weight_logs`, `streaks`) are wired in
  `src/infrastructure/di/use_cases.py` like the existing ones. No new tables, no migration, no new endpoint,
  no wire change.

## Section formats (exact headers; bounded size)

```
WATER
- Today (2026-10-14): 1250 ml of 2000 ml goal          # goal = target_water_ml of the goal in force; "no goal" when none
- Last 7 days: 2026-10-08: 1800 ml, 2026-10-09: not logged, …, 2026-10-14: 1250 ml (so far)

ACTIVITY (kcal burned)
- Today: 320 kcal — Chạy bộ 250 kcal, Steps 70 kcal    # at most MAX_ACTIVITIES_LISTED = 10 named items, names cut at MAX_NAME_CHARS, then "… and N more"
- Last 7 days: one entry per day, same 'not logged' / '(so far)' convention as food

WEIGHT (kg)
- Latest: 68.4 on 2026-10-12
- Change over the last 30 days: -1.2 kg (70.0 on 2026-09-16 → 68.4)   # first vs latest log in the window; omitted with a single log
- or: "- no weigh-ins in the last 30 days"

STREAK
- Current: 5 days (longest 12)        # "- none yet" when no row / current 0 and longest 0
```

Activity names: `activity_type` as stored (free text from the app). Weight is stored in kg, always shown in
kg. Numbers: water and kcal as integers, weight with one decimal (`:.1f`). "not logged" means unknown,
not zero, same wording as the food section header.

## Tests (TDD)

- Unit (`tests/unit/test_chat_context.py` or a sibling): each section, empty states, the goal-in-force pick
  for water, the activity cap and "… and N more", weight change sign/omission with one log, broken streak
  shows 0, days outside the window ignored.
- Unit for the use case (existing fakes pattern) or API (`tests/api`, `FakeAiChatProvider` records the
  context): logging water / an activity / a weight / a streak, then sending a chat message, puts each value
  in the recorded context.
- Repository: `get_by_user` returns the row or `None`.
- Before commit: `make test`, `uv run lint-imports`.

## Docs

- `CLAUDE.md` → "AI chat" → "User context" bullet: add water, activity, weight and streak.
- `2026-10-05-chat-user-context-design.md` "Out of scope": note that water/activity/weight/streak moved
  in via this spec.
