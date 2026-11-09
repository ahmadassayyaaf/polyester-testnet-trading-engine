# Konfigurasi `.env` dan API key Polyester Testnet

Dokumen ini menjelaskan cara menyiapkan kredensial dan parameter bot secara lokal atau pada server persisten. Proyek ini **hanya mendukung Polyester Testnet**. Jangan gunakan API key Mainnet, dan jangan menempelkan private key ke chat, issue, pull request, atau repository.

## 1. Prasyarat API key

Buat API key pada Polyester Testnet, bukan pada Mainnet. Gunakan Subaccount khusus untuk bot dan batasi policy API key sekecil mungkin:

- permission: spot trading saja;
- Pair: hanya Pair yang akan diuji, misalnya `BTC-USDT`;
- account scope: Subaccount khusus strategi;
- saldo: tersedia pada Trading balance Subaccount, bukan hanya Funding balance.

Simpan tiga nilai berikut saat key dibuat:

- `POLYESTER_API_KEY_ID`: public key/API key identifier;
- `POLYESTER_API_PRIVATE_KEY`: private key Ed25519 hexadecimal 64 karakter;
- `POLYESTER_SUBACCOUNT_ID`: public ID Subaccount yang menjadi scope bot.

Private key biasanya hanya ditampilkan ketika key dibuat. Jika pernah terekspos, revoke key tersebut dan buat key baru.

## 2. Membuat file `.env`

Dari root repository:

```bash
cp .env.example .env
chmod 600 .env
```

Edit `.env` dan isi kredensial Testnet:

```dotenv
POLYESTER_API_KEY_ID=ak_your_testnet_key_id
POLYESTER_API_PRIVATE_KEY=64_character_hex_private_key
POLYESTER_SUBACCOUNT_ID=your_testnet_subaccount_id

BOT_SYMBOL=BTC-USDT
BOT_QTY=0.0001
BOT_HALF_SPREAD_BPS=20
BOT_MAX_INVENTORY=0.001
BOT_MAX_OPEN_ORDERS=2
BOT_DB_PATH=./state/bot.sqlite3
BOT_LOG_LEVEL=INFO
BOT_DMS_TIMEOUT_SECONDS=30
BOT_DMS_REFRESH_SECONDS=10

# Tetap false sampai mutation test disetujui dan dilakukan secara terkontrol.
ENABLE_LIVE_TRADING=false
```

Nilai pada contoh di atas hanyalah placeholder. Jangan mengganti placeholder dengan kredensial pada file `.env.example`; simpan nilai nyata hanya di `.env` lokal atau secret manager.

## 3. Memuat `.env` ke shell

Python script proyek membaca environment process dan **tidak memuat `.env` secara otomatis**. Muat file ke shell yang sama sebelum menjalankan healthcheck atau bot:

```bash
set -a
. ./.env
set +a
```

Validasi keberadaan variabel tanpa mencetak nilainya:

```bash
for name in POLYESTER_API_KEY_ID POLYESTER_API_PRIVATE_KEY POLYESTER_SUBACCOUNT_ID; do
  value="${!name}"
  if [ -n "$value" ]; then
    echo "$name=SET length=${#value}"
  else
    echo "$name=UNSET"
  fi
done
```

Expected output hanya berupa status dan panjang, misalnya:

```text
POLYESTER_API_KEY_ID=SET length=...
POLYESTER_API_PRIVATE_KEY=SET length=64
POLYESTER_SUBACCOUNT_ID=SET length=...
```

Jangan gunakan `echo "$POLYESTER_API_PRIVATE_KEY"` atau perintah lain yang mencetak secret.

## 4. Jalankan pemeriksaan read-only

Dengan virtual environment aktif dan `.env` sudah dimuat:

```bash
python scripts/healthcheck.py
python -m pytest -q
python -m compileall -q src tests scripts
```

Healthcheck read-only memeriksa:

- environment Testnet;
- versi SDK;
- kelengkapan dan format private key;
- catalog Pair dan status Pair;
- tick size, quantity step, minimum quantity, dan minimum notional;
- orderbook dan admissibility quantity;
- authenticated `list_open()` jika seluruh kredensial tersedia.

Healthcheck tidak membuat, membatalkan, atau memodifikasi order. Status mutation lifecycle dan dead-man switch tetap memerlukan pengujian terpisah dengan otorisasi operator.

## 5. Mengaktifkan order secara sengaja

Default harus tetap:

```dotenv
ENABLE_LIVE_TRADING=false
```

Jangan mengaktifkan order hanya untuk menghilangkan warning healthcheck. Sebelum controlled mutation test:

1. pastikan key adalah key Testnet;
2. pastikan Pair dan Subaccount benar;
3. pastikan saldo Trading balance cukup;
4. review `docs/compliance-checklist.md`;
5. pastikan tidak ada open order yang tidak dikenal;
6. siapkan prosedur cancel-all dan disarm dead-man switch.

Hanya setelah semua pemeriksaan selesai, ubah pada shell/session terisolasi:

```bash
export ENABLE_LIVE_TRADING=true
```

Kemudian jalankan bot sesuai prosedur deployment. Untuk operasi 24/7, gunakan server persisten dan service manager seperti `systemd`; jangan mengandalkan terminal mobile atau sandbox yang dapat hibernasi.

## 6. Menjalankan sebagai service persisten

Pada server persisten, simpan `.env` di luar repository atau gunakan secret manager. Jika memakai systemd, gunakan `EnvironmentFile` dengan permission ketat:

```ini
[Service]
WorkingDirectory=/opt/polyester-testnet-trading-engine
EnvironmentFile=/etc/polyester-testnet-trading-engine.env
ExecStart=/opt/polyester-testnet-trading-engine/.venv/bin/polyester-bot
Restart=on-failure
RestartSec=5
```

Batasi file environment:

```bash
sudo chown root:root /etc/polyester-testnet-trading-engine.env
sudo chmod 600 /etc/polyester-testnet-trading-engine.env
```

Jangan menaruh secret pada unit file yang di-commit atau pada log. Setelah konfigurasi berubah, lakukan restart terkontrol dan periksa status service tanpa mencetak environment:

```bash
sudo systemctl daemon-reload
sudo systemctl restart polyester-testnet-trading-engine
sudo systemctl status polyester-testnet-trading-engine --no-pager
```

## 7. Jika kredensial tidak terdeteksi

Periksa hal berikut:

- `.env` sudah dimuat pada shell yang sama dengan command;
- nama variabel sama persis, termasuk underscore;
- private key berisi 64 karakter hexadecimal tanpa tanda kutip yang ikut tersimpan;
- tidak ada spasi di sekitar `=` pada file `.env`;
- API key dibuat pada Testnet;
- Subaccount ID sesuai dengan key scope;
- proses service sudah direstart setelah secret diperbarui.

Jangan mengatasi masalah dengan menaruh key langsung di source code atau mengunggah `.env` ke GitHub.

## Referensi resmi

- [Polyester Python SDK authentication](https://testnet.polyester.com/docs/sdk/python/guides/authentication)
- [Polyester Python SDK trading](https://testnet.polyester.com/docs/sdk/python/guides/trading)
- [Testnet environments and hosts](https://testnet.polyester.com/docs/developer-docs/getting-started/environments-and-hosts)
- [Testnet Pair rules](https://testnet.polyester.com/docs/developer-docs/market-data/pairs-and-trading-rules)
