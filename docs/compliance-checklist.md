# Compliance checklist

## Safety boundary

- [ ] `environment` remains `testnet` and SDK receives `POLYESTER_TESTNET_ENVIRONMENT`.
- [ ] No Mainnet URL, withdrawal call, or private key is present in source or logs.
- [ ] `ENABLE_LIVE_TRADING=false` during development and dry-run verification.
- [ ] Live key is bound to a dedicated Subaccount with spot permission only.
- [ ] Pair rules are loaded from `GetSpotConfig` at startup and refreshed.

## Order safety

- [ ] Price and quantity pass dynamic tick/step/min/max/notional validation.
- [ ] Client order IDs remain stable across retry of an ambiguous create.
- [ ] Batch/request IDs are not reused for a different payload.
- [ ] Unknown outcomes trigger reconciliation before a new logical order.
- [ ] Self-trade prevention policy is configured at the venue/account level or passed explicitly when supported.
- [ ] Maximum open orders and inventory exposure are enforced.
- [ ] Client order prefix is unique to this bot process and is documented for operator cleanup.

## Operational safety

- [ ] Dead-man switch is armed before quotes and refreshed with a new request ID.
- [ ] Shutdown cancels only prefix-owned orders, confirms they disappear, and disarms DMS only after confirmation.
- [ ] SQLite state is backed up before a version change.
- [ ] Private stream disconnect causes reconciliation before quoting resumes.
- [ ] Managed orderbook sequence gap pauses quoting until snapshot refresh.
- [ ] Monitoring alerts on stale stream, DMS heartbeat failure, rejected orders, and unknown outcomes.

## Evidence levels

- Offline unit tests: available through `python -m pytest -q`.
- Public Testnet market-data connectivity: run only with an operator-approved network check.
- Credentialed mutation tests: not performed automatically; require explicit operator authorization and a funded isolated Subaccount.
