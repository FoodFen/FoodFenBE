# Chat User Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ground every `POST /chat/messages` turn in the user's own profile, goal, and recent meals so Fen can answer diet questions from real data.

**Architecture:** A pure stdlib function renders the user's data as text. `SendChatMessageUseCase._build_context` reads three existing repositories and joins sections (one today; future sources like a food catalog or a RAG retriever append more). The text reaches `GeminiChatProvider` through a new opaque `context: str` parameter and is appended to `system_instruction`.

**Tech Stack:** Python 3.11+, FastAPI, async SQLAlchemy 2.0, Pydantic v2, google-genai, pytest (asyncio_mode=auto), `uv`.

**Spec:** `docs/superpowers/specs/2026-10-05-chat-user-context-design.md`

## Global Constraints

- `src/application/` imports stdlib + `src.domain` + `src.application` only. No fastapi/sqlalchemy/pydantic/google.
- Ports are `typing.Protocol`, never `abc.ABC`.
- No migration, no new dependency, no new repository method. Use only `UserRepositoryProtocol.get_by_id`, `DailyGoalRepositoryProtocol.list_by_user`, `FoodEntryRepositoryProtocol.list_by_date_range`.
- Every repository call is scoped to the authenticated `user_id` from `CurrentUserDep`. Never read a user id from the request body.
- The context is never persisted. `chat_messages` stores only the user's text and the assistant's reply, exactly as today.
- Context goes **after** the system prompt in `system_instruction` (stable prefix first).
- Tests never call the real Gemini API.
- Run `uv run lint-imports` after touching imports; it must pass.
- Commit messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>` (or the model actually doing the work).

## Review Focus

1. **Another user's data leaking into the context.** Covered by the Task 3 API test `test_chat_context_excludes_other_users_meals`.
2. **A day with no entries rendered as 0 kcal** (the model would then say "you ate nothing"). Covered by the Task 1 test `test_day_without_entries_is_not_logged_not_zero`.
3. **A brand-new user with no profile, no goal, no meals.** Rendering must not crash and must say "not set" / "nothing logged". Covered by the Task 1 test `test_empty_user_renders_not_set_everywhere`.
4. **Goal history.** A future-dated goal must not apply today, and the latest past goal wins. Covered by the Task 1 test `test_goal_in_force_is_latest_effective_on_or_before_today`.
5. **Pydantic field named `date` shadowing the `date` type** in `SendChatMessageRequest`, which silently makes it `None`-typed. Import the type under another name. Covered by the Task 3 API test that sends `"date"` and asserts it reached the context.

---

## File map

| File | Change |
|---|---|
| `src/application/chat_context.py` | **Create.** `WINDOW_DAYS`, `render_user_context()` |
| `tests/unit/test_chat_context.py` | **Create.** Renderer tests |
| `src/application/ports/ai_chat_provider.py` | Add `context: str` to `stream_reply` |
| `src/infrastructure/ai/gemini_chat_provider.py` | Append context to `system_instruction` |
| `src/application/use_cases/send_chat_message.py` | New repos, `today` param, `_build_context` |
| `src/infrastructure/di/use_cases.py` | Wire 3 repo deps into `get_send_chat_message_use_case` |
| `tests/unit/test_send_chat_message.py` | Fakes for the new repos/signature, new tests |
| `tests/unit/test_gemini_providers.py` | Context in `system_instruction` tests |
| `tests/api/conftest.py` | `FakeAiChatProvider` records `context` |
| `src/adapters/schemas/chat_schemas.py` | Optional `date` field |
| `src/adapters/controllers/chat_controller.py` | Pass `body.date` |
| `src/infrastructure/config.py` | System prompt: data-usage rules |
| `tests/api/test_chat_endpoints.py` | Grounding + isolation API tests |
| `CLAUDE.md` | One bullet in "AI chat" |

---

### Task 1: `render_user_context` (pure renderer)

**Files:**
- Create: `src/application/chat_context.py`
- Test: `tests/unit/test_chat_context.py`

**Interfaces:**
- Consumes: domain entities `User`, `DailyGoal`, `FoodEntry`; enums `UnitSystem`, `Gender`, `MealType`, `InputMethod`, `ActivityLevel`, `DietType` (all in `src/domain/enums.py`).
- Produces:
  - `WINDOW_DAYS: int = 7`
  - `render_user_context(user: User | None, goals: list[DailyGoal], entries: list[FoodEntry], today: date) -> str`
  - Output section headers, exactly: `PROFILE`, `DAILY GOAL`, `MEALS TODAY (<today ISO>)`, `LAST 7 DAYS (daily totals; 'not logged' means unknown, not zero)`. Sections are joined by a blank line.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_chat_context.py`:

