# Testnet deployment guide

1. Read [API key and `.env` setup](api-key-and-env.md), then create a dedicated Polyester Testnet Subaccount and API key. Grant only the spot-trading permission and Pair scope required by the test.
2. Install the pinned dependencies from `pyproject.toml` in a Python 3.11+ virtual environment.
3. Copy `.env.example` to `.env`, set the key, Subaccount, symbol, and conservative quantity. Keep `ENABLE_LIVE_TRADING=false`.
4. Run `python scripts/healthcheck.py`, then `python -m pytest -q` and `python -m compileall -q src tests`.
5. Perform a public-data-only connectivity check first. Confirm Pair rules and orderbook values are read from Testnet.
6. Review `docs/compliance-checklist.md` with a human operator. Only then set `ENABLE_LIVE_TRADING=true` for a controlled test.
7. Watch logs and SQLite state. Verify the dead-man switch cancels resting quotes when heartbeats stop, then verify clean shutdown cancels and disarms it.
8. To roll back, stop the process, run cancel-all from the Testnet UI/API if necessary, disarm DMS, preserve the SQLite file, and restore the previous code/dependencies.

This guide does not authorize live mutation by itself. Credentials, funding, and execution remain operator-controlled.

For persistent VPS deployment with automatic restart, secret permissions, journald, and graceful systemd shutdown, see [systemd VPS guide](systemd-vps.md).
