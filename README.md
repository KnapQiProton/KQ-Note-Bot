# 🌸 Bot Telegram Pencatat Pengeluaran Pribadi

Bot Telegram interaktif dan cerdas untuk pencatatan keuangan harian dengan antarmuka santai (*cutecore kaomoji*), parsing teks natural, inline button, dan database PostgreSQL asynchronous (SQLAlchemy 2.0 + asyncpg). Siap di-deploy ke Railway.

---

## ✨ Fitur Utama

1. **Natural Input & Parsing:** Ketik santai tanpa command kaku:
   - `25000 kopi kampus`
   - `50rb bensin #perjalanan`
   - `1.5jt bayar kosan`
   - `kemarin 15.000 print #kuliah` *(otomatis H-1)*
2. **Kategori via Inline Keyboard:** Memilih kategori secara instan sebelum data dikonfirmasi ke database.
3. **List Riwayat & Hapus:**
   - `/list` : Melihat 10 riwayat transaksi terakhir lengkap dengan ID.
   - `/hapus <ID>` : Menghapus transaksi lama berdasarkan ID (misal: `/hapus 5`).
   - `/undo` : Membatalkan transaksi paling terakhir secara instan.
4. **Rekap Pengeluaran:**
   - `/hari_ini` : Rekap per kategori hari ini
   - `/bulan_ini` : Rekap per kategori bulan ini
5. **Split Bill:** `/split <nominal> <jumlah orang>` dengan tombol instan untuk mencatat porsi sendiri ke database.
6. **Budgeting Alert:** Notifikasi otomatis jika pengeluaran bulanan menyentuh 80% atau 100% dari batas `/budget <nominal>`.
7. **Backup & Restore:** `/backup` dan `/restore` instan langsung via chat Telegram.
8. **Web Dashboard Visual:** Halaman web interaktif modern dengan grafik Donut Kategori, Bar Chart Tren 7 Hari, KPI Cards, dan Live Search tabel transaksi (Command: `/web`).
9. **Export Data:** `/export` untuk mendownload riwayat transaksi dalam bentuk `.csv`.

---

## 📁 Struktur Direktori

```text
Bot Pencatat Keuangan/
├── bot/
│   ├── handlers/
│   │   ├── expense.py       # Handler teks natural, inline kategori, & /undo
│   │   ├── reports.py       # /hari_ini, /bulan_ini, & /export (CSV)
│   │   └── tools.py         # /start, /split, /budget, /web, /backup, /restore
│   ├── keyboards/
│   │   └── inline.py        # Inline keyboards Telegram
│   ├── database/
│   │   ├── models.py        # Skema tabel SQLAlchemy (PostgreSQL)
│   │   └── session.py       # Async engine & sessionmaker (asyncpg)
│   ├── utils/
│   │   ├── parser.py        # Ekstraktor teks nominal, waktu, & tag
│   │   └── formatters.py    # Formatting rupiah & kaomoji
│   ├── web/
│   │   ├── templates/
│   │   │   └── dashboard.html # Template Web Dashboard (Tailwind + Chart.js)
│   │   └── app.py           # FastAPI Web Application & API
│   └── config.py            # Konfigurasi Pydantic & Railway URL converter
├── main.py                  # Entry point (FastAPI Web + Aiogram Bot Polling)
├── requirements.txt         # Daftar pustaka Python
├── Procfile                 # Web runner untuk Railway
└── .env.example             # Contoh environment variables
```

---

## 🚀 Panduan Menjalankan Secara Lokal

1. **Buat Virtual Environment:**
   ```bash
   python -m venv venv
   # Di Windows PowerShell:
   .\venv\Scripts\Activate.ps1
   ```

2. **Install Dependensi:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Buat File `.env`:**
   Salin `.env.example` menjadi `.env`:
   ```env
   BOT_TOKEN=token_bot_kamu_dari_botfather
   DATABASE_URL=postgresql://user:password@localhost:5432/nama_database
   TIMEZONE=Asia/Jakarta
   ```

4. **Jalankan Bot:**
   ```bash
   python main.py
   ```

---

## ☁️ Panduan Deploy ke Railway

1. **Buat Project di Railway:**
   - Buka [Railway.app](https://railway.app).
   - Klik **`+ New Project`** $\rightarrow$ **Provision PostgreSQL**.

2. **Deploy Kode Bot:**
   - Push folder ini ke repository GitHub Anda.
   - Di dashboard Railway, klik **`+ New`** $\rightarrow$ **GitHub Repo** $\rightarrow$ Pilih repositori bot.

3. **Atur Environment Variables di Service Bot:**
   - Klik pada service bot Python Anda di Railway $\rightarrow$ buka tab **Variables**.
   - Tambahkan:
     - `BOT_TOKEN`: Token bot dari `@BotFather`.
     - `DATABASE_URL`: Klik **Add Reference** dan pilih `${{Postgres.DATABASE_URL}}`.
     - `TIMEZONE`: `Asia/Jakarta`

4. **Selesai!**
   Railway akan otomatis mendeteksi `Procfile` (`worker: python main.py`) dan bot akan aktif 24/7. Data Anda aman tersimpan di PostgreSQL persisten.