```python
"""render_user_context: pure text rendering of the user's own data for the chat model."""

from __future__ import annotations

from datetime import UTC, date, datetime

from src.application.chat_context import WINDOW_DAYS, render_user_context
from src.domain.entities.daily_goal import DailyGoal
from src.domain.entities.food_entry import FoodEntry
from src.domain.entities.user import User
from src.domain.enums import ActivityLevel, DietType, Gender, InputMethod, MealType

TODAY = date(2026, 10, 5)


def _user(**overrides) -> User:
    fields = dict(
        email="a@b.co",
        id=1,
        gender=Gender.FEMALE,
        birth_year=2006,
        height=160.0,
        weight_current=55.0,
        weight_goal=52.0,
        activity_level=ActivityLevel.MODERATE,
        diet_type=DietType.BALANCED,
    )
    fields.update(overrides)
    return User(**fields)


def _goal(effective: date, kcal: int) -> DailyGoal:
    return DailyGoal.create(1, kcal, 200.0, 100.0, 60.0, 2000, effective, client_id=f"g-{kcal}")


def _entry(name: str, day: date, kcal: int, meal: MealType = MealType.LUNCH, hour: int = 12) -> FoodEntry:
    return FoodEntry.create(
        1, name, InputMethod.MANUAL, kcal, 50.0, 30.0, 10.0, meal,
        client_id=f"{name}-{day}",
        logged_on=day,
        logged_at=datetime(day.year, day.month, day.day, hour, tzinfo=UTC),
    )


def test_full_profile_is_rendered():
    text = render_user_context(_user(), [], [], TODAY)

    assert "PROFILE" in text
    assert "- Age: 20" in text
    assert "- Gender: female" in text
    assert "- Height: 160" in text
    assert "- Current weight: 55" in text
    assert "- Goal weight: 52" in text
    assert "- Activity level: moderate" in text
    assert "- Diet type: balanced" in text
    assert "- Units: metric (cm, kg)" in text


def test_empty_user_renders_not_set_everywhere():
    bare = User(email="a@b.co", id=1)

    text = render_user_context(bare, [], [], TODAY)

    assert "PROFILE\n- not set" in text
    assert "DAILY GOAL\n- not set" in text
    assert f"MEALS TODAY ({TODAY.isoformat()})\n- nothing logged yet" in text
    assert text.count(": not logged") == WINDOW_DAYS


def test_missing_user_renders_profile_not_set():
    assert "PROFILE\n- not set" in render_user_context(None, [], [], TODAY)


def test_goal_in_force_is_latest_effective_on_or_before_today():
    goals = [
        _goal(date(2026, 9, 1), 1800),
        _goal(date(2026, 10, 1), 2000),
        _goal(date(2026, 10, 9), 2500),  # future: not in force yet
    ]

    text = render_user_context(_user(), goals, [], TODAY)

    assert "DAILY GOAL\n- 2000 kcal, carbs 200 g, protein 100 g, fat 60 g" in text
    assert "2500" not in text
    assert "1800" not in text


def test_meals_today_lists_only_todays_entries_in_time_order():
    entries = [
        _entry("Pho bo", TODAY, 450, MealType.BREAKFAST, hour=7),
        _entry("Com tam", TODAY, 700, MealType.LUNCH, hour=12),
        _entry("Banh mi", date(2026, 10, 4), 400),
    ]

    text = render_user_context(_user(), [], entries, TODAY)
    today_section = text.split(f"MEALS TODAY ({TODAY.isoformat()})\n")[1].split("\n\n")[0]

    assert today_section.splitlines() == [
        "- breakfast: Pho bo — 450 kcal, C 50 g, P 30 g, F 10 g",
        "- lunch: Com tam — 700 kcal, C 50 g, P 30 g, F 10 g",
    ]


def test_last_days_sums_per_day_oldest_first():
    entries = [
        _entry("A", TODAY, 450),
        _entry("B", TODAY, 700),
        _entry("C", date(2026, 9, 29), 300),  # today - 6: first line of the window
        _entry("D", date(2026, 9, 28), 999),  # outside the window
    ]

    text = render_user_context(_user(), [], entries, TODAY)
    window = text.split("LAST 7 DAYS (daily totals; 'not logged' means unknown, not zero)\n")[1].splitlines()

    assert len(window) == WINDOW_DAYS
    assert window[0] == "- 2026-09-29: 300 kcal, C 50 g, P 30 g, F 10 g"
    assert window[-1] == "- 2026-10-05: 1150 kcal, C 100 g, P 60 g, F 20 g"
    assert "999" not in text


def test_day_without_entries_is_not_logged_not_zero():
    text = render_user_context(_user(), [], [_entry("A", TODAY, 450)], TODAY)

    assert "- 2026-10-04: not logged" in text
    assert "- 2026-10-04: 0 kcal" not in text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/unit/test_chat_context.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.application.chat_context'`.

