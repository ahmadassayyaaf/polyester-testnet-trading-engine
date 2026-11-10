from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from polyester_bot.models import Side
from polyester_bot.polyester_adapter import PolyesterAdapter


class Money:
    def __init__(self, value: str):
        self.value = value

    def as_decimal(self) -> Decimal:
        return Decimal(self.value)


class FakeBookSubscription:
    def __init__(self, callbacks):
        self.callbacks = callbacks

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def __aiter__(self):
        return self._events()

    async def _events(self):
        self.callbacks["on_sequence_gap"]()
        yield SimpleNamespace(
            symbol="BTC-USDT",
            book_seq="10",
            available=True,
            bids=[SimpleNamespace(price=Money("100"))],
            asks=[SimpleNamespace(price=Money("101"))],
        )
        self.callbacks["on_snapshot_refresh"]()
        yield SimpleNamespace(
            symbol="BTC-USDT",
            book_seq="11",
            available=True,
            bids=[SimpleNamespace(price=Money("100"))],
            asks=[SimpleNamespace(price=Money("101"))],
        )


class FakeOrderbook:
    async def create_subscription(self, **kwargs):
        return FakeBookSubscription(kwargs)


class FakeBalances:
    async def list(self):
        return SimpleNamespace(
            balances=[
                SimpleNamespace(asset_id=7, available="1250000000000000000", reserved="250000000000000000", trading_revision=3)
            ]
        )


@pytest.fixture
def adapter():
    value = object.__new__(PolyesterAdapter)
    value._symbol = "BTC-USDT"
    value._symbol_id = 11
    value._client = SimpleNamespace(orderbook=FakeOrderbook(), balances=FakeBalances())
    return value


@pytest.mark.asyncio
async def test_balances_map_ledger_values_to_decimal(adapter):
    balances = await adapter.balances()
    assert balances[0].asset_id == 7
    assert balances[0].available == Decimal("1.25")
    assert balances[0].reserved == Decimal("0.25")
    assert balances[0].trading_revision == 3


@pytest.mark.asyncio
async def test_managed_orderbook_is_stale_during_gap_until_refresh(adapter):
    books = [book async for book in adapter.subscribe_orderbook(20)]
    assert books[0].fresh is False
    assert books[1].fresh is True
    assert books[1].book_seq == "11"


def test_private_fill_event_maps_without_sdk_types():
    raw = SimpleNamespace(
        order_id="order-1",
        version=4,
        kind="FILLED",
        cancel_reason=None,
        replacement_order_id="",
        fill=SimpleNamespace(match_id="match-1", ordinal=2, qty=Money("0.01"), price=Money("100.5")),
    )
    event = PolyesterAdapter._event(raw)
    assert event.order_id == "order-1"
    assert event.version == 4
    assert event.kind == "filled"
    assert event.fill is not None
    assert event.fill.qty == Decimal("0.01")
    assert event.fill.price == Decimal("100.5")
    assert event.fill.event_id == "match-1:2"
    assert event.fill.side == Side.BUY
