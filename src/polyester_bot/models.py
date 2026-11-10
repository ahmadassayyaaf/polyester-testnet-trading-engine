from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True)
class Quote:
    side: Side
    price: Decimal
    qty: Decimal
    client_order_id: str


@dataclass(frozen=True)
class OrderSnapshot:
    order_id: str
    client_order_id: str
    symbol: str
    side: Side
    price: Decimal
    qty: Decimal
    filled_qty: Decimal = Decimal("0")
    status: str = "new"
    version: int = 0


@dataclass(frozen=True)
class AssetBalance:
    asset_id: int
    available: Decimal
    reserved: Decimal = Decimal("0")
    trading_revision: int = 0


@dataclass(frozen=True)
class BookSnapshot:
    symbol: str
    book_seq: str
    best_bid: Decimal | None
    best_ask: Decimal | None
    fresh: bool = True


@dataclass(frozen=True)
class OrderEvent:
    order_id: str
    version: int
    kind: str
    fill: Fill | None = None
    cancel_reason: str | None = None
    replacement_order_id: str | None = None


@dataclass(frozen=True)
class Fill:
    order_id: str
    qty: Decimal
    price: Decimal
    side: Side
    event_id: str