- [ ] **Step 3: Write the implementation**

Create `src/application/chat_context.py`:

```python
"""Render the user's own data as grounding text for the chat model. Standard library only.

One section of the chat context assembled by ``SendChatMessageUseCase._build_context``.
Pure: the caller reads the repositories, so this needs no fakes to test.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from src.domain.entities.daily_goal import DailyGoal
from src.domain.entities.food_entry import FoodEntry
from src.domain.entities.user import User
from src.domain.enums import UnitSystem

WINDOW_DAYS = 7


def render_user_context(
    user: User | None, goals: list[DailyGoal], entries: list[FoodEntry], today: date
) -> str:
    """``entries`` should cover ``today - (WINDOW_DAYS - 1) .. today``; anything outside is ignored."""
    return "\n\n".join(
        [_profile(user, today), _goal(goals, today), _meals_today(entries, today), _last_days(entries, today)]
    )


def _profile(user: User | None, today: date) -> str:
    if user is None:
        return "PROFILE\n- not set"
    fields = [
        ("Age", today.year - user.birth_year if user.birth_year else None),
        ("Gender", user.gender),
        ("Height", user.height),
        ("Current weight", user.weight_current),
        ("Goal weight", user.weight_goal),
        ("Target weekly change (kg)", user.weekly_rate_kg),
        ("Activity level", user.activity_level),
        ("Diet type", user.diet_type),
    ]
    lines = [f"- {label}: {value:g}" if isinstance(value, float) else f"- {label}: {value}"
             for label, value in fields if value is not None]
    if not lines:
        return "PROFILE\n- not set"
    units = "metric (cm, kg)" if user.unit_system == UnitSystem.METRIC else "imperial"
    return "\n".join(["PROFILE", *lines, f"- Units: {units}"])


def _goal(goals: list[DailyGoal], today: date) -> str:
    in_force = [g for g in goals if g.effective_date <= today]
    if not in_force:
        return "DAILY GOAL\n- not set"
    g = max(in_force, key=lambda g: g.effective_date)
    return (
        f"DAILY GOAL\n- {g.target_kcal} kcal, carbs {g.target_carbs_g:.0f} g, "
        f"protein {g.target_protein_g:.0f} g, fat {g.target_fat_g:.0f} g"
    )


def _macros(kcal: int, carbs: float, protein: float, fat: float) -> str:
    return f"{kcal} kcal, C {carbs:.0f} g, P {protein:.0f} g, F {fat:.0f} g"


def _meals_today(entries: list[FoodEntry], today: date) -> str:
    header = f"MEALS TODAY ({today.isoformat()})"
    meals = sorted((e for e in entries if e.logged_on == today), key=lambda e: e.logged_at)
    if not meals:
        return f"{header}\n- nothing logged yet"
    lines = [
        f"- {e.meal_type}: {e.name} — {_macros(e.total_kcal, e.carbs_g, e.protein_g, e.fat_g)}"
        for e in meals
    ]
    return "\n".join([header, *lines])


def _last_days(entries: list[FoodEntry], today: date) -> str:
    by_day: dict[date, list[FoodEntry]] = defaultdict(list)
    for e in entries:
        by_day[e.logged_on].append(e)
    lines = []
    for offset in range(WINDOW_DAYS - 1, -1, -1):
        day = today - timedelta(days=offset)
        day_entries = by_day.get(day)
        if not day_entries:
            lines.append(f"- {day.isoformat()}: not logged")
            continue
        totals = _macros(
            sum(e.total_kcal for e in day_entries),
            sum(e.carbs_g for e in day_entries),
            sum(e.protein_g for e in day_entries),
            sum(e.fat_g for e in day_entries),
        )
        lines.append(f"- {day.isoformat()}: {totals}")
    return "\n".join([f"LAST {WINDOW_DAYS} DAYS (daily totals; 'not logged' means unknown, not zero)", *lines])
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/test_chat_context.py -v`
Expected: 7 passed. If `- Height: 160` fails, check that the float branch uses `:g` (renders `160`, not `160.0`).

