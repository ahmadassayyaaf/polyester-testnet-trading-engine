from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal

TESTNET_HOST = "api-testnet.polyester.com"


def _decimal(name: str, default: str) -> Decimal:
    raw = os.getenv(name, default)
    try:
        value = Decimal(raw)
    except Exception as exc:
        raise ValueError(f"{name} must be a decimal") from exc
    if not value.is_finite() or value < 0:
        raise ValueError(f"{name} must be a finite non-negative decimal")
    return value


@dataclass(frozen=True)
class Settings:
    api_key_id: str | None
    api_private_key: str | None
    subaccount_id: str | None
    symbol: str
    qty: Decimal
    half_spread_bps: Decimal
    max_inventory: Decimal
    max_open_orders: int
    db_path: str
    log_level: str
    dms_timeout_seconds: int
    dms_refresh_seconds: int
    enable_live_trading: bool
    environment: str = "testnet"

    @classmethod
    def from_env(cls) -> "Settings":
        settings = cls(
            api_key_id=os.getenv("POLYESTER_API_KEY_ID"),
            api_private_key=os.getenv("POLYESTER_API_PRIVATE_KEY"),
            subaccount_id=os.getenv("POLYESTER_SUBACCOUNT_ID"),
            symbol=os.getenv("BOT_SYMBOL", "BTC-USDT"),
            qty=_decimal("BOT_QTY", "0.0001"),
            half_spread_bps=_decimal("BOT_HALF_SPREAD_BPS", "20"),
            max_inventory=_decimal("BOT_MAX_INVENTORY", "0.001"),
            max_open_orders=int(os.getenv("BOT_MAX_OPEN_ORDERS", "2")),
            db_path=os.getenv("BOT_DB_PATH", "./state/bot.sqlite3"),
            log_level=os.getenv("BOT_LOG_LEVEL", "INFO").upper(),
            dms_timeout_seconds=int(os.getenv("BOT_DMS_TIMEOUT_SECONDS", "30")),
            dms_refresh_seconds=int(os.getenv("BOT_DMS_REFRESH_SECONDS", "10")),
            enable_live_trading=os.getenv("ENABLE_LIVE_TRADING", "false").lower() == "true",
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.environment != "testnet":
            raise ValueError("mainnet is not supported; environment must be testnet")
        if not self.symbol or "-" not in self.symbol:
            raise ValueError("BOT_SYMBOL must be a Polyester symbol such as BTC-USDT")
        if self.qty <= 0 or self.max_inventory <= 0:
            raise ValueError("quantity and max inventory must be positive")
        if self.max_open_orders < 1:
            raise ValueError("BOT_MAX_OPEN_ORDERS must be positive")
        if not 10 <= self.dms_timeout_seconds <= 120:
            raise ValueError("dead-man timeout must be between 10 and 120 seconds")
        if self.dms_refresh_seconds >= self.dms_timeout_seconds:
            raise ValueError("dead-man refresh must be shorter than timeout")
        if self.enable_live_trading and not all((self.api_key_id, self.api_private_key, self.subaccount_id)):
            raise ValueError("live trading requires API key ID, private key, and subaccount ID")
        if self.api_private_key and len(self.api_private_key) != 64:
            raise ValueError("POLYESTER_API_PRIVATE_KEY must be a 64-character hex key")
