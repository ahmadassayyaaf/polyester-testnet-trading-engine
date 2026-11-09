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


@dataclass(frozen=True)
class Fill:
    order_id: str
    qty: Decimal
    price: Decimal
    side: Side
    event_id: str