- [ ] **Step 5: Lint imports and commit**

```bash
uv run lint-imports
git add src/application/chat_context.py tests/unit/test_chat_context.py
git commit -m "feat(chat): render the user's profile, goal and recent meals as model context"
```

---

### Task 2: Thread `context` from the use case to Gemini

**Files:**
- Modify: `src/application/ports/ai_chat_provider.py`
- Modify: `src/infrastructure/ai/gemini_chat_provider.py`
- Modify: `src/application/use_cases/send_chat_message.py`
- Modify: `src/infrastructure/di/use_cases.py` (`get_send_chat_message_use_case`, ~line 184)
- Modify: `tests/api/conftest.py` (`FakeAiChatProvider`, ~line 108)
- Test: `tests/unit/test_send_chat_message.py`, `tests/unit/test_gemini_providers.py`

**Interfaces:**
- Consumes (Task 1): `WINDOW_DAYS`, `render_user_context(user, goals, entries, today) -> str` from `src.application.chat_context`.
- Produces:
  - `AiChatProviderProtocol.stream_reply(self, history: list[ChatMessage], user_message: str, context: str) -> AsyncIterator[str]`
  - `SendChatMessageUseCase(chat_messages, provider, users, daily_goals, food_entries, history_limit)` (all keyword-constructed)
  - `SendChatMessageUseCase.execute(self, user_id: int, message: str, today: date | None = None) -> AsyncIterator[ChatStreamEvent]`
  - `FakeAiChatProvider.last_context: str | None` (in `tests/api/conftest.py`)

- [ ] **Step 1: Update the unit test fakes and add failing tests in `tests/unit/test_send_chat_message.py`**

Replace the imports and the `FakeProvider` class / `_collect` helper at the top of the file, and add the new fakes and `_use_case` helper:

