# ⚡ CLASH LIVE PROXY STUDIO (PC AUDITOR & CONFIG MANAGER)

Aplikasi Desktop & Web UI untuk menguji, memantau, dan mengelola konfigurasi proxy Clash / OpenClash (`.yaml`) langsung dari PC Windows tanpa perlu membuka Android (Clash for Android) ataupun STB (OpenClash).

Dibuat khusus untuk pengujian proxy Telkomsel / operator inject, Trojan-WS, Vmess, Vless, Shadowsocks, dengan akurasi pengujian latency riil (*real HTTP 204 end-to-end handshake*) menggunakan engine resmi **Mihomo Meta**.

---

## 🌟 Fitur Utama

1. **⚡ Live Ping & Latency Audit (Real Handshake Test)**:
   - Menguji konektivitas riil ke target Google 204 (`http://www.gstatic.com/generate_204`) atau Cloudflare 204.
   - Hasil latency akurat dalam milidetik (`ms`), deteksi node hidup (🟢 Alive) vs node mati (🔴 Dead/503/Timeout).
   - Pengujian live streaming (SSE) satu per satu secara visual dengan progress bar dinamis.

2. **🎛️ Visual Proxy Node Manager**:
   - Tambah, Edit, Duplikasi, dan Hapus node proxy dengan formulir visual (tidak perlu pusing indentasi spasi YAML).
   - Mendukung Trojan, VMess, VLESS, Shadowsocks, Hysteria2.
   - Pengaturan lengkap: Server (Bug Host), Port, Password/UUID, SNI, Network (WS/gRPC/TCP), Path, dan Host Header.

3. **🔀 1-Click Bulk Bug Host / SNI Replacer**:
   - Mengganti Bug Host operator (misal saat bug `support.zoom.us` mati dan ingin diganti ke bug baru) sekaligus di semua proxy hanya dengan 1 klik!
   - Bisa dipilih target penggantian: hanya Server, hanya SNI, hanya Host Header, atau semuanya.

4. **🧹 1-Click Purge Dead Nodes**:
   - Otomatis membersihkan semua proxy yang mati/timeout dari file YAML dan sinkronisasi grup proxy (*clean housekeeping*).

5. **📂 Multi-Config Switcher**:
   - Otomatis mendeteksi semua file YAML di folder `C:\Users\...\OneDrive\CONFIG\` (seperti `Telkomsel_V6_LIVE_ONLY.yaml`, `TELKOMSEL_LIVE.yaml`, `XL-BIZ.yaml`, dll).
   - Berpindah konfigurasi seketika dengan dropdown.

6. **🛡️ Safe & Zero-Conflict Architecture**:
   - Menjalankan core Mihomo pada port terisolasi (`19090` controller & `17890` mixed-port).
   - Tidak membajak DNS PC, tidak bentrok dengan VPN lain, dan otomatis membuat backup file (`.bak`) sebelum setiap perubahan.

7. **📝 Built-in Raw YAML Editor**:
   - Dilengkapi editor kode raw YAML dengan validasi sintaks sebelum disimpan.

---

## 🚀 Cara Menjalankan di PC

### Di PC Rumah:
Cukup double-click file:
```cmd
START_PROXY_STUDIO.bat
```
Browser akan otomatis terbuka di `http://127.0.0.1:8999`.

### Di PC Kantor (Instalasi Baru 1 Menit):
1. Buka Terminal / Git Bash di PC kantor:
   ```bash
   git clone https://github.com/dinggatripramono-stack/clash-proxy-studio.git
   cd clash-proxy-studio
   ```
2. Double-click `START_PROXY_STUDIO.bat`.
3. Skrip akan otomatis:
   - Memeriksa Python dan menginstall `requirements.txt` (FastAPI, Uvicorn, PyYAML, Requests).
   - Mengunduh binary resmi `mihomo.exe` ke folder `bin/` dalam 3 detik.
   - Membuka aplikasi di browser PC kantor!

---

## 📊 Tampilan Antarmuka (UI/UX)
- **Tema**: Calm Matte Obsidian dengan aksen Vice Electric Cyan & Emerald.
- **HUD Executive**: Total Nodes, Alive Nodes, Dead Nodes, Average Ping, dan Best Performing Node.
- **Filter**: Filter berdasarkan status (Semua / Hidup / Mati / Belum Diuji) dan pengurutan berdasarkan latency tercepat.

---

*Dikembangkan dengan standar Zero-Defect untuk Boss Dingga.*
