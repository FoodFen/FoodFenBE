"""SendChatMessageUseCase unit tests: fake repo + fake AI provider. No DB, no real LLM call."""

from __future__ import annotations

from uuid import uuid4

from src.application.dtos.chat import ChatStreamDone, ChatStreamError, ChatStreamToken
from src.application.use_cases.send_chat_message import SendChatMessageUseCase
from src.domain.entities.chat_message import ChatMessage
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


class FakeProvider:
    """Yields a scripted sequence of deltas, or raises mid-stream."""

    def __init__(self, deltas: list[str], *, fail_after: int | None = None) -> None:
        self._deltas = deltas
        self._fail_after = fail_after

    async def stream_reply(self, history, user_message):
        for i, delta in enumerate(self._deltas):
            if self._fail_after is not None and i == self._fail_after:
                raise RuntimeError("upstream generation error")
            yield delta


async def _collect(use_case, user_id, message):
    return [event async for event in use_case.execute(user_id, message)]


async def test_successful_reply_persists_both_turns_and_yields_done():
    repo = FakeChatMessageRepo()
    provider = FakeProvider(["Hel", "lo!"])
    uc = SendChatMessageUseCase(chat_messages=repo, provider=provider, history_limit=10)

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
    uc = SendChatMessageUseCase(chat_messages=repo, provider=provider, history_limit=10)

    events = await _collect(uc, user_id=1, message="hi")

    assert isinstance(events[-1], ChatStreamError)
    assert "upstream generation error" not in events[-1].message  # not leaked to the client
    # user message persisted; no assistant message for the failed generation
    assert len(repo.rows) == 1
    assert repo.rows[0].role == ChatRole.USER


async def test_empty_reply_is_reported_as_error_not_persisted():
    repo = FakeChatMessageRepo()
    provider = FakeProvider([])
    uc = SendChatMessageUseCase(chat_messages=repo, provider=provider, history_limit=10)

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
        async def stream_reply(self, history, user_message):
            seen_history.extend(m.content for m in history)
            yield "ok"

    uc = SendChatMessageUseCase(chat_messages=repo, provider=RecordingProvider(), history_limit=2)
    await _collect(uc, user_id=1, message="new")

    # only the 2 most recent prior messages, oldest-first
    assert seen_history == ["old-1", "old-2"]
