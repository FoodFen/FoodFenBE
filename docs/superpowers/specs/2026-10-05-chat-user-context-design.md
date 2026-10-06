# Chat grounded in the user's own data — design

Status: approved by the product owner (2026-10-05); implemented on branch feat/chat-user-context.

## Context

`POST /chat/messages` sends Gemini only the system prompt and the last `chat_history_limit` (10)
messages. Fen can't see the user's profile, goal, or meals, so it can't answer the questions users
actually ask: "are my meals OK?", "what should I eat each day?" — diet questions grounded in their
own data. A food catalog owned by the system may come later, and the AI will need to read from it.

## Decisions

- **Approach A: a SQL snapshot in every turn.** The use case reads the user's data from repositories
  that already exist, renders it as compact text (~300–500 tokens), and the provider appends it to
  `system_instruction`. No migration, no new dependency, no embeddings.
- **Not function calling (yet).** Diet questions are the majority of turns. A tool call costs a
  second model round that re-sends the whole prompt (~+2,500–3,500 input tokens) and delays the
  first streamed token. The snapshot costs ~+400 tokens on every turn. Break-even is ~10% of turns
  being data questions, and we expect far more than that. Revisit when `log_usage("chat", ...)`
  shows otherwise, or when users ask about arbitrary past ranges.
- **Not MongoDB, not a vector store.** The data is tabular, and `SUM` beats similarity search.
  When free text needs semantic search, use `pgvector` in the existing Postgres.

## Snapshot content

Built from one `today: date` (the client's local day):

| Section | Source | Content |
|---|---|---|
| Profile | `UserRepository.get_by_id` | age (`today.year - birth_year`), gender, height, current weight → goal weight, `weekly_rate_kg`, activity level, diet type, `unit_system` (cm/kg when metric) |
| Goal | `DailyGoalRepository.list_by_user` | the goal in force on `today`: last row with `effective_date <= today`. kcal, carbs, protein, fat |
| Today's meals | `FoodEntryRepository.list_by_date_range(today-6, today)` | each entry on `today`: meal type, name, kcal, C/P/F g |
| Last 7 days | same query | per-day totals of kcal, C, P, F for `today-6 .. today`. A day with no entries renders as "not logged", never as 0 kcal |

So that's 3 repository calls per turn, all filtered by the authenticated `user_id`. Fields left
unset during onboarding are omitted, and a section with nothing in it renders a one-line
"not set / nothing logged". The labels are in English, like the system prompt; Fen still replies
in the user's language.

Deliberately left out: water, activity, weight history, streaks. Neither question type needs them.
Each one is a single extra repository call plus a few lines in the renderer when a real question
does.

## Design

```
ChatController ──(message, date?)──▶ SendChatMessageUseCase
                                        ├─ history   = chat_messages.list_before(...)
                                        ├─ context   = _build_context(user_id, today)
                                        │                └─ "\n\n".join(sections)
                                        │                     └─ render_user_context(user, goals, entries, today)
                                        └─ provider.stream_reply(history, message, context)
                                                         └─ GeminiChatProvider: system_instruction =
                                                            system_prompt + "\n\n" + context
```

### Units

1. **`src/application/chat_context.py`** (new, stdlib only). This is a pure function
   `render_user_context(user: User | None, goals: list[DailyGoal], entries: list[FoodEntry], today: date) -> str`.
   It does no I/O, so it can be unit-tested without fakes. It also picks the goal in force and
   groups the entries by day.
2. **`AiChatProviderProtocol.stream_reply(history, user_message, context: str)`**. `context` is
   opaque grounding text. The provider doesn't know or care where it came from.
3. **`GeminiChatProvider`** builds `system_instruction` from `self._system_prompt` plus
   `"\n\nDATA ABOUT THIS USER (from their FoodFen account — real, not hypothetical)\n"` plus
   `context`. When `context` is empty, it uses the system prompt alone.
4. **`SendChatMessageUseCase`** gains `users`, `daily_goals`, `food_entries` (existing protocols)
   and a private `_build_context(user_id, today) -> str`.
   `execute(user_id, message, today: date | None = None)`, where `today` defaults to the Vietnam (UTC+7)
   day.
5. **`SendChatMessageRequest.date: date | None = None`** (optional, the client's local day, the same
   convention as `loggedOn` and `GET /quests?date=`). The controller passes it through. There's no
   ±1-day window check: a wrong date only shows users their own data for another day, which
   involves no coins and no other user's rows.
6. **DI**: `get_send_chat_message_use_case` gets the three repository deps that already exist.
7. **System prompt** (`DEFAULT_GEMINI_SYSTEM_PROMPT`, still overridable by `GEMINI_SYSTEM_PROMPT`):
   - Ground advice in the user data section when it is present.
   - Never invent numbers that aren't there. If data is missing, say so and suggest logging.
   - Treat "not logged" as unknown, not as "ate nothing".
   - Change "Don't assume a goal — ask" to "Use the goal from the user's data if present;
     otherwise ask."

### Extension points (where RAG and other sources plug in)

The seam is the `context: str` parameter plus `_build_context` assembling sections. A future source
adds one section, and nothing downstream changes:

| Future need | Change |
|---|---|
| System food catalog (`ILIKE` / `pg_trgm` search) | New `FoodCatalogRepositoryProtocol` injected into the use case. `_build_context` gets `message` as the query and appends a "Matching catalog foods" section |
| Semantic RAG (pgvector + embeddings over articles/recipes) | New `KnowledgeRetrieverProtocol` port with a pgvector adapter, then append a section as above. The provider is unchanged |
| Arbitrary date ranges (function calling) | Add one tool to `GeminiChatProvider` whose handler reuses `render_user_context` for the requested range. The snapshot stays as the default |
| Water / activity / weight trend | Another repository plus a few lines in `render_user_context` |

There's deliberately no `ContextSource` protocol or registry yet: with one source, it would be an
interface with one implementation. Extract it when the second source lands, if `_build_context`
grows past a handful of lines.

## Error handling

- A context read failure (DB error) propagates like the existing `list_before` failure does today.
  We don't silently degrade to an ungrounded answer, because that is where the AI starts inventing
  numbers.
- Missing data is not an error. It renders as "not set / nothing logged".

## Privacy and security

- Every repository call is scoped to the authenticated `user_id`. Never accept a user id from the
  request.
- The user's health data is now sent to Google Gemini. **The privacy policy needs a line about
  this** (FE/legal, outside this repo).
- The context is never persisted in `chat_messages`. It's rebuilt on each turn, so a meal the user
  just edited is reflected on the next message.

## Testing

- **Unit, `tests/unit/test_chat_context.py`**: `render_user_context` with full data; with an empty
  profile, no goal and no entries; goal selection across several `effective_date`s; a day without
  entries rendered as "not logged"; today's meals listed only for `today`.
- **Unit, `tests/unit/test_send_chat_message.py`**: update the construction for the new repositories.
  Assert that the provider receives the rendered context and that `today` defaults to the Vietnam (UTC+7) day.
- **API**: `FakeAiChatProvider.stream_reply` takes `context` and records it. One test logs a food
  entry, sends a chat message with `date`, and asserts the entry's name is in the recorded context.
- Never call the real Gemini API.

## Out of scope

Function calling, embeddings/pgvector, a food catalog, context caching (3 indexed queries take
milliseconds; Gemini takes seconds), and water/activity/weight/streak data.
