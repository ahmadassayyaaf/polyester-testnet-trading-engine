# Production Reliability Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mengembangkan bot Polyester Testnet dari polling quote loop menjadi engine yang lebih dekat dengan pola production resmi: order ownership tertarget, sizing dari available Trading balance, sequence-aware book, private order reconciliation, dan quote refresh idempotent.

**Architecture:** Pertahankan `Exchange` sebagai boundary SDK dan gunakan domain models yang bebas dari tipe SDK. Adapter menerjemahkan managed orderbook, balances, private order events, dan batch replacement ke domain. Engine menjadi orchestration layer yang fail-closed: pause quoting saat book/stream stale, reconcile sebelum retry, dan hanya membatalkan order dengan prefix bot sendiri.

**Tech Stack:** Python 3.11+, `asyncio`, `Decimal`, `aiosqlite`, `polyester-sdk==0.14.0`, pytest, pytest-asyncio.

**Spec:** Official Polyester Testnet production trading bot, two-sided quoting, portfolio tracker, market-maker guide, private WebSocket, error handling, and requests/idempotency documentation listed in `docs/polyester-contract-notes.md`.

## Global Constraints

- Bot tetap Testnet-only dan tidak menambah withdrawal atau Mainnet code path.
- Jangan memakai `float` untuk harga, quantity, balance, fee, atau notional.
- `wait_for_catalogs()` dan `GetSpotConfig` adalah startup gate sebelum decoding atau mutation.
- Semua mutation memakai stable `client_order_id`/`request_id`; unknown outcome wajib direkonsiliasi sebelum membuat identitas baru.
- Shutdown hanya membersihkan order yang dimiliki prefix bot; dead-man switch tetap menjadi last-resort safety control.
- `ENABLE_LIVE_TRADING=false` tetap default dan semua test baru harus offline/fake exchange.
- Private stream/orderbook failure, sequence gap, stale snapshot, dan balance read failure harus menghentikan quoting, bukan mengarang state.

## Review Focus

- Open order account lain atau sesi bot lama tidak boleh dibatalkan oleh shutdown bot ini; uji filter ownership dan targeted cancel.
- Bid dan ask tidak boleh memakai quantity yang sama secara buta; uji sizing terhadap `available` quote/base balance, min notional, step, dan inventory cap.
- Reconnect/gap pada managed book harus mem-pause quote sampai snapshot refresh; uji callback sequence gap dan empty/crossed book.
- Private order unit dengan version lebih rendah atau removal tanpa cancel tidak boleh menurunkan state lokal; uji version merge dan removed-order handling.
- Batch replace/admission timeout tidak boleh membuat duplicate quote; uji stable request ID, successor identity, dan reconciliation.

---

### Task 1: Domain state dan konfigurasi ownership/risk

**Files:**
- Modify: `src/polyester_bot/config.py`
- Modify: `src/polyester_bot/models.py`
- Modify: `src/polyester_bot/storage.py`
- Test: `tests/test_config.py`, `tests/test_storage.py`

**Interfaces:**
- Add settings `client_order_prefix: str`, `book_depth: int`, and `requote_ticks: int`, sourced from `BOT_CLIENT_ORDER_PREFIX`, `BOT_BOOK_DEPTH`, and `BOT_REQUOTE_TICKS`.
- Add `AssetBalance(asset_id: int, available: Decimal, reserved: Decimal, trading_revision: int)`.
- Add `OrderEvent(order_id: str, version: int, kind: str, fill: Fill | None, cancel_reason: str | None, replacement_order_id: str | None)`.
- Add storage method `owned_orders(symbol: str, prefix: str) -> list[dict[str, str]]` and event/order upsert semantics that ignore stale versions.

- [ ] **Step 1: Write failing tests**
  - Assert default prefix is non-empty and ASCII-safe for Polyester client IDs.
  - Assert invalid prefix, depth, and requote tick values fail configuration validation.
  - Assert an older order version cannot overwrite a newer persisted row.
  - Assert `owned_orders` excludes client IDs outside the configured prefix.

- [ ] **Step 2: Run focused tests and verify failure**

```bash
pytest tests/test_config.py tests/test_storage.py -q
```

Expected: FAIL because the new settings, version field, and ownership query do not exist.

- [ ] **Step 3: Implement domain/config/storage changes**
  - Keep database backward-compatible by adding an `order_version` column through a guarded migration.
  - Store event payloads with the version and ignore lower-version updates.
  - Keep all values as strings at the SQLite boundary and convert to `Decimal` in domain code.

- [ ] **Step 4: Run focused tests**

