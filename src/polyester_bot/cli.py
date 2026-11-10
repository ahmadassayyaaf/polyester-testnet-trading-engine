from __future__ import annotations
import asyncio
from .config import Settings
from .engine import TradingEngine
from .logging import configure_logging
from .polyester_adapter import PolyesterAdapter
from .storage import Store
from .strategy import MarketMaker

def main() -> None:
    settings = Settings.from_env(); configure_logging(settings.log_level)
    async def run():
        async with PolyesterAdapter(settings) as adapter:
            strategy = MarketMaker(
                settings.symbol,
                settings.qty,
                settings.half_spread_bps,
                settings.max_inventory,
                settings.client_order_prefix,
                settings.quote_notional_cap,
            )
            await TradingEngine(settings, adapter, Store(settings.db_path), strategy).run()
    asyncio.run(run())
