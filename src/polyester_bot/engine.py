from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from datetime import datetime, timezone
from uuid import uuid4

from .config import Settings
from .exchange import Exchange
from .models import BookSnapshot, OrderEvent, OrderSnapshot
from .retry import retry_write
from .storage import Store
from .strategy import MarketMaker

log = logging.getLogger(__name__)


class TradingEngine:
    def __init__(self, settings: Settings, exchange: Exchange, store: Store, strategy: MarketMaker):
        self.settings, self.exchange, self.store, self.strategy = settings, exchange, store, strategy
        self.stop_event = asyncio.Event()
        self.rules = None
        self.live = False
        self._latest_book: BookSnapshot | None = None
        self._book_ready = asyncio.Event()
        self._known_orders: dict[str, OrderSnapshot] = {}

    async def run(self, *, once: bool = False) -> None:
        await self.store.open()
        self.rules = await self.exchange.load_rules(self.settings.symbol)
        self._configure_strategy()
        if not self.settings.enable_live_trading:
            log.warning("dry-run mode: no orders will be submitted")
            if once:
                await self.store.close()
                return
        self.live = self.settings.enable_live_trading
        tasks: list[asyncio.Task] = []
        if hasattr(self.exchange, "subscribe_orderbook"):
            tasks.append(asyncio.create_task(self._book_loop()))
        if self.live and hasattr(self.exchange, "subscribe_order_events"):
            tasks.append(asyncio.create_task(self._event_loop()))
        dms_task = asyncio.create_task(self._dead_man_loop()) if self.live else None
        try:
            if tasks and hasattr(self.exchange, "subscribe_orderbook"):
                with suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(self._book_ready.wait(), timeout=10.0)
            while not self.stop_event.is_set():
                await self.cycle()
                if once:
                    break
                try:
                    await asyncio.wait_for(self.stop_event.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    pass
        finally:
            if dms_task:
                dms_task.cancel()
                await asyncio.gather(dms_task, return_exceptions=True)
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            await self.shutdown()
            await self.store.close()

    def _configure_strategy(self) -> None:
        self.strategy.client_order_prefix = self.settings.client_order_prefix
        self.strategy.quote_notional_cap = self.settings.quote_notional_cap

    async def cycle(self) -> None:
        assert self.rules
        if self._latest_book is not None:
            if not self._latest_book.fresh or self._latest_book.best_bid is None or self._latest_book.best_ask is None:
                log.warning("quote cycle paused: managed orderbook is not fresh")
                return
            bid, ask = self._latest_book.best_bid, self._latest_book.best_ask
        else:
            bid, ask = await self.exchange.best_bid_ask(self.settings.symbol)

        if hasattr(self.exchange, "reconcile_owned_orders"):
            open_orders = await self.exchange.reconcile_owned_orders(self.settings.symbol, self.settings.client_order_prefix)
        else:
            open_orders = [
                order for order in await self.exchange.open_orders(self.settings.symbol)
                if order.client_order_id.startswith(self.settings.client_order_prefix)
            ]
        self._known_orders = {order.order_id: order for order in open_orders}
        balances = None
        if hasattr(self.exchange, "balances"):
            balance_list = await self.exchange.balances()
            balances = {balance.asset_id: balance for balance in balance_list}
        quotes = self.strategy.quotes(self.rules, bid, ask, open_orders, balances)
        if not self.live:
            return
        for quote in quotes:
            order = await retry_write(lambda q=quote: self.exchange.place(q), replayable=True)
            self._known_orders[order.order_id] = order
            await self.store.upsert_order(self._row(order))

    async def _book_loop(self) -> None:
        try:
            async for book in self.exchange.subscribe_orderbook(self.settings.book_depth):
                self._latest_book = book
                if book.fresh:
                    self._book_ready.set()
                else:
                    self._book_ready.clear()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("managed orderbook failed; quote production is paused")
            self._book_ready.clear()

    async def _event_loop(self) -> None:
        try:
            async for event in self.exchange.subscribe_order_events():
                await self._apply_event(event)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("private order stream failed; quote production is paused")
            self.stop_event.set()

    async def _apply_event(self, event: OrderEvent) -> None:
        order = self._known_orders.get(event.order_id)
        if event.fill is not None and order is not None:
            self.strategy.apply_fill(order, event.fill.qty)
        await self.store.record_event(
            event_id=f"{event.order_id}:{event.version}:{event.kind}",
            kind=event.kind,
            payload={
                "order_id": event.order_id,
                "version": event.version,
                "cancel_reason": event.cancel_reason,
                "replacement_order_id": event.replacement_order_id,
                "fill_event_id": event.fill.event_id if event.fill else None,
            },
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    async def _dead_man_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                await retry_write(lambda: self.exchange.arm_dead_man(self.settings.dms_timeout_seconds), replayable=True)
            except Exception:
                log.exception("dead-man refresh failed; stopping new quote production")
                self.stop_event.set()
                return
            try:
                await asyncio.wait_for(self.stop_event.wait(), timeout=self.settings.dms_refresh_seconds)
            except asyncio.TimeoutError:
                pass

    async def shutdown(self) -> None:
        if not self.live:
            return
        try:
            if hasattr(self.exchange, "reconcile_owned_orders"):
                owned = await self.exchange.reconcile_owned_orders(self.settings.symbol, self.settings.client_order_prefix)
            else:
                owned = [
                    order for order in await self.exchange.open_orders(self.settings.symbol)
                    if order.client_order_id.startswith(self.settings.client_order_prefix)
                ]
            for order in owned:
                with suppress(Exception):
                    await retry_write(lambda o=order: self.exchange.cancel(o), replayable=True)
            remaining = await self.exchange.reconcile_owned_orders(self.settings.symbol, self.settings.client_order_prefix) if hasattr(self.exchange, "reconcile_owned_orders") else []
            if remaining:
                log.error("owned order cleanup could not be confirmed; leaving dead-man armed")
                return
            with suppress(Exception):
                await retry_write(self.exchange.disarm_dead_man, replayable=True)
        except Exception:
            log.exception("targeted shutdown cleanup failed; leaving dead-man armed")

    def request_stop(self) -> None:
        self.stop_event.set()

    @staticmethod
    def _row(order: OrderSnapshot) -> dict[str, str | int]:
        return {
            "order_id": order.order_id,
            "client_order_id": order.client_order_id,
            "symbol": order.symbol,
            "side": order.side.value,
            "price": str(order.price),
            "qty": str(order.qty),
            "filled_qty": str(order.filled_qty),
            "status": order.status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "order_version": order.version,
        }
