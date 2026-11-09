# Menjalankan bot dengan systemd di VPS

Panduan ini memasang `polyester-bot` sebagai service `systemd` pada VPS Linux. Konfigurasi di bawah tetap **Testnet-only** dan tidak membuka endpoint web. Bot memakai SQLite lokal, reconnect/retry SDK, dead-man switch, dan shutdown cleanup.

> Peringatan: repository ini belum mengklaim credentialed mutation Testnet telah tervalidasi pada workspace. Mulai dari `ENABLE_LIVE_TRADING=false`, lakukan healthcheck, review compliance checklist, dan lakukan controlled mutation test sebelum mengaktifkan order.

## 1. Asumsi direktori

Contoh ini memakai user service `polyesterbot` dan direktori instalasi `/opt/polyester-testnet-trading-engine`.

- source code: `/opt/polyester-testnet-trading-engine`
- virtualenv: `/opt/polyester-testnet-trading-engine/.venv`
- state SQLite: `/opt/polyester-testnet-trading-engine/state/bot.sqlite3`
- secret environment: `/etc/polyester-testnet-trading-engine.env`
- unit file: `/etc/systemd/system/polyester-testnet-trading-engine.service`

Ganti path jika Anda memakai layout lain, tetapi pastikan `WorkingDirectory`, `EnvironmentFile`, dan `BOT_DB_PATH` menunjuk ke lokasi yang sama.

## 2. Siapkan user dan source code

Jalankan sebagai administrator VPS:

```bash
sudo useradd --system --home-dir /opt/polyester-testnet-trading-engine \
  --shell /usr/sbin/nologin polyesterbot
sudo mkdir -p /opt/polyester-testnet-trading-engine/state
sudo chown -R polyesterbot:polyesterbot /opt/polyester-testnet-trading-engine
```

Clone repository sebagai `polyesterbot` atau salin source yang sudah direview:

```bash
sudo -u polyesterbot git clone \
  https://github.com/ahmadassayyaaf/polyester-testnet-trading-engine.git \
  /opt/polyester-testnet-trading-engine
cd /opt/polyester-testnet-trading-engine
sudo -u polyesterbot python3.11 -m venv .venv
sudo -u polyesterbot .venv/bin/pip install -e '.[test]'
sudo -u polyesterbot mkdir -p state
```

Jalankan test sebelum memasang service:

```bash
sudo -u polyesterbot .venv/bin/python -m pytest -q
sudo -u polyesterbot .venv/bin/python -m compileall -q src tests scripts
```

## 3. Simpan secret di EnvironmentFile

Buat file environment di luar repository:

```bash
sudo install -o root -g root -m 600 /dev/null \
  /etc/polyester-testnet-trading-engine.env
sudoedit /etc/polyester-testnet-trading-engine.env
```

Isi dengan nilai nyata dari **Polyester Testnet**, bukan Mainnet:

```dotenv
POLYESTER_API_KEY_ID=ak_your_testnet_key_id
POLYESTER_API_PRIVATE_KEY=64_character_hex_private_key
POLYESTER_SUBACCOUNT_ID=your_testnet_subaccount_id

BOT_SYMBOL=BTC-USDT
BOT_QTY=0.0001
BOT_HALF_SPREAD_BPS=20
BOT_MAX_INVENTORY=0.001
BOT_MAX_OPEN_ORDERS=2
BOT_DB_PATH=/opt/polyester-testnet-trading-engine/state/bot.sqlite3
BOT_LOG_LEVEL=INFO
BOT_DMS_TIMEOUT_SECONDS=30
BOT_DMS_REFRESH_SECONDS=10

# Tetap false sampai controlled mutation test disetujui.
ENABLE_LIVE_TRADING=false
```

API key sebaiknya dibatasi ke spot trading, Pair yang diperlukan, dan Subaccount khusus bot. Trading balance Testnet harus tersedia pada Subaccount. Jangan menaruh file ini di Git, dan jangan memasukkan private key ke unit file atau command line.

Periksa owner dan permission tanpa menampilkan isi:

```bash
sudo stat -c '%U:%G %a %n' /etc/polyester-testnet-trading-engine.env
```

Expected:

```text
root:root 600 /etc/polyester-testnet-trading-engine.env
```

## 4. Jalankan healthcheck melalui unit service

`healthcheck.py` tidak memuat `.env` otomatis. Karena `EnvironmentFile` dimiliki oleh systemd, cara paling aman untuk menguji konfigurasi yang sama adalah memasang unit pada langkah berikut, memastikan `ENABLE_LIVE_TRADING=false`, lalu menjalankan service sebentar:

```bash
sudo systemctl daemon-reload
sudo systemctl start polyester-testnet-trading-engine.service
sudo journalctl -u polyester-testnet-trading-engine.service -n 100 --no-pager
sudo systemctl stop polyester-testnet-trading-engine.service
```

Untuk healthcheck yang lebih rinci, jalankan `scripts/healthcheck.py` dari shell yang sudah memuat file environment secara aman, atau buat unit oneshot sementara yang memakai `EnvironmentFile` yang sama. Jangan menyalin secret ke command line atau log. Healthcheck harus menunjukkan environment Testnet, Pair, orderbook, dan authenticated read jika kredensial tersedia.

