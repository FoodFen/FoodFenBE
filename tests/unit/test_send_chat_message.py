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
    def __init__(self) -> None:
        self.rows: list[ChatMessage] = []

    async def create(self, message: ChatMessage) -> ChatMessage:
        self.rows.append(message)
        return message

    async def list_before(self, user_id, before, limit):
        rows = [m for m in self.rows if m.user_id == user_id]
        rows.sort(key=lambda m: (m.created_at, m.id), reverse=True)
        return rows[:limit]


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


async def test_successful_reply_persists_both_turns_and_yields_done():
    repo = FakeChatMessageRepo()
    provider = FakeProvider(["Hel", "lo!"])
    uc = _use_case(repo, provider)

    events = await _collect(uc, user_id=1, message="hi")

    assert events[0] == ChatStreamToken("Hel")
    assert events[1] == ChatStreamToken("lo!")
    assert isinstance(events[2], ChatStreamDone)
    assert events[2].message.content == "Hello!"
    assert events[2].message.role == ChatRole.ASSISTANT

    assert [m.role for m in repo.rows] == [ChatRole.USER, ChatRole.ASSISTANT]
    assert repo.rows[0].content == "hi"


async def test_failure_after_streaming_started_discards_partial_reply():
    repo = FakeChatMessageRepo()
    provider = FakeProvider(["Hel", "lo"], fail_after=1)
    uc = _use_case(repo, provider)

    events = await _collect(uc, user_id=1, message="hi")

    assert isinstance(events[-1], ChatStreamError)
    assert "upstream generation error" not in events[-1].message  # not leaked to the client
    # user message persisted; no assistant message for the failed generation
    assert len(repo.rows) == 1
    assert repo.rows[0].role == ChatRole.USER


async def test_empty_reply_is_reported_as_error_not_persisted():
    repo = FakeChatMessageRepo()
    provider = FakeProvider([])
    uc = _use_case(repo, provider)

    events = await _collect(uc, user_id=1, message="hi")

    assert isinstance(events[-1], ChatStreamError)
    assert len(repo.rows) == 1  # only the user's message


async def test_history_sent_to_provider_is_oldest_first_and_capped():
    repo = FakeChatMessageRepo()
    for i in range(3):
        await repo.create(
            ChatMessage(id=uuid4(), user_id=1, role=ChatRole.USER, content=f"old-{i}")
        )
    seen_history = []

    class RecordingProvider:
        async def stream_reply(self, history, user_message, context):
            seen_history.extend(m.content for m in history)
            yield "ok"

    uc = _use_case(repo, RecordingProvider(), history_limit=2)
    await _collect(uc, user_id=1, message="new")

    # only the 2 most recent prior messages, oldest-first
    assert seen_history == ["old-1", "old-2"]


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
