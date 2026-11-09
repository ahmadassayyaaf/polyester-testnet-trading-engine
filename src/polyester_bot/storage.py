from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
  order_id TEXT PRIMARY KEY, client_order_id TEXT NOT NULL UNIQUE, symbol TEXT NOT NULL,
  side TEXT NOT NULL, price TEXT NOT NULL, qty TEXT NOT NULL, filled_qty TEXT NOT NULL DEFAULT '0',
  status TEXT NOT NULL, updated_at TEXT NOT NULL
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
        await self.db.execute("""INSERT INTO orders VALUES (:order_id,:client_order_id,:symbol,:side,:price,:qty,:filled_qty,:status,:updated_at)
        ON CONFLICT(order_id) DO UPDATE SET filled_qty=excluded.filled_qty,status=excluded.status,updated_at=excluded.updated_at""", row)
        await self.db.commit()

    async def open_orders(self, symbol: str) -> list[dict[str, str]]:
        assert self.db
        cur = await self.db.execute("SELECT order_id,client_order_id,symbol,side,price,qty,filled_qty,status,updated_at FROM orders WHERE symbol=? AND status NOT IN ('filled','canceled','rejected')", (symbol,))
        rows = await cur.fetchall()
        columns = [d[0] for d in cur.description]
        return [dict(zip(columns, row)) for row in rows]
