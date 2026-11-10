from __future__ import annotations

import importlib.metadata
import uuid
from collections.abc import AsyncIterator
from decimal import Decimal

from .config import TESTNET_HOST, Settings
from .models import AssetBalance, BookSnapshot, Fill, OrderEvent, OrderSnapshot, Quote, Side
from .rules import PairRules

class PolyesterAdapter:
    """Thin SDK boundary. All mutations are Testnet-scoped and intentionally explicit."""
    def __init__(self, settings: Settings):
        if settings.environment != "testnet": raise ValueError("PolyesterAdapter only supports Testnet")
        from polyester import AsyncPolyester, POLYESTER_TESTNET_ENVIRONMENT
        self._client = AsyncPolyester(environment=POLYESTER_TESTNET_ENVIRONMENT, api_key_id=settings.api_key_id, api_private_key=settings.api_private_key, default_sub_account_id=settings.subaccount_id)
        self._symbol = settings.symbol
        self._symbol_id: int | None = None

    @staticmethod
    def sdk_version() -> str:
        return importlib.metadata.version("polyester-sdk")

    async def __aenter__(self):
        await self._client.__aenter__(); return self
    async def __aexit__(self, *args): await self._client.__aexit__(*args)

    async def load_rules(self, symbol: str) -> PairRules:
        await self._client.wait_for_catalogs()
        config = await self._client.market_data.get_spot_config()
        rules = PairRules.from_raw(next(p for p in config.raw["pairs"] if p["symbol"] == symbol))
        self._symbol_id = rules.symbol_id
        return rules

    async def best_bid_ask(self, symbol: str) -> tuple[Decimal, Decimal]:
        book = await self._client.orderbook.get(symbol=symbol, depth=1)
        if not book.available or not book.bids or not book.asks or not book.bids[0].price or not book.asks[0].price:
            raise RuntimeError(f"order book unavailable for {symbol}")
        return book.bids[0].price.as_decimal(), book.asks[0].price.as_decimal()

    async def open_orders(self, symbol: str) -> list[OrderSnapshot]:
        result = await self._client.orders.list_open()
        return [self._order(o) for o in result.orders if o.symbol_id == self._symbol_id]

    async def balances(self) -> list[AssetBalance]:
        from polyester import format_ledger_u128
        result = await self._client.balances.list()
        return [
            AssetBalance(
                asset_id=int(balance.asset_id),
                available=Decimal(format_ledger_u128(balance.available)),
                reserved=Decimal(format_ledger_u128(balance.reserved)),
                trading_revision=int(balance.trading_revision),
            )
            for balance in result.balances
        ]

    async def subscribe_orderbook(self, depth: int) -> AsyncIterator[BookSnapshot]:
        fresh = True

        def on_sequence_gap() -> None:
            nonlocal fresh
            fresh = False

        def on_snapshot_refresh() -> None:
            nonlocal fresh
            fresh = True

        subscription = await self._client.orderbook.create_subscription(
            symbol=self._symbol,
            symbol_id=self._symbol_id,
            depth=depth,
            on_sequence_gap=on_sequence_gap,
            on_snapshot_refresh=on_snapshot_refresh,
        )
        async with subscription:
            async for book in subscription:
                bid = book.bids[0].price.as_decimal() if book.bids and book.bids[0].price else None
                ask = book.asks[0].price.as_decimal() if book.asks and book.asks[0].price else None
                valid = bool(book.available and bid and ask and bid < ask)
                yield BookSnapshot(str(book.symbol), str(book.book_seq), bid, ask, fresh and valid)

    async def subscribe_order_events(self) -> AsyncIterator[OrderEvent]:
        subscription = await self._client.orders.subscribe()
        async with subscription:
            async for event in subscription:
                if getattr(event, "type", "") != "unit":
                    continue
                for raw in event.events:
                    if not hasattr(raw, "order_id") or not hasattr(raw, "kind"):
                        continue
                    yield self._event(raw)

    async def place(self, quote: Quote) -> OrderSnapshot:
        result = await self._client.orders.create(symbol=self._symbol, side=quote.side.value, order_type="limit", tif="gtc", qty=str(quote.qty), price=str(quote.price), post_only=True, client_order_id=quote.client_order_id)
        return OrderSnapshot(str(result.order_id), quote.client_order_id, self._symbol, quote.side, quote.price, quote.qty, status=str(result.status))

    async def cancel(self, order: OrderSnapshot) -> None:
        from polyester.models.order_key import ClientOrderId
        await self._client.orders.cancel(key=ClientOrderId(order.client_order_id), symbol=order.symbol)

    async def cancel_all(self, symbol: str) -> None:
        await self._client.orders.cancel_all(symbol=symbol, request_id=f"cancel-{uuid.uuid4().hex}")

    async def arm_dead_man(self, timeout_seconds: int) -> None:
        await self._client.orders.cancel_all_after(timeout_sec=timeout_seconds, request_id=f"dms-{uuid.uuid4().hex}")

    async def disarm_dead_man(self) -> None:
        await self._client.orders.cancel_all_after(timeout_sec=0, request_id=f"dms-{uuid.uuid4().hex}")

    async def events(self, symbol: str) -> AsyncIterator[OrderSnapshot]:
        subscription = await self._client.orders.subscribe()
        async with subscription:
            async for event in subscription:
                event_type = getattr(event, "type", "")
                if event_type == "snapshot":
                    orders = event.orders
                elif event_type == "unit":
                    orders = event.orders
                else:
                    continue
                for order in orders:
                    if order.symbol_id == self._symbol_id:
                        yield self._order(order)

    @staticmethod
    def _order(o) -> OrderSnapshot:
        if o.price is None or o.orig_qty is None:
            raise ValueError("SDK order is missing price or original quantity")
        return OrderSnapshot(str(o.order_id), str(o.client_order_id), self._symbol, Side(str(o.side).lower()), o.price.as_decimal(), o.orig_qty.as_decimal(), o.cum_qty.as_decimal() if o.cum_qty else Decimal("0"), str(o.status).lower(), int(getattr(o, "version", 0)))

    @staticmethod
    def _event(raw) -> OrderEvent:
        fill = None
        if getattr(raw, "fill", None) is not None:
            if raw.fill.price is None:
                raise ValueError("private fill is missing price")
            fill = Fill(
                order_id=str(raw.order_id),
                qty=raw.fill.qty.as_decimal(),
                price=raw.fill.price.as_decimal(),
                side=Side.BUY,
                event_id=f"{raw.fill.match_id}:{raw.fill.ordinal}",
            )
        return OrderEvent(
            order_id=str(raw.order_id),
            version=int(raw.version),
            kind=str(raw.kind).lower(),
            fill=fill,
            cancel_reason=getattr(raw, "cancel_reason", None),
            replacement_order_id=getattr(raw, "replacement_order_id", None) or None,
        )
