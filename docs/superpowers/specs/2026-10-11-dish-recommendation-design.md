# Dish recommendation (marketplace piece 4)

Status: approved in brainstorming 2026-10-11. Business rules go to `docs/marketplace.md` in the same change.

## Goal

Two layers over one ranking:

1. **Dish tab** (`GET /dishes`): order by what fits the rest of the user's **day** — kcal *and* macro mix —
   instead of kcal alone, never too strict (a tolerance, and always at least 3 suggestions), with reason codes
   the app renders as short phrases.
2. **Fen recommends real dishes**: a "Gợi ý cho tôi" button in the dish tab opens the existing chat with the
   user's wish ("đồ nước, không cay"); Fen picks from the ranked catalog and the reply carries **dish cards**.

Decisions:

- **No LLM in the list ranking.** The list must be instant, stable across cursor pages and testable; an LLM
  is bad at comparing numbers. The LLM is used where understanding dishes matters and order does not: Fen.
- **No per-meal split.** Users often log at the end of the day, so the target is the remaining day only.
- **No RAG.** The whole (diet-filtered) catalog fits the prompt; the ranking already does the numeric
  filtering embeddings can't. Revisit when public dishes exceed the 200 cap (see Fen).
- **Server parses Fen's dish references, the app only renders a field.** LLM output is untrusted: ids are
  validated against the turn's candidates, and the card data comes from the DB.
- **Vegetarian/vegan is a dish attribute declared by the owner** and checked by the admin like nutrition.

Out of scope: taste/history signals (needs `dish_id` on food entries), AI dish tagging, distance, ads.

## 1. `dietTag` on dishes

- `DishDiet(StrEnum)` in `domain/enums.py`: `none` | `vegetarian` | `vegan`. `Dish.diet_tag: DishDiet =
  DishDiet.NONE`; `dishes.diet_tag` via `enum_column()`, migration **0022** with server default `none`.
- Owner `POST /restaurants/mine/dishes`: optional `dietTag` (default `none`), so an un-updated web client still
  works. `PATCH`: optional; changing it on an approved dish returns it to `pending` like any other edit
  (`Dish.mark_edited`, unchanged rule). Owner/admin dish responses and public `Dish` include `dietTag`.
- Compatibility (`dish_fit.py`): user `diet_type == vegan` → only `vegan` dishes; `vegetarian` → `vegetarian`
  or `vegan`; any other or unset diet → every dish.

## 2. Ranking (`application/dish_fit.py`, stdlib only)

Inputs: public dishes, the user's `diet_type`, and `remaining` = goal in force on `date` minus that day's
logged kcal/protein/carbs/fat, each clamped at 0 (`None` when no goal is in force).

**Score** (lower = better) compares the *energy split* of the dish with the energy split of what is left,
so dish size and time of day don't matter. Energy: P×4, C×4, F×9; shares `P%`, `C%`, `F%` of their sum.

```
score = max(P%_left − P%_dish, 0) + max(C%_dish − C%_left, 0) + max(F%_dish − F%_left, 0)
```

When nothing is left of any macro (energy sum 0) or a dish has zero macro energy, its score is 0.
Ties: lower kcal first, then id.

**Order**:

| Tier | Condition | Suggested (`fits`) | Order |
|---|---|---|---|
| 1 | diet-ok, `kcal <= remaining_kcal` | yes | score |
| 2 | diet-ok, `kcal <= remaining_kcal * 1.1` (`KCAL_TOLERANCE = 1.1`) | yes | score |
| 3 | diet-ok, the rest | no, except top-up | kcal asc |
| 4 | not diet-ok | no | kcal asc |

- **Top-up**: if tiers 1+2 hold fewer than 3 dishes, the first tier-3 dishes (lowest kcal) are suggested until
  there are 3 (`MIN_SUGGESTED = 3`). Applies when `remaining_kcal` is 0 too. Tier 4 is never topped up.
- **No goal**: newest first as today, tier 4 last, nothing suggested, no reasons.
- `fits` now means **suggested** (tiers 1–2 + top-up). `remainingKcal` is unchanged.

**Reasons** (`reasons: list[str]`, only on suggested dishes, this order):

- `fills_protein`: `remaining_protein > 0`, `remaining_kcal > 0`, and the dish's protein per kcal ≥ the
  remaining protein per remaining kcal.
- `exceeds_kcal` / `exceeds_carbs` / `exceeds_fat`: the dish's value is greater than what is left of it.
  No `exceeds_protein` (extra protein is not a problem).

