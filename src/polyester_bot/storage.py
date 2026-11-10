from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
  order_id TEXT PRIMARY KEY, client_order_id TEXT NOT NULL UNIQUE, symbol TEXT NOT NULL,
  side TEXT NOT NULL, price TEXT NOT NULL, qty TEXT NOT NULL, filled_qty TEXT NOT NULL DEFAULT '0',
  status TEXT NOT NULL, updated_at TEXT NOT NULL, order_version INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS fills (
  event_id TEXT PRIMARY KEY, order_id TEXT NOT NULL, qty TEXT NOT NULL, price TEXT NOT NULL,
  side TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
  event_id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL
);
"""


class Store:
    def __init__(self, path: str):
        self.path = path
        self.db: aiosqlite.Connection | None = None

    async def open(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = await aiosqlite.connect(self.path)
        await self.db.executescript(SCHEMA)
        columns = {row[1] for row in await (await self.db.execute("PRAGMA table_info(orders)")).fetchall()}
        if "order_version" not in columns:
            await self.db.execute("ALTER TABLE orders ADD COLUMN order_version INTEGER NOT NULL DEFAULT 0")
        await self.db.commit()

    async def close(self) -> None:
        if self.db:
            await self.db.close()
            self.db = None

    async def record_event(self, event_id: str, kind: str, payload: dict[str, Any], created_at: str) -> None:
        assert self.db
        await self.db.execute("INSERT OR IGNORE INTO events VALUES (?, ?, ?, ?)", (event_id, kind, json.dumps(payload), created_at))
        await self.db.commit()

    async def upsert_order(self, row: dict[str, str]) -> None:
        assert self.db
        values = dict(row)
        values.setdefault("order_version", 0)
        await self.db.execute("""INSERT INTO orders
        (order_id,client_order_id,symbol,side,price,qty,filled_qty,status,updated_at,order_version)
        VALUES (:order_id,:client_order_id,:symbol,:side,:price,:qty,:filled_qty,:status,:updated_at,:order_version)
        ON CONFLICT(order_id) DO UPDATE SET filled_qty=excluded.filled_qty,status=excluded.status,
        updated_at=excluded.updated_at,order_version=excluded.order_version
        WHERE excluded.order_version >= orders.order_version""", values)
        await self.db.commit()

    async def open_orders(self, symbol: str) -> list[dict[str, str]]:
        assert self.db
        cur = await self.db.execute("SELECT order_id,client_order_id,symbol,side,price,qty,filled_qty,status,updated_at,order_version FROM orders WHERE symbol=? AND status NOT IN ('filled','canceled','rejected')", (symbol,))
        rows = await cur.fetchall()
        columns = [d[0] for d in cur.description]
        return [dict(zip(columns, row)) for row in rows]

    async def owned_orders(self, symbol: str, prefix: str) -> list[dict[str, str]]:
        assert self.db
        cur = await self.db.execute(
            "SELECT order_id,client_order_id,symbol,side,price,qty,filled_qty,status,updated_at,order_version "
            "FROM orders WHERE symbol=? AND client_order_id LIKE ? AND status NOT IN ('filled','canceled','rejected')",
            (symbol, f"{prefix}%"),
        )
        rows = await cur.fetchall()
        columns = [d[0] for d in cur.description]
        return [dict(zip(columns, row)) for row in rows]
