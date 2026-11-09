from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from datetime import datetime, timezone

from .config import Settings
from .exchange import Exchange
from .models import OrderSnapshot
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

    async def run(self, *, once: bool = False) -> None:
        await self.store.open()
        self.rules = await self.exchange.load_rules(self.settings.symbol)
        if not self.settings.enable_live_trading:
            log.warning("dry-run mode: no orders will be submitted")
            if once:
                await self.store.close()
                return
        self.live = self.settings.enable_live_trading
        dms_task = asyncio.create_task(self._dead_man_loop()) if self.live else None
        try:
            while not self.stop_event.is_set():
                await self.cycle()
                if once: break
                try: await asyncio.wait_for(self.stop_event.wait(), timeout=2.0)
                except asyncio.TimeoutError: pass
        finally:
            if dms_task: dms_task.cancel(); await asyncio.gather(dms_task, return_exceptions=True)
            await self.shutdown()
            await self.store.close()

    async def cycle(self) -> None:
        assert self.rules
        open_orders = await self.exchange.open_orders(self.settings.symbol)
        bid, ask = await self.exchange.best_bid_ask(self.settings.symbol)
        quotes = self.strategy.quotes(self.rules, bid, ask, open_orders)
        if not self.live: return
        for quote in quotes:
            order = await retry_write(lambda q=quote: self.exchange.place(q), replayable=True)
            await self.store.upsert_order(self._row(order))

    async def _dead_man_loop(self) -> None:
        while not self.stop_event.is_set():
            await retry_write(lambda: self.exchange.arm_dead_man(self.settings.dms_timeout_seconds), replayable=True)
            try: await asyncio.wait_for(self.stop_event.wait(), timeout=self.settings.dms_refresh_seconds)
            except asyncio.TimeoutError: pass

    async def shutdown(self) -> None:
        if self.live:
            with suppress(Exception): await retry_write(lambda: self.exchange.cancel_all(self.settings.symbol), replayable=True)
            with suppress(Exception): await retry_write(self.exchange.disarm_dead_man, replayable=True)

    def request_stop(self) -> None: self.stop_event.set()

    @staticmethod
    def _row(order: OrderSnapshot) -> dict[str, str]:
        return {"order_id": order.order_id, "client_order_id": order.client_order_id, "symbol": order.symbol, "side": order.side.value, "price": str(order.price), "qty": str(order.qty), "filled_qty": str(order.filled_qty), "status": order.status, "updated_at": datetime.now(timezone.utc).isoformat()}
