from __future__ import annotations

from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from uuid import uuid4

from .models import OrderSnapshot, Quote, Side
from .rules import PairRules

class MarketMaker:
    def __init__(self, symbol: str, qty: Decimal, half_spread_bps: Decimal, max_inventory: Decimal):
        self.symbol, self.qty, self.half_spread_bps, self.max_inventory = symbol, qty, half_spread_bps, max_inventory
        self.inventory = Decimal("0")

    def _floor(self, value: Decimal, step: Decimal) -> Decimal:
        return (value / step).to_integral_value(rounding=ROUND_FLOOR) * step

    def _ceil(self, value: Decimal, step: Decimal) -> Decimal:
        return (value / step).to_integral_value(rounding=ROUND_CEILING) * step

    def quotes(self, rules: PairRules, bid: Decimal, ask: Decimal, open_orders: list[OrderSnapshot]) -> list[Quote]:
        if len(open_orders) >= 2:
            return []
        mid = (bid + ask) / 2
        spread = self.half_spread_bps / Decimal("10000")
        bid_price = self._floor(mid * (1 - spread), rules.tick_size)
        ask_price = self._ceil(mid * (1 + spread), rules.tick_size)
        result: list[Quote] = []
        sides = {o.side for o in open_orders}
        if self.inventory < self.max_inventory and Side.BUY not in sides:
            quote = Quote(Side.BUY, bid_price, self.qty, f"mm-bid-{uuid4().hex[:16]}")
            rules.validate_quote(quote); result.append(quote)
        if self.inventory > -self.max_inventory and Side.SELL not in sides:
            quote = Quote(Side.SELL, ask_price, self.qty, f"mm-ask-{uuid4().hex[:16]}")
            rules.validate_quote(quote); result.append(quote)
        return result

    def apply_fill(self, order: OrderSnapshot, delta_qty: Decimal) -> None:
        self.inventory += delta_qty if order.side == Side.BUY else -delta_qty
        if abs(self.inventory) > self.max_inventory:
            raise RuntimeError("inventory exposure limit exceeded")