`rank_dishes(dishes, remaining, diet) -> list[RankedDish]` (`RankedDish(dish, fits, reasons)`), replacing the
current `(dish, fits)` pairs. Filters (`DishFilter.matches`) keep applying to the ranked list unchanged; the
`fits` filter now filters on *suggested*. `ListPublicDishesUseCase` gains the users repository for `diet_type`
and computes the four remaining macros (today it computes kcal only).

## 3. Fen dish cards

**Context.** `SendChatMessageUseCase._build_context` appends a `DISHES` section (rendered by a new pure
`application/chat_dishes.py`) when there is at least one diet-ok public dish: the same `rank_dishes` output,
tier 4 dropped, capped at `MAX_CHAT_DISHES = 200` (`ponytail:` comment: past the cap, pick candidates by
retrieval, e.g. pgvector, before ranking). One line per dish: id, name, restaurant name, kcal/P/C/F, price,
`suggested` + its `exceeds_*` reasons. The section header carries the instructions (so a
`GEMINI_SYSTEM_PROMPT` override can't drop them): recommend only dishes from this list, prefer suggested
ones, mention an `exceeds_*` warning in words, and write `[[dish:<id>]]` after each dish recommended.

**Stream.** The use case strips markers from the token deltas before yielding them: a small stateful
stripper holds back text from an unclosed `[[` until it closes or can no longer be a marker (`[[dish:` +
UUID + `]]`, so at most ~46 chars buffered), then flushes; leftovers flush at the end. Collected ids are kept
only if they are in this turn's candidates, de-duplicated in order, max `MAX_CARDS = 5`. The persisted
content is the stripped text.

**Persistence.** `ChatMessage.dish_ids: list[UUID] = []`; `chat_messages.dish_ids` JSON column (list of UUID
strings), migration **0023**, default `[]`. Reads (`done` and `GET /chat/messages`) hydrate ids into cards from
the current public dishes (`RestaurantRepository.list_public_dishes()`); an id that is no longer public is
dropped. Fen's history sent back to Gemini is the stripped text only.

**Wire.** `ChatMessage` gains `dishes: ChatDish[]` (always present, `[]` on ordinary messages), in the `done`
frame and in history. `ChatDish` = public `Dish` (incl. `dietTag`) + `restaurant {id, name, address,
latitude, longitude}` — `ListedDish` without `fits`/`reasons` (a stale card in old history must not claim to
fit today). Request body unchanged.

Failure: no marker → `dishes: []`; no diet-ok public dish → no section, Fen behaves as today; a bad or
unknown id → silently dropped.

## Contract changes for the clients

Mobile (`FoodFenFE/docs/backend-contracts/dishes.md`, `ai-chat.md`):

- `Dish` + `dietTag: "none" | "vegetarian" | "vegan"`.
- `ListedDish` + `reasons: string[]` (`fills_protein`, `exceeds_kcal`, `exceeds_carbs`, `exceeds_fat`; ignore
  unknown codes). `fits` = suggested by the server (may exceed the goal slightly — see reasons); the app keeps
  sending `fits=true` and must not re-sort.
- Chat `message` + `dishes: ChatDish[]`. Render cards under the assistant bubble; tap → the same restaurant
  detail screen as a dish-tab tap (`GET /restaurants/{restaurant.id}`). Text streaming is unchanged; markers
  never reach the client.
- "Gợi ý cho tôi" button: app-only — open chat and send the user's wish as a normal `POST /chat/messages`.

Web (FoodFenWeb): owner dish form gets `dietTag` (select, default `none`); admin dish review shows it.

## Tests

- Unit `dish_fit`: protein-short user ranks the high-protein dish first; keto user sinks a high-carb dish;
  tolerance tier; top-up to 3 with `exceeds_kcal`; `remaining_kcal == 0`; no goal; vegan/vegetarian filtering
  and tier 4; reasons.
- Unit `chat_dishes`: stripper with markers split across deltas, `[[` that is not a marker, unclosed marker at
  end; id validation, de-dup, cap; section rendering and omission.
- API: `GET /dishes` returns `reasons`/`dietTag` and the new order; owner create/patch `dietTag` (patch →
  pending); chat `done` and history carry hydrated `dishes` (scripted `FakeAiChatProvider` reply with markers),
  unpublished dish dropped.
- Migrations 0022/0023 checked against `Base.metadata` per CLAUDE.md.

## Slices

1. **Ranking + `dietTag`** — enums, `Dish`, ORM + 0022, owner/admin/public schemas, `dish_fit.py`,
   `ListPublicDishesUseCase`, DI. Tests above.
2. **Fen cards** (after 1) — `chat_dishes.py`, `ChatMessage.dish_ids` + 0023, `SendChatMessageUseCase`,
   history use case, chat schemas, DI. Tests above.