```python
"""SendChatMessageUseCase unit tests: fake repos + fake AI provider. No DB, no real LLM call."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from src.application.dtos.chat import ChatStreamDone, ChatStreamError, ChatStreamToken
from src.application.use_cases.send_chat_message import SendChatMessageUseCase
from src.domain.entities.chat_message import ChatMessage
from src.domain.entities.user import User
from src.domain.enums import ChatRole


class FakeChatMessageRepo:
    ...  # unchanged


class FakeUserRepo:
    def __init__(self, user: User | None = None) -> None:
        self.user = user

    async def get_by_id(self, user_id):
        return self.user


class FakeDailyGoalRepo:
    async def list_by_user(self, user_id):
        return []


class FakeFoodEntryRepo:
    def __init__(self) -> None:
        self.calls: list[tuple[int, date, date]] = []

    async def list_by_date_range(self, user_id, from_date, to_date):
        self.calls.append((user_id, from_date, to_date))
        return []


class FakeProvider:
    """Yields a scripted sequence of deltas, or raises mid-stream."""

    def __init__(self, deltas: list[str], *, fail_after: int | None = None) -> None:
        self._deltas = deltas
        self._fail_after = fail_after

    async def stream_reply(self, history, user_message, context):
        for i, delta in enumerate(self._deltas):
            if self._fail_after is not None and i == self._fail_after:
                raise RuntimeError("upstream generation error")
            yield delta


def _use_case(repo, provider, *, history_limit=10, users=None, food_entries=None):
    return SendChatMessageUseCase(
        chat_messages=repo,
        provider=provider,
        users=users or FakeUserRepo(User(email="a@b.co", id=1)),
        daily_goals=FakeDailyGoalRepo(),
        food_entries=food_entries or FakeFoodEntryRepo(),
        history_limit=history_limit,
    )


async def _collect(use_case, user_id, message, **kwargs):
    return [event async for event in use_case.execute(user_id, message, **kwargs)]
```

In the four existing tests, replace each `SendChatMessageUseCase(chat_messages=repo, provider=..., history_limit=N)` with `_use_case(repo, ..., history_limit=N)` (omit `history_limit` when it is 10). In `test_history_sent_to_provider_is_oldest_first_and_capped`, change `RecordingProvider.stream_reply(self, history, user_message)` to `stream_reply(self, history, user_message, context)`.

Append these new tests:

```python
async def test_provider_receives_the_rendered_user_context():
    seen: list[str] = []

    class RecordingProvider:
        async def stream_reply(self, history, user_message, context):
            seen.append(context)
            yield "ok"

    uc = _use_case(FakeChatMessageRepo(), RecordingProvider())
    await _collect(uc, user_id=1, message="am I eating ok?", today=date(2026, 10, 4))

    assert "PROFILE" in seen[0]
    assert "MEALS TODAY (2026-10-04)" in seen[0]


async def test_context_reads_the_callers_last_seven_days():
    food = FakeFoodEntryRepo()
    uc = _use_case(FakeChatMessageRepo(), FakeProvider(["ok"]), food_entries=food)

    await _collect(uc, user_id=42, message="hi", today=date(2026, 10, 4))

    assert food.calls == [(42, date(2026, 9, 28), date(2026, 10, 4))]


async def test_today_defaults_to_server_utc_date():
    food = FakeFoodEntryRepo()
    uc = _use_case(FakeChatMessageRepo(), FakeProvider(["ok"]), food_entries=food)

    await _collect(uc, user_id=1, message="hi")

    today = datetime.now(UTC).date()
    assert food.calls == [(1, today - timedelta(days=6), today)]


async def test_context_is_not_persisted():
    repo = FakeChatMessageRepo()
    uc = _use_case(repo, FakeProvider(["ok"]))

    await _collect(uc, user_id=1, message="hi")

    assert [m.content for m in repo.rows] == ["hi", "ok"]
```

- [ ] **Step 2: Add failing provider tests in `tests/unit/test_gemini_providers.py`**

In `test_chat_uses_low_thinking_and_logs_token_usage`, change `provider.stream_reply(history, "again")` to `provider.stream_reply(history, "again", "")`. Append:

```python
async def test_chat_appends_context_after_the_system_prompt():
    models = _FakeModels(chunks=[SimpleNamespace(text="ok", usage_metadata=_USAGE)])
    provider = GeminiChatProvider(api_key="", model="m", system_prompt="p", client=_client(models))

    _ = [d async for d in provider.stream_reply([], "hi", "PROFILE\n- Age: 20")]

    instruction = models.kwargs["config"].system_instruction
    assert instruction.startswith("p\n\nDATA ABOUT THIS USER")
    assert instruction.endswith("PROFILE\n- Age: 20")


async def test_chat_without_context_sends_the_bare_system_prompt():
    models = _FakeModels(chunks=[SimpleNamespace(text="ok", usage_metadata=_USAGE)])
    provider = GeminiChatProvider(api_key="", model="m", system_prompt="p", client=_client(models))

    _ = [d async for d in provider.stream_reply([], "hi", "")]

    assert models.kwargs["config"].system_instruction == "p"
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/unit/test_send_chat_message.py tests/unit/test_gemini_providers.py -v`
Expected: FAIL. `SendChatMessageUseCase.__init__() got an unexpected keyword argument 'users'` and `stream_reply() takes 3 positional arguments but 4 were given`.