```bash
pytest tests/test_config.py tests/test_storage.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/polyester_bot/config.py src/polyester_bot/models.py src/polyester_bot/storage.py tests/test_config.py tests/test_storage.py
git commit -m "feat: add owned order and versioned state controls"
```

### Task 2: SDK adapter for balances, managed orderbook, and private events

**Files:**
- Modify: `src/polyester_bot/exchange.py`
- Modify: `src/polyester_bot/polyester_adapter.py`
- Modify: `src/polyester_bot/models.py`
- Test: `tests/test_adapter_mapping.py`

**Interfaces:**
- Extend `Exchange` with `balances() -> list[AssetBalance]`, `subscribe_orderbook(depth: int) -> AsyncIterator[BookSnapshot]`, and `subscribe_order_events() -> AsyncIterator[OrderEvent]`.
- Add `BookSnapshot(symbol: str, book_seq: str, best_bid: Decimal | None, best_ask: Decimal | None, fresh: bool)`.
- Preserve existing one-shot `best_bid_ask` for healthcheck compatibility.

- [ ] **Step 1: Write failing adapter mapping tests**
  - Map SDK `AssetBalance.available`, `reserved`, and `trading_revision` exactly.
  - Map an SDK private snapshot/unit into owned domain orders/events.
  - Ignore connection/ready events and reject missing price/quantity scales.
  - Mark a sequence-gap callback as stale until snapshot refresh.

- [ ] **Step 2: Run focused tests and verify failure**

```bash
pytest tests/test_adapter_mapping.py -q
```

Expected: FAIL because the new adapter/domain interfaces do not exist.

- [ ] **Step 3: Implement adapter boundary**
  - Use `orderbook.create_subscription(symbol, symbol_id, depth, on_sequence_gap, on_snapshot_refresh)`.
  - Use `orders.subscribe(account_id=...)` and map only `PrivateOrdersSnapshot`/`PrivateOrdersUnit` after SDK readiness.
  - Convert SDK money types via `as_decimal()` and never decode scales manually in the engine.
  - Expose balances from `client.balances.list(sub_account_id=...)`.

- [ ] **Step 4: Run focused tests and compile**

```bash
pytest tests/test_adapter_mapping.py -q
python -m compileall -q src tests scripts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/polyester_bot/exchange.py src/polyester_bot/polyester_adapter.py src/polyester_bot/models.py tests/test_adapter_mapping.py
git commit -m "feat: add managed market and private state adapters"
```

### Task 3: Balance-aware two-sided strategy

**Files:**
- Modify: `src/polyester_bot/strategy.py`
- Modify: `src/polyester_bot/config.py`
- Test: `tests/test_strategy.py`

**Interfaces:**
- Change `MarketMaker.quotes(...)` to accept `balances: Mapping[int, AssetBalance]` and return independently sized bid/ask `Quote` values.
- Add `quote_notional_cap: Decimal` from `BOT_QUOTE_NOTIONAL_CAP`.
- Add `asset_id`/scale mapping from `PairRules` or a small immutable pair metadata object so quote sizing knows base and quote assets.

- [ ] **Step 1: Write failing strategy tests**
  - With enough quote but no base, create only a valid bid.
  - With enough base but no quote, create only a valid ask.
  - Cap both sides by available balance, inventory cap, configured quantity, pair step/minimums, and quote notional cap.
  - Suppress a side when the computed quantity falls below pair minimums.
  - Preserve unique bot prefix client IDs and validate every generated quote.

- [ ] **Step 2: Run focused tests and verify failure**

```bash
pytest tests/test_strategy.py -q
```

Expected: FAIL because strategy currently uses one fixed quantity and synthetic inventory only.

- [ ] **Step 3: Implement deterministic sizing**
  - Use exact `Decimal` floor-to-step sizing.
  - Buy sizing uses quote `available` at the bid plus configured reserve headroom.
  - Sell sizing uses base `available` and inventory ceiling.
  - Never force a quote that violates min quantity/notional or max order constraints.

- [ ] **Step 4: Run focused tests**

```bash
pytest tests/test_strategy.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/polyester_bot/config.py src/polyester_bot/strategy.py tests/test_strategy.py
git commit -m "feat: size quotes from available balances"
```

### Task 4: Reconciliation-first engine and idempotent quote refresh

**Files:**
- Modify: `src/polyester_bot/engine.py`
- Modify: `src/polyester_bot/exchange.py`
- Modify: `src/polyester_bot/polyester_adapter.py`
- Modify: `src/polyester_bot/storage.py`
- Test: `tests/test_engine.py`

