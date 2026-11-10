# Polyester contract notes

These notes were captured from the official Testnet documentation on 2026-11-09 and refreshed on 2026-11-10.

- Python SDK overview: https://testnet.polyester.com/docs/sdk/python/get-started
- Installation: https://testnet.polyester.com/docs/sdk/python/get-started/installation
- Quickstart: https://testnet.polyester.com/docs/sdk/python/get-started/quickstart
- Trading bot tutorial: https://testnet.polyester.com/docs/developer-docs/getting-started/build-a-trading-bot
- Pair rules: https://testnet.polyester.com/docs/developer-docs/market-data/pairs-and-trading-rules
- Batch orders/idempotency: https://testnet.polyester.com/docs/developer-docs/shared-concepts/batch-orders
- Dead-man switch: https://testnet.polyester.com/docs/developer-docs/shared-concepts/dead-man-switch
- Rate limits: https://testnet.polyester.com/docs/developer-docs/shared-concepts/rate-limits
- Production trading bot: https://testnet.polyester.com/docs/sdk/python/tutorials/trading-bot
- Two-sided quoting: https://testnet.polyester.com/docs/sdk/python/tutorials/two-sided-quoting
- Portfolio tracker: https://testnet.polyester.com/docs/sdk/python/tutorials/portfolio-tracker
- Market maker guide: https://testnet.polyester.com/docs/developer-docs/getting-started/market-maker-guide
- Private WebSocket: https://testnet.polyester.com/docs/developer-docs/connectrpc/private-websocket
- Realtime channels: https://testnet.polyester.com/docs/developer-docs/market-data/realtime-channels
- SDK error handling: https://testnet.polyester.com/docs/sdk/python/guides/error-handling
- SDK requests and idempotency: https://testnet.polyester.com/docs/sdk/python/concepts/requests-and-idempotency

Important observed contracts:

1. Use `AsyncPolyester` for bots and pass `POLYESTER_TESTNET_ENVIRONMENT` explicitly.
2. Testnet hosts are `https://api-testnet.polyester.com` and `wss://api-testnet.polyester.com`.
3. Pair rules come from `client.market_data.get_spot_config().raw["pairs"]`; use Decimal strings, never floats.
4. Pair status can be ENABLED, POST_ONLY, DISABLED, CANCEL_ONLY, REDUCE_ONLY, or HALTED. Listing/delisting timestamps also matter.
5. Batch request IDs and client order IDs are idempotency keys. Reuse the same payload and identifier within the retry window after an unknown outcome.
6. `CancelAllAfter` must be refreshed with a new request ID; timeout 0 disarms, 10–120 seconds arms.
7. The official tutorial is explicitly Testnet-only and not trading advice; example parameters are not assumed profitable.

Additional production invariants from the refreshed docs:

8. Use the SDK-managed orderbook subscription with sequence-gap and snapshot-refresh callbacks; pause quoting while the book is stale, empty, crossed, or refreshing.
9. Size bid and ask independently from `available` Trading balance, existing reservations, pair rules, policy limits, fees, and strategy inventory caps.
10. Give orders a bot-owned client ID prefix and reconcile only that prefix after reconnect or restart; do not use account-wide cancel-all as ownership cleanup.
11. Private order streams begin with a snapshot and then versioned units. Install the snapshot, apply only higher versions, store cursors, and reconcile from read APIs after gaps or overflow.
12. A batch replace admission is not final execution state. Persist successor order/client IDs and reuse the same request ID for an ambiguous retry.
13. A failed dead-man refresh, private stream overflow, or unknown mutation outcome must stop new quoting and enter reconciliation rather than guessing.
