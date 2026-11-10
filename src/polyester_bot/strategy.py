from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from uuid import uuid4

from .models import AssetBalance, OrderSnapshot, Quote, Side
from .rules import PairRules


class MarketMaker:
    def __init__(
        self,
        symbol: str,
        qty: Decimal,
        half_spread_bps: Decimal,
        max_inventory: Decimal,
        client_order_prefix: str = "mm-",
        quote_notional_cap: Decimal | None = None,
    ):
        self.symbol = symbol
        self.qty = qty
        self.half_spread_bps = half_spread_bps
        self.max_inventory = max_inventory
        self.client_order_prefix = client_order_prefix
        self.quote_notional_cap = quote_notional_cap
        self.inventory = Decimal("0")

    def _floor(self, value: Decimal, step: Decimal) -> Decimal:
        return (value / step).to_integral_value(rounding=ROUND_FLOOR) * step

    def _ceil(self, value: Decimal, step: Decimal) -> Decimal:
        return (value / step).to_integral_value(rounding=ROUND_CEILING) * step

    def _available(self, balances: Mapping[int, AssetBalance], asset_id: int | None) -> Decimal | None:
        if asset_id is None:
            return None
        balance = balances.get(asset_id)
        return balance.available if balance is not None else Decimal("0")

    def _size(
        self,
        rules: PairRules,
        side: Side,
        price: Decimal,
        balances: Mapping[int, AssetBalance] | None,
    ) -> Decimal | None:
        cap = self.qty
        if side == Side.BUY:
            remaining_inventory = self.max_inventory - self.inventory
            available = self._available(balances, rules.quote_asset_id) if balances is not None else None
            if remaining_inventory <= 0:
                return None
            cap = min(cap, remaining_inventory)
            if available is not None:
                cap = min(cap, available / price)
        else:
            remaining_inventory = self.max_inventory + self.inventory
            available = self._available(balances, rules.base_asset_id) if balances is not None else None
            if remaining_inventory <= 0:
                return None
            cap = min(cap, remaining_inventory)
            if available is not None:
                cap = min(cap, available)

        if self.quote_notional_cap is not None:
            cap = min(cap, self.quote_notional_cap / price)
        if rules.max_qty is not None:
            cap = min(cap, rules.max_qty)
        if rules.max_notional is not None:
            cap = min(cap, rules.max_notional / price)

        qty = self._floor(cap, rules.step_size)
        return qty if qty >= rules.min_qty and price * qty >= rules.min_notional else None

    def _client_id(self, side: Side) -> str:
        marker = "b" if side == Side.BUY else "s"
        return f"{self.client_order_prefix}{marker}-{uuid4().hex[:10]}"

    def quotes(
        self,
        rules: PairRules,
        bid: Decimal,
        ask: Decimal,
        open_orders: list[OrderSnapshot],
        balances: Mapping[int, AssetBalance] | None = None,
    ) -> list[Quote]:
        if len(open_orders) >= 2 or bid <= 0 or ask <= bid:
            return []
        mid = (bid + ask) / 2
        spread = self.half_spread_bps / Decimal("10000")
        bid_price = self._floor(mid * (1 - spread), rules.tick_size)
        ask_price = self._ceil(mid * (1 + spread), rules.tick_size)
        result: list[Quote] = []
        sides = {o.side for o in open_orders}
        if Side.BUY not in sides:
            qty = self._size(rules, Side.BUY, bid_price, balances)
            if qty is not None:
                quote = Quote(Side.BUY, bid_price, qty, self._client_id(Side.BUY))
                rules.validate_quote(quote)
                result.append(quote)
        if Side.SELL not in sides:
            qty = self._size(rules, Side.SELL, ask_price, balances)
            if qty is not None:
                quote = Quote(Side.SELL, ask_price, qty, self._client_id(Side.SELL))
                rules.validate_quote(quote)
                result.append(quote)
        return result

    def apply_fill(self, order: OrderSnapshot, delta_qty: Decimal) -> None:
        self.inventory += delta_qty if order.side == Side.BUY else -delta_qty
        if abs(self.inventory) > self.max_inventory:
            raise RuntimeError("inventory exposure limit exceeded")
