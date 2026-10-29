"""ListCoinTransactionsUseCase + cursor codec with coin rows: fake repo, no DB."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.application.chat_cursor import decode_cursor, encode_cursor
from src.application.use_cases.list_coin_transactions import ListCoinTransactionsUseCase
from src.domain.entities.coin_transaction import CoinTransaction
from src.domain.enums import CoinReason


class FakeCoinRepo:
    def __init__(self, rows) -> None:
        self.rows = rows

    async def list_page(self, user_id, before, limit):
        rows = sorted((r for r in self.rows if r.user_id == user_id),
                      key=lambda r: (r.created_at, r.id), reverse=True)
        if before is not None:
            cut = decode_cursor(before)
            rows = [r for r in rows if (r.created_at, r.id) < cut]
        return rows[:limit]


def _tx(minutes_ago: int) -> CoinTransaction:
    tx = CoinTransaction.create(1, 5, CoinReason.ADJUSTMENT)
    tx.created_at = datetime.now(UTC) - timedelta(minutes=minutes_ago)
    return tx


def test_cursor_round_trips_a_coin_transaction():
    tx = _tx(0)
    assert decode_cursor(encode_cursor(tx)) == (tx.created_at, tx.id)


async def test_pages_newest_first_then_last_page_has_no_cursor():
    rows = [_tx(i) for i in range(3)]
    uc = ListCoinTransactionsUseCase(coins=FakeCoinRepo(rows))

    first = await uc.execute(1, None, 2)
    assert [t.id for t in first.transactions] == [rows[0].id, rows[1].id]
    assert first.next_cursor is not None

    last = await uc.execute(1, first.next_cursor, 2)
    assert [t.id for t in last.transactions] == [rows[2].id]
    assert last.next_cursor is None
