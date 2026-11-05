# Feature notes

Per-feature contracts and rules, moved out of `CLAUDE.md` so they are read only when a
change touches that feature. Specs in `docs/superpowers/specs/` have the full design.

## Auth

> New to JWT auth? `docs/authentication.md` is a full beginner walk-through of the flow.
> The endpoint names, field names, and response shapes below follow a front-end API
> contract (a real client, not our own design) — see docs/authentication.md §0.

- **Endpoints**: `POST /auth/sign-up|sign-in|refresh|sign-out|social`, `POST /auth/password-reset`,
  `GET /auth/me`. `sign-up`/`sign-in`/`refresh`/`password-reset`/`social` need no bearer token;
  `sign-out` and `me` do. `verify-email` / `resend-verification` / `reset-password` are **extras**,
  not required by the contract.
- **Social sign-in** (`POST /auth/social`, Google/Apple): see `docs/social-sign-in.md`. Verifies the
  provider's identity token with PyJWT's `PyJWKClient` (no new heavyweight dependency), resolves via
  `social_identities` (migration 0006, unique on `(provider, provider_user_id)`), **auto-links** to
  an existing password account with the same verified email. A provider with no
  `GOOGLE_OAUTH_CLIENT_IDS`/`APPLE_CLIENT_IDS` configured fails closed (500), never open.
  `pyjwt[crypto]` (not bare `pyjwt`) is required — RS256 needs the `cryptography` package.
- **Wire format is camelCase**, not snake_case: `src/adapters/schemas/base.py::CamelModel`
  (`alias_generator=to_camel`). Python stays snake_case; the alias does the translation both ways.
