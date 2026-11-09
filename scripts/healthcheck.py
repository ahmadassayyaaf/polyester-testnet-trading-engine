from __future__ import annotations

import asyncio
import importlib.metadata
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from polyester_bot.config import Settings
from polyester_bot.rules import PairRules


@dataclass
class Check:
    name: str
    status: str
    detail: str


class HealthReport:
    def __init__(self) -> None:
        self.checks: list[Check] = []

    def add(self, name: str, status: str, detail: str) -> None:
        self.checks.append(Check(name, status, detail))

    @property
    def failed(self) -> bool:
        return any(check.status == "FAIL" for check in self.checks)

    def print(self) -> None:
        for check in self.checks:
            print(f"[{check.status}] {check.name}: {check.detail}")


def _secret_state(settings: Settings) -> tuple[str, str]:
    values = (settings.api_key_id, settings.api_private_key, settings.subaccount_id)
    present = sum(value is not None and value != "" for value in values)
    if present == 0:
        return "WARN", "credentials not configured; authenticated checks skipped"
    if present != 3:
        return "FAIL", "partial credentials; set API key ID, 64-char private key, and Subaccount ID"
    if settings.api_private_key is None or len(settings.api_private_key) != 64:
        return "FAIL", "private key length is not 64 characters"
    try:
        int(settings.api_private_key, 16)
    except ValueError:
        return "FAIL", "private key is not hexadecimal"
    return "PASS", "credential variables are present; values were not printed"


def _pair_raw(config: Any, symbol: str) -> dict[str, Any] | None:
    return next((pair for pair in config.raw.get("pairs", []) if pair.get("symbol") == symbol), None)


async def run() -> HealthReport:
    report = HealthReport()
    try:
        settings = Settings.from_env()
    except Exception as exc:
        report.add("configuration", "FAIL", str(exc))
        return report

    if settings.environment == "testnet":
        report.add("environment", "PASS", "explicit environment=testnet; no Mainnet path is supported")
    else:
        report.add("environment", "FAIL", f"unexpected environment={settings.environment}")

    try:
        sdk_version = importlib.metadata.version("polyester-sdk")
        report.add("sdk", "PASS", f"polyester-sdk={sdk_version}")
    except importlib.metadata.PackageNotFoundError:
        report.add("sdk", "FAIL", "polyester-sdk is not installed")
        return report

    credential_status, credential_detail = _secret_state(settings)
    credentials_present = credential_status == "PASS"
    report.add("credentials", credential_status, credential_detail)
    if settings.enable_live_trading:
        report.add("live authorization", "WARN", "ENABLE_LIVE_TRADING=true; this healthcheck remains read-only")
    else:
        report.add("live authorization", "PASS", "live order execution is disabled")

    try:
        from polyester import AsyncPolyester, POLYESTER_TESTNET_ENVIRONMENT

        async with AsyncPolyester(
            environment=POLYESTER_TESTNET_ENVIRONMENT,
            api_key_id=settings.api_key_id if credentials_present else None,
            api_private_key=settings.api_private_key if credentials_present else None,
            default_sub_account_id=settings.subaccount_id if credentials_present else None,
        ) as client:
            await client.wait_for_catalogs()
            config = await client.market_data.get_spot_config()
            raw = _pair_raw(config, settings.symbol)
            if raw is None:
                report.add("pair catalog", "FAIL", f"{settings.symbol} is not listed")
                return report

            rules = PairRules.from_raw(raw)
            report.add(
                "pair catalog",
                "PASS",
                f"{rules.symbol} symbol_id={rules.symbol_id}, status={rules.status}",
            )
            report.add(
                "pair status",
                "PASS" if rules.status in {"ENABLED", "PAIR_STATUS_ENABLED", "POST_ONLY", "PAIR_STATUS_POST_ONLY"} else "WARN",
                f"{rules.status}; new quoting is {'allowed' if rules.status in {'ENABLED', 'PAIR_STATUS_ENABLED', 'POST_ONLY', 'PAIR_STATUS_POST_ONLY'} else 'not allowed'}",
            )
            report.add(
                "pair precision",
                "PASS",
                f"tick={rules.tick_size}, step={rules.step_size}, min_qty={rules.min_qty}, min_notional={rules.min_notional}",
            )

            try:
                bid_ask = await client.orderbook.get(symbol=settings.symbol, depth=1)
                if not bid_ask.available or not bid_ask.bids or not bid_ask.asks:
                    raise RuntimeError("orderbook is unavailable or has no bid/ask")
                bid = bid_ask.bids[0].price.as_decimal()
                ask = bid_ask.asks[0].price.as_decimal()
                if bid <= 0 or ask <= 0 or bid >= ask:
                    raise RuntimeError(f"invalid market {bid}/{ask}")
                report.add("orderbook", "PASS", f"available; bid={bid}, ask={ask}")
            except Exception as exc:
                report.add("orderbook", "FAIL", str(exc))
                bid = ask = Decimal("0")

            if bid > 0:
                try:
                    rules.validate_order(bid, settings.qty)
                    report.add(
                        "configured order admissibility",
                        "PASS",
                        f"qty={settings.qty} passes dynamic tick/step/min/max/notional checks at best bid",
                    )
                except ValueError as exc:
                    report.add("configured order admissibility", "FAIL", str(exc))

            if credentials_present:
                try:
                    open_orders = await client.orders.list_open()
                    scoped = [order for order in open_orders.orders if order.symbol_id == rules.symbol_id]
                    report.add("authenticated read", "PASS", f"list_open succeeded; {len(scoped)} open order(s) on target Pair")
                except Exception as exc:
                    report.add("authenticated read", "FAIL", f"list_open failed: {type(exc).__name__}: {exc}")
            else:
                report.add("authenticated read", "WARN", "skipped because credentials are unavailable")
    except Exception as exc:
        report.add("Testnet connectivity", "FAIL", f"{type(exc).__name__}: {exc}")

    report.add("mutation lifecycle", "INFO", "not tested by this read-only healthcheck")
    report.add("dead-man switch", "INFO", "not tested by this read-only healthcheck; requires explicit mutation test")
    report.add("withdrawals", "PASS", "no withdrawal code path is executed")
    return report


def main() -> int:
    report = asyncio.run(run())
    report.print()
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