- [ ] **Step 4: Change the port**

In `src/application/ports/ai_chat_provider.py`, append to the module docstring:

```
`context` is opaque grounding text (the user's own data today; catalog or retrieval
results later) for the provider to show the model alongside its system prompt. Empty
means none.
```

and change the method to:

```python
class AiChatProviderProtocol(Protocol):
    def stream_reply(
        self, history: list[ChatMessage], user_message: str, context: str
    ) -> AsyncIterator[str]: ...
```

- [ ] **Step 5: Change `GeminiChatProvider`**

In `src/infrastructure/ai/gemini_chat_provider.py`, add below `_GEMINI_ROLE`:

```python
_CONTEXT_HEADER = "DATA ABOUT THIS USER (from their FoodFen account — real, not hypothetical)"
```

Change the signature and `system_instruction`:

```python
    async def stream_reply(
        self, history: list[ChatMessage], user_message: str, context: str
    ) -> AsyncIterator[str]:
        ...
        # Context goes after the fixed prompt so the stable prefix stays identical across turns.
        system_instruction = (
            f"{self._system_prompt}\n\n{_CONTEXT_HEADER}\n{context}" if context else self._system_prompt
        )
        stream = await self._client.aio.models.generate_content_stream(
            model=self._model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                ...  # the rest unchanged
```

- [ ] **Step 6: Change `SendChatMessageUseCase`**

In `src/application/use_cases/send_chat_message.py`, add imports:

```python
from datetime import UTC, date, datetime, timedelta

from src.application.chat_context import WINDOW_DAYS, render_user_context
from src.application.ports.daily_goal_repository import DailyGoalRepositoryProtocol
from src.application.ports.food_entry_repository import FoodEntryRepositoryProtocol
from src.application.ports.user_repository import UserRepositoryProtocol
```

Replace the dataclass body:

```python
@dataclass
class SendChatMessageUseCase:
    chat_messages: ChatMessageRepositoryProtocol
    provider: AiChatProviderProtocol
    users: UserRepositoryProtocol
    daily_goals: DailyGoalRepositoryProtocol
    food_entries: FoodEntryRepositoryProtocol
    history_limit: int

    async def execute(
        self, user_id: int, message: str, today: date | None = None
    ) -> AsyncIterator[ChatStreamEvent]:
        # Fetch history before persisting the new message, or it would appear
        # twice: once in `history`, once as the separate `user_message` param.
        recent = await self.chat_messages.list_before(user_id, None, self.history_limit)
        history = list(reversed(recent))
        context = await self._build_context(user_id, today or datetime.now(UTC).date())

        await self.chat_messages.create(ChatMessage.create(user_id, ChatRole.USER, message))

        chunks: list[str] = []
        try:
            async for delta in self.provider.stream_reply(history, message, context):
                chunks.append(delta)
                yield ChatStreamToken(delta)
        except Exception:
            ...  # unchanged from here down

    async def _build_context(self, user_id: int, today: date) -> str:
        """One section per source. A new source (food catalog, RAG retriever) appends its own."""
        user = await self.users.get_by_id(user_id)
        goals = await self.daily_goals.list_by_user(user_id)
        entries = await self.food_entries.list_by_date_range(
            user_id, today - timedelta(days=WINDOW_DAYS - 1), today
        )
        sections = [render_user_context(user, goals, entries, today)]
        return "\n\n".join(sections)
```

Add one line to the module docstring: `Each turn is grounded in the user's own data via _build_context; it is rebuilt per turn and never persisted.`

- [ ] **Step 7: Wire DI**

