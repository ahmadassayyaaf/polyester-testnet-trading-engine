# Polyester Testnet Trading Engine Implementation Plan

> **For agentic workers:** Implement task-by-task with tests and verification evidence.

**Goal:** Build a production-structured, Testnet-only asynchronous market-making engine for Polyester DEX using the official Python SDK, with dynamic rules, safe order lifecycle handling, persistence, observability, and failure recovery.

**Architecture:** Keep strategy logic independent from the SDK through small protocols. A Testnet adapter owns SDK calls, while validation, retry/idempotency, persistence, reconciliation, dead-man heartbeat, and strategy orchestration remain testable offline. The first vertical slice supports a two-sided post-only quote; live trading stays disabled unless explicitly authorized.

**Tech Stack:** Python 3.11+, asyncio, official `polyester-sdk`, `Decimal`, SQLite via `aiosqlite`, pytest/pytest-asyncio, structured JSON logging, optional Telegram notifications, static HTML monitoring dashboard.

**Spec:** `/home/ubuntu/upload/pasted_content.txt`

## Global Constraints

- TESTNET ONLY; explicitly use `POLYESTER_TESTNET_ENVIRONMENT`.
- Never connect to Mainnet or perform withdrawals.
- Credentials come only from environment variables; never log private keys.
- Require explicit `ENABLE_LIVE_TRADING=true` before order execution.
- Never hardcode exchange rules; load Pair rules from `GetSpotConfig`.
- Use strict `Decimal` arithmetic and decimal strings at the SDK boundary.
- Preserve client IDs/request IDs across replayable retries.

## Review Focus

- SDK/API drift: adapter tests must isolate SDK calls and live checks must report exact installed SDK version.
- Unknown mutation outcomes: retries must reuse identifiers and reconciliation must happen before new logical orders.
- Pair status/listing windows: quote only when status and listing timestamps allow it.
- Partial fills: inventory and slot state must update from events and survive restart.
- Dead-man timing: heartbeat must use a fresh request ID and shutdown must cancel then disarm.

### Task 1: Repository and configuration foundation

**Files:** `pyproject.toml`, `.env.example`, `.gitignore`, `README.md`, `src/polyester_bot/config.py`, `src/polyester_bot/logging.py`, `tests/test_config.py`.

- [ ] Define typed settings with safe defaults and fail-closed live trading.
- [ ] Add dependency pins and test/lint commands.
- [ ] Verify settings reject non-Testnet endpoints and missing live authorization.

### Task 2: Dynamic Pair-rule validation

**Files:** `src/polyester_bot/rules.py`, `tests/test_rules.py`.

- [ ] Parse `GetSpotConfig` raw pair records into `PairRules` using `Decimal`.
- [ ] Validate tick, step, min quantity, min notional, max quantity/notional, status, and listing windows.
- [ ] Add tests for invalid price/quantity increments and minimum notional.

### Task 3: Persistence and order state

**Files:** `src/polyester_bot/storage.py`, `src/polyester_bot/models.py`, `tests/test_storage.py`.

- [ ] Create SQLite schema for orders, fills, events, and bot state.
- [ ] Implement idempotent upserts and restart recovery queries.
- [ ] Add partial-fill and unknown-outcome persistence tests.

### Task 4: Retry-safe exchange boundary

**Files:** `src/polyester_bot/exchange.py`, `src/polyester_bot/retry.py`, `tests/test_retry.py`, `tests/test_exchange_fake.py`.

- [ ] Define an exchange protocol and fake adapter.
- [ ] Implement exponential backoff for rate limits/overload/system errors.
- [ ] Retry unknown outcomes only with unchanged payload identifiers.
- [ ] Add duplicate submission, rate-limit, and unknown-outcome tests.

### Task 5: Polyester SDK Testnet adapter

**Files:** `src/polyester_bot/polyester_adapter.py`, `tests/test_adapter_contract.py`.

- [ ] Construct `AsyncPolyester(environment=POLYESTER_TESTNET_ENVIRONMENT, ...)`.
- [ ] Implement catalog read, public market data, private order stream, create/replace/cancel, cancel-all, and `CancelAllAfter` wrappers.
- [ ] Keep all SDK-specific imports in this module and provide an SDK version diagnostic.

### Task 6: Strategy and engine orchestration

**Files:** `src/polyester_bot/strategy.py`, `src/polyester_bot/engine.py`, `src/polyester_bot/cli.py`, `tests/test_strategy.py`, `tests/test_engine.py`.

- [ ] Implement configurable two-sided post-only market-making strategy.
- [ ] Enforce inventory exposure and maximum open orders.
- [ ] Reconcile before quoting, refresh rules, maintain DMS, handle stream reconnects, and safe shutdown.
- [ ] Add tests for partial fills, disconnect recovery, DMS activation, and cancel-all shutdown.

### Task 7: Operations and monitoring deliverables

**Files:** `dashboard/index.html`, `scripts/healthcheck.py`, `docs/compliance-checklist.md`, `docs/testnet-deployment.md`, `README.md`.

- [ ] Add a read-only local dashboard backed by SQLite export data.
- [ ] Document installation, environment setup, dry-run, explicit authorization, monitoring, and rollback.
- [ ] Add a compliance checklist that distinguishes offline tests, public Testnet checks, and credentialed mutation checks.

### Verification gate

- [ ] Run `python -m pytest -q`.
- [ ] Run `python -m compileall -q src tests`.
- [ ] Run a no-credentials dry-run/health check.
- [ ] Inspect `git diff` and confirm no secrets or Mainnet endpoints are present.
