# Production reliability controls

Bot ini tetap Testnet-only dan tidak menjanjikan profitabilitas. Perubahan pada fase ini mengikuti pola resmi Polyester untuk sistem quoting: state market dan order diperlakukan sebagai data yang bisa stale, sehingga bot berhenti membuat order ketika state tidak dapat dipercaya.

## Konfigurasi baru

`BOT_CLIENT_ORDER_PREFIX` menentukan namespace order milik process ini. Default-nya `mm-`. Prefix harus memakai karakter yang diterima Polyester dan cukup pendek agar client order ID tetap di bawah batas 36 karakter. Cleanup saat restart dan shutdown hanya memilih order dengan prefix ini.

`BOT_BOOK_DEPTH` menentukan tier managed orderbook dan menerima `1`, `20`, `50`, `200`, atau `500`. `BOT_REQUOTE_TICKS` menyimpan ambang refresh untuk fase quote maintenance berikutnya. `BOT_QUOTE_NOTIONAL_CAP` adalah batas notional opsional per sisi; bila kosong, pair limits dan balance limits tetap berlaku.

## Market state dan balances

Adapter memakai `wait_for_catalogs()` serta `GetSpotConfig` untuk pair rules, scales, asset ledger IDs, dan status Pair. Harga dan quantity diproses sebagai `Decimal`. Managed orderbook menggunakan sequence-aware SDK subscription. Callback sequence gap membuat snapshot tidak fresh sampai snapshot refresh selesai. Engine tidak membuat quote ketika book kosong, crossed, unavailable, atau menunggu refresh.

Balance sizing memisahkan bid dan ask. Bid menggunakan `available` Trading balance asset quote; ask menggunakan `available` Trading balance asset base. Quantity juga dibatasi oleh inventory strategy, min/max quantity, min/max notional, step size, dan optional notional cap. Funding balance tidak dipakai sebagai spendable collateral.

## Order ownership dan restart

Semua order baru memakai client ID dengan prefix bot. Setelah timeout, reconnect, atau restart, engine membaca open orders dan hanya mengambil order milik prefix tersebut. Ia tidak memakai account-wide `cancel_all` sebagai ownership cleanup. Cancel dilakukan satu per satu sehingga order milik strategi lain pada Subaccount yang sama tidak ikut tersentuh.

Private order events dicatat dengan `order_id`, `version`, event kind, fill identity, dan replacement identity. State lokal harus menerima versi yang lebih tinggi saja. Removal dari private stream tidak dianggap sebagai cancel tanpa bukti dari order state atau read API.

## Dead-man switch dan shutdown

Dead-man switch di-refresh dengan request ID baru sebelum timeout. Kegagalan refresh menghentikan quote producer dan membiarkan backend melakukan expiry cleanup. Saat shutdown, engine menghentikan producer, melakukan targeted cancel terhadap order ber-prefix bot, membaca ulang open orders, lalu hanya men-disarm switch jika tidak ada owned order yang tersisa. Jika cleanup tidak dapat dikonfirmasi, switch dibiarkan armed dan operator harus menyelesaikan cleanup secara manual.

## Dry-run dan verifikasi

`ENABLE_LIVE_TRADING=false` tetap default. Dry-run masih membaca pair rules dan market state, tetapi tidak mengirim create, replace, atau cancel mutation. Verifikasi lokal:

```bash
python -m compileall -q src tests scripts
python -m pytest -q
git diff --check
```

Credentialed mutation Testnet tetap merupakan prosedur terpisah. Gunakan dedicated Subaccount, key dengan permission minimal, funding kecil, dan persetujuan operator sebelum mengaktifkan live gate.

## Sumber resmi

- [Build a production trading bot](https://testnet.polyester.com/docs/sdk/python/tutorials/trading-bot)
- [Two-sided quoting](https://testnet.polyester.com/docs/sdk/python/tutorials/two-sided-quoting)
- [Portfolio tracker](https://testnet.polyester.com/docs/sdk/python/tutorials/portfolio-tracker)
- [Market maker guide](https://testnet.polyester.com/docs/developer-docs/getting-started/market-maker-guide)
- [Private WebSocket](https://testnet.polyester.com/docs/developer-docs/connectrpc/private-websocket)
- [Error handling](https://testnet.polyester.com/docs/sdk/python/guides/error-handling)
- [Requests and idempotency](https://testnet.polyester.com/docs/sdk/python/concepts/requests-and-idempotency)
