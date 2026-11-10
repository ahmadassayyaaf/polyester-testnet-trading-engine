from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from .models import Quote

QUOTABLE_STATUSES = {"ENABLED", "PAIR_STATUS_ENABLED", "POST_ONLY", "PAIR_STATUS_POST_ONLY"}
RULE_ERROR_CODES = {"PRICE_TICK_SIZE", "QTY_STEP_SIZE", "MIN_QTY", "MIN_NOTIONAL", "MAX_QTY", "MAX_NOTIONAL"}


def _d(value: Any) -> Decimal:
    return Decimal(str(value or "0"))


def _time(value: Any) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


@dataclass(frozen=True)
class PairRules:
    symbol: str
    symbol_id: int
    status: str
    tick_size: Decimal
    step_size: Decimal
    min_qty: Decimal
    min_notional: Decimal
    max_qty: Decimal | None = None
    max_notional: Decimal | None = None
    listing_at: datetime | None = None
    delisting_at: datetime | None = None
    base_asset_id: int | None = None
    quote_asset_id: int | None = None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> "PairRules":
        return cls(
            symbol=raw["symbol"], symbol_id=int(raw["symbolId"]), status=str(raw["status"]),
            base_asset_id=int(raw["baseAssetId"]) if raw.get("baseAssetId") is not None else None,
            quote_asset_id=int(raw["quoteAssetId"]) if raw.get("quoteAssetId") is not None else None,
            tick_size=_d(raw["tickSize"]), step_size=_d(raw["stepSize"]),
            min_qty=_d(raw.get("minQtyBase")), min_notional=_d(raw.get("minNotionalQuote")),
            max_qty=_d(raw["maxLimitQtyBase"]) if raw.get("maxLimitQtyBase") is not None else None,
            max_notional=_d(raw["maxOrderNotionalQuote"]) if raw.get("maxOrderNotionalQuote") is not None else None,
            listing_at=_time(raw.get("listingAt")), delisting_at=_time(raw.get("delistingAt")),
        )

    def validate_order(self, price: Decimal, qty: Decimal, now: datetime | None = None) -> None:
        now = now or datetime.now(timezone.utc)
        if self.status not in QUOTABLE_STATUSES:
            raise ValueError(f"pair {self.symbol} is not quotable: {self.status}")
        if self.listing_at and now < self.listing_at:
            raise ValueError("pair is not listed yet")
        if self.delisting_at and now >= self.delisting_at:
            raise ValueError("pair is delisted")
        if price <= 0 or price % self.tick_size != 0:
            raise ValueError("PRICE_TICK_SIZE")
        if qty <= 0 or qty % self.step_size != 0:
            raise ValueError("QTY_STEP_SIZE")
        if qty < self.min_qty:
            raise ValueError("MIN_QTY")
        notional = price * qty
        if notional < self.min_notional:
            raise ValueError("MIN_NOTIONAL")
        if self.max_qty is not None and qty > self.max_qty:
            raise ValueError("MAX_QTY")
        if self.max_notional is not None and notional > self.max_notional:
            raise ValueError("MAX_NOTIONAL")

    def validate_quote(self, quote: Quote, now: datetime | None = None) -> None:
        self.validate_order(quote.price, quote.qty, now)
