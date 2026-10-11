# ⚡ CLASH LIVE PROXY STUDIO (PC AUDITOR & CONFIG MANAGER)

Aplikasi Desktop & Web UI untuk menguji, memantau, dan mengelola konfigurasi proxy Clash / OpenClash (`.yaml`) langsung dari PC Windows (Rumah & Kantor) tanpa perlu menyalakan Android atau STB OpenClash.

---

## 🌟 Fitur Unggulan (Apex v1.1)

1. **Auto-Generate Dual Mode (Bolak-Balik & Wildcard)**:
   - Cukup paste link akun (1 baris 1 akun), sistem otomatis membuat 2 varian untuk setiap akun:
     - **BOLAK-BALIK**: Server = Bug Host (`support.zoom.us`), SNI = Domain Asli VPS, Host Header = Domain Asli VPS.
     - **WILDCARD**: Server = Bug Host (`support.zoom.us`), SNI = `{Bug}.{DomainAsli}`, Host Header = `{Bug}.{DomainAsli}`.
   - Mendukung format link: `trojan://`, `vless://`, dan `vmess://`.
2. **✨ Buat Config YAML Baru (1-Klik)**:
   - Masukkan nama file (misal: `Telkomsel_V7_LIVE.yaml`), tentukan Bug Host, dan paste baris akun.
   - Otomatis merakit struktur Clash lengkap dengan Proxy Groups:
     - `AUTO-SELECT` (Master Switch)
     - `AUTO-BESTPING` (Latency URL-Test 120s)
     - `AUTO-FALLBACK` (Auto Fallback 120s)
     - `LOAD-BALANCE` (Round-Robin 300s)
     - `MANUAL-LIVE` (Pilihan manual node)
3. **📥 Paste & Tambah Akun ke File Aktif**:
   - Menu cepat untuk menambahkan akun baru ke konfigurasi yang sedang dibuka tanpa merusak node atau rule yang sudah ada.
4. **⚡ Live Delay Audit & Ping Test Real-Time**:
   - Menjalankan core **Mihomo (Clash.Meta)** terisolasi di background (port controller `19090`).
   - Melakukan pengujian delay HTTP 204 nyata (Google / Cloudflare) persis seperti OpenClash di STB.
   - Menampilkan indikator latensi live (🟢 Cepat, 🟡 Sedang, 🔴 Timeout/Dead).
5. **⚡ Export Live Only (Buang yang Mati & Export)**:
   - Satu klik untuk mengekspor hanya node-node yang lolos tes (hidup).
   - Node yang mati otomatis dibuang dari seluruh proxy group, menghasilkan file bersih yang siap di-import ke Clash for Android atau STB OpenClash.
6. **🔄 Git Auto-Sync Lintas PC (Rumah <=> Kantor)**:
   - Script `START_PROXY_STUDIO.bat` otomatis mengecek dan melakukan `git pull --rebase` dari GitHub setiap kali dijalankan.
   - Perubahan atau update dari PC Rumah (`ZAVIER`) otomatis ditarik saat dibuka di PC Kantor (`admin`), dan sebaliknya.

---

## 🚀 Cara Menjalankan di PC

### Di PC Rumah:
Cukup double-click file:
```
C:\Users\ZAVIER\projects\clash-proxy-studio\START_PROXY_STUDIO.bat
```

### Di PC Kantor:
1. Buka Git Bash / Terminal di PC Kantor, lalu clone repository:
   ```bash
   git clone https://github.com/dinggatripramono-stack/clash-proxy-studio.git
   cd clash-proxy-studio
   ```
2. Cukup double-click:
   ```
   START_PROXY_STUDIO.bat
   ```
   *Script akan otomatis menginstall dependensi, mendownload Mihomo core, dan membuka dashboard di browser (`http://127.0.0.1:8999`).*

---

## 🛠️ API & Endpoint Utama

- `GET /api/configs/list`: Daftar file `.yaml` di folder OneDrive CONFIG.
- `POST /api/configs/select`: Ganti file konfigurasi yang sedang aktif.
- `POST /api/configs/create-new`: Buat file konfigurasi YAML baru dari paste link akun.
- `POST /api/proxies/import-links`: Tambahkan akun baru ke file yang aktif.
- `POST /api/test/all`: Jalankan pengujian delay seluruh node secara paralel.
- `POST /api/export/live-only`: Download YAML bersih berisi node aktif saja.
- `POST /api/proxies/bulk-replace-bug`: Ganti Bug Host masal ke seluruh node.