In `src/infrastructure/di/use_cases.py`, make sure `UserRepositoryDep`, `DailyGoalRepositoryDep` and `FoodEntryRepositoryDep` are imported from `src.infrastructure.di.repositories` (add any that are missing to the existing import block), then:

```python
def get_send_chat_message_use_case(
    chat_messages: ChatMessageRepositoryDep,
    provider: AiChatProviderDep,
    users: UserRepositoryDep,
    daily_goals: DailyGoalRepositoryDep,
    food_entries: FoodEntryRepositoryDep,
) -> SendChatMessageUseCase:
    return SendChatMessageUseCase(
        chat_messages=chat_messages,
        provider=provider,
        users=users,
        daily_goals=daily_goals,
        food_entries=food_entries,
        history_limit=settings.chat_history_limit,
    )
```

- [ ] **Step 8: Update the API fake**

In `tests/api/conftest.py`:

```python
class FakeAiChatProvider:
    """Yields a scripted reply instead of calling a real LLM; records the context it was given."""

    def __init__(self) -> None:
        self.deltas = ["Hello", ", world!"]
        self.last_context: str | None = None

    async def stream_reply(self, history, user_message, context):
        self.last_context = context
        for delta in self.deltas:
            yield delta
```

- [ ] **Step 9: Run the full suite**

Run: `uv run pytest -q`
Expected: all pass, including the 4 new use-case tests and 2 new provider tests. Existing `tests/api/test_chat_endpoints.py` still passes unchanged.

- [ ] **Step 10: Lint imports and commit**

```bash
uv run lint-imports
git add src/application/ports/ai_chat_provider.py src/infrastructure/ai/gemini_chat_provider.py \
  src/application/use_cases/send_chat_message.py src/infrastructure/di/use_cases.py \
  tests/unit/test_send_chat_message.py tests/unit/test_gemini_providers.py tests/api/conftest.py
git commit -m "feat(chat): ground every turn in the user's own data via a provider context param"
```

---

### Task 3: Client-local `date`, system prompt rules, end-to-end tests, docs

**Files:**
- Modify: `src/adapters/schemas/chat_schemas.py` (`SendChatMessageRequest`, ~line 37)
- Modify: `src/adapters/controllers/chat_controller.py` (`send_message`)
- Modify: `src/infrastructure/config.py` (`DEFAULT_GEMINI_SYSTEM_PROMPT`)
- Modify: `CLAUDE.md` ("AI chat" section)
- Test: `tests/api/test_chat_endpoints.py`

**Interfaces:**
- Consumes (Task 2): `SendChatMessageUseCase.execute(user_id, message, today: date | None = None)`; `FakeAiChatProvider.last_context`; the `ai_chat_provider` fixture in `tests/api/conftest.py`.
- Produces: `SendChatMessageRequest.date: date | None` (wire field `date`, `YYYY-MM-DD`, optional).

- [ ] **Step 1: Write the failing API tests**

Append to `tests/api/test_chat_endpoints.py`:

```python
_MEAL = {
    "name": "Pho bo",
    "inputMethod": "manual",
    "totalKcal": 450,
    "carbsG": 60.0,
    "proteinG": 25.0,
    "fatG": 12.0,
    "mealType": "breakfast",
    "clientId": "meal_1",
    "loggedOn": "2026-10-04",
}


async def test_chat_context_includes_the_users_own_meals_for_the_client_date(
    client, signed_up, ai_chat_provider
):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    assert (await client.post("/food-entries", json=_MEAL, headers=headers)).status_code in (200, 201)

    resp = await client.post(
        "/chat/messages", json={"message": "am I eating ok?", "date": "2026-10-04"}, headers=headers
    )

    assert resp.status_code == 200
    assert "MEALS TODAY (2026-10-04)" in ai_chat_provider.last_context
    assert "Pho bo" in ai_chat_provider.last_context


async def test_chat_context_excludes_other_users_meals(client, signed_up, ai_chat_provider):
    owner = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    assert (await client.post("/food-entries", json=_MEAL, headers=owner)).status_code in (200, 201)

    other = await client.post(
        "/auth/sign-up", json={"email": "other@example.com", "password": "another-pass-123"}
    )
    assert other.status_code == 200
    other_headers = {"Authorization": f"Bearer {other.json()['accessToken']}"}

    resp = await client.post(
        "/chat/messages", json={"message": "hi", "date": "2026-10-04"}, headers=other_headers
    )

    assert resp.status_code == 200
    assert "Pho bo" not in ai_chat_provider.last_context


async def test_chat_rejects_a_malformed_date(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    resp = await client.post("/chat/messages", json={"message": "hi", "date": "yesterday"}, headers=headers)

    assert resp.status_code == 422
```

