# Polyester contract notes

These notes were captured from the official Testnet documentation on 2026-11-09.

- Python SDK overview: https://testnet.polyester.com/docs/sdk/python/get-started
- Installation: https://testnet.polyester.com/docs/sdk/python/get-started/installation
- Quickstart: https://testnet.polyester.com/docs/sdk/python/get-started/quickstart
- Trading bot tutorial: https://testnet.polyester.com/docs/developer-docs/getting-started/build-a-trading-bot
- Pair rules: https://testnet.polyester.com/docs/developer-docs/market-data/pairs-and-trading-rules
- Batch orders/idempotency: https://testnet.polyester.com/docs/developer-docs/shared-concepts/batch-orders
- Dead-man switch: https://testnet.polyester.com/docs/developer-docs/shared-concepts/dead-man-switch
- Rate limits: https://testnet.polyester.com/docs/developer-docs/shared-concepts/rate-limits

Important observed contracts:

1. Use `AsyncPolyester` for bots and pass `POLYESTER_TESTNET_ENVIRONMENT` explicitly.
2. Testnet hosts are `https://api-testnet.polyester.com` and `wss://api-testnet.polyester.com`.
3. Pair rules come from `client.market_data.get_spot_config().raw["pairs"]`; use Decimal strings, never floats.
4. Pair status can be ENABLED, POST_ONLY, DISABLED, CANCEL_ONLY, REDUCE_ONLY, or HALTED. Listing/delisting timestamps also matter.
5. Batch request IDs and client order IDs are idempotency keys. Reuse the same payload and identifier within the retry window after an unknown outcome.
6. `CancelAllAfter` must be refreshed with a new request ID; timeout 0 disarms, 10–120 seconds arms.
7. The official tutorial is explicitly Testnet-only and not trading advice; example parameters are not assumed profitable.
