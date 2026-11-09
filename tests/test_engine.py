from decimal import Decimal
import pytest
from polyester_bot.config import Settings
from polyester_bot.engine import TradingEngine
from polyester_bot.models import OrderSnapshot, Side
from polyester_bot.rules import PairRules
from polyester_bot.storage import Store
from polyester_bot.strategy import MarketMaker

class FakeExchange:
    def __init__(self):
        self.placed = []; self.cancelled_all = 0; self.armed = 0; self.disarmed = 0
    async def load_rules(self, symbol):
        return PairRules.from_raw(dict(symbol=symbol, symbolId=1, status='ENABLED', tickSize='0.01', stepSize='0.001', minQtyBase='0.01', minNotionalQuote='5'))
    async def best_bid_ask(self, symbol): return Decimal('100'), Decimal('101')
    async def open_orders(self, symbol): return []
    async def place(self, quote):
        self.placed.append(quote); return OrderSnapshot(f'o{len(self.placed)}', quote.client_order_id, 'BTC-USDT', quote.side, quote.price, quote.qty, status='accepted')
    async def cancel(self, order): pass
    async def arm_dead_man(self, timeout_seconds): self.armed += 1
    async def disarm_dead_man(self): self.disarmed += 1
    async def cancel_all(self, symbol): self.cancelled_all += 1
    async def events(self, symbol):
        if False: yield

def settings(live):
    return Settings(None, None, None, 'BTC-USDT', Decimal('0.1'), Decimal('20'), Decimal('1'), 2, ':memory:', 'INFO', 30, 10, live)

@pytest.mark.asyncio
async def test_dry_run_never_places_orders(tmp_path):
    exchange = FakeExchange(); store = Store(str(tmp_path/'x.db'))
    await TradingEngine(settings(False), exchange, store, MarketMaker('BTC-USDT', Decimal('0.1'), Decimal('20'), Decimal('1'))).run(once=True)
    assert exchange.placed == []

@pytest.mark.asyncio
async def test_live_once_cancels_and_disarms(tmp_path):
    exchange = FakeExchange(); store = Store(str(tmp_path/'x.db'))
    await TradingEngine(settings(True), exchange, store, MarketMaker('BTC-USDT', Decimal('0.1'), Decimal('20'), Decimal('1'))).run(once=True)
    assert len(exchange.placed) == 2 and exchange.cancelled_all == 1 and exchange.disarmed == 1
