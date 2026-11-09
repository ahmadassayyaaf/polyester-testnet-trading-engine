# Polyester Testnet Trading Engine

Bot market-making asynchronous yang **khusus Polyester Testnet**. Proyek ini memprioritaskan kepatuhan protokol, kontrol risiko, rekonsiliasi state, dan shutdown aman. Parameter strategi contoh tidak dianggap menguntungkan dan bukan nasihat trading.

## Status implementasi

Fondasi offline dan adapter SDK tersedia: konfigurasi fail-closed, validasi pair dinamis, Decimal arithmetic, retry idempotent, SQLite persistence, strategi dua sisi post-only, dead-man switch wrapper, cancel-all shutdown, dan private-stream boundary. **Credentialed Testnet mutation belum dijalankan pada workspace ini**, sehingga acceptance criteria live belum boleh dianggap terpenuhi.

## Instalasi

```bash
python3.11 -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
cp .env.example .env
chmod 600 .env
```

Isi `.env` hanya dengan kredensial API key Testnet yang terikat ke Subaccount. Jangan commit `.env` atau private key. Script membaca environment process, jadi load `.env` pada shell yang sama sebelum menjalankan pemeriksaan:

```bash
set -a
. ./.env
set +a
```

Panduan lengkap tersedia di [docs/api-key-and-env.md](docs/api-key-and-env.md), termasuk [deployment systemd pada VPS](docs/systemd-vps.md). Jalankan pemeriksaan tanpa order dengan `ENABLE_LIVE_TRADING=false`.

```bash
python scripts/healthcheck.py
python -m pytest -q
python -m compileall -q src tests
```

## Otorisasi live yang disengaja

Engine tetap dry-run secara default. Untuk mengaktifkan order, operator harus mengatur `ENABLE_LIVE_TRADING=true`, menyediakan `POLYESTER_API_KEY_ID`, `POLYESTER_API_PRIVATE_KEY`, dan `POLYESTER_SUBACCOUNT_ID`, serta menggunakan environment Testnet SDK. Tidak ada code path untuk Mainnet atau withdrawal.

```bash
ENABLE_LIVE_TRADING=true polyester-bot
```

Sebelum itu, pastikan Pair policy API key mengizinkan spot trading, saldo test tersedia di Subaccount, dan dead-man switch dapat dibuktikan cancel-nya. Jalankan pada Subaccount khusus strategi.

## Struktur

- `src/polyester_bot/config.py`: settings dan fail-closed authorization.
- `rules.py`: Pair rules dari `GetSpotConfig`, tanpa hardcode exchange rules.
- `polyester_adapter.py`: satu-satunya boundary resmi `polyester-sdk`.
- `strategy.py`: market-making post-only yang dapat diuji tanpa jaringan.
- `engine.py`: loop, DMS, retry, persistence, dan shutdown.
- `storage.py`: state SQLite untuk restart recovery.
- `tests/`: unit dan offline integration tests.
- `docs/`: contract notes, deployment, API key/.env, systemd VPS, dan compliance.

## Official references

- [Python SDK](https://testnet.polyester.com/docs/sdk/python/get-started)
- [Quickstart](https://testnet.polyester.com/docs/sdk/python/get-started/quickstart)
- [Trading bot tutorial](https://testnet.polyester.com/docs/developer-docs/getting-started/build-a-trading-bot)
- [Pair rules](https://testnet.polyester.com/docs/developer-docs/market-data/pairs-and-trading-rules)
- [Batch orders](https://testnet.polyester.com/docs/developer-docs/shared-concepts/batch-orders)
- [Dead-man switch](https://testnet.polyester.com/docs/developer-docs/shared-concepts/dead-man-switch)