**Interfaces:**
- Add `Exchange.reconcile_owned_orders(symbol: str, prefix: str) -> list[OrderSnapshot]`.
- Add `Exchange.replace_quotes(symbol: str, orders: list[Quote], request_id: str) -> list[OrderSnapshot]`.
- Add `TradingEngine.reconcile()` and `TradingEngine.shutdown()` targeted cleanup behavior.

- [ ] **Step 1: Write failing engine tests**
  - Startup reconciliation cancels stale owned quotes but never calls account-wide cancel.
  - Unknown create outcome causes lookup by original `client_order_id` before any retry.
  - Requote only occurs when price drifts by configured ticks or a side is missing.
  - Accepted batch replacement switches local tracking to successor identities.
  - Shutdown cancels owned orders, confirms they disappear, and only then disarms DMS.
  - Dry-run still performs reads/reconciliation but never mutation writes.

- [ ] **Step 2: Run focused tests and verify failure**

```bash
pytest tests/test_engine.py -q
```

Expected: FAIL because engine currently polls one-shot book data, uses account-wide cancel-all, and does not reconcile private events.

- [ ] **Step 3: Implement engine orchestration**
  - Start with catalog/rules, balances, owned-order reconciliation, and DMS arm before quoting.
  - Consume managed book and private order events in separate tasks.
  - Gate every quote cycle on fresh book, fresh balances, stream readiness, and known local state.
  - Use `batch_replace` with stable request ID only for the same logical refresh; persist successor IDs immediately.
  - On stream overflow/gap or failed DMS refresh, stop quote creation and reconcile.
  - During shutdown, cancel only owned prefix orders and leave DMS armed if cleanup cannot be confirmed.

- [ ] **Step 4: Run complete offline verification**

```bash
python -m compileall -q src tests scripts
pytest -q
```

Expected: all existing tests plus new engine tests pass; no Testnet mutation is performed.

- [ ] **Step 5: Commit**

```bash
git add src/polyester_bot/engine.py src/polyester_bot/exchange.py src/polyester_bot/polyester_adapter.py src/polyester_bot/storage.py tests/test_engine.py
git commit -m "feat: reconcile owned quotes before refresh and shutdown"
```

### Task 5: Documentation and release gate

**Files:**
- Modify: `README.md`
- Modify: `docs/testnet-deployment.md`
- Modify: `docs/compliance-checklist.md`
- Modify: `docs/polyester-contract-notes.md`
- Create: `docs/production-reliability.md`

- [ ] **Step 1: Document operational invariants and new environment variables**
  - Explain prefix ownership, balance sizing, book freshness, private stream readiness, batch replacement, and fail-closed behavior.
  - Add official source links and note SDK version differences where relevant.

- [ ] **Step 2: Run final checks**

```bash
python -m compileall -q src tests scripts
pytest -q
git diff --check
git ls-files | grep -Ei '(^|/)(\.env|.*private.*|.*secret.*|.*credential.*|.*\.pem)$' || true
```

Expected: tests pass, diff is clean, and no secret-like file is tracked.

- [ ] **Step 3: Commit and push**

```bash
git add README.md docs/
git commit -m "docs: document production reliability controls"
git push origin main
```

## Official evidence used

- Production bot invariants, managed book, balances, private stream, targeted cleanup: https://testnet.polyester.com/docs/sdk/python/tutorials/trading-bot
- Independent two-sided sizing and batch quote cycle: https://testnet.polyester.com/docs/sdk/python/tutorials/two-sided-quoting
- Balance revisions, available/reserved, private order versions, and fill completion: https://testnet.polyester.com/docs/sdk/python/tutorials/portfolio-tracker
- Interface choice, Subaccount policies, risk controls, rate limits, fee sizing, and reconciliation: https://testnet.polyester.com/docs/developer-docs/getting-started/market-maker-guide
- Private order snapshot/unit/cursor/version contract: https://testnet.polyester.com/docs/developer-docs/connectrpc/private-websocket
- Retry and realtime overflow rules: https://testnet.polyester.com/docs/sdk/python/guides/error-handling
- Stable mutation identifiers and unknown-outcome reconciliation: https://testnet.polyester.com/docs/sdk/python/concepts/requests-and-idempotency

## Gaps intentionally outside this phase

- No claim of profitability or financial performance.
- No Mainnet support, withdrawals, triggers, or hedging strategy.
- No live mutation test until credentials, funding, and explicit operator approval are available.
- No direct custom WebSocket protocol implementation; rely on SDK-managed subscriptions first.