Check the sign-up body against `_CREDENTIALS` in `tests/api/conftest.py` (field names and password policy) and adjust the second user's JSON to match its shape if it differs.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/api/test_chat_endpoints.py -v`
Expected: the first test fails (`MEALS TODAY (2026-10-04)` missing, because the server used its own UTC day) and the malformed-date test fails (200 instead of 422, because the field is ignored). The isolation test may already pass. That is fine: it pins behaviour.

- [ ] **Step 3: Add the request field**

In `src/adapters/schemas/chat_schemas.py`, change the datetime import and the request model:

```python
# `date` is also the field name below; aliasing the type keeps Pydantic from
# resolving the annotation to the field's own default (None).
from datetime import date as LocalDate
from datetime import datetime
```

```python
class SendChatMessageRequest(CamelModel):
    message: str = Field(max_length=2000)
    # The client's local day (same convention as loggedOn / GET /quests?date=).
    # Omitted → the server's UTC day.
    date: LocalDate | None = None
```

- [ ] **Step 4: Pass it through the controller**

In `src/adapters/controllers/chat_controller.py`, `send_message`:

```python
        async for event in use_case.execute(current_user.id, body.message, body.date):
```

- [ ] **Step 5: Run the API tests to verify they pass**

Run: `uv run pytest tests/api/test_chat_endpoints.py -v`
Expected: all pass.

- [ ] **Step 6: Update the system prompt**

In `src/infrastructure/config.py`, `DEFAULT_GEMINI_SYSTEM_PROMPT`:

1. Insert this block immediately before the line `WHAT YOU DON'T DO`:

```
USING THE USER'S DATA
- When a "DATA ABOUT THIS USER" section follows, ground your advice in it: compare what
  they ate with their daily goal and point out patterns across the last 7 days.
- Never invent numbers that aren't in that data. If something is missing, say so and
  suggest logging it in the app.
- "not logged" means unknown, not that they ate nothing.

```

2. Replace the line
`- Don't assume a goal (weight loss, bulking, etc.) — ask, or stay neutral until told.`
with
`- Don't assume a goal (weight loss, bulking, etc.) — use the one in the user's data if present; otherwise ask, or stay neutral until told.`

- [ ] **Step 7: Document in CLAUDE.md**

In the `## AI chat` section of `CLAUDE.md`, add this bullet after the "Provider port" bullet:

```markdown
- **User context** (spec `docs/superpowers/specs/2026-10-05-chat-user-context-design.md`): every
  turn, `SendChatMessageUseCase._build_context` renders profile, goal in force, today's meals and
  7-day totals (`application/chat_context.py`, stdlib-only) and passes it as `stream_reply(...,
  context)`; Gemini appends it after the system prompt. Rebuilt per turn, never persisted.
  `POST /chat/messages` takes an optional `date` (client-local day). A new source (food catalog,
  RAG retriever) adds one section in `_build_context`; the provider doesn't change.
```

- [ ] **Step 8: Full verification**

Run: `uv run pytest -q && uv run lint-imports`
Expected: all tests pass, all import contracts kept.

- [ ] **Step 9: Commit**

```bash
git add src/adapters/schemas/chat_schemas.py src/adapters/controllers/chat_controller.py \
  src/infrastructure/config.py tests/api/test_chat_endpoints.py CLAUDE.md
git commit -m "feat(chat): accept the client's local date and tell Fen how to use the user's data"
```
