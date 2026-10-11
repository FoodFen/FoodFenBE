"""ListChatMessagesUseCase unit tests: fake repo. No DB."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from src.application.chat_cursor import decode_cursor
from src.application.use_cases.list_chat_messages import ListChatMessagesUseCase
from src.domain.entities.chat_message import ChatMessage
from src.domain.enums import ChatRole


class FakeRestaurantRepo:
    def __init__(self, pairs=()) -> None:
        self.pairs = list(pairs)
        self.calls = 0

    async def list_public_dishes(self):
        self.calls += 1
        return self.pairs


class FakeChatMessageRepo:
    def __init__(self) -> None:
        self.rows: list[ChatMessage] = []

    async def create(self, message: ChatMessage) -> ChatMessage:
        self.rows.append(message)
        return message

    async def list_before(self, user_id, before, limit):
        rows = [m for m in self.rows if m.user_id == user_id]
        rows.sort(key=lambda m: (m.created_at, m.id), reverse=True)
        if before is not None:
            cursor_created_at, cursor_id = decode_cursor(before)
            rows = [m for m in rows if (m.created_at, m.id) < (cursor_created_at, cursor_id)]
        return rows[:limit]


def _message(user_id: int, minutes_ago: int, content: str = "hi") -> ChatMessage:
    return ChatMessage(
        id=uuid4(),
        user_id=user_id,
        role=ChatRole.USER,
        content=content,
        created_at=datetime.now(UTC) - timedelta(minutes=minutes_ago),
    )


async def test_first_page_returns_newest_first_with_no_more_pages():
    repo = FakeChatMessageRepo()
    for i in range(3):
        await repo.create(_message(1, minutes_ago=i))
    uc = ListChatMessagesUseCase(chat_messages=repo, restaurants=FakeRestaurantRepo())

    page = await uc.execute(user_id=1, before=None, limit=10)

    assert [m.content for m in page.messages] == ["hi", "hi", "hi"]
    assert page.next_cursor is None


async def test_pagination_walks_full_history_without_gaps_or_dupes():
    repo = FakeChatMessageRepo()
    for i in range(5):
        await repo.create(_message(1, minutes_ago=i, content=f"msg-{i}"))
    uc = ListChatMessagesUseCase(chat_messages=repo, restaurants=FakeRestaurantRepo())

    first = await uc.execute(user_id=1, before=None, limit=2)
    assert [m.content for m in first.messages] == ["msg-0", "msg-1"]
    assert first.next_cursor is not None

    second = await uc.execute(user_id=1, before=first.next_cursor, limit=2)
    assert [m.content for m in second.messages] == ["msg-2", "msg-3"]
    assert second.next_cursor is not None

    third = await uc.execute(user_id=1, before=second.next_cursor, limit=2)
    assert [m.content for m in third.messages] == ["msg-4"]
    assert third.next_cursor is None


async def test_scoped_to_the_requesting_user_only():
    repo = FakeChatMessageRepo()
    await repo.create(_message(1, minutes_ago=0, content="mine"))
    await repo.create(_message(2, minutes_ago=0, content="theirs"))
    uc = ListChatMessagesUseCase(chat_messages=repo, restaurants=FakeRestaurantRepo())

    page = await uc.execute(user_id=1, before=None, limit=10)

    assert [m.content for m in page.messages] == ["mine"]


async def test_history_hydrates_cards_and_drops_dishes_no_longer_public():
    from decimal import Decimal

    from src.domain.entities.dish import Dish
    from src.domain.entities.restaurant import Restaurant

    r = Restaurant.create(
        user_id=9, name="Quán A", address="a", phone="1", opening_hours="x", latitude=1.0, longitude=2.0
    )
    live = Dish.create(
        restaurant_id=r.id, name="Phở", price=Decimal(1), serving_g=1, kcal=1, protein_g=1, carbs_g=1, fat_g=1
    )
    repo, restaurants = FakeChatMessageRepo(), FakeRestaurantRepo([(live, r)])
    msg = _message(1, 0, "reply")
    msg.dish_ids = [live.id, uuid4()]
    await repo.create(msg)
    await repo.create(_message(1, 1, "plain"))
    uc = ListChatMessagesUseCase(chat_messages=repo, restaurants=restaurants)

    page = await uc.execute(user_id=1, before=None, limit=10)

    assert [c.dish.id for c in page.messages[0].dishes] == [live.id]
    assert page.messages[1].dishes == []
    assert restaurants.calls == 1


async def test_history_without_cards_does_not_query_restaurants():
    repo, restaurants = FakeChatMessageRepo(), FakeRestaurantRepo()
    await repo.create(_message(1, 0))

    await ListChatMessagesUseCase(chat_messages=repo, restaurants=restaurants).execute(1, None, 10)

    assert restaurants.calls == 0