## 5. Buat unit service

Buat `/etc/systemd/system/polyester-testnet-trading-engine.service`:

```ini
[Unit]
Description=Polyester Testnet Trading Engine
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=polyesterbot
Group=polyesterbot
WorkingDirectory=/opt/polyester-testnet-trading-engine
EnvironmentFile=/etc/polyester-testnet-trading-engine.env
ExecStart=/opt/polyester-testnet-trading-engine/.venv/bin/polyester-bot

# Biarkan asyncio menjalankan finally/shutdown cleanup saat stop normal.
KillSignal=SIGINT
TimeoutStopSec=90s
Restart=on-failure
RestartSec=10s

# Kurangi risiko kebocoran dan akses filesystem yang tidak diperlukan.
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=strict
ReadWritePaths=/opt/polyester-testnet-trading-engine/state

[Install]
WantedBy=multi-user.target
```

`KillSignal=SIGINT` dipakai agar engine mendapat kesempatan menjalankan `cancel_all` dan `disarm_dead_man` pada shutdown. `TimeoutStopSec` harus lebih besar dari waktu yang realistis untuk cleanup dan retry jaringan.

## 6. Aktifkan service

```bash
sudo systemctl daemon-reload
sudo systemctl enable polyester-testnet-trading-engine.service
sudo systemctl start polyester-testnet-trading-engine.service
sudo systemctl status polyester-testnet-trading-engine.service --no-pager
```

Periksa log:

```bash
sudo journalctl -u polyester-testnet-trading-engine.service -n 100 --no-pager
sudo journalctl -u polyester-testnet-trading-engine.service -f
```

Saat `ENABLE_LIVE_TRADING=false`, log harus menyatakan dry-run dan tidak ada order yang dikirim.

## 7. Prosedur controlled live start

Jangan mengaktifkan order dengan mengedit source code. Setelah controlled mutation test dan compliance review disetujui:

```bash
sudoedit /etc/polyester-testnet-trading-engine.env
# ubah hanya:
# ENABLE_LIVE_TRADING=true
sudo systemctl daemon-reload
sudo systemctl restart polyester-testnet-trading-engine.service
sudo systemctl status polyester-testnet-trading-engine.service --no-pager
```

Sebelum start live, pastikan:

- key adalah Testnet key;
- Pair dan Subaccount benar;
- tidak ada open order yang tidak dikenal;
- quantity lolos rules dinamis Pair;
- saldo Trading balance cukup;
- dead-man timeout berada pada 10–120 detik;
- refresh dead-man lebih pendek dari timeout;
- ada operator yang memantau log dan dapat menjalankan cancel-all.

## 8. Stop, restart, dan rollback aman

Stop normal memberi engine kesempatan membatalkan quote dan men-disarm dead-man switch:

```bash
sudo systemctl stop polyester-testnet-trading-engine.service
sudo systemctl status polyester-testnet-trading-engine.service --no-pager
```

Restart terkontrol:

```bash
sudo systemctl restart polyester-testnet-trading-engine.service
```

Jika bot berperilaku tidak sesuai:

1. Jalankan `systemctl stop`.
2. Verifikasi open orders melalui Testnet UI/API.
3. Jalankan cancel-all dan disarm dead-man switch jika masih ada order atau timer aktif.
4. Simpan dan periksa file SQLite state.
5. Kembalikan `ENABLE_LIVE_TRADING=false`.
6. Roll back source ke commit yang sudah direview.

Jangan langsung memakai `kill -9` atau `systemctl kill -s KILL` kecuali proses benar-benar macet dan Anda sudah memiliki prosedur cancel-all manual, karena cleanup async dapat dilewati.

## 9. Update kode

Gunakan update yang dapat diulang dan verifikasi sebelum restart:

```bash
sudo systemctl stop polyester-testnet-trading-engine.service
cd /opt/polyester-testnet-trading-engine
sudo -u polyesterbot git fetch origin
sudo -u polyesterbot git checkout main
sudo -u polyesterbot git pull --ff-only origin main
sudo -u polyesterbot .venv/bin/pip install -e '.[test]'
sudo -u polyesterbot .venv/bin/python -m pytest -q
sudo -u polyesterbot .venv/bin/python scripts/healthcheck.py
sudo systemctl start polyester-testnet-trading-engine.service
```

Jangan melakukan update dengan `git reset --hard` pada server tanpa backup state dan persetujuan operator.

## 10. Monitoring minimum

Pantau setidaknya:

- status service dan restart count;
- journal error dan exception;
- koneksi/private stream;
- keberhasilan dead-man refresh;
- open orders dan cancel reason;
- ukuran file SQLite dan disk VPS;
- waktu sistem/NTP.

Contoh pemeriksaan ringkas:

```bash
systemctl is-active polyester-testnet-trading-engine.service
systemctl show polyester-testnet-trading-engine.service \
  -p ActiveState -p SubState -p NRestarts
sudo journalctl -u polyester-testnet-trading-engine.service \
  --since '15 minutes ago' --no-pager
sudo du -sh /opt/polyester-testnet-trading-engine/state
```

Systemd menjaga process tetap hidup, tetapi bukan pengganti reconciliation, dead-man switch, atau risk controls pada bot.