- **`User.id` is an integer**, not a UUID — the contract types it as a number. Only `users` has an
  int PK (`IntPrimaryKey` mixin, autoincrement); every other table keeps a UUID PK. `User.id` is
  `None` until the row is inserted (an autoincrement id doesn't exist before that), unlike every
  other entity, which mints its own UUID up front in `.create()`.
- **Sign-up returns a live session immediately** — `RegisterResultDTO{session: AuthSessionDTO,
  verification_token}`. Email verification does **not** gate login; it's sent (via
  `BackgroundTasks`, since a use case can't reach it) but purely informational. Sign-in and refresh
  also return a full `AuthSessionDTO` (tokens + the `user`), via the shared
  `use_cases/token_pair.py::issue_session` helper.
- **Refresh token**: JWT (`type: "refresh"`, carries a `jti`); every issued one gets a
  `refresh_tokens` row (`jti` unique, `expires_at`, `revoked_at`). Accepted only if a matching
  **unrevoked, unexpired** row exists, so sign-out and rotation take effect immediately. Rotated on
  every `/auth/refresh` — single-use.
- **Password reset**: `POST /auth/password-reset {email}` always 2xx, enumeration-safe (mirrors
  `resend-verification`'s pattern). `POST /auth/reset-password {token, newPassword}` (extra, not in
  the contract — there is no "confirm" endpoint documented client-side) verifies a fourth JWT type
  (`password_reset`, short TTL) and updates the hash. The token carries a `stamp` claim
  (`User.password_stamp`) so it works once, and a successful reset revokes all the user's refresh tokens.
- **Client IP** (rate limits): the Nth entry from the right of `X-Forwarded-For`, N =
  `TRUSTED_PROXY_HOPS` (default 1, Render). uvicorn runs with `--no-proxy-headers`; never trust
  leftmost entries, they are client-supplied. Set `TRUSTED_PROXY_HOPS=0` with no proxy in front.
- **Failure body shape**: `{"message"?: str, "error"?: str, "errors"?: {field: str}}` — **not**
  FastAPI's default `{"detail": ...}`. `src/adapters/exception_handlers.py` overrides both domain
  exceptions and Pydantic's `RequestValidationError` to this shape. `UserAlreadyExistsException`
  (duplicate email at sign-up) gets its own handler: `errors.email`, not just a message.
- **Protected routes**: depend on `CurrentUserDep` (or `dependencies=[Depends(get_current_user)]`
  when the handler doesn't need the user, e.g. `sign-out`). `get_current_user` lives in
  `src/infrastructure/di/security.py`.
- **Swagger UI**: `get_current_user` depends on `OAuth2PasswordBearer(tokenUrl="auth/token")`, not
  `HTTPBearer` — same header extraction at runtime, but it makes `/docs`' Authorize button render a
  username/password form instead of a bare token field. `POST /auth/token` (form-encoded, per the
  OAuth2 spec) exists only as that form's target; it's `include_in_schema=False` and calls the same
  `LoginUseCase` as the real, JSON `POST /auth/sign-in`. Requires `python-multipart`.
- **Never** log, return, or persist a plaintext password. Hashing is `PasswordHasherProtocol`
  (bcrypt, cost 12; `async`, runs bcrypt in `asyncio.to_thread` so it never blocks the loop) — the domain never sees bcrypt. No JWT is stored; only the refresh token's `jti` is.
- **Never** raise `HTTPException` for auth failures. Raise a `DomainException` subclass
  (`InvalidCredentialsException`/`InvalidTokenException` → 401); `src/adapters/exception_handlers.py`
  maps the type to a status. 401s also carry `WWW-Authenticate: Bearer`.
- Password policy (`>= 8` chars, `<= 72` bytes) is `User.validate_password_strength`, called by
  `RegisterUserUseCase` and `ResetPasswordUseCase`. `bcrypt` truncates past 72 bytes — the schema
  caps it too.
- App logs go through `configure_logging()` (`src/infrastructure/logging.py`) — a bare
  `getLogger("foodfenbe")` produces no output under uvicorn.
- `JWT_SECRET` has an insecure dev default; `main.lifespan` warns if it's still in use. Set a real one
  (`openssl rand -hex 32`) via env for anything shared.

## AI chat

- **Endpoints** (`src/adapters/controllers/chat_controller.py`, all `CurrentUserDep`-protected):
  `GET /chat/messages?before=&limit=` returns a page of history; `POST /chat/messages` streams the
  assistant's reply as SSE (`text/event-stream`), not JSON.
- **SSE contract**: `event: token` per delta (`{"delta": str}`), then either `event: done`
  (`{"message": ChatMessageResponse}`) or `event: error` (`{"message": str}`). A failure *before*
  streaming starts (auth, validation) is a normal 401/422; only a failure *after* the stream opens
  becomes an `event: error` frame, since headers are already committed at that point.
- **Persistence order** (`use_cases/send_chat_message.py`): the user's message is saved *before* the
  provider is called, so it's already in history if generation then fails. The assistant's reply is
  only persisted once fully generated — a failed or empty generation is discarded, not saved
  partially, and yields `event: error` instead.
- **Pagination cursor**: opaque `"{created_at.isoformat()}|{id}"`, encoded/decoded only by
  `src/application/chat_cursor.py` (stdlib-only, shared by the use case and the repository so they
  can't drift out of sync). The `id` tiebreaks same-timestamp rows at a page boundary.
- **Provider port**: `AiChatProviderProtocol` (`application/ports/ai_chat_provider.py`), implemented
  by `GeminiChatProvider` (`infrastructure/ai/gemini_chat_provider.py`) using `google-genai`.
  Gemini's role vocabulary (`user`/`model`) is translated from the domain `ChatRole` enum
  (`user`/`assistant`) only inside that class.
- **User context** (spec `docs/superpowers/specs/2026-10-05-chat-user-context-design.md`): every
  turn, `SendChatMessageUseCase._build_context` renders profile, goal in force, today's meals and
  7-day totals (`application/chat_context.py`, stdlib-only), then water, activity, weight (30 days) and streak
  (`render_activity_context`, spec `docs/superpowers/specs/2026-10-14-chat-more-context-design.md`), and passes it as `stream_reply(...,
  context)`; Gemini appends it after the system prompt. Rebuilt per turn, never persisted.
  `POST /chat/messages` takes an optional `date` (client-local day; omitted → the Vietnam, UTC+7, day). A new source (food catalog,
  RAG retriever) adds one section in `_build_context`; the provider doesn't change.
- **System prompt is config, not code**: `settings.gemini_system_prompt` (default in
  `DEFAULT_GEMINI_SYSTEM_PROMPT`, `infrastructure/config.py`), overridable via
  `GEMINI_SYSTEM_PROMPT` without touching `gemini_chat_provider.py`. `settings.chat_history_limit`
  caps how many prior messages are sent to the model per turn.
- **Dish cards** (spec `docs/superpowers/specs/2026-10-11-dish-recommendation-design.md`): `_build_context`
  also appends a `DISHES` section (`application/chat_dishes.py`: diet-ok public dishes ranked by `rank_dishes`,
  capped at 200, omitted when none; its header tells Fen to write `[[dish:<id>]]` after each recommendation).
  The use case strips those markers from every token delta, so they never reach the client or the stored text;
  ids not offered this turn are dropped, max 5. They persist in `chat_messages.dish_ids` and every
  `ChatMessage` (`done` frame, `GET /chat/messages`) carries `dishes` (public dish + restaurant, `[]` if none),
  hydrated from the currently public dishes, so an unpublished dish disappears from old history.
- Tests never call the real Gemini API — `tests/api/conftest.py::FakeAiChatProvider` overrides
  `get_ai_chat_provider` with a scripted reply.

## Coins & quests

Design + defaults: `docs/superpowers/specs/2026-09-30-coins-quests-design.md`.

- **Endpoints** (`coin_controller.py`, `CurrentUserDep`): `GET /quests?date=` (client's local day),
  `POST /coins/redeem {days}`, `GET /coins/bundles` (public; the `coin_bundles` table, seeded in migration 0019:
  10 days / 600 coins, 30 days / 1500 coins; redeem prices from the same rows). `GET /payments/plans` (public) lists the
  monthly/annual prices from settings. `GET /quests` also takes `language=vi|en` and returns each quest's
  `unit` (`count`|`percent`, derived in `Quest.unit`), `completionRatio`, `title` and `description` (the
  `title_*`/`description_*` columns of `quest_definitions`: static text, edit it with SQL together with any
  target/ratio change).
- **History** (spec `docs/superpowers/specs/2026-10-14-coin-history-design.md`): `GET /coins/transactions?before=&limit=`
  (limit 1..50, default 20) returns `{transactions: [{id, amount, reason, createdAt}], nextCursor}`, newest first, own rows only.
  Same opaque cursor as chat (`chat_cursor.encode_cursor` takes any row with `created_at`/`id`).
- **Redeem is idempotent** with an optional `clientId` (1..64 chars) in `POST /coins/redeem`, stored on the `SPEND` row
  (`coin_transactions.client_id`, unique with `user_id`, migration 0027). A repeat of a known `clientId` is a replay:
  200 with the current balance and subscription, nothing spent or granted, even if `days` differs.
- **Balance is `SUM(coin_transactions.amount)`**, never a stored field. Redeem takes the user row
  `FOR UPDATE` before checking it; insufficient coins → `InsufficientCoinsException` (409).
- **Quests are evaluated lazily** inside `GET /quests` from synced diary rows — the client never reports
  completion. Payout happens only for the request whose `QuestRepository.record()` flips `completed`
  (conditional UPDATE), so concurrent reads can't pay twice.
- **The catalog is the `quest_definitions` table** (seeded in migration 0012). What each `QuestType`
  *measures* lives in `SQLAlchemyQuestRepository.measure()`; a new type needs an evaluator there.
- **`PlanType.COIN_REDEEM` is not purchasable** — `CreateCheckoutRequest` only accepts monthly/annual.
- **Mascots** (spec `docs/superpowers/specs/2026-10-19-mascots-design.md`, `mascot_controller.py`, `CurrentUserDep`):
  `GET /mascots` (also open to guests: no bearer → `OptionalUserDep` is `None` → a new account's view, balance 0,
  `default` equipped; a bad/expired bearer is still 401 so token refresh works), `POST /mascots/{id}/purchase` (`mascot_purchase` ledger line, same lock as redeem; older buys
  were backfilled from `spend` in 0029), `PUT /mascots/equipped`.
  Catalogue is the `mascots` table (seeded in 0026; its PK is the slug the app's artwork keys on — the second
  deliberate non-UUID PK). `coin_cost == 0` = owned by everyone, no `user_mascots` row. `users.equipped_mascot_id`
  is not on the `User` entity; only the mascot repository touches it (`user_repository.update` skips it).
- **Mascot art and admin** (spec `docs/superpowers/specs/2026-10-30-mascot-admin-coin-reason-design.md`): art is
  server-side, one Cloudinary URL per `MascotState` in `mascot_images` (0030); `idle` is the fallback for any state,
  and every mascot item carries `images`. Admin manages the catalogue with `GET|POST /admin/mascots`,
  `PATCH|DELETE /admin/mascots/{id}` (`images` merges per state, `null` removes) and uploads via `POST /admin/images`
  (no rate limit). Rules live in `Mascot.create/update`: `default` stays active and free and is never deleted; an
  active mascot needs an `idle` image except the hand-drawn `HAND_DRAWN_IDS`; delete only when nobody owns or equips
  it (else 409 `mascot_in_use`, hide instead). New mascots default to inactive. `bodyColor` (`mascots.body_color`,
  0031) is the app's body circle: `#RRGGBB` or null = app theme green; PATCH absent keeps it, `null` resets it.

## Quiz

Spec: `docs/superpowers/specs/2026-10-03-quiz-design.md`. Wire contract (owned by the FE repo):
`FoodFenFE/docs/backend-contracts/quiz.md`.

- **Endpoints** (`quiz_controller.py`, `CurrentUserDep` except the public `GET /quizzes/topics`): `GET /quizzes/topics`, `GET /quizzes/daily?date=`,
  `POST /quizzes/practice {topic, date}`, `GET /quizzes/{id}`, `POST /quizzes/{id}/submit`.
- **The client never reports a score.** Correct answers and explanations live in `quiz_questions` and
  appear only in the submit response / a completed quiz — never in a question payload.
- **Payout** only happens for the request whose `QuizRepository.mark_submitted()` (conditional UPDATE on
  `submitted_at IS NULL`) succeeds; a loser gets 409 with `error: "quiz_already_submitted"`. Practice also
  takes the user row `FOR UPDATE` first, so the daily cap can't be overshot by concurrent submits.
- **Practice cap** is per the quiz's own `quiz_date` (client-local day, must be within ±1 day of server UTC),
  summed from `quizzes.coins_earned`. Past the cap a submit still returns 200 with `coinsEarned: 0` and no
  ledger row.
- **Rewards** are settings, not data: `QUIZ_DAILY_COINS_PER_CORRECT` (4), `QUIZ_PRACTICE_COINS_PER_CORRECT` (1),
  `QUIZ_PRACTICE_DAILY_CAP` (10).
- **Content** is Vietnamese, seeded by migration 0017; add or fix questions with SQL. Deactivate
  (`active = false`), never delete: issued quizzes reference questions by id.

## Restaurants & admin

Business rules (roles, moderation, what is public, open questions) live in `docs/marketplace.md`,
a **living document**: read it before touching restaurants, dishes, admin or recommendation, and
update it in the same change as any decision.

- **Admin** = `users.role = 'admin'`, bootstrapped at startup from `ADMIN_EMAIL`/`ADMIN_PASSWORD` (creates or promotes, never resets a password; `src/infrastructure/db/bootstrap.py`). `CurrentAdminDep` / router-level
  `Depends(get_current_admin)` (403); the role is read from the DB per request, never from the JWT.
- **Owner** is not a role: `restaurants.user_id` (unique). Owner routes are `/restaurants/mine/...`;
  ownership is implied, and another owner's dish is a 404 (`use_cases/restaurant_support.py`).
- Moderation transitions live only in `Restaurant`/`Dish` `.review()` / `.mark_edited()`; a use case
  never assigns `status`. Public = approved dish of an approved restaurant.
- **Diner endpoints** (`CurrentUserDep`, free): `GET /dishes?date=` (fits-first by remaining kcal, ordering in
  `application/dish_fit.py`) and `GET /restaurants/{id}` (404 unless approved). Spec:
  `docs/superpowers/specs/2026-10-09-dish-tab-design.md`. Reviews take an optional `expectedUpdatedAt`
  (stale → 409); `imageUrl` must be a Cloudinary upload on our cloud (`restaurant_schemas.py`).
- **Paid placement** (spec `docs/superpowers/specs/2026-10-12-paid-placement-design.md`): `GET /restaurants/mine/ads`,
  `POST /restaurants/mine/ads/checkout {packageId, provider}` (owner, approved restaurant only: 409
  `restaurant_not_approved`), admin `GET|POST /admin/ad-packages` + `PATCH /admin/ad-packages/{id}` (no delete). Payment history (read-only, `?cursor=&limit=` like `/admin/users`): owner `GET /restaurants/mine/payments` (own ad payments), admin `GET /admin/payments` (filters `q|status|planType|provider|from|to`, `total`).
  A package is N days for the whole restaurant: `PlanType.AD_PACKAGE` payment with a snapshotted `payments.ad_days`
  (set iff ad_package), and `apply_payment_result` extends `restaurants.featured_until` (from the current end if still
  featured) instead of renewing Premium. `POST /payments/checkout` stays monthly|annual. **Health gate**:
  `GET /dishes` returns `featured` (first page only) from `dish_fit.pick_featured`: the best-ranked *`fits`* dish within kcal
  left x `KCAL_TOLERANCE` per featured restaurant, max 3, from the filtered ranking (top-up dishes are never
  sponsored); no goal or nothing qualifies means `[]`. The main list is never
  changed. Each shown restaurant gets +1 in `ad_impressions` (Vietnam day, upsert). **Fen is neutral**: chat never sees
  sponsorship. Ad payments are `adRevenue`, not `premiumRevenue`. `priceVnd` is a JSON integer on the wire.
- Dashboard buckets rows into Vietnam days in `get_admin_dashboard.py` (Python, not SQL; see its
  `ponytail:` note).


## Food catalog

Design (owned by the FE repo): `FoodFenFE/docs/superpowers/specs/2026-11-02-catalog-grounded-ai-design.md`.
Phases 1-3 are done: the table, a read port, AI food analysis grounded in it, and the admin API (below).

- **Table** `foods` (`food_model.py`), entity `CatalogFood`, port `FoodCatalogRepositoryProtocol`
  (`list_active()` = non-archived by slug, `get_by_slug()` returns archived foods too; the caller reads `archived`).
- **`slug` is the public id**, unique and immutable: the Mobile bundle and its local
  `ingredient.catalog_food_id` reference foods by it. The UUID PK is `uuid5("foodfen:food:<slug>")`, the same in every env.
- **`verified` is derived** (`source_kind != legacy`), never stored. `source_ref` is null exactly for `legacy`
  (DB CHECK + entity invariant); recipe foods carry the literal `recipe`.
- **`GET /foods?updatedSince=<iso>`** (Phase 4, public, no auth): `{foods: Food[], serverTime}`. Foods with
  `updated_at >= updatedSince` (inclusive), archived included; no `updatedSince` = every food. `updatedSince` must carry
  an offset (`Z`/`+07:00`), else 422. `serverTime` is read **before** the query so the client's next cursor never skips a
  concurrent write. No paging, no `FoodCatalogCache` (it holds active foods only). Every admin write, archive and
  unarchive included, bumps `updated_at`: keep that true or the delta misses the change. No index on `updated_at`
  (~700 rows).
- **Per-100 g numbers**; `fiber_g` null means "no value", never 0.
- **Seed**: migration 0033 loads `alembic/data/foods.json`, a verbatim copy of the Mobile build
  (`FoodFenFE/src/data/catalog/foods.json`, 670 foods). Recipe breakdowns and source notes are not imported.
  From now on the BE table is the source of truth for new foods and edits; never hand-edit both sides.
  Archive, never delete: logged meals reference slugs.
- **AI grounding** (`POST /ai/food/analyze-image|analyze-text`): the system instruction starts with the catalog block,
  one `slug | name | aliases | default serving g` line per active food. It is built from `FoodCatalogCache`
  (process-wide, 10 min TTL, `invalidate()` on any catalog write) and must stay byte-identical between requests.
  The model returns `catalog_id` per row.
- **Explicit Gemini cache** (implicit caching never hit on gemini-3.8-flash): the catalog block + rules are a
  `caches.create` cached content (1 h TTL), created lazily per process, recreated 5 min before expiry or when the
  catalog text changes (old ones just expire). A request that finds the cache gone recreates it and retries once; if
  creation fails, the request goes uncached with the same prefix as `system_instruction`. The per-request language
  sentence lives in `contents`, never in the cached prefix. Check hits in the logs: `cache created` once, then
  `cached=` ≈ the prompt size on each call.
  `application/food_grounding.py` replaces a known slug's numbers with per-100 g × grams, rounded half-up like
  JS `Math.round` (kcal int, macros 1 decimal; null fiber stays null). An unknown or null slug keeps the
  model's estimate. Rows carry `catalogFoodId`, `catalogName`, `verified`, `sourceRef`, `per100g`
  (null/false when unmatched); `name` stays the model's.
- **Prompts are code** (`gemini_food_vision_provider.py`); the `GEMINI_FOOD_ANALYSIS_PROMPT` override is gone.
  `FOOD_ANALYSIS_GROUNDING=false` is the kill switch: old prompt, new fields null/false.

### Admin catalog (Phase 3)

All under `/admin` (admin-only, camelCase), in `admin_controller.py`; use cases in `use_cases/admin_foods.py`.

- **Routes**: `GET/POST /admin/foods`, `GET/PATCH /admin/foods/{slug}`, `POST .../archive|unarchive`,
  `GET .../changes`, `GET /admin/food-misses`, `POST /admin/food-misses/{id}/ignore|reopen`. Paging is the
  same opaque offset `cursor` / `limit` as `/admin/users`.
- **Validation lives in `CatalogFood.__post_init__`** (422 `InvalidCatalogFoodException`): name 1-120, `name_en`
  <=120 (blank -> null), aliases <=20 of 1-80 chars (trimmed, exact duplicates dropped), `kcal` 0-900, carbs /
  protein / fat 0-100 with a sum <=100, fiber null or 0-100, 1-10 servings (label 1-40, grams 1-5000, exactly one
  default). A test loads the whole seed through the entity, so a future seed cannot break the list.
  Each violation is a 422 `{message, code, field?}`: `code` is a stable snake_case id (the Web translates it to
  vi/en; `message` stays English for logs), `field` the camelCase wire field (`servings.1.grams`), absent when no
  single field is at fault. Codes: `name_required`, `name_too_long`, `name_en_too_long`, `too_many_aliases`,
  `alias_too_long`, `kcal_out_of_range`, `macro_out_of_range` (field `carbsG`/`proteinG`/`fatG`),
  `macros_sum_over_100`, `fiber_out_of_range`, `servings_count_out_of_range`, `serving_label_out_of_range`,
  `serving_grams_out_of_range`, `servings_need_one_default`, plus internal `slug_invalid`, `source_ref_mismatch`.
  A new rule gets a new code in the entity and a row in `_RULE_CODES` (`tests/api/test_admin_food_endpoints.py`).
- **Names**: two foods never share a folded name (`fold()`, archived included): 409 `food_name_taken` on create /
  rename; unarchive 409s while another active food has the name. The slug is built from the folded name on create
  (`-2`, `-3` on a clash) and never changes. `name_en` is the English name (migration 0034 backfilled 654 of 670
  from the first new-word ASCII alias; the alias also stays in `aliases`). It is not in the prompt's catalog block.
- **Source rules**: create -> `team` / `"team"` (verified). A PATCH that changes any of kcal / carbs / protein /
  fat / fiber -> `team` / `"team"`, legacy foods included; any other edit keeps the source, so renaming a legacy
  food leaves it unverified. `fiberG: null` clears fiber (not tracked), `0` is a value; `nameEn: null` clears it;
  other `null`s in a PATCH are ignored. A PATCH that changes nothing writes nothing (no change row).
- **`food_changes`** (append-only): one row per create / update / archive / unarchive (archive and unarchive only
  when the state flips), written in the request's transaction. `before` / `after` are full snapshots of the editable
  fields + source + `archived` (before null for create); the Web diffs them. Admin FK is `SET NULL`.
- **`food_misses`**: one row per `miss_key` = `fold` of the name minus a `(x3)` suffix and trailing punctuation
  (`application/food_names.py`, shared by recording and matching). Written by both analyze use cases on the grounded
  path only, for rows with no catalog id, via `food_grounding.record_misses`: one multi-row upsert per analysis
  (`count + 1`, `last_seen_at`; never touches `name`, `language`, `status`) inside a SAVEPOINT, and a failure is logged
  and swallowed. Nothing about the user or the image is stored. An `ignored` / `resolved` key keeps its status.
  Creating a food, or saving a new name / English name / alias, resolves every open miss whose key is one of the food's
  keys; `missId` on create also resolves that miss (unknown or not open: ignored). `existingFood` on the list is the
  active food whose keys include the miss key, computed per read.
- **Cache**: create / patch / archive / unarchive carry `invalidate_food_catalog_after_write`, a yield dependency
  in the default request scope: its teardown runs after the response, i.e. after `SessionDep`'s function-scope
  commit, and not when the endpoint raised (tested: commit, then invalidate). The next analysis rebuilds the
  catalog block; the explicit Gemini cache re-keys itself on the new text. One instance on prod: if it scales out,
  the others pick the change up within the 600 s TTL.
- **List/search** is in memory over `list_all()` (folded name / English name / aliases / slug, sorted by folded
  name). Move it to SQL if the catalog grows large.
